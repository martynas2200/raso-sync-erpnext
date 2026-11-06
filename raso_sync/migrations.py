import frappe

from raso_sync.custom_fields import create_custom_fields
from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


def run_migrations():
	create_custom_fields()
	recreate_scheduler_jobs()


def recreate_scheduler_jobs():
	"""Recreate scheduler jobs after migration/container rebuild."""
	try:
		settings = RASOSyncSettings.get_settings()
		settings.on_update()
	except Exception as e:
		frappe.log_error(
			"RASO Jobs creation failed during migration", f"Error recreating RASO Sync scheduler jobs: {e!s}"
		)
