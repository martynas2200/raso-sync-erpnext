import frappe
from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields

from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings

RASO_ID_FIELD = "raso_id"

REMOVABLE_CUSTOM_FIELDS = {
	"Sales Invoice": ["raso_receipt_no"],
	"Item Group": [
		"raso_id",
		"pos_section",
		"pos_department_no",
		"is_refundable",
		"is_visible_in_catalog",
		"column_break_raso",
	],
}


def run_migrations():
	fill_missing_raso_ids()
	recreate_scheduler_jobs()


def fill_missing_raso_ids():
	"""Give every Item Group a numeric id; existing values are never renumbered."""
	if not frappe.get_meta("Item Group").has_field(RASO_ID_FIELD):
		return

	rows = frappe.get_all("Item Group", fields=["name", RASO_ID_FIELD], order_by="creation asc")
	values = [str(row.get(RASO_ID_FIELD) or "").strip() for row in rows]
	next_id = max((int(value) for value in values if value.isdigit()), default=0)

	filled = 0
	for row, value in zip(rows, values, strict=True):
		if value:
			continue
		next_id += 1
		frappe.db.set_value("Item Group", row.name, RASO_ID_FIELD, str(next_id), update_modified=False)
		filled += 1

	if filled:
		frappe.db.commit()
		print(f"Filled RASO ID for {filled} Item Groups (last id: {next_id}).")


def recreate_scheduler_jobs():
	"""Recreate scheduler jobs after migration/container rebuild."""
	try:
		settings = RASOSyncSettings.get_settings()
		settings.on_update()
	except Exception as e:
		frappe.log_error(
			"RASO Jobs creation failed during migration", f"Error recreating RASO Sync scheduler jobs: {e!s}"
		)


def remove_custom_fields():
	"""Delete the custom fields this app owns; runs before uninstall."""
	delete_custom_fields(REMOVABLE_CUSTOM_FIELDS, bypass_hooks=True)
	frappe.db.commit()
