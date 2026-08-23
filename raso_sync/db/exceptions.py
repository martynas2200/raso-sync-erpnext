"""RASO Sync specific database exceptions."""

import frappe


class RASOServerUnavailableError(frappe.ValidationError):
	"""Raised when the RASO MSSQL server is unreachable or the connection times out."""
