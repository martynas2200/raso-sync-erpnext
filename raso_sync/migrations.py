import frappe

from raso_sync.custom_fields import create_custom_fields
from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


def run_migrations():
	create_custom_fields()
	recreate_scheduler_jobs()


def recreate_scheduler_jobs():
	"""
	Recreate scheduler jobs after migration/container rebuild.
	Called by after_migrate hook to ensure scheduled jobs are restored.
	"""
	try:
		settings = RASOSyncSettings.get_settings()
		settings.on_update()
		frappe.logger().info("RASO Sync scheduler jobs recreated after migration")
	except Exception as e:
		frappe.log_error(f"Error recreating RASO Sync scheduler jobs: {e}", "Migration")
