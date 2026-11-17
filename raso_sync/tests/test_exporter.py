from __future__ import annotations

import importlib
import sys

import pytest


def import_exporter_module(fake_frappe):
	fake_frappe.whitelist = lambda *a, **kw: (lambda fn: fn)
	fake_frappe.get_traceback = lambda with_context=False: "TRACEBACK-LINE"
	sys.modules.pop("raso_sync.api.exporter", None)
	return importlib.import_module("raso_sync.api.exporter")


def test_export_for_raso_logs_diagnostics_on_failure(fake_frappe, monkeypatch):
	mod = import_exporter_module(fake_frappe)

	def explode(*args, **kwargs):
		raise ValueError("handler exploded")

	monkeypatch.setattr(mod, "good_prices_internal", explode)

	root = mod.export_for_raso(4, full_sync=1)

	assert root.tag == "Error"
	assert root.findtext("Message") == "handler exploded"

	title, message = fake_frappe.logged_errors[0]
	assert title == "RASO Sync API Export Error"
	assert "handler exploded" in message
	assert "full_sync=1" in message
	# A one-line-only message makes log_error drop the traceback entirely.
	assert "TRACEBACK-LINE" in message
