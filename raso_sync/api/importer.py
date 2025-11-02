import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import frappe
from frappe.utils import cint, flt, now_datetime

from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


@frappe.whitelist(allow_guest=False)
def import_raso_data(type=0, xml_data=None):
	"""
	Import sales data from RASO POS system.
	The request body contains XML data with sales information.

	Returns:
	    dict: Response with status and message
	"""
	try:
		if type != 0:
			# dump the received xml data to log
			frappe.log_error(
				"RASO Import - Unsupported DataType",
				f"Received unsupported DataType {type}. XML Data:\n{xml_data if xml_data else frappe.request.data.decode('utf-8')}",
			)
			return {
				"status": "error",
				"message": f"Unsupported DataType {type}. Only DataType 0 (Sales) is supported.",
			}

		if xml_data is None:
			xml_data = frappe.request.data.decode("utf-8")

		root = ET.fromstring(xml_data)

		# if empty root
		if root is None or len(root) == 0:
			return {
				"status": "error",
				"message": "No data found in the request.",
			}

		validation_result = validate_sales_payments(root)
		if not validation_result["valid"]:
			frappe.log_error(
				"RASO Payment Validation Error", f"Payment validation failed: {validation_result}"
			)
			return {
				"status": "error",
				"message": "Payment validation failed: The sum of individual payments does not match the total payments in the document.",
			}

		# Process each receipt
		response = {"status": "success", "message": "", "results": []}

		for sales in root.findall("Sales"):
			result = process_sales(sales)
			response["results"].append(result)

		# NOTE: we need a text summary of errors and successes here as a single line, and status number to leave in the RASO database log
		# TODO: status number logic or perhaps in the client side app. or by using http response codes
		error_count = sum(1 for r in response["results"] if r["status"] == "error")
		response["message"] = "Success!" if not error_count else f"Completed with {error_count} errors."

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

		if difference > 0:
			has_errors = True
			comparison.append(
				f"Payment Code {code}: Individual sales sum={sales_sum:.2f}, Expected total={total_sum:.2f}, Difference={difference:.2f}"
			)

	return {
		"valid": not has_errors,
		"error": "Payment validation failed:\n" + "\n".join(comparison) if has_errors else "",
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
		# shop_no = sales_node.get('ShopNo')
		# pos_no = sales_node.get('PosNo')
		# TODO: add a setting, whether to use shop_no and pos_no in the invoice title

		invoice_title = f"EKA{receipt_no}"

		# Check if this invoice already exists
		existing_invoice = frappe.db.get_value("Sales Invoice", {"title": invoice_title}, "name")
		if existing_invoice:
			return {
				"receipt_no": receipt_no,
				"status": "skipped",
				"message": f"Invoice {invoice_title} already exists",
			}

		# Get settings
		settings = RASOSyncSettings.get_settings()

		# Prepare Sales Invoice document
		invoice = frappe.new_doc("Sales Invoice")
		invoice.title = invoice_title
		invoice.posting_date = posting_date
		invoice.posting_time = posting_time
		invoice.set_posting_time = 1
		invoice.is_pos = 1

		if settings.pos_profile:
			invoice.pos_profile = settings.pos_profile

		if settings.sales_tax_template:
			invoice.taxes_and_charges = settings.sales_tax_template

			# NOTE: might not be possible to use sales tax template, so might just ask user tax account instead, and then we set Actual type, and account head.
			vat = 0.00
			for sale in sales_node.findall("Sale"):
				vatsum = flt(sale.find("VATSUM").text) if sale.find("VATSUM") is not None else 0
				vatsum_manual = (
					flt(sale.find("VATSUMMANUAL").text) if sale.find("VATSUMMANUAL") is not None else 0
				)
				vat += vatsum + vatsum_manual
			# Get template
			tax_template = frappe.get_doc("Sales Taxes and Charges Template", settings.sales_tax_template)
			for tax in tax_template.taxes:
				if tax.charge_type == "Actual":
					invoice.append(
						"taxes",
						{
							"charge_type": tax.charge_type,
							"account_head": tax.account_head,
							"description": tax.description,
							"tax_amount": vat,
						},
					)
					break
				else:
					# wrong type, give a frappe log
					frappe.log_error(
						"RASO Import VAT - Wrong Tax Type",
						f"Tax {tax.account_head} in template {settings.sales_tax_template} is not of type Actual.",
					)

		invoice.raso_receipt_no = receipt_no
		invoice.raso_import_status = "Processing"

		# Handle employee mapping if available
		if user_id and settings.employee_mappings:
			sales_person = RASOSyncSettings.get_sales_person_from_employee(user_id)
			if sales_person:
				invoice.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})

		for sale in sales_node.findall("Sale"):
			add_item_to_invoice(invoice, sale)

		total_payment = 0
		for payment in sales_node.findall("Payment"):
			payment_amount = add_payment_to_invoice(invoice, payment)
			total_payment += payment_amount

		invoice.save()

		# Checks before submission
		can_submit = True
		error_list = ""

		if hasattr(invoice, "_item_lookup_errors") and invoice._item_lookup_errors:
			error_list = "<br>".join(invoice._item_lookup_errors)
			can_submit = False

		for item in invoice.items:
			if flt(item.actual_qty) < flt(item.qty) and item.is_stock_item:
				can_submit = False
				error_list += (
					f"<br> Insufficient stock for item {item.item_code}: Missing {item.qty - item.actual_qty}"
				)

		# Try to submit
		if can_submit:
			try:
				invoice.submit()
				invoice.raso_import_status = "Success"
				invoice.save()
				return {
					"receipt_no": receipt_no,
					"status": "success",
					"message": "Invoice created and submitted",
				}
			except Exception as e:
				error_msg = str(e)
				invoice.raso_import_status = "Failed"
				invoice.save()

				add_comment("Invoice Submission Failed", str(e), "Sales Invoice", invoice.name)

				return {
					"receipt_no": receipt_no,
					"status": "accepted",
					"message": "Invoice created but submission failed",
				}
		else:
			invoice.raso_import_status = "Missing Stock or Information"
			invoice.save()

			add_comment("Invoice Creation Failed", error_list, "Sales Invoice", invoice.name)

			return {
				"receipt_no": receipt_no,
				"status": "accepted",
				"message": "Invoice created but not submitted",
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

	# Determine which quantity and amount to use
	qty = flt(sale_node.find("QTY").text) if sale_node.find("QTY") is not None else 0
	amount = flt(sale_node.find("AMOUNT").text) if sale_node.find("AMOUNT") is not None else 0
	qty_manual = flt(sale_node.find("QTYMANUAL").text) if sale_node.find("QTYMANUAL") is not None else 0
	amount_manual = (
		flt(sale_node.find("AMOUNTMANUAL").text) if sale_node.find("AMOUNTMANUAL") is not None else 0
	)
	discount = flt(sale_node.find("DISCOUNT").text) if sale_node.find("DISCOUNT") is not None else 0

	final_qty = qty_manual if qty_manual > 0 else qty
	final_amount = amount_manual if amount_manual > 0 else amount

	if final_qty <= 0:
		return

	rate = final_amount / final_qty if final_qty > 0 else 0

	# Determine item
	item_code = None

	# If VCODE starts with P, use it directly as item_code
	# TODO: finish making this logic more robust, add settings
	if vcode and (vcode.startswith("P") or vcode.startswith("I")):
		item_code = vcode

	if item_code:
		# Verify that VCODE is item_code
		item_exists = frappe.db.exists("Item", item_code)
		if not item_exists:
			item_code = None

	if not item_code:
		# Barcode lookup instead
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
			item_code = "TEMP-ITEM"  # TODO: I am not sure about this

	enhanced_description = f"{item_name}\nScanned {code}"
	# TODO: fix this logic, discount_amount:
	if discount > 0:
		enhanced_description += f"\nDiscount: {discount}"

	# TODO: Inspect records, it might be a good reason to split up records manual rate vs automatic rate
	# Would be a good idea to wrap this in a try-except
	invoice.append(
		"items",
		{
			"item_code": item_code,
			"qty": final_qty,
			"rate": rate,
			"amount": final_amount,
			"description": enhanced_description,
			"barcode": code,
			"has_item_scanned": 1,
		},
	)

	# Forward the comment
	if "settings" in locals() and settings.default_item and item_code == settings.default_item:
		if not hasattr(invoice, "_item_lookup_errors"):
			invoice._item_lookup_errors = []
		invoice._item_lookup_errors.append(f"Item not found with a barcode {code}, kodu {vcode}")


def add_payment_to_invoice(invoice, payment_node):
	"""
	Add payment information to the sales invoice
	"""
	code = payment_node.find("CODE").text
	amount = flt(payment_node.find("AMOUNT").text)
	# paymethod = payment_node.find("PAYMETHOD").text

	payment_method = RASOSyncSettings.get_payment_method_mapping(code)

	# TODO: seems like a hardcoded list
	if code in ["1001", "1002"]:
		invoice.rounding_adjustment = amount
		return amount

	invoice.append("payments", {"mode_of_payment": payment_method, "amount": amount})

	return amount
