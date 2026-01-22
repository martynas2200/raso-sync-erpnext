import traceback
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

import frappe
from frappe import _

from raso_sync.data_imports.sales import sales_internal
from raso_sync.data_imports.z_reports import z_report_internal
from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


@frappe.whitelist(allow_guest=False)
def import_data():
	"""
	Public API endpoint to accept RASO POS sales data.
	Args:
	    type (int): DataType sent by RASO (only 0, 3, 5 supported)
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
	    type (int): DataType sent by RASO (only 0, 3, 5 supported)
	    xml_data (str|None): XML payload

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
		if root_tag == "SalesZReportsDataSync":
			type = 5
		elif root_tag == "SalesSync":
			type = 0  #! or 3, it can be both, it depends if the RASO configuration export both in the same SalesSync, this is why we infer it later on for each record.
		else:
			return {
				"status": "error",
				"message": _("DataType not specified and could not be inferred from XML."),
			}

	if type not in [0, 3, 5]:
		frappe.log_error(
			"RASO Import - Unsupported DataType",
			_("Received unsupported DataType. XML Data:") + f"\n{xml_data}",
		)
		return {"status": "error", "message": _("Unsupported DataType")}

	if type == 5:
		return z_report_internal(xml_data=xml_data)
	else:
		return sales_internal(xml_data=xml_data)
