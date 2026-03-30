from xml.etree.ElementTree import Element, SubElement, tostring

import frappe
from werkzeug.wrappers import Response

from raso_sync.api.good_groups import good_groups_internal
from raso_sync.api.good_prices import good_prices_internal
from raso_sync.api.goods import goods_internal
from raso_sync.api.partners import partners_internal


def format_xml_response(root):
	"""Format XML with proper declaration and pretty printing"""
	# Ensure all text values in the XML are strings
	for elem in root.iter():
		if elem.text is not None and not isinstance(elem.text, str):
			elem.text = str(elem.text)

	return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(root, encoding="unicode")


@frappe.whitelist(allow_guest=False, methods=["GET", "POST"])
def get():
	"""
	Main API endpoint for RASO sync data - Returns XML directly

	Parameters:
	- DataType: 1 (Partners), 2 (GoodsGroups), 3 (Goods), 4 (GoodsPrices)
	- FullSync: 1 for full sync, 0 for incremental
	- recentModified: Required when FullSync=0, ISO datetime string

	Returns XML document directly
	"""
	# Get parameters
	data_type = frappe.form_dict.get("DataType")
	full_sync = int(frappe.form_dict.get("FullSync", 1))
	date_from = frappe.form_dict.get("recentModified")

	# Validate parameters
	if not data_type:
		frappe.throw("DataType parameter is required")

	if full_sync == 0 and not date_from:
		frappe.throw("recentModified parameter is required when FullSync=0")
	root = export_for_raso(data_type=data_type, full_sync=full_sync, date_from=date_from)
	if not list(root):
		return Response(status=204)

	return Response(
		format_xml_response(root),
		content_type="application/xml; charset=utf-8",
		status=200 if root.tag != "Error" else 500,
	)


def export_for_raso(data_type, full_sync=1, date_from=None, docnames=None):
	"""
	Export data for RASO sync based on DataType.

	Returns XML Element root, or Error tag in XML if an error occurs.
	"""
	try:
		data_type = int(data_type)

		if data_type == 1:
			root = partners_internal(full_sync, date_from, docnames=docnames)
		elif data_type == 2:
			root = good_groups_internal(full_sync, date_from, docnames=docnames)
		elif data_type == 3:
			root = goods_internal(full_sync, date_from, docnames=docnames)
		elif data_type == 4:
			root = good_prices_internal(full_sync, date_from, docnames=docnames)
		else:
			frappe.throw(
				f"Invalid DataType '{data_type}'. Supported values: 1 (Partners), 2 (GoodsGroups), 3 (Goods), 4 (GoodsPrices)"
			)

		return root

	except Exception as e:
		error_root = Element("Error")
		frappe.log_error(
			"RASO Sync API Export Error",
			f"RASO sync API Type {data_type} error: {e!s}",
		)

		# Return error as XML
		error_root = Element("Error")
		error_elem = SubElement(error_root, "Message")
		error_elem.text = str(e) if e is not None else "Unknown error"

		return error_root
