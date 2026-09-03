import logging
import traceback
from collections import Counter

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from ..db.connection import mssql_session
from . import get_exports, process_export_record, with_msgprint_logging

logger = frappe.logger("raso_sync_maintenance")
logger.setLevel("DEBUG")


def execute_maintenance_task():
	"""
	Enqueue the maintenance task to check and retry previous import errors.

	Returns:
		status: str: 'queued' if enqueued, 'skipped' if already running
		job_id: str: ID of the enqueued job
	"""
	job_id = "raso_sync_maintenance_task_worker"

	if is_job_enqueued(job_id):
		return {"status": "skipped"}

	frappe.enqueue(
		"raso_sync.tasks.maintenance.execute_maintenance_task_worker",
		job_id=job_id,
		enqueue_after_commit=True,
		queue="long",
	)

	return {"status": "queued", "job_id": job_id}


@mssql_session
@with_msgprint_logging(logger)
def execute_maintenance_task_worker(inform_user=False):
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_maintenance_task_worker

	Worker function that performs maintenance tasks including:
	- Checking for previous import errors (Status 3 and 4)
	- Retrying failed imports

	Args:
		inform_user: If True, sends log messages to users via frappe.msgprint
	"""
	logger.debug("Starting Maintenance Task")

	# check if fetch period is set
	fetch_period = frappe.db.get_single_value("RASO Sync Settings", "fetch_sales_interval_minutes")
	if not fetch_period:
		logger.warning("Fetch period is not set. Skipping maintenance task.")
		return

	try:
		error_exports = check_for_errors_in_previous_imports()

		if error_exports:
			logger.info(f"Maintenance Task: Completed. Processed {len(error_exports)} error records")
		else:
			logger.info("Maintenance Task: No error records found")

	except Exception as e:
		logger.error(f"Maintenance Task: Fatal error - {e!s}")
		frappe.log_error("RASO: execute_maintenance_task", traceback.format_exc())
		raise  # So RQ Job is marked as failed


def check_for_errors_in_previous_imports():
	"""
	Check for errors in previous imports by querying exports with Status = 3 (Error) or 4 (Partial Success).
	Attempts to retry processing these exports.

	Returns:
		list: List of error export records that were processed
	"""
	try:
		error_exports = get_exports(status=3) + get_exports(status=4)

		if not error_exports:
			logger.info("No previous import errors found")
			return []

		logger.warning(f"Found {len(error_exports)} previous import errors to retry")
		results = Counter()

		# Retry processing each error export
		for export_record in error_exports:
			sync_id = export_record.get("SyncDataExportId")
			data_type = export_record.get("DataType")
			shop_no = export_record.get("ShopNo")

			logger.info(f"Retrying Export ID: {sync_id}, DataType: {data_type}, ShopNo: {shop_no}")

			try:
				status = process_export_record(export_record)
				results[status] += 1
			except Exception as e:
				results["failed"] += 1
				logger.error(f"Error retrying export {sync_id}: {e!s}")
				error_details = f"Export Record: {export_record}\n\nException:\n{traceback.format_exc()}"
				frappe.log_error("RASO: maintenance_retry_failed", error_details)

		logger.info(
			"Maintenance completed. Processed: %s, Success: %s, Partial: %s, Failed: %s",
			len(error_exports),
			results.get("success", 0),
			results.get("partial_success", 0),
			results.get("failed", 0),
		)

		return error_exports

	except Exception as e:
		logger.error(f"Error checking for previous import errors: {e!s}")
		frappe.log_error("RASO: check_for_errors_in_previous_imports", traceback.format_exc())
		raise
