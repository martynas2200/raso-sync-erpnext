"""Sent Task (ERPNext -> RASO)"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from . import MsgprintHandler

logger = frappe.logger("raso_sync_send")
logger.setLevel("DEBUG")

from raso_sync.api.exporter import export_for_raso
from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings
from raso_sync.utils.working_hours import is_within_working_hours

from ..db.executor import ProcedureBuilder

# Supported export data types
RASO_TYPES = {
	"partners": 1,
	"good_groups": 2,
	"goods": 3,
	"good_prices": 4,
}

# Mapping from ERPNext DocType to RASO_TYPES numeric codes
DOCTYPE_TO_RASO_TYPE = {
	"Customer": RASO_TYPES["partners"],
	"Item Group": RASO_TYPES["good_groups"],
	"Item": RASO_TYPES["goods"],
	"Item Price": RASO_TYPES["good_prices"],
}

# Reverse mapping: export code -> DocType
CODE_TO_DOCTYPE = {code: doctype for doctype, code in DOCTYPE_TO_RASO_TYPE.items()}


# Cache key helpers
def _needs_attention_key(doctype: str) -> str:
	return f"raso:needs_attention:{doctype}"


def _now_str() -> str:
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _export_type_to_code(exp_t):
	if isinstance(exp_t, str):
		return RASO_TYPES.get(exp_t)
	if isinstance(exp_t, int) and exp_t in RASO_TYPES.values():
		return exp_t
	return None


def get_delay_minutes() -> int:
	settings = frappe.get_single("RASO Sync Settings") or {}
	delay_minutes = settings.get("sending_delay_minutes") or 0
	try:
		delay_minutes = int(delay_minutes)
	except Exception:
		delay_minutes = 0
	return delay_minutes


def execute_send_task(export_type=None, date_from=None):
	"""
	Enqueue the send task to export data to RASO.

	Returns:
		status: str: 'queued' if enqueued, 'skipped' if already running
		job_id: str: ID of the enqueued job

	"""
	# Define unique job ID to prevent parallel execution
	job_id = "raso_sync_send_task_worker"

	if is_job_enqueued(job_id):
		return {"status": "skipped"}

	frappe.enqueue(
		"raso_sync.tasks.send.execute_send_task_worker",
		job_id=job_id,
		queue="long",
		enqueue_after_commit=True,
		export_type=export_type,
		date_from=date_from,
	)

	return {"status": "queued", "job_id": job_id}


def mark_doctype_needs_attention(doc, method):
	"""
	Enqueue send task triggered by document event hooks.

	Args:
		doc (Document): The document that triggered the event
		method (str): The method that was called (not used here)

	Returns:
		dict: Result of enqueue operation
	"""
	# Only consider supported doctypes
	if doc.doctype not in DOCTYPE_TO_RASO_TYPE:
		logger.debug(f"RASO Sync: Ignoring document event for unsupported doctype: {doc.doctype}")

	# TODO: Check if sending is enabled
	# NOTE: Once again, it is unnecessary since it is less intensive to create a cache mark than to avoid it by checking DB.

	# Mark needs-attention entry in cache with last event and timestamp
	key = _needs_attention_key(doc.doctype)
	value = {
		"doctype": doc.doctype,
		"last_event": method,
		"marked_at": _now_str(),
	}
	frappe.cache().set_value(key, value)
	logger.debug(f"RASO Sync: Marked {doc.doctype} as needing attention ({method})")
	return {"status": "marked", "doctype": doc.doctype, "event": method}


def process_cache_marks():
	"""
	Scheduler worker that checks debounced DocType events and enqueues a send task
	once the configured delay has elapsed.

	Behavior:
	- Reads per-DocType cache marks created by execute_send_task_on_doc_event.
	- If at least one DocType has waited past delay, enqueue a single consolidated
	  send task (export_type=None => all types) to avoid parallel/duplicate jobs.
	- If any marked event was a delete, we perform a full sync (date_from=None),
	  otherwise we use the 15-minute window.
	- Clears processed cache marks after enqueuing.
	"""
	settings = () or {}
	delay_minutes = settings.get("sending_delay_minutes") or 0
	try:
		delay_minutes = int(delay_minutes)
	except Exception:
		delay_minutes = 0

	# NECESSARY CHECK
	# send_check_interval_minutes > 0
	if (
		settings.get("send_check_interval_minutes") is None
		or int(settings.get("send_check_interval_minutes")) <= 0
	):
		logger.debug("RASO Sync: Sending disabled, skipping debounced send processing")
		return {"status": "disabled"}

	now = datetime.now()

	# Collect marks
	marks: dict[str, dict[str, Any]] = {}
	any_due = False
	saw_delete = False

	for doctype in DOCTYPE_TO_RASO_TYPE.keys():
		key = _needs_attention_key(doctype)
		value = frappe.cache().get_value(key)
		if not value:
			continue

		try:
			marked_at_str = value.get("marked_at") if isinstance(value, dict) else None
			last_event = value.get("last_event") if isinstance(value, dict) else None
			marked_at = datetime.strptime(marked_at_str, "%Y-%m-%d %H:%M:%S") if marked_at_str else None
		except Exception:
			marked_at = None
			last_event = None

		marks[doctype] = {
			"marked_at": marked_at,
			"last_event": last_event,
		}

		if last_event == "after_delete":
			saw_delete = True

		# Checking in the same loop if any are due immediately
		if marked_at and (now - marked_at) >= timedelta(minutes=delay_minutes):
			any_due = True

	if not any_due:
		return {"status": "pending", "message": "No doctypes past delay yet"}

	# Compute date_from: full sync if any delete, else last 15 minutes window like immediate path
	date_from: str | None
	if saw_delete:
		date_from = None
	else:
		date_from = (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

	# Enqueue a send task with a array of export types based on marked doctypes
	needs_export = []
	for doctype in marks.keys():
		export_type = DOCTYPE_TO_RASO_TYPE.get(doctype)
		if export_type and export_type not in needs_export:
			needs_export.append(export_type)

	result = execute_send_task(export_type=needs_export, date_from=date_from)
	logger.info(
		f"RASO Sync: Enqueued debounced send task for doctypes {list(marks.keys())} with date_from={date_from}, result: {result}"
	)

	# Cleaning up cache marks only if successfully queued
	if isinstance(result, dict) and result.get("status") == "queued":
		delay_minutes = get_delay_minutes()
		for doctype, info in marks.items():
			marked_at = info.get("marked_at")
			if marked_at and (now - marked_at) >= timedelta(minutes=delay_minutes):
				frappe.cache().delete_value(_needs_attention_key(doctype))

	return {"status": result.get("status") if isinstance(result, dict) else "unknown", "result": result}


def execute_send_task_worker(
	export_type: str | list[str] | None = None,
	date_from: str | None = None,
	inform_user: bool = False,
):
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_send_task_worker

	Worker function that performs the actual export and sending.

	Args:
		export_type (str | list[str] | None): Type(s) of data to export, or None for all types
		date_from (str, optional): Start date filter (YYYY-MM-DD format)
	"""
	msgprint_handler = None
	if inform_user:
		msgprint_handler = MsgprintHandler()
		msgprint_handler.setLevel(logging.INFO)
		logger.addHandler(msgprint_handler)

	if not is_within_working_hours():
		logger.info("Send Task: Skipped due to outside of working hours.")
		return

	# TODO: Argument check ---
	results = {
		"total_exported": 0,
		"types_processed": [],
		"failed": 0,
		"successful": 0,
		"errors": [],
	}

	try:
		# Read debounce delay to decide whether to clean cache at the end
		delay_minutes = get_delay_minutes()
		now = datetime.now()

		if export_type is None or export_type == "all":
			types_to_export = list(RASO_TYPES.keys())
		elif isinstance(export_type, str):
			types_to_export = [export_type]
		elif not isinstance(export_type, list):
			raise TypeError("export_type must be a string, list of strings, or None.")
		else:
			types_to_export = export_type

		for export_type in types_to_export:
			if _export_type_to_code(export_type) is None:
				raise ValueError(f"Invalid export type: {export_type}.")

		# NOTE: types_to_export is ready and validated and contains only RASO_TYPES keys

		logger.info(f"Send Task: started for {types_to_export}")

		for exp_type in types_to_export:
			try:
				type_result = export_and_send_type(
					export_type=exp_type,
					date_from=date_from,
				)

				results["types_processed"].append(exp_type)
				results["total_exported"] += type_result.get("count", 0)
				results["successful"] += 1

			except Exception as e:
				results["failed"] += 1
				error_msg = str(e)
				results["errors"].append({"type": exp_type, "error": error_msg})
				logger.error(f"Sent Task: Error exporting {exp_type}: {error_msg}")

		logger.info(
			"Sent Task: Completed. Exported: %s, Successful: %s, Failed: %s"
			% (
				results["total_exported"],
				results["successful"],
				results["failed"],
			)
		)

		# Clean debounce marks only for successfully processed doctypes that are past delay
		if delay_minutes > 0:
			try:
				for key in map(
					_needs_attention_key,
					map(CODE_TO_DOCTYPE.get, map(_export_type_to_code, results["types_processed"])),
				):
					value = frappe.cache().get_value(key)
					if not value:
						continue
					marked_at_str = value.get("marked_at") if isinstance(value, dict) else None
					try:
						marked_at = (
							datetime.strptime(marked_at_str, "%Y-%m-%d %H:%M:%S") if marked_at_str else None
						)
					except Exception:
						marked_at = None
					if marked_at and (now - marked_at) >= timedelta(minutes=delay_minutes):
						frappe.cache().delete_value(key)
			except Exception as e:
				logger.error(f"Sent Task: Error cleaning cache for {key}: {e!s}")
				pass

	except Exception as e:
		logger.error(f"Sent Task: Fatal error - {e!s}")
		raise
	finally:
		# Remove msgprint handler after task completion
		if msgprint_handler:
			logger.removeHandler(msgprint_handler)


