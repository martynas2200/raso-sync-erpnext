import frappe

OLD_MODULE = "Raso Sync"


def execute():
	"""
	Remove the orphaned `Raso Sync` Module Def left over from renaming the
	module to `RASO Sync`.
	"""
	if not frappe.db.exists("Module Def", OLD_MODULE):
		return

	# Bail if anything still points at the old name
	if frappe.db.exists("DocType", {"module": OLD_MODULE}):
		return

	frappe.delete_doc("Module Def", OLD_MODULE, ignore_permissions=True, force=True)
