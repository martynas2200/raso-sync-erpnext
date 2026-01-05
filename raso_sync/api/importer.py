import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


@frappe.whitelist(allow_guest=False)
def import_data():
	"""
	Public API endpoint to accept RASO POS sales data.
	- Normalizes incoming request payload (form arg or raw body)
	- Delegates processing to the internal function `import_data_internal`.

	Args:
	    type (int): DataType sent by RASO (only 0 = Sales supported)
	    xml_data (str|None): Optional XML payload; if missing, taken from request body

	Returns:
	    dict: Response with status and message
	"""
	# Normalize incoming payload here (change/shape the request)
	# check content-type and return an error if not xml
	if not frappe.request.content_type == "application/xml":
		return {
			"status": "error",
			"message": "Invalid content type. Expected application/xml.",
		}

	frappe.request.data.decode("utf-8")
	if getattr(frappe, "request", None) and getattr(frappe.request, "data", None):
		xml_data = frappe.request.data.decode("utf-8")

	if not xml_data:
		return {
			"status": "error",
			"message": "No XML data found in the request.",
		}

	return import_data_internal(type=None, xml_data=xml_data)


def import_data_internal(type=None, xml_data=None):
	"""
	Internal implementation of RASO sales import logic. Not whitelisted.

	Args:
	    type (int): DataType sent by RASO (only 0 = Sales supported)
	    xml_data (str|None): XML payload (if None, will attempt to read from request body)

	Returns:
	    dict: Response with status and message
	"""

	try:
		ET.fromstring(xml_data)
	except ET.ParseError as e:
		return {
			"status": "error",
			"message": f"Invalid XML data: {e!s}",
		}

	if type is None:
		# check the root element to determine type
		root = ET.fromstring(xml_data)
		root_tag = root.tag.strip()
		if root_tag == "SalesSync":
			type = 0  # Sales
		else:
			return {
				"status": "error",
				"message": _("DataType not specified and could not be inferred from XML."),
			}

	if type != 0:
		frappe.log_error(
			"RASO Import - Unsupported DataType",
			_("Received unsupported DataType. XML Data:") + f"\n{xml_data}",
		)
		return {"status": "error", "message": _("Unsupported DataType")}

	try:
		if xml_data is None:
			xml_data = frappe.request.data.decode("utf-8")

		root = ET.fromstring(xml_data)

		# if empty root
		if root is None or len(root) == 0:
			return {
				"status": "error",
				"message": _("No data found in the request."),
			}

		validation_result = validate_sales_payments(root)
		if not validation_result["valid"]:
			frappe.log_error(
				"RASO Payment Validation Error", f"Payment validation failed: {validation_result}"
			)
			return {
				"status": "error",
				"message": _(
					"Payment validation failed: The sum of individual payments does not match the total payments in the document."
				),
			}

		# Process each receipt
		response = {"status": "success", "message": "", "results": []}

		for sales in root.findall("Sales"):
			result = process_sales(sales)
			response["results"].append(result)

		error_count = sum(1 for r in response["results"] if r["status"] == "error")
		if not error_count:
			response["message"] = f"{len(response['results'])} sales receipts imported successfully."
		else:
			response["message"] = f"Completed with {error_count} errors."

		# Update the last import timestamp
		RASOSyncSettings.update_last_sale_import()

		return response

	except Exception as e:
		frappe.log_error("RASO Import Error", str(e))
		return {"status": "error", "message": str(e)[:50] if str(e) else "An unknown error occurred."}


def validate_sales_payments(root):
	"""
	Validate that the sum of all payments in Sales nodes matches
	the totals in Payments nodes under SalesSync

	Args:
	    root: ElementTree root node of SalesSync XML

	Returns:
	    dict: Result with 'valid' (bool) and 'error' (str) keys
	"""
	# Sum up all payments from individual Sales nodes
	sales_payments = defaultdict(float)

	for sales in root.findall("Sales"):
		for payment in sales.findall("Payment"):
			code = payment.find("CODE").text
			amount = flt(payment.find("AMOUNT").text)
			sales_payments[code] += amount

	# Get the totals from Payments nodes
	total_payments = defaultdict(float)

	for payment in root.findall("Payments"):
		code = payment.find("CODE").text
		amount = flt(payment.find("AMOUNT").text)
		total_payments[code] = amount

	# Validate that sums match for each payment code
	all_payment_codes = set(sales_payments.keys()) | set(total_payments.keys())

	# Prepare comparison details
	comparison = []
	has_errors = False

	for code in sorted(all_payment_codes):  # Sort for consistent reporting
		sales_sum = sales_payments.get(code, 0)
		total_sum = total_payments.get(code, 0)
		difference = abs(sales_sum - total_sum)

		if difference > 0.005:
			has_errors = True
			comparison.append(
				f"Payment Code {code}: Individual sales sum={sales_sum:.2f}, Expected total={total_sum:.2f}, Difference={difference:.2f}"
			)

	return {
		"valid": not has_errors,
		"error": _("Payment validation failed") + "\n" + "\n".join(comparison) if has_errors else "",
		"sales_payments": dict(sales_payments),
		"total_payments": dict(total_payments),
	}