def export_and_send_type(export_type, date_from=None):
	"""
	Export a single data type from ERPNext and send to RASO.

	Args:
		export_type (str): Type of data to export RASO_TYPE
		date_from (str, optional): Start date filter

	Returns:
		dict: Export result with keys:
			- count: Number of records exported
			- sync_import_id: ID returned from RASO database

	Raises:
		Exception: If export or send fails
	"""
	# Parse and validate export_type argument
	if isinstance(export_type, str):
		export_type = RASO_TYPES.get(export_type, None)
	elif isinstance(export_type, int):
		if export_type not in RASO_TYPES.values():
			raise ValueError(f"Invalid export type number: {export_type}. Must be between 1 and 4.")
	else:
		raise TypeError("export_type must be a string or an integer.")

	if export_type is None:
		raise ValueError("Invalid export type. Must be one of the defined keys or numbers in RASO_TYPES.")

	logger.debug(f"Exporting {export_type}...")

	export_data = export_for_raso(data_type=export_type, full_sync=0 if date_from else 1, date_from=date_from)

	record_count = len(export_data)
	logger.debug(f"Exported {record_count} {export_type} records from ERPNext")

	# Get RASO settings
	# settings = get_raso_settings()
	# data_provider = settings.get('data_provider', 'FRAPPE')
	# NOTE: can be implemented later, just not really using different types, need to have documentation for it

	# Send to RASO database using ie.usp_SyncDataImport_i
	sync_import_id = insert_to_raso(data_type=export_type, sync_data=export_data)
	logger.info(f"Sent {export_type} to RASO (SyncDataImportId: {sync_import_id})")

	return {"count": record_count, "sync_import_id": sync_import_id}


