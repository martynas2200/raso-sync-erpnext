from __future__ import annotations

import importlib
import sys

import pytest


def import_connection_module():
	"""Import connection module under test after faking external deps in fixtures."""
	for key in [
		"raso_sync.db.connection",
		"raso_sync.db.exceptions",
		"raso_sync.db",
		"raso_sync.utils.app_logging",
	]:
		sys.modules.pop(key, None)
	return importlib.import_module("raso_sync.db.connection")


def test_connect_raises_server_unavailable_on_operational_error(fake_frappe, fake_pymssql, monkeypatch):
	mod = import_connection_module()
	ex_mod = importlib.import_module("raso_sync.db.exceptions")

	conn = mod.MSSQLConnection(host="x", user="u", password="p", database="d")

	def boom(*args, **kwargs):
		raise fake_pymssql.OperationalError(
			20009,
			b"Unable to connect: Adaptive Server is unavailable or does not exist",
		)

	monkeypatch.setattr(fake_pymssql, "connect", boom)

	with pytest.raises(ex_mod.RASOServerUnavailableError):
		conn._connect()

	assert fake_frappe.published_realtime == [
		(("raso_sync_status_update", {"is_running": False}), {}),
	]


def test_connect_raises_validation_error_on_generic_pymssql_error(fake_frappe, fake_pymssql, monkeypatch):
	mod = import_connection_module()
	ex_mod = importlib.import_module("raso_sync.db.exceptions")

	conn = mod.MSSQLConnection(host="x", user="u", password="p", database="d")

	def boom(*args, **kwargs):
		raise fake_pymssql.Error("some other db error")

	monkeypatch.setattr(fake_pymssql, "connect", boom)

	with pytest.raises(fake_frappe.ValidationError) as excinfo:
		conn._connect()

	# Must NOT be classified as a server-unavailable error
	assert not isinstance(excinfo.value, ex_mod.RASOServerUnavailableError)
	assert fake_frappe.published_realtime == [
		(("raso_sync_status_update", {"is_running": False}), {}),
	]


def test_update_sync_status_publishes_expected_event(fake_frappe):
	mod = import_connection_module()

	mod.MSSQLConnection._update_sync_status(True)
	mod.MSSQLConnection._update_sync_status(False)

	assert fake_frappe.published_realtime == [
		(("raso_sync_status_update", {"is_running": True}), {}),
		(("raso_sync_status_update", {"is_running": False}), {}),
	]


def test_session_reuses_connection_across_cursor_executions(
	fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_connection_module()
	manager = mod.MSSQLConnectionManager
	fake_frappe.local = type("Local", (), {"site": "test.local"})()
	fake_connection = fake_connection_factory()

	monkeypatch.setattr(
		manager,
		"_get_config_from_settings",
		lambda: {"host": "x", "user": "u", "password": "p", "database": "d"},
	)
	monkeypatch.setattr(fake_pymssql, "connect", lambda **kwargs: fake_connection)

	with manager.session() as connection:
		with connection.cursor():
			first_connection = connection._connection
		assert first_connection is fake_connection
		assert fake_connection.close_count == 0

		with connection.cursor():
			second_connection = connection._connection
		assert second_connection is first_connection
		assert fake_connection.close_count == 0

	assert fake_connection.commit_count == 2
	assert fake_connection.close_count == 1
	assert fake_frappe.published_realtime == [
		(("raso_sync_status_update", {"is_running": True}), {}),
		(("raso_sync_status_update", {"is_running": False}), {}),
	]


def test_cursor_rolls_back_and_closes_on_operation_error(
	fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_connection_module()
	connection = mod.MSSQLConnection(host="x", user="u", password="p", database="d")
	fake_connection = fake_connection_factory()
	monkeypatch.setattr(fake_pymssql, "connect", lambda **kwargs: fake_connection)

	with pytest.raises(RuntimeError, match="operation failed"):
		with connection.cursor():
			raise RuntimeError("operation failed")

	assert fake_connection.rollback_count == 1
	assert fake_connection.commit_count == 0
	assert len(fake_connection.cursors) == 1
	assert fake_connection.cursors[0].close_count == 1
	assert fake_connection.close_count == 1
	assert not connection.is_connected()


def test_mssql_session_closes_connection_when_worker_raises(
	fake_frappe, fake_pymssql, fake_connection_factory, monkeypatch
):
	mod = import_connection_module()
	manager = mod.MSSQLConnectionManager
	fake_frappe.local = type("Local", (), {"site": "test.local"})()
	fake_connection = fake_connection_factory()
	monkeypatch.setattr(
		manager,
		"_get_config_from_settings",
		lambda: {"host": "x", "user": "u", "password": "p", "database": "d"},
	)
	monkeypatch.setattr(fake_pymssql, "connect", lambda **kwargs: fake_connection)

	@mod.mssql_session
	def worker():
		manager.get_connection().connect()
		raise RuntimeError("worker failed")

	with pytest.raises(RuntimeError, match="worker failed"):
		worker()

	assert fake_connection.close_count == 1
	assert manager._connections == {}


def test_connection_manager_keeps_sites_isolated(fake_frappe, monkeypatch):
	mod = import_connection_module()
	manager = mod.MSSQLConnectionManager
	monkeypatch.setattr(
		manager,
		"_get_config_from_settings",
		lambda: {"host": "x", "user": "u", "password": "p", "database": "d"},
	)

	fake_frappe.local = type("Local", (), {"site": "first.local"})()
	first = manager.get_connection()
	fake_frappe.local = type("Local", (), {"site": "second.local"})()
	second = manager.get_connection()

	assert first is not second
	assert set(manager._connections) == {"first.local", "second.local"}
	manager.reset()