def add_comment(subject, content, reference_doctype=None, reference_name=None):
	try:
		if reference_doctype and reference_name:
			doc = frappe.get_doc(reference_doctype, reference_name)
			doc.add_comment("Comment", f"{subject}: {content}")
		else:
			frappe.log_error("Failed to add a comment", f"{subject}: {content}")
	except Exception as e:
		frappe.log_error("Error adding comment", str(e) if str(e) else "Unknown error")


def process_sales(sales_node):
	"""
	Process a single sales receipt
	"""
	try:
		receipt_no = sales_node.get("ReceiptNo")
		posting_date = datetime.strptime(sales_node.get("SaleDate"), "%Y-%m-%d").date()
		posting_time = datetime.strptime(sales_node.get("SaleTime"), "%H:%M:%S").time()
		user_id = sales_node.get("UserId")
		shop_no = sales_node.get("ShopNo") or ""
		pos_no = sales_node.get("PosNo") or ""

		settings = RASOSyncSettings.get_settings()
		company_uses_negative_stock = frappe.db.get_single_value("Stock Settings", "allow_negative_stock")
		if not receipt_no or posting_date is None or posting_time is None:
			return {
				"receipt_no": "Unknown",
				"status": "error",
				"message": "Missing data",
			}
		if settings.use_shop_no_and_pos_no:
			receipt = f"{shop_no}-{pos_no}-{receipt_no}"
		else:
			receipt = f"{receipt_no}"

		# Check for existing invoice with the same raso_receipt_no
		existing_invoice = frappe.db.get_value("Sales Invoice", {"raso_receipt_no": receipt}, "name")
		if existing_invoice:
			return {
				"receipt_no": receipt_no,
				"status": "skipped",
				"message": f"Invoice {receipt} already exists",
			}

		# Prepare Sales Invoice document
		invoice = frappe.new_doc("Sales Invoice")
		invoice.posting_date = posting_date
		invoice.posting_time = posting_time
		invoice.set_posting_time = 1
		invoice.debit_to = settings.debit_to_account
		invoice.customer = settings.default_customer
		invoice.ignore_pricing_rule = 1
		invoice.is_pos = 1
		invoice.update_stock = 1
		invoice.raso_receipt_no = receipt
		invoice.title = _("POS Receipt") + f" {receipt}"
		invoice.naming_series = settings.default_naming_series
		invoice.raso_import_status = "Processing"
		invoice.disable_rounded_total = 1

		if settings.vat_account:
			vat = 0.00
			for sale in sales_node.findall("Sale"):
				vatsum = flt(sale.find("VATSUM").text) if sale.find("VATSUM") is not None else 0
				vatsum_manual = (
					flt(sale.find("VATSUMMANUAL").text) if sale.find("VATSUMMANUAL") is not None else 0
				)
				vat += vatsum + vatsum_manual
			invoice.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": settings.vat_account,
					"description": "PVM/VAT",
					"tax_amount": vat,
				},
			)

		if user_id and settings.employee_mappings:
			sales_person = RASOSyncSettings.get_sales_person_from_employee(user_id)
			if sales_person:
				invoice.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})

		for sale in sales_node.findall("Sale"):
			add_item_to_invoice(invoice, sale)

		for payment in sales_node.findall("Payment"):
			# Check for rounding codes
			if payment.find("CODE").text in settings.rounding_codes.split(","):
				invoice.disable_rounded_total = 0
			elif settings.add_payments_to_invoices:
				add_payment_to_invoice(settings, invoice, payment)

		invoice.save()

		# Checks before submission
		can_submit = True
		error_list = ""

		if hasattr(invoice, "_item_lookup_errors") and invoice._item_lookup_errors:
			error_list = "<br>".join(invoice._item_lookup_errors)
			can_submit = False

		for item in invoice.items:
			if (
				not company_uses_negative_stock
				and flt(item.actual_qty) < flt(item.qty)
				and item.maintain_stock
			):
				can_submit = False
				error_list += _("Insufficient stock for item") + f"- {item.item_code}"

		if can_submit is False:
			invoice.raso_import_status = "Missing Stock or Information"
			invoice.save()

			add_comment(_("Invoice Creation Failed"), error_list, "Sales Invoice", invoice.name)

			return {
				"receipt_no": receipt_no,
				"status": "accepted",
				"message": _("Invoice created but not submitted"),
			}
		elif not settings.submit_sales_documents:
			invoice.raso_import_status = "Success"
			invoice.save()
			return {
				"receipt_no": receipt_no,
				"status": "success",
				"message": _("Invoice created (not submitted as per settings)"),
			}
		else:
			try:
				invoice.raso_import_status = "Success"
				invoice.save()
				invoice.submit()
				return {
					"receipt_no": receipt_no,
					"status": "success",
					"message": _("Invoice created and submitted"),
				}
			except Exception as e:
				error_msg = str(e)
				invoice.raso_import_status = "Failed"
				invoice.save()

				add_comment("Invoice Submission Failed", str(e), "Sales Invoice", invoice.name)

				return {
					"receipt_no": receipt_no,
					"status": "accepted",
					"message": _("Invoice created but submission failed"),
				}
	except Exception as e:
		frappe.log_error(f"RASO Sales {receipt_no} processing Error:", str(e))
		return {
			"receipt_no": receipt_no if "receipt_no" in locals() else "Unknown",
			"status": "error",
			"message": str(e),
		}


