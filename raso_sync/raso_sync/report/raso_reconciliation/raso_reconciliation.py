"""
Days where the Z reports and the imported POS invoices disagree.

Only days that fail a check are listed: turnover total or receipt count.
"""

import frappe
from frappe import _

from raso_sync.reconciliation import scan


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result = scan(from_date=filters.get("from_date"), to_date=filters.get("to_date"))

	if result.get("message"):
		return get_columns(), [], result["message"]

	summary = [
		{"label": _("Days checked"), "value": result["days_checked"], "datatype": "Int"},
		{"label": _("Days differing"), "value": result["days_differing"], "datatype": "Int"},
		{
			"label": _("Net turnover difference"),
			"value": result["net_turnover_difference"],
			"datatype": "Currency",
		},
		{
			"label": _("Receipt difference"),
			"value": result["receipt_difference"],
			"datatype": "Int",
		},
	]

	message = _("Compared {0} to {1}").format(result["from_date"], result["to_date"])
	return get_columns(), result["rows"], message, None, summary


def get_columns():
	return [
		{"label": _("Day"), "fieldname": "day", "fieldtype": "Date", "width": 100},
		{"label": _("Z reports"), "fieldname": "z_count", "fieldtype": "Int", "width": 90},
		{
			"label": _("Z turnover"),
			"fieldname": "z_turnover",
			"fieldtype": "Currency",
			"width": 120,
		},
		{"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Difference"),
			"fieldname": "turnover_diff",
			"fieldtype": "Currency",
			"width": 120,
		},
		{"label": _("Z receipts"), "fieldname": "z_receipts", "fieldtype": "Int", "width": 100},
		{
			"label": _("Imported receipts"),
			"fieldname": "invoiced_receipts",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Receipt difference"),
			"fieldname": "receipt_diff",
			"fieldtype": "Int",
			"width": 130,
		},
	]
