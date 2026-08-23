"""Send Task (ERPNext -> RASO)"""

import logging
from typing import Any

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from . import with_msgprint_logging

logger = frappe.logger("raso_sync_send")
logger.setLevel("DEBUG")

from raso_sync.api.exporter import export_for_raso, format_xml_response
from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings

from ..db.exceptions import RASOServerUnavailableError
from ..db.executor import ProcedureBuilder
from ..utils.system_notifications import notify_server_unavailable

# Supported export data types
RASO_TYPES = {
	"partners": 1,
	"good_groups": 2,
	"goods": 3,
	"good_prices": 4,
}

# Reverse mapping: export code -> RASO_TYPES key
CODE_TO_RASO_TYPE = {code: name for name, code in RASO_TYPES.items()}

# Mapping from ERPNext DocType to RASO_TYPES numeric codes
DOCTYPE_TO_RASO_TYPE = {
	"Customer": RASO_TYPES["partners"],
	"Item Group": RASO_TYPES["good_groups"],
	"Item": RASO_TYPES["goods"],
	"Item Price": RASO_TYPES["good_prices"],
}

# Reverse mapping: export code -> DocType
CODE_TO_DOCTYPE = {code: doctype for doctype, code in DOCTYPE_TO_RASO_TYPE.items()}
QUEUE_DOCTYPE = "RASO Sync Queue Doc"


def _resolve_export_type_code(exp_t):
	if isinstance(exp_t, str):
		return RASO_TYPES.get(exp_t)
	if isinstance(exp_t, int) and exp_t in CODE_TO_RASO_TYPE:
		return exp_t
	return None


def _export_code_to_key(exp_code: int) -> str | None:
	return CODE_TO_RASO_TYPE.get(exp_code)


def _normalize_export_types(export_type: str | int | list[str | int] | None) -> list[str]:
	if export_type is None or export_type == "all":
		raw_types = list(RASO_TYPES.keys())
	elif isinstance(export_type, str | int):
		raw_types = [export_type]
	elif not isinstance(export_type, list):
		raise TypeError("export_type must be a string, integer, list, or None.")
	else:
		raw_types = export_type

	types_to_export = []
	for exp_t in raw_types:
		code = _resolve_export_type_code(exp_t)
		if code is None:
			raise ValueError(f"Invalid export type: {exp_t}.")

		name = _export_code_to_key(code)
		if not name:
			raise ValueError(f"Could not normalize export type: {exp_t}.")

		if name not in types_to_export:
			types_to_export.append(name)

	return types_to_export


def _update_or_insert_queue_mark(doctype: str, docname: str, method: str) -> None:
	"""Helper function to update or insert a mark in the RASO Sync Queue Doc for a given document event."""

	if doctype == "Item Price":
		if not frappe.db.get_value("Item Price", docname, "selling"):
			return

	previous_value = (
		frappe.db.get_value(
			QUEUE_DOCTYPE,
			{"source_doctype": doctype, "source_name": docname},
			["name", "has_delete", "last_event"],
			as_dict=True,
		)
		or {}
	)

	previous_has_delete = (
		previous_value.get("has_delete") or previous_value.get("last_event") == "after_delete"
	)
	value = {
		"source_doctype": doctype,
		"source_name": docname,
		"last_event": method,
		"marked_at": frappe.utils.now(),
		"has_delete": 1 if previous_has_delete or method == "after_delete" else 0,
	}
	existing_name = previous_value.get("name")

	if existing_name:
		frappe.db.set_value(QUEUE_DOCTYPE, existing_name, value, update_modified=False)
		return

	try:
		frappe.get_doc({"doctype": QUEUE_DOCTYPE, **value}).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		existing_name = frappe.db.get_value(
			QUEUE_DOCTYPE,
			{"source_doctype": doctype, "source_name": docname},
			"name",
		)
		if existing_name:
			frappe.db.set_value(QUEUE_DOCTYPE, existing_name, value, update_modified=False)


def _cleanup_persisted_queue_docs(
	doctype: str,
	docnames: list[str],
) -> None:
	for docname in docnames:
		if not isinstance(docname, str) or not docname:
			continue

		frappe.db.delete(QUEUE_DOCTYPE, {"source_doctype": doctype, "source_name": docname})
		frappe.db.commit()


def execute_send_task(
	export_type=None,
	date_from=None,
	doc_targets=None,
	full_sync_doctypes=None,
):
	"""
	Enqueue the send task to export data to RASO.
	Returns 'queued' if enqueued, 'skipped' if already running
	"""
	# Define unique job ID to prevent parallel execution
	job_id = "raso_sync_send_task_worker"

	if is_job_enqueued(job_id):
		return "skipped"

	frappe.enqueue(
		"raso_sync.tasks.send.execute_send_task_worker",
		job_id=job_id,
		queue="long",
		enqueue_after_commit=True,
		export_type=export_type,
		date_from=date_from,
		doc_targets=doc_targets,
		full_sync_doctypes=full_sync_doctypes,
	)

	return "queued"


