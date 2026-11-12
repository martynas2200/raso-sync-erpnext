import frappe


def has_app_permission() -> bool:
	"""Whether the RASO Sync tile shows on the apps screen for the current user."""
	return frappe.has_permission("RASO Sync Settings", "read")
