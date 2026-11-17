"""
Compare RASO Z reports against the POS invoices imported.

Per day it checks if turnover and count of receipts match.
The turnover figure check ignores refunds.

The receipt count assumes every imported POS invoice, refunds included, is one fiscal receipt in the Z report.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

Z_REPORT = "Z Report"
SALES_INVOICE = "Sales Invoice"

# Two decimals are shown everywhere, so smaller differences are rounding noise.
TOLERANCE = 0.005

_Z_SQL = """
select date(z.date) as day,
	sum(z.daily_turnover) as z_turnover,
	sum(z.fiscal_receipts_count) as fiscal_receipts,
	sum(z.non_fiscal_receipts_count) as non_fiscal_receipts,
	count(*) as z_count
from `tabZ Report` z
where 1 = 1
{conditions}
group by date(z.date)
order by day desc
"""

_INVOICE_SQL = """
select si.posting_date as day,
	sum(case when si.is_return = 1 then 0 else si.grand_total end) as invoiced,
	sum(case when si.is_return = 1 then 0 else 1 end) as sale_receipts,
	sum(case when si.is_return = 1 then 1 else 0 end) as refund_receipts
from `tabSales Invoice` si
where si.docstatus < 2
	and ifnull(si.raso_receipt_no, '') != ''
{conditions}
group by si.posting_date
order by day desc
"""


def _conditions(column: str, from_date, to_date) -> tuple[str, dict]:
	"""Build the date bound clause."""
	clauses: list[str] = []
	values: dict = {}

	if from_date:
		clauses.append(f"and {column} >= %(from_date)s")
		values["from_date"] = getdate(from_date)
	if to_date:
		clauses.append(f"and {column} <= %(to_date)s")
		values["to_date"] = getdate(to_date)

	return (" ".join(clauses), values)


def _z_rows(from_date, to_date) -> list[dict]:
	conditions, values = _conditions("date(z.date)", from_date, to_date)
	return frappe.db.sql(_Z_SQL.format(conditions=conditions), values, as_dict=True)


def _invoice_rows(from_date, to_date) -> list[dict]:
	conditions, values = _conditions("si.posting_date", from_date, to_date)
	return frappe.db.sql(_INVOICE_SQL.format(conditions=conditions), values, as_dict=True)


def _z_window() -> tuple:
	"""First and last day that has a Z report, or (None, None)."""
	row = frappe.db.sql(
		"select min(date(date)) as start, max(date(date)) as end from `tabZ Report`",
		as_dict=True,
	)[0]
	return row.start, row.end


def _resolve_window(from_date, to_date) -> tuple:
	"""Fill missing bounds from the Z report range"""
	z_start, z_end = _z_window()

	start = getdate(from_date) if from_date else z_start
	end = getdate(to_date) if to_date else z_end

	if start and end and start > end:
		start, end = end, start

	return start, end


def scan(from_date=None, to_date=None) -> dict:
	"""
	      Return per-day discrepancies between Z reports and imported invoices.
	Without a range, every day covered by a Z report is checked.
	"""
	frappe.has_permission(Z_REPORT, "read", throw=True)
	frappe.has_permission(SALES_INVOICE, "read", throw=True)

	start, end = _resolve_window(from_date, to_date)
	if not start or not end:
		return {
			"rows": [],
			"days_checked": 0,
			"days_differing": 0,
			"message": _("No Z reports yet, so there is nothing to compare against."),
		}

	z_by_day = {row.day: row for row in _z_rows(start, end)}
	invoices_by_day = {row.day: row for row in _invoice_rows(start, end)}

	days = sorted(set(z_by_day) | set(invoices_by_day), reverse=True)
	rows = []
	for day in days:
		z = z_by_day.get(day)
		invoiced_row = invoices_by_day.get(day)

		z_turnover = flt(z.z_turnover) if z else 0.0
		invoiced = flt(invoiced_row.invoiced) if invoiced_row else 0.0
		z_receipts = cint(z.fiscal_receipts) if z else 0
		invoiced_receipts = (
			cint(invoiced_row.sale_receipts) + cint(invoiced_row.refund_receipts) if invoiced_row else 0
		)

		turnover_diff = invoiced - z_turnover
		receipt_diff = z_receipts - invoiced_receipts

		issues = []
		if abs(turnover_diff) >= TOLERANCE:
			issues.append("turnover")
		if receipt_diff:
			issues.append("receipts")

		# only report problems
		if not issues:
			continue

		rows.append(
			{
				"day": str(day),
				"z_count": cint(z.z_count) if z else 0,
				"z_turnover": z_turnover,
				"invoiced": invoiced,
				"turnover_diff": turnover_diff,
				"z_receipts": z_receipts,
				"invoiced_receipts": invoiced_receipts,
				"receipt_diff": receipt_diff,
				"status": "+".join(issues),
			}
		)

	return {
		"from_date": str(start),
		"to_date": str(end),
		"days_checked": len(days),
		"days_differing": len(rows),
		"net_turnover_difference": flt(sum(row["turnover_diff"] for row in rows)),
		"receipt_difference": sum(row["receipt_diff"] for row in rows),
		"rows": rows,
	}
