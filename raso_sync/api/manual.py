import time
from datetime import datetime

import frappe
from frappe import _
from frappe.utils.background_jobs import is_job_enqueued

from ..db.connection import MSSQLConnectionManager


@frappe.whitelist()
def test_connection():
	"""Test the connection to RASO database"""
	try:
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
			# Get connection (this automatically connects)
			connection = MSSQLConnectionManager.get_connection()

			# Test the connection by executing a simple query
			with connection.cursor() as cursor:
				cursor.execute("SELECT 1")
				cursor.fetchone()

			return {"success": True, "message": _("Connection successful")}
		except Exception as e:
			return {
				"success": False,
				"error": _("Failed to connect to RASO database: {0}").format(
					str(e) if str(e) else "Unknown error"
				),
			}

	except Exception as e:
		frappe.log_error(
			f"Connection test failed: {str(e) if str(e) else 'Unknown error'}", "RASO Sync Connection Test"
		)
		return {"success": False, "error": str(e) if str(e) else "Unknown error"}


@frappe.whitelist()
def manual_upload(data_type, mode):
	"""
	Manually trigger upload of data to RASO
	Args:
		data_type: Type of data to upload (goods, good_prices, good_groups, partners, all)
		mode: Sync mode (fullsync or today)
	"""
	time.sleep(0.5)

	try:
		settings = frappe.get_single("RASO Sync Settings")

		if settings.synchronization_is_running:
			return {
				"success": False,
				"error": _("Synchronization is already running. Please wait for it to complete."),
			}

		date_from = None
		if mode == "today":
			date_from = datetime.now().strftime("%Y-%m-%d 00:00:00")

		job = frappe.enqueue(
			"raso_sync.tasks.send.execute_send_task_worker",
			queue="long",
			job_id="raso_sync_send_task_worker",
			enqueue_after_commit=True,
			at_front=True,
			arguments=[data_type, date_from],
			on_success=frappe.msgprint(_("RASO Upload task is completed successfully.")),
			on_failure=frappe.msgprint(_("RASO Upload task failed. Please check error logs.")),
		)

		# TODO: set a button to possibly view the job status
		frappe.msgprint(
			msg=_("Upload task has been enqueued. Job ID: {0}").format(job.name),
			primary_action={
				"label": _("View Job Status"),
				"action": f"frappe.show_job_status('{job.name}')",
			},
		)

		return {"success": True}

	except Exception as e:
		frappe.log_error(
			f"Manual upload failed: {str(e) if str(e) else 'Unknown error'}", "RASO Sync Manual Upload"
		)
		return {
			"success": False,
			"error": _("The enqueue failed: {0}").format(str(e) if str(e) else "Unknown error"),
		}


@frappe.whitelist()
def manual_fetch(data_type):
	"""
	Manually trigger fetch of data from RASO
	"""
	try:
		settings = frappe.get_single("RASO Sync Settings")

		if settings.synchronization_is_running:
			return {
				"success": False,
				"error": _("Synchronization is already running. Please wait for it to complete."),
			}

		job = frappe.enqueue(
			"raso_sync.tasks.fetch.execute_fetch_task_worker",
			queue="long",
			job_id="raso_sync_fetch_task_worker",
			enqueue_after_commit=True,
			at_front=True,
			on_success=frappe.msgprint(_("Fetch task is completed successfully.")),
			on_failure=frappe.msgprint(_("Fetch task failed. Please check error logs.")),
		)

		# TODO: set a button to possibly view the job status
		frappe.msgprint(
			msg=_("Fetch task has been enqueued. Job ID: {0}").format(job.name),
			primary_action={
				"label": _("View Job Status"),
				"action": f"frappe.show_job_status('{job.name}')",
			},
		)

		return {"success": True}

	except Exception as e:
		frappe.log_error(
			f"Manual fetch failed: {str(e) if str(e) else 'Unknown error'}", "RASO Sync Manual Fetch"
		)
		return {"success": False, "error": _("The enqueue failed: {0}").format(str(e) if str(e) else "")}
