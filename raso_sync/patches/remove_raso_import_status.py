import frappe
from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields


def execute():
	"""
	Remove the `raso_import_status` Custom Field from Sales Invoice.
	This field used to be created by raso_sync (custom_fields.py) but was
	removed from the definitions.
	"""
	delete_custom_fields({"Sales Invoice": ["raso_import_status"]})