def mark_doctype_for_sync(doc, method):
	"""
	Marks a document as needing sync via the RASO Sync Queue Doc.
	This is called from document events.
	"""
	# Only consider supported doctypes
	if doc.doctype not in DOCTYPE_TO_RASO_TYPE:
		logger.debug(f"RASO Sync: Ignoring document event for unsupported doctype: {doc.doctype}")
		return {"status": "ignored", "doctype": doc.doctype}

	_update_or_insert_queue_mark(doc.doctype, doc.name, method)
	logger.debug(f"RASO Sync: Marked {doc.doctype} as needing attention ({method})")
	return {"status": "marked", "doctype": doc.doctype, "event": method}


def process_queued_marks():
	"""
	Scheduler worker that checks persisted DocType queue marks and enqueues a send task.

	Behavior:
	- Reads per-document queue rows from RASO Sync Queue Doc.
	- Enqueues a single consolidated send task with exact pending document targets.
	- If any marked event was a delete, we perform a full sync for that DocType.
	- Clears processed queue marks after enqueuing.
	"""
	# Collect marks
	marks: dict[str, dict[str, Any]] = {}

	queue_rows = frappe.get_all(
		QUEUE_DOCTYPE,
		fields=["source_doctype", "source_name", "last_event", "has_delete"],
		filters={"source_doctype": ["in", list(DOCTYPE_TO_RASO_TYPE.keys())]},
		limit_page_length=0,
	)

	for row in queue_rows:
		doctype = row.get("source_doctype")
		docname = row.get("source_name")
		if not isinstance(doctype, str) or not isinstance(docname, str) or not doctype or not docname:
			continue

		if doctype not in marks:
			marks[doctype] = {"docs": [], "has_delete": False}

		if docname not in marks[doctype]["docs"]:
			marks[doctype]["docs"].append(docname)

		row_has_delete = bool(row.get("has_delete")) or row.get("last_event") == "after_delete"
		marks[doctype]["has_delete"] = bool(marks[doctype]["has_delete"]) or row_has_delete

	if not marks:
		return {"status": "pending", "message": "No pending doctypes"}

	# Enqueue a send task with exact doc targets and full-sync fallback for deletes
	needs_export = []
	doc_targets: dict[str, list[str]] = {}
	full_sync_doctypes: list[str] = []

	for doctype, info in marks.items():
		export_type = DOCTYPE_TO_RASO_TYPE.get(doctype)
		if export_type and export_type not in needs_export:
			needs_export.append(export_type)

		doc_targets[doctype] = info.get("docs") or []

		if info.get("has_delete"):
			if doctype not in full_sync_doctypes:
				full_sync_doctypes.append(doctype)

	result = execute_send_task(
		export_type=needs_export,
		date_from=None,
		doc_targets=doc_targets,
		full_sync_doctypes=full_sync_doctypes,
	)
	logger.info(f"RASO Sync: Enqueued precise send task for doctypes {list(marks.keys())}, result: {result}")

	return {"status": result.get("status") if isinstance(result, dict) else "unknown", "result": result}


