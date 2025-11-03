"""Fetch Task (RASO -> ERPNext)"""

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from raso_sync.api.importer import import_raso_data

from ..db.executor import ProcedureBuilder

logger = frappe.logger("raso_sync_fetch", allow_site=True, file_count=30)
# TODO: Check the how long is it retained by default.
# https://docs.frappe.io/framework/user/en/api/logging


def execute_fetch_task(type=None):
	"""
	Enqueue the fetch task to import data from RASO.
	Returns:
	    status: str: 'queued' if enqueued, 'skipped' if already running
	    job_id: str: ID of the enqueued job
	"""
	job_id = "raso_sync_fetch_task_worker"

	if is_job_enqueued(job_id):
		return {"status": "skipped"}

	frappe.enqueue(
		"raso_sync.tasks.fetch.execute_fetch_task_worker",
		job_id=job_id,
		enqueue_after_commit=True,
		queue="long",
		type=type,
	)

	return {"status": "queued", "job_id": job_id}


def execute_fetch_task_worker(type=None):
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_fetch_task_worker

	Worker function that performs the actual fetching and importing.

	Args:
	    type: Optional filter for data type
	"""
	# TODO: Argument check --- not needed, we only support a single type

	results = {"total_processed": 0, "successful": 0, "failed": 0, "errors": []}

	try:
		# Retrieve all new data exports (Status = 0)
		new_exports = get_new_exports()
		results["total_processed"] = len(new_exports)

		if not new_exports:
			frappe.logger().info("Fetch Task: No new data exports to process")
			return results

		frappe.logger().info(f"Fetch Task: Found {len(new_exports)} new export records to process")

		# Process each export record
		for export_record in new_exports:
			try:
				process_export_record(export_record)
				results["successful"] += 1
			except Exception as e:
				results["failed"] += 1
				results["errors"].append({"sync_id": export_record.get("SyncDataExportId"), "error": str(e)})
				frappe.logger().error(
					f"Fetch Task: Error processing export {export_record.get('SyncDataExportId')}: {e!s}"
				)
				if export_record.get("SyncData"):
					frappe.logger().debug(export_record.get("SyncData"))
				ui_error_msg = f"Error processing export: {e!s}"
				frappe.msgprint(ui_error_msg)
				document = frappe.log_error("execute_fetch_task", ui_error_msg)
				# NOTE: Not yet sure about best channel to inform user about errors.
				update_export_status(
					export_record.get("SyncDataExportId"),
					status=3,  # Error
					message="See error log: " + document.name + " for details in ERPNext logs.",
				)
		frappe.logger().info(f"Fetch Task Completed. Successful: {results['successful']}")
		if results["failed"] > 0:
			frappe.logger().info(f"Fetch Task Completed. Failed: {results['failed']}")

	except Exception as e:
		frappe.logger().error(f"Fetch Task: Fatal error - {e!s}")
		raise

	return results


def get_new_exports(data_type=None, data_provider=None):
	"""
	Retrieve new data exports from RASO database.

	Uses ie.usp_SyncDataExport_rp stored procedure to query new records.
	Filters for Status = 0 ("New Data").

	Args:
	    data_type (int, optional): Filter by specific data type
	    data_provider (str, optional): Filter by data provider

	Returns:
	    list: List of export records with new data
	"""
	try:
		params = {
			"Status": 0,  # New Data
		}

		if data_type is not None:
			params["DataType"] = data_type or 1

		if data_provider is not None:
			params["DataProvider"] = data_provider

		# Use reporting procedure for querying (read-only, efficient)
		result = ProcedureBuilder.execute_procedure("ie.usp_SyncDataExport_rp", params)

		return result if result else []

	except Exception as e:
		frappe.logger().error(f"Error retrieving new exports: {e!s}")
		raise


def process_export_record(export_record):
	"""
	Process a single export record from RASO.

	1. Extract and parse SyncData
	2. Call import_raso_data to save to ERPNext
	3. Update status to 1 (success)

	Args:
	    export_record (dict): Export record from database with keys:
	        - SyncDataExportId
	        - DataType
	        - DataProvider
	        - SyncData (JSON string)
	        - ShopNo

	Raises:
	    Exception: If processing fails
	"""
	sync_id = export_record.get("SyncDataExportId")
	data_type = export_record.get("DataType")
	sync_data_str = export_record.get("SyncData")
	shop_no = export_record.get("ShopNo")

	frappe.logger().info(f"Processing export {sync_id} (Type: {data_type}, Shop: {shop_no})")

	# Get full SyncData from the database record
	if sync_data_str.endswith("..."):
		full_sync_data = ProcedureBuilder.execute_procedure(
			"ie.usp_SyncDataExport_v", {"SyncDataExportId": sync_id}
		)
		sync_data_str = full_sync_data[0].get("SyncData")

	if not sync_data_str:
		raise Exception(f"Empty SyncData for export {sync_id}")

	# Import data to ERPNext
	import_result = import_raso_data(type=data_type, xml_data=sync_data_str)

	# Update status to success
	update_export_status(
		sync_id,
		status=1 if import_result.status == "success" else 3,
		message=import_result.get("message", "No message returned"),
	)


def update_export_status(sync_id, status, message=None):
	"""
	Update the status of an export record in RASO database.

	Uses ie.usp_SyncDataExport_u stored procedure.

	Args:
	    sync_id (int): SyncDataExportId
	    status (int): New status code (1=success, 3=error)
	    message (str, optional): Status message (max 1024 chars)

	Raises:
	    Exception: If database update fails
	"""

	return

	try:
		params = {
			"SyncDataExportId": sync_id,
			"Status": status,
		}

		if message:
			params["StatusMsg"] = message[:1024]

		ProcedureBuilder.execute_procedure("ie.usp_SyncDataExport_u", params)

		frappe.logger().debug(f"Updated export {sync_id} status to {status}")

	except Exception as e:
		frappe.logger().error(f"Error updating export status: {e!s}")
		raise
