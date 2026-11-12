"""
Number Card methods for the RASO Sync dashboard.
These run on every dashboard page load. They must query MariaDB only.
"""

import re

import frappe
from frappe.utils import cint, flt

Z_REPORT = "Z Report"
SALES_INVOICE = "Sales Invoice"
LAST_30_DAYS = ["timespan", "last 30 days"]


def _currency() -> str | None:
	return frappe.db.get_default("currency")


def _custom(value) -> dict:
	"""Wrap a raw number so the card renders it as currency, not a bare float."""
	return {"value": flt(value), "fieldtype": "Currency", "options": _currency()}


def _sum(doctype: str, field: str, filters: dict) -> float:
	"""SUM a numeric field, respecting the session user's read permission."""
	rows = frappe.get_list(
		doctype,
		fields=[{"SUM": field, "as": "total"}],
		filters=filters,
		limit_page_length=0,
	)
	return flt(rows[0].get("total")) if rows else 0.0


@frappe.whitelist()
def department_share_last_30_days(filters=None) -> str:
	"""Share of Z turnover rung up on one additional counter (POS department)."""
	fieldname = f"additional_counter_{_department_from_filters(filters)}"
	if not frappe.get_meta(Z_REPORT).has_field(fieldname):
		return "—"

	rows = frappe.get_list(
		Z_REPORT,
		fields=[
			{"SUM": "daily_turnover", "as": "total"},
			{"SUM": fieldname, "as": "department"},
		],
		filters={"date": LAST_30_DAYS},
		limit_page_length=0,
	)
	total = flt(rows[0].get("total")) if rows else 0.0
	if not total:
		return "—"

	return f"{round(flt(rows[0].get('department')) / total * 100)} %"


def _department_from_filters(filters) -> int:
	"""Counter/department number carried by the card's ``filters_json``."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	for condition in filters or []:
		if not isinstance(condition, list | tuple):
			continue

		for part in condition:
			if match := re.match(r"additional_counter_(\d+)$", str(part)):
				return cint(match.group(1))

		if "pos_department_no" in {str(part) for part in condition}:
			value = condition[-1]
			if value not in (None, ""):
				return cint(value)

	return 1


@frappe.whitelist()
def card_share_last_30_days(filters=None) -> str:
	"""Share of Z turnover that was not paid in cash, last 30 days."""
	rows = frappe.get_list(
		Z_REPORT,
		fields=[
			{"SUM": "daily_turnover", "as": "total"},
			{"SUM": "daily_turnover_cash", "as": "cash"},
		],
		filters={"date": LAST_30_DAYS},
		limit_page_length=0,
	)
	total = flt(rows[0].get("total")) if rows else 0.0
	if not total:
		return "—"

	cash = flt(rows[0].get("cash"))
	return f"{round((total - cash) / total * 100)} %"


@frappe.whitelist()
def z_discounts_last_30_days(filters=None) -> dict:
	"""Discounts on receipt + on items, over the Z report window."""
	receipt = _sum(Z_REPORT, "discount_amount_receipt", {"date": LAST_30_DAYS})
	items = _sum(Z_REPORT, "discount_amount_items", {"date": LAST_30_DAYS})
	return _custom(receipt + items)
