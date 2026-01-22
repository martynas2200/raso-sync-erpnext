import traceback
import xml.etree.ElementTree as ET

import frappe
from frappe.utils import cint, flt

from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


# NOTE: helper function for cases like: if IdetaGrynuju2 = 0, then there is no exported IdetaGrynujuKartai2 for some reason
def _get_text(node, tag_name):
	element = node.find(tag_name)
	return element.text if element is not None and element.text else None


def z_report_internal(xml_data=None):
	"""
	Internal implementation of RASO Z Report import logic.

	Args:
	    xml_data (str): XML payload containing Z Report data

	Returns:
	    dict: Response with status and message
	"""
	try:
		try:
			root = ET.fromstring(xml_data)
		except ET.ParseError as e:
			return {
				"status": "error",
				"message": f"Invalid XML data: {e!s}",
			}

		if root.tag != "SalesZReportsDataSync":
			return {
				"status": "error",
				"message": f"Invalid root element. Expected 'SalesZReportsDataSync', got '{root.tag}'",
			}
		# Process each Z Report
		response = {"status": "success", "message": "", "results": []}

		for z_report_node in root.findall("SalesZReportsData"):
			result = process_z_report(z_report_node)
			response["results"].append(result)

		# Summary
		error_count = sum(1 for r in response["results"] if r["status"] == "error")
		success_count = sum(1 for r in response["results"] if r["status"] == "success")

		if not error_count:
			response["message"] = f"{success_count} Z Report(s) imported successfully."
		else:
			response["status"] = "partial_success" if success_count > 0 else "error"
			response["message"] = f"{success_count} succeeded, {error_count} failed."

		return response

	except Exception as e:
		frappe.log_error("RASO Z Report Import Error", traceback.format_exc())
		return {"status": "error", "message": str(e)[:100] if str(e) else "An unknown error occurred."}


# NOTE: half of the node names are in Lithuanian as per RASO XML spec... for some reason..., so just need to stick to that, even though it looks awful.
def process_z_report(z_report_node):
	"""
	Process a single Z Report node
	"""
	try:
		# Check if Z report already exists based on ZNr and FiscalNo
		number = _get_text(z_report_node, "ZNr")
		fiscal_no = _get_text(z_report_node, "FiscalNo")
		id = f"{fiscal_no}-{number}"

		if not number or not fiscal_no:
			return {
				"status": "error",
				"message": "Missing ZNr or FiscalNo",
			}

		if frappe.db.exists("Z Report", id):
			return {
				"id": id,
				"status": "skipped",
				"message": "Z Report already exists",
			}

		# Create new report
		doc = frappe.new_doc("Z Report")
		doc.id = id
		doc.fiscal_no = fiscal_no
		doc.z_no = number
		# Map all fields from XML to document
		doc.shop_no = _get_text(z_report_node, "ShopNo")
		doc.pos_no = _get_text(z_report_node, "PosNo")
		doc.receipt_no = _get_text(z_report_node, "ReceiptNo")
		doc.user_code = _get_text(z_report_node, "SUsersCode")
		doc.sales_person = RASOSyncSettings.get_sales_person_from_employee(doc.user_code)

		# Parse Z Report Date
		z_report_date_text = _get_text(z_report_node, "ZReportDate")
		if z_report_date_text:
			doc.date = frappe.utils.get_datetime(z_report_date_text)

		# Counters
		doc.fiscal_receipts_count = cint(_get_text(z_report_node, "FiskaliniuKvituKiekis"))
		doc.non_fiscal_receipts_count = cint(_get_text(z_report_node, "NefiskaliniuKvituKiekis"))

		# Financial data
		doc.daily_turnover = flt(_get_text(z_report_node, "DienosApyvarta"))
		doc.gt = flt(_get_text(z_report_node, "GT"))

		# VAT amounts
		for i in range(1, 6):
			setattr(doc, f"vat_amount_{i}", flt(_get_text(z_report_node, f"PVMSuma{i}")))
			setattr(doc, f"amount_without_vat_{i}", flt(_get_text(z_report_node, f"SumaBePVM{i}")))
			setattr(
				doc, f"return_amount_without_vat_{i}", flt(_get_text(z_report_node, f"GrazinimoSumaBePVM{i}"))
			)
			setattr(doc, f"return_vat_amount_{i}", flt(_get_text(z_report_node, f"GrazinimoPVMSuma{i}")))

		# Payment details
		doc.daily_turnover_cash = flt(_get_text(z_report_node, "DienosApyvartaGrynaisiais"))
		for i in range(1, 6):
			setattr(
				doc, f"daily_turnover_credit_{i}", flt(_get_text(z_report_node, f"DienosApyvartaKreditan{i}"))
			)

		# Cash operations
		doc.cash_deposited_1 = flt(_get_text(z_report_node, "IdetaGrynuju1"))
		doc.cash_deposited_times_1 = cint(_get_text(z_report_node, "IdetaGrynujuKartai1"))
		doc.cash_deposited_2 = flt(_get_text(z_report_node, "IdetaGrynuju2"))
		doc.cash_withdrawn_1 = flt(_get_text(z_report_node, "IsimtaGrynuju1"))
		doc.cash_withdrawn_times_1 = cint(_get_text(z_report_node, "IsimtaGrynujuKartai1"))
		doc.cash_withdrawn_2 = flt(_get_text(z_report_node, "IsimtaGrynuju2"))
		doc.cash_in_register = flt(_get_text(z_report_node, "GrynujuKasoje"))
		# TODO: check for IsimtaGrynujuKartai2, my export sample does not have it.

		# Discounts and markups
		doc.discount_amount_receipt = flt(_get_text(z_report_node, "NuolaidosSumaKvitui"))
		doc.discount_amount_items = flt(_get_text(z_report_node, "NuolaidosSumaPrekems"))
		doc.markup_amount_receipt = flt(_get_text(z_report_node, "AntkainioSumaKvitui"))
		doc.markup_amount_items = flt(_get_text(z_report_node, "AntkainioSumaPrekems"))

		# Amends
		doc.error_amount = flt(_get_text(z_report_node, "KlaiduSuma"))
		doc.error_count = cint(_get_text(z_report_node, "KlaiduKartai"))
		doc.drawer_opening_times = cint(_get_text(z_report_node, "StalciausAtidarymoKartai"))

		# Returns
		doc.return_amount = flt(_get_text(z_report_node, "GrazinimuSuma"))
		doc.return_count = cint(_get_text(z_report_node, "GrazinimuKartai"))
		doc.tare_amount = flt(_get_text(z_report_node, "TarosSuma"))
		doc.tare_quantity = cint(_get_text(z_report_node, "TarosKiekis"))

		# Cancellations
		doc.receipt_cancellation_amount = flt(_get_text(z_report_node, "KvituPanaikinimuSuma"))
		doc.receipt_cancellation_count = cint(_get_text(z_report_node, "KvituPanaikinimuKartai"))

		# Additional counters (1-22)
		for i in range(1, 23):
			field_name = f"additional_counter_{i}"
			xml_tag = f"PapildomoSkaitiklioSuma{i}"
			setattr(doc, field_name, flt(_get_text(z_report_node, xml_tag)))

		doc.insert(ignore_permissions=True)
		return {
			"id": id,
			"status": "success",
			"message": "Z Report processed successfully",
		}

	except Exception as e:
		frappe.log_error("RASO Z Report Processing Error", str(e))
		return {
			"id": id if "id" in locals() else "Unknown",
			"status": "error",
			"message": str(e)[:100],
		}
