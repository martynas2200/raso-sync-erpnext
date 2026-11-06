from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import pytest


def import_executor_module():
	"""Import the module under test after faking external deps in fixtures."""
	# Ensure a clean import each time so it binds to the faked modules
	for key in [
		"raso_sync.db.executor",
		"raso_sync.db.connection",
		"raso_sync.db",
		"raso_sync.utils.app_logging",
	]:
		sys.modules.pop(key, None)
	return importlib.import_module("raso_sync.db.executor")


def test_execute_success_returns_rows(fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch):
	mod = import_executor_module()

	rows = [{"col": 1}, {"col": 2}]
	conn = fake_connection_factory(rows=rows, rowcount=len(rows))
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	execu = mod.ProcedureExecutor("dbo.usp_Test")
	execu.add_parameter("id", 42, param_type="INT")

	result = execu.execute()

	assert result["success"] is True
	assert result["rows_affected"] == 2
	assert result["result_set"] == rows
	# Verify SQL built and bound values
	assert conn.last_cursor is not None
	assert conn.last_cursor.executed_command is not None
	assert "EXEC dbo.usp_Test" in conn.last_cursor.executed_command
	assert "@id = %s" in conn.last_cursor.executed_command
	assert conn.last_cursor.executed_params == [42]


def test_execute_without_results_is_handled(fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch):
	mod = import_executor_module()

	conn = fake_connection_factory(rows=None, rowcount=0, fetchall_error=AttributeError())
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	execu = mod.ProcedureExecutor("dbo.usp_Test")
	result = execu.execute()

	assert result["success"] is True
	assert result["rows_affected"] == 0
	assert result["result_set"] == []