@with_msgprint_logging(logger)
def execute_send_task_worker(
	export_type: str | int | list[str | int] | None = None,
	date_from: str | None = None,
	doc_targets: dict[str, list[str]] | None = None,
	full_sync_doctypes: list[str] | None = None,
	inform_user: bool = False,
):
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_send_task_worker

	Worker function that performs the actual export and sending.

	Args:
	    export_type (str | int | list[str | int] | None): Type(s) of data to export,
	        as names or numeric codes, or None for all types
	    date_from (str, optional): Start date filter (YYYY-MM-DD format)
	    doc_targets (dict[str, list[str]] | None): Pending document names by DocType
	    full_sync_doctypes (list[str] | None): Doctypes that require full-sync fallback
	"""
	results = {
		"total_exported": 0,
		"types_processed": [],
		"failed": 0,
		"successful": 0,
		"errors": [],
	}

	try:
		types_to_export = _normalize_export_types(export_type)
		full_sync_doctypes_set = set(full_sync_doctypes or [])

		logger.info(f"Send Task: started for {types_to_export}")

		for exp_type in types_to_export:
			try:
				exp_code = _resolve_export_type_code(exp_type)
				doctype = CODE_TO_DOCTYPE.get(exp_code)
				target_docnames = (doc_targets or {}).get(doctype, [])
				force_full_sync = doctype in full_sync_doctypes_set

				record_count = export_and_send_type(
					export_type=exp_type,
					date_from=date_from,
					docnames=target_docnames,
					force_full_sync=force_full_sync,
				)

				results["types_processed"].append(exp_type)
				results["total_exported"] += record_count
				results["successful"] += 1
				if doctype:
					_cleanup_persisted_queue_docs(
						doctype,
						target_docnames,
					)
				frappe.publish_realtime(
					event="msgprint",
					message={
						"message": frappe._("{0} records of {1} were sent to RASO").format(
							record_count,
							frappe._(CODE_TO_DOCTYPE.get(_resolve_export_type_code(exp_type), exp_type)),
						),
						"alert": 1,
					},
					room="all",
				)

			except Exception as e:
				results["failed"] += 1
				error_msg = str(e)
				results["errors"].append({"type": exp_type, "error": error_msg})
				logger.error(f"Send Task: Error exporting {exp_type}: {error_msg}")

		logger.info(
			"Send Task is completed. Exported: %s, Successful: %s, Failed: %s"
			% (
				results["total_exported"],
				results["successful"],
				results["failed"],
			)
		)
		if results["total_exported"] > 0:
			RASOSyncSettings.update_last_data_export()
		if results["failed"] > 0:
			frappe.msgprint(
				frappe._("Send Task: Completed with errors. Failed types: {0}").format(
					", ".join([err["type"] for err in results["errors"]])
				)
			)
			frappe.log_error(
				"RASO Sync: Send task completed with errors",
				f"Failed types: {', '.join([err['type'] for err in results['errors']])}",
			)

	except RASOServerUnavailableError as e:
		logger.error(f"Send Task: RASO server unavailable - {e!s}")
		notify_server_unavailable()
		raise
	except Exception as e:
		logger.error(f"Send Task: Fatal error - {e!s}")
		raise


def export_and_send_type(
	export_type, date_from=None, docnames: list[str] | None = None, force_full_sync=False
):
	"""
	Export a single data type from ERPNext and send to RASO.

	Args:
	    export_type (str): Type of data to export RASO_TYPE
	    date_from (str, optional): Start date filter

	Returns the number of records exported

	Raises:
	    Exception: If export or send fails
	"""

	export_type = _resolve_export_type_code(export_type)
	if export_type is None:
		raise ValueError("Invalid export type. Must be one of the defined keys or numbers in RASO_TYPES.")

	if force_full_sync:
		export_data = export_for_raso(export_type, full_sync=1)

	elif docnames:
		export_data = export_for_raso(export_type, full_sync=0, docnames=docnames)
	else:
		export_data = export_for_raso(export_type, full_sync=0 if date_from else 1, date_from=date_from)

	logger.debug(f"Exporting type {export_type}...")

	record_count = len(export_data)
	logger.debug(f"Exported {record_count} records of type {export_type} from ERPNext")

	if record_count == 0:
		return 0

	# Convert XML Element to string payload expected by MSSQL
	xml_payload = format_xml_response(export_data)

	# Send to RASO database using ie.usp_SyncDataImport_i
	sync_import_id = insert_to_raso(data_type=export_type, sync_data=xml_payload)
	logger.debug(f"Sent type {export_type} to RASO (SyncDataImportId: {sync_import_id})")

	return record_count


def insert_to_raso(data_type, sync_data):
	"""
	Sends formatted data to RASO database.

	Uses ie.usp_SyncDataImport_i stored procedure to insert new import records.
	Records are inserted with Status = 0 ("New Data").

	Args:
	    data_type (int): Data type identifier
	    sync_data (str): Data payload

	Returns:
	    int: SyncDataImportId of the newly created record

	Raises:
	    Exception: If database insert fails
	"""
	params = {
		"DataType": data_type,
		"DataProvider": "KVITAS",  # defines which API contract RASO follows, more information in RASO UI of Common configuration, setting 63
		"SyncData": sync_data,
	}

	# Execute stored procedure to insert import record
	# The procedure returns the newly created SyncDataImportId
	result = ProcedureBuilder.execute_procedure("ie.usp_SyncDataImport_i", params)

	# Extract the ID from result
	if isinstance(result, dict) and result.get("result_set") and len(result["result_set"]) > 0:
		sync_import_id = result["result_set"][0].get("SyncDataImportId")
	else:
		sync_import_id = result.get("SyncDataImportId") if result else None

	if not sync_import_id:
		frappe.log_error(
			"No SyncDataImportId in RASO send task",
			f"RASO Sync: insert_to_raso failed, data_type={data_type}, result: {result}",
		)
		raise Exception("No SyncDataImportId returned from RASO database.")

	logger.debug(f"Created import record {sync_import_id} in RASO")
	return sync_import_id
