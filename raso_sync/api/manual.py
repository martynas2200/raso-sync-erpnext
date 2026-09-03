from datetime import datetime

import frappe
from frappe import _
from frappe.utils.background_jobs import is_job_enqueued

from ..db.connection import MSSQLConnectionManager
from ..tasks.send import DOCTYPE_TO_RASO_TYPE, QUEUE_DOCTYPE

SEND_SCHEDULER_METHOD = "raso_sync.tasks.send.process_queued_marks"


def _get_scheduled_job_state(method: str) -> dict | None:
	"""Return scheduler state for a RASO scheduled job method or None."""
	name = frappe.db.get_value("Scheduled Job Type", {"method": method}, "name")
	if not name:
		return None

	job = frappe.get_doc("Scheduled Job Type", name)
	return {
		"stopped": bool(job.stopped),
		"last_execution": job.last_execution,
		"next_execution": job.next_execution,  # next_execution is a virtual field
	}


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
		if is_job_enqueued("raso_sync_send_task_worker"):
			return {
				"success": False,
				"error": _("Synchronisation is in queue. Please wait for it to start."),
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
	"""Manually trigger fetch of data from RASO"""
	try:
		if is_job_enqueued("raso_sync_fetch_task_worker"):
			return {
				"success": False,
				"error": _("Synchronisation is in queue. Please wait for it to start."),
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
	"""Get current sync status including dates, sync state, and some pending queue marks."""
	try:
		settings = frappe.get_single("RASO Sync Settings")
		send_job = _get_scheduled_job_state(SEND_SCHEDULER_METHOD)

		return {
			"last_sale_import": settings.last_sale_import,
			"last_data_export": settings.last_data_export,
			"is_running": False,  # This will be updated in real-time via websocket events
			"send_job": send_job,
			"queued_doc_rows": _get_queue_mark_rows(),
		}

	except Exception as e:
		frappe.log_error("RASO Sync Get Status", f"Failed to get sync status: {e!r}")
		raise e
