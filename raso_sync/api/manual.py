from datetime import datetime

import frappe
from frappe import _

from ..db.connection import MSSQLConnectionManager
from ..tasks.send import DOCTYPE_TO_RASO_TYPE, QUEUE_DOCTYPE


def _get_queue_mark_rows() -> list[dict]:
	"""Return pending queue rows in a frontend-ready table shape."""
	return frappe.get_all(
		QUEUE_DOCTYPE,
		fields=["source_doctype", "source_name", "last_event", "marked_at", "has_delete"],
		filters={"source_doctype": ["in", list(DOCTYPE_TO_RASO_TYPE.keys())]},
		order_by="marked_at desc, source_doctype asc, source_name asc",
		limit_page_length=50,
	)


@frappe.whitelist()
def test_connection():
	"""Test the connection to RASO database"""
	settings = frappe.get_single("RASO Sync Settings")
	if (
		not settings.ip
		or not settings.port
		or not settings.database_name
		or not settings.database_username
		or not settings.database_password
	):
		return {"success": False, "error": _("Database connection settings are incomplete")}

	try:
		connection = MSSQLConnectionManager.get_connection()

		with connection.cursor() as cursor:
			cursor.execute("SELECT GETDATE() AS test_time;")
			row = cursor.fetchone()
			db_time = row["test_time"] if row else None
		connection.close()

		if db_time is not None:
			message = _("Connection successful. Database time: {0}").format(db_time)
		else:
			message = _("Connection successful, database time not retrieved...")

		return {"success": True, "message": message}
	except Exception as e:
		return {"success": False, "error": _("Failed to connect to RASO database: {0}").format(str(e))}


@frappe.whitelist()
def manual_send(data_type, mode):
	"""
	Manually trigger send of data to RASO
	Args:
	    data_type: Type of data to send (goods, good_prices, good_groups, partners, all)
	    mode: Sync mode (fullsync or today)
	"""
	try:
		if frappe.get_single_value("RASO Sync Settings", "synchronization_is_running"):
			return {
				"success": False,
				"error": _("Synchronization is already running. Please wait for it to complete."),
			}

		date_from = None
		if mode == "today":
			date_from = datetime.now().strftime("%Y-%m-%d 00:00:00")

		frappe.enqueue(
			"raso_sync.tasks.send.execute_send_task_worker",
			queue="long",
			job_id="raso_sync_send_task_worker",
			enqueue_after_commit=True,
			at_front=True,
			export_type=data_type,
			date_from=date_from,
			inform_user=True,
		)

		return {"success": True}

	except Exception as e:
		frappe.log_error("RASO Sync Manual Send", f"Manual send failed: {e!r}")
		return {
			"success": False,
			"error": repr(e),
		}


@frappe.whitelist()
def manual_fetch():
	"""
	Manually trigger fetch of data from RASO
	"""
	try:
		if frappe.get_single_value("RASO Sync Settings", "synchronization_is_running"):
			return {
				"success": False,
				"error": _("Synchronization is already running. Please wait for it to complete."),
			}

		frappe.enqueue(
			"raso_sync.tasks.fetch.execute_fetch_task_worker",
			queue="long",
			job_id="raso_sync_fetch_task_worker",
			enqueue_after_commit=True,
			ignore_workhours=True,
			at_front=True,
			inform_user=True,
		)

		return {"success": True}

	except Exception as e:
		frappe.log_error("RASO Sync Manual Fetch", f"Manual fetch failed: {e!r}")
		return {"success": False, "error": repr(e)}


@frappe.whitelist()
def get_sync_status():
	"""
	Get current sync status including dates, sync state, and some pending queue marks.
	"""
	try:
		settings = frappe.get_single("RASO Sync Settings")

		return {
			"last_sale_import": settings.last_sale_import,
			"last_data_export": settings.last_data_export,
			"is_running": bool(settings.synchronization_is_running),
			"send_check_interval_minutes": int(settings.send_check_interval_minutes or 0),
			"queued_doc_rows": _get_queue_mark_rows(),
		}

	except Exception as e:
		frappe.log_error("RASO Sync Get Status", f"Failed to get sync status: {e!r}")
		raise e
