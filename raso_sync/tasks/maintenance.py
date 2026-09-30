from collections import Counter

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from ..db.connection import mssql_session
from . import get_exports, process_export_record, with_msgprint_logging

logger = frappe.logger("raso_sync_maintenance")


def execute_maintenance_task():
	"""
	Enqueue the maintenance task to check and retry previous import errors.
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

	return {"status": "queued"}


@mssql_session
@with_msgprint_logging(logger)
def execute_maintenance_task_worker(inform_user=False):
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_maintenance_task_worker

	Worker function that performs checking for previous import errors and retries processing them.

	:param inform_user: If True, sends log messages to users via frappe.msgprint
	"""
	logger.debug("Starting Maintenance Task")

	# check if we automatically fetch in the first place
	fetch_period = frappe.db.get_single_value("RASO Sync Settings", "fetch_sales_interval_minutes")
	if not fetch_period:
		logger.warning("Fetch period is not set. Skipping maintenance task.")
		return

	try:
		error_exports = check_for_errors_in_previous_imports()

		if error_exports:
			logger.info("Maintenance Task completed. Processed %d error records", len(error_exports))
		else:
			logger.debug("Maintenance Task completed. No error records found")

	except Exception as e:
		logger.exception("Maintenance Task")
		raise e  # job is marked as Failed.


def check_for_errors_in_previous_imports():
	"""
	Check for errors in previous imports by querying exports with Status = 3 (Error) or 4 (Partial Success).
	Attempts to retry processing these exports.

	Returns the list of error export records that were processed
	"""
	error_exports = get_exports(status=3) + get_exports(status=4)

	if not error_exports:
		return []

	logger.info("Found %d previous import errors to retry", len(error_exports))
	results = Counter()

	# Retry processing each error export
	for export_record in error_exports:
		sync_id = export_record.get("SyncDataExportId")

		try:
			status = process_export_record(export_record)
			results[status] += 1
		except Exception:
			results["failed"] += 1
			logger.exception("Error while retrying export %d record", sync_id)
			frappe.log_error("RASO Retry of Failed Export")

	logger.info(
		"Maintenance task completed. Processed: %s, Success: %s, Partial: %s, Failed: %s",
		len(error_exports),
		results.get("success", 0),
		results.get("partial_success", 0),
		results.get("failed", 0),
	)

	return error_exports
