"""
Pytest fixtures and test helpers for raso_sync.
These provide lightweight fakes for frappe and pymssql so tests
can run without a real Frappe site or MSSQL server.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable, Iterable
from typing import Any, Optional

import pytest


class FakeLogger:
	def __init__(self, name: str):
		self.name = name
		self.infos: list[str] = []
		self.errors: list[str] = []

	def setLevel(self, level) -> None:
		return None

	@staticmethod
	def _format(msg: str, args: tuple[Any, ...]) -> str:
		return msg % args if args else msg

	def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
		return None

	def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
		self.infos.append(self._format(msg, args))

	def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
		return None

	def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
		self.errors.append(self._format(msg, args))

	def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
		self.errors.append(self._format(msg, args))


@pytest.fixture
def fake_frappe(monkeypatch: pytest.MonkeyPatch):
	"""Inject a minimal fake `frappe` module into sys.modules.

	Exposes:
	- ValidationError: Exception subclass used by code under test
	- logger(name): returns a FakeLogger instance per name
	- log_error(message, title=None): records last error
	"""

	module = types.ModuleType("frappe")

	class ValidationError(Exception):
		pass

	module.ValidationError = ValidationError

	module._loggers = {}

	def logger(name: str) -> FakeLogger:
		if name not in module._loggers:
			module._loggers[name] = FakeLogger(name)
		return module._loggers[name]

	module.logger = logger  # type: ignore[attr-defined]

	module.logged_errors = []

	def log_error(message: str, title: str | None = None) -> None:
		module.logged_errors.append((message, title))

	module.log_error = log_error  # type: ignore[attr-defined]

	module.published_realtime = []

	def msgprint(*args, **kwargs):
		return None

	module.msgprint = msgprint  # type: ignore[attr-defined]

	def publish_realtime(*args, **kwargs):
		module.published_realtime.append((args, kwargs))

	module.publish_realtime = publish_realtime  # type: ignore[attr-defined]

	def _(text: str, lang: str | None = None, context: str | None = None) -> str:
		return text

	module._ = _  # type: ignore[attr-defined]

	translate_module = types.ModuleType("frappe.translate")
	translate_module.get_user_lang = lambda user: "en"  # type: ignore[attr-defined]

	# Make available to imports
	monkeypatch.setitem(sys.modules, "frappe", module)
	monkeypatch.setitem(sys.modules, "frappe.translate", translate_module)
	return module


@pytest.fixture
def fake_pymssql(monkeypatch: pytest.MonkeyPatch):
	"""Inject a minimal fake `pymssql` module with Error base class."""
	module = types.ModuleType("pymssql")

	class Error(Exception):
		pass

	class OperationalError(Error):
		pass

	module.Error = Error
	module.OperationalError = OperationalError

	def connect(*args, **kwargs):
		raise NotImplementedError("override pymssql.connect in your test")

	module.connect = connect

	# Provide placeholder types used in annotations
	class Connection:  # pragma: no cover - placeholder for type hints
		...

	class Cursor:  # pragma: no cover - placeholder for type hints
		...

	module.Connection = Connection
	module.Cursor = Cursor

	monkeypatch.setitem(sys.modules, "pymssql", module)
	return module


class FakeCursor:
	"""A minimal DB-API-like cursor for tests."""

	def __init__(
		self,
		rows: Iterable[Any] | None = None,
		rowcount: int | None = None,
		execute_error: BaseException | None = None,
		fetchall_error: BaseException | None = None,
	) -> None:
		self._rows = list(rows) if rows is not None else []
		self._rowcount = rowcount if rowcount is not None else len(self._rows)
		self._execute_error = execute_error
		self._fetchall_error = fetchall_error
		self.executed_command: str | None = None
		self.executed_params: list[Any] | tuple[Any, ...] | None = None
		self.close_count = 0

	# Context manager support
	def __enter__(self) -> FakeCursor:
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		return None

	def close(self) -> None:
		self.close_count += 1

	# DB-API surface used by code under test
	def execute(self, command: str, params: Iterable[Any] | None = None) -> None:
		self.executed_command = command
		if params is not None:
			self.executed_params = list(params)
		if self._execute_error:
			raise self._execute_error

	def fetchall(self):
		if self._fetchall_error:
			raise self._fetchall_error
		return list(self._rows)

	@property
	def rowcount(self) -> int:
		return self._rowcount


class FakeConnection:
	"""Connection that returns a configurable FakeCursor for each call."""

	def __init__(
		self,
		*,
		rows: Iterable[Any] | None = None,
		rowcount: int | None = None,
		execute_error: BaseException | None = None,
		fetchall_error: BaseException | None = None,
	) -> None:
		self._rows = rows
		self._rowcount = rowcount
		self._execute_error = execute_error
		self._fetchall_error = fetchall_error
		self.last_cursor: FakeCursor | None = None
		self.cursors: list[FakeCursor] = []
		self.commit_count = 0
		self.rollback_count = 0
		self.close_count = 0

	def commit(self) -> None:
		self.commit_count += 1

	def rollback(self) -> None:
		self.rollback_count += 1

	def close(self) -> None:
		self.close_count += 1

	def cursor(self) -> FakeCursor:
		cur = FakeCursor(
			rows=self._rows,
			rowcount=self._rowcount,
			execute_error=self._execute_error,
			fetchall_error=self._fetchall_error,
		)
		self.last_cursor = cur
		self.cursors.append(cur)
		return cur


@pytest.fixture
def fake_connection_factory() -> Callable[..., FakeConnection]:
	"""Factory fixture to create a FakeConnection with desired behavior."""

	def _factory(**kwargs: Any) -> FakeConnection:
		return FakeConnection(**kwargs)

	return _factory