def test_execute_handles_db_error_and_raises_validation_error(
	fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_executor_module()

	# Sanity: our fake pymssql.Error should be the same class used in the module
	assert mod.pymssql.Error is fake_pymssql.Error

	# Simulate pymssql.Error during execute
	conn = fake_connection_factory(execute_error=fake_pymssql.Error("boom"))
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	execu = mod.ProcedureExecutor("dbo.usp_Fail")

	with pytest.raises(fake_frappe.ValidationError):
		execu.execute()

	# Error should be logged via frappe
	log = fake_frappe._loggers.get("raso_sync.db")
	assert log is not None
	assert any("Procedure execution error" in msg for msg in log.errors)
	assert any("Procedure execution error" in (e[0] or "") for e in fake_frappe.logged_errors)


@pytest.mark.parametrize(
	"rows, expected",
	[
		([(10, "b")], 10),
		([{"x": "first", "y": "second"}], "first"),
	],
)
def test_execute_scalar_returns_first_value(
	rows: list[Any], expected: Any, fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_executor_module()
	conn = fake_connection_factory(rows=rows)
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	execu = mod.ProcedureExecutor("dbo.usp_Scalar")
	value = execu.execute_scalar()
	assert value == expected


def test_execute_single_row_and_list(fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch):
	mod = import_executor_module()
	rows = [{"a": 1}, {"a": 2}]
	conn = fake_connection_factory(rows=rows)
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	execu = mod.ProcedureExecutor("dbo.usp_List")
	assert execu.execute_single_row() == rows[0]
	assert execu.execute_row_list() == rows


def test_procedure_builder_execute_procedure_builds_and_executes(
	fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_executor_module()

	conn = fake_connection_factory(rows=[{"ok": True}], rowcount=1)
	monkeypatch.setattr(mod.MSSQLConnectionManager, "get_connection", lambda: conn)

	params = {"group_id": 123, "status": "active"}
	result = mod.ProcedureBuilder.execute_procedure("dbo.usp_Test", params)

	assert result["success"] is True
	assert conn.last_cursor is not None
	sql = conn.last_cursor.executed_command or ""
	assert "EXEC dbo.usp_Test" in sql
	assert "@group_id = %s" in sql and "@status = %s" in sql
	# Parameter order preserved
	assert conn.last_cursor.executed_params == [123, "active"]


def test_send_task_logs_error_details(fake_frappe, monkeypatch):
	"""Send task logs should keep the underlying exception details for failed export types."""
	for key in [
		"raso_sync.tasks.send",
		"raso_sync.tasks",
		"raso_sync.api.exporter",
		"raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings",
		"raso_sync.db.connection",
		"raso_sync.db.exceptions",
		"raso_sync.db.executor",
		"raso_sync.utils.app_logging",
		"raso_sync.utils.system_notifications",
	]:
		sys.modules.pop(key, None)

	fetch_mod = types.ModuleType("raso_sync.tasks.fetch")
	fetch_mod.execute_fetch_task = lambda *args, **kwargs: None
	fetch_mod.get_exports = lambda *args, **kwargs: []
	fetch_mod.process_export_record = lambda *args, **kwargs: None
	fetch_mod.update_export_status = lambda *args, **kwargs: None
	monkeypatch.setitem(sys.modules, "raso_sync.tasks.fetch", fetch_mod)

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.flt = lambda value, *args, **kwargs: value
	frappe_utils.cint = lambda value, *args, **kwargs: value
	background_jobs = types.ModuleType("frappe.utils.background_jobs")
	background_jobs.is_job_enqueued = lambda job_id: False
	monkeypatch.setitem(sys.modules, "frappe.utils", frappe_utils)
	monkeypatch.setitem(sys.modules, "frappe.utils.background_jobs", background_jobs)
	fake_frappe.utils = frappe_utils

	exporter = types.ModuleType("raso_sync.api.exporter")
	exporter.export_for_raso = lambda *args, **kwargs: []
	exporter.format_xml_response = lambda data: "<xml />"
	monkeypatch.setitem(sys.modules, "raso_sync.api.exporter", exporter)

	settings_mod = types.ModuleType("raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings")
	settings_mod.RASOSyncSettings = type(
		"RASOSyncSettings", (), {"update_last_data_export": staticmethod(lambda: None)}
	)
	monkeypatch.setitem(
		sys.modules, "raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings", settings_mod
	)

	db_connection = types.ModuleType("raso_sync.db.connection")
	db_connection.mssql_session = lambda func: func
	monkeypatch.setitem(sys.modules, "raso_sync.db.connection", db_connection)

	db_exceptions = types.ModuleType("raso_sync.db.exceptions")

	class RASOServerUnavailableError(Exception):
		pass

	db_exceptions.RASOServerUnavailableError = RASOServerUnavailableError
	monkeypatch.setitem(sys.modules, "raso_sync.db.exceptions", db_exceptions)

	db_executor = types.ModuleType("raso_sync.db.executor")
	db_executor.ProcedureBuilder = type(
		"ProcedureBuilder",
		(),
		{
			"execute_procedure": staticmethod(
				lambda *args, **kwargs: {"result_set": [{"SyncDataImportId": 1}]}
			)
		},
	)
	monkeypatch.setitem(sys.modules, "raso_sync.db.executor", db_executor)

	notifications = types.ModuleType("raso_sync.utils.system_notifications")
	notifications.notify_server_unavailable = lambda: None
	monkeypatch.setitem(sys.modules, "raso_sync.utils.system_notifications", notifications)

	mod = importlib.import_module("raso_sync.tasks.send")
	monkeypatch.setattr(
		mod,
		"export_and_send_type",
		lambda export_type, date_from=None, docnames=None, force_full_sync=False: (_ for _ in ()).throw(
			RuntimeError(f"boom for {export_type}")
		),
	)

	mod.execute_send_task_worker(
		export_type=["partners", "goods"],
		queue_marks={
			"Customer": [mod.QueueMark("C-1", "2024-01-01")],
			"Item": [mod.QueueMark("I-1", "2024-01-01")],
		},
	)

	logged = "\n".join(str(part) for entry in fake_frappe.logged_errors for part in entry)
	assert "boom for partners" in logged
	assert "boom for goods" in logged