def insert_to_raso(data_type, sync_data, data_provider=None):
	"""
	Sends formatted data to RASO database.

	Uses ie.usp_SyncDataImport_i stored procedure to insert new import records.
	Records are inserted with Status = 0 ("New Data").

	Args:
		data_type (int): Data type identifier
		sync_data (str): Data payload
		data_provider (str, optional): Data provider name (defaults from settings)

	Returns:
		int: SyncDataImportId of the newly created record

	Raises:
		Exception: If database insert fails
	"""
	try:
		params = {
			"DataType": data_type,
			"DataProvider": "KVITAS",  # For now harcoding like this since RASO somewhat expects it
			#    data_provider or settings.get('data_provider', 'FRAPPE'),
			"SyncData": sync_data,
		}

		# Execute stored procedure to insert import record
		# The procedure returns the newly created SyncDataImportId
		result = ProcedureBuilder.execute_procedure("ie.usp_SyncDataImport_i", params)

		# Extract the ID from result
		if isinstance(result, list) and len(result) > 0:
			sync_import_id = result[0].get("SyncDataImportId")
		else:
			sync_import_id = result.get("SyncDataImportId") if result else None

		if not sync_import_id:
			logger.error("No SyncDataImportId returned from procedure")
			raise Exception("No SyncDataImportId returned from procedure")

		logger.debug(f"Created import record {sync_import_id} in RASO")
		return sync_import_id

	except Exception as e:
		logger.error(f"Error sending data to RASO: {e!s}")
		raise


def store_export_to_disk(export_type, data, export_data):
	"""
	Store exported data to disk for audit/debugging purposes.
	"""
	# Create exports directory in site's private directory
	exports_dir = Path(frappe.get_site_path()) / "private" / "raso_exports"
	exports_dir.mkdir(parents=True, exist_ok=True)

	# Create timestamped filename
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = f"{export_type}_{timestamp}.json"
	file_path = exports_dir / filename

	# Write to file
	with open(file_path, "w", encoding="utf-8") as f:
		f.write(data)

	return str(file_path)


def get_raso_settings():
	"""Retrieve RASO Sync Settings document."""
	try:
		settings = frappe.get_doc("RASO Sync Settings")
		return settings.as_dict()
	except frappe.DoesNotExistError:
		logger.warning("RASO Sync Settings not configured")
		return {}