def add_item_to_invoice(invoice, sale_node):
	"""
	Add an item to the sales invoice
	"""
	settings = RASOSyncSettings.get_settings()
	code = sale_node.find("CODE").text
	vcode = sale_node.find("VCODE").text
	name_element = sale_node.find("NAME")
	if name_element is None:  # Check for alternate field name
		name_element = sale_node.find("n")
	item_name = name_element.text if name_element is not None else "Unknown Item"

	qty = flt(sale_node.find("QTY").text) if sale_node.find("QTY") is not None else 0
	amount = flt(sale_node.find("AMOUNT").text) if sale_node.find("AMOUNT") is not None else 0

	qty_manual = flt(sale_node.find("QTYMANUAL").text) if sale_node.find("QTYMANUAL") is not None else 0
	amount_manual = (
		flt(sale_node.find("AMOUNTMANUAL").text) if sale_node.find("AMOUNTMANUAL") is not None else 0
	)
	vat = flt(sale_node.find("VATSUM").text) if sale_node.find("VATSUM") is not None else 0
	vat_manual = flt(sale_node.find("VATSUMMANUAL").text) if sale_node.find("VATSUMMANUAL") is not None else 0
	discount = flt(sale_node.find("DISCOUNT").text) if sale_node.find("DISCOUNT") is not None else 0
	vat += vat_manual
	final_qty = qty + qty_manual
	final_amount = amount + amount_manual

	if final_qty <= 0:
		return

	rate = (final_amount - vat) / final_qty if final_qty > 0 else 0

	# Determine item
	item_code = None

	# If VCODE starts with uppercase letter, take it as item code
	if vcode and vcode[0].isalpha():
		item_code = vcode

	if item_code:
		# Verify that VCODE is item_code
		item_exists = frappe.db.exists("Item", item_code)
		if not item_exists:
			item_code = None

	if not item_code:
		# Barcode lookup instead, no leading zeros
		stripped_code = code.lstrip("0")
		item_code_from_barcode = frappe.db.get_value("Item Barcode", {"barcode": stripped_code}, "parent")
		if item_code_from_barcode:
			item_code = item_code_from_barcode

	if not item_code:
		# Direct item barcode lookup
		item_code_from_barcode = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
		if item_code_from_barcode:
			item_code = item_code_from_barcode

	if not item_code:
		# Use default item
		error_msg = f"Item not found: CODE={code}, VCODE={vcode}. Using default item: {settings.default_item}"
		frappe.log_error("RASO Import while looking up item", error_msg)

		if settings.default_item:
			item_code = settings.default_item
		else:
			raise ValueError("No item found and no default item set in RASO Sync Settings.")

	item_doc = frappe.get_doc("Item", item_code)
	stock_uom = item_doc.stock_uom if item_doc and item_doc.stock_uom else "Nos"
	if not item_doc:
		raise ValueError(f"Item {item_code} does not exist.")
	if not stock_uom:
		raise ValueError(f"Item {item_code} does not have a stock UOM defined.")

	if discount > 0:
		enhanced_description = f"Discount: {discount:.2f} EUR"
	else:
		enhanced_description = ""

	# Not wrapping this in a try-except block; we either import the whole receipt or none of it
	item_dict = {
		"item_code": item_code,
		"qty": final_qty,
		"stock_uom": stock_uom,
		"uom": stock_uom,
		"rate": rate,
		"amount": final_amount,
		"description": enhanced_description,
		"barcode": code,
		"has_item_scanned": 1,
	}

	if rate <= 0:
		item_dict["is_free_item"] = 1
		item_dict["discount_percentage"] = 100
	else:
		item_dict["discount_amount"] = discount

	invoice.append("items", item_dict)

	# Forward the comment
	if "settings" in locals() and settings.default_item and item_code == settings.default_item:
		if not hasattr(invoice, "_item_lookup_errors"):
			invoice._item_lookup_errors = []
		invoice._item_lookup_errors.append(f"Item not found with a barcode {code}, kodu {vcode}")


def add_payment_to_invoice(settings, invoice, payment_node):
	"""
	Add payment information to the sales invoice
	"""
	code = payment_node.find("CODE").text
	amount = flt(payment_node.find("AMOUNT").text)

	payment_method = RASOSyncSettings.get_payment_method_mapping(code)

	if not payment_method:
		frappe.log_error(
			"RASO Payment Method Mapping Missing",
			f"No payment method mapping found for RASO payment code {code}. Skipping payment addition.",
		)
		return 0

	invoice.append("payments", {"mode_of_payment": payment_method.frappe_payment_method, "amount": amount})

	return amount
