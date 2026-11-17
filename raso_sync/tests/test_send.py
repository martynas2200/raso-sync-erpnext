from __future__ import annotations

import importlib
import os
import sys
import types
import xml.etree.ElementTree as ET

import pytest

import raso_sync


def import_send_module(fake_frappe, monkeypatch):
	fake_frappe.whitelist = lambda *a, **kw: (lambda fn: fn)

	background_jobs = types.ModuleType("frappe.utils.background_jobs")
	background_jobs.is_job_enqueued = lambda job_id: False  # type: ignore[attr-defined]
	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.background_jobs = background_jobs  # type: ignore[attr-defined]
	fake_frappe.utils = frappe_utils

	document = types.ModuleType("frappe.model.document")
	document.Document = type("Document", (), {})  # type: ignore[attr-defined]
	model = types.ModuleType("frappe.model")
	model.document = document  # type: ignore[attr-defined]
	fake_frappe.model = model

	scheduler_manager = types.ModuleType("raso_sync.utils.scheduler_manager")
	scheduler_manager.create_or_update_scheduled_job = lambda *a, **kw: None  # type: ignore[attr-defined]
	scheduler_manager.disable_scheduled_job = lambda *a, **kw: None  # type: ignore[attr-defined]

	# Stub the tasks package itself so importing send does not pull in the fetch chain.
	tasks = types.ModuleType("raso_sync.tasks")
	tasks.__path__ = [os.path.join(os.path.dirname(raso_sync.__file__), "tasks")]  # type: ignore[attr-defined]
	tasks.with_msgprint_logging = lambda logger: (lambda fn: fn)  # type: ignore[attr-defined]

	for name, module in {
		"frappe.utils": frappe_utils,
		"frappe.utils.background_jobs": background_jobs,
		"frappe.model": model,
		"frappe.model.document": document,
		"raso_sync.utils.scheduler_manager": scheduler_manager,
		"raso_sync.tasks": tasks,
	}.items():
		monkeypatch.setitem(sys.modules, name, module)

	sys.modules.pop("raso_sync.tasks.send", None)
	return importlib.import_module("raso_sync.tasks.send")


def test_export_and_send_type_rejects_error_payload(fake_frappe, fake_pymssql, monkeypatch):
	mod = import_send_module(fake_frappe, monkeypatch)

	error_root = ET.Element("Error")
	ET.SubElement(error_root, "Message").text = "boom"
	monkeypatch.setattr(mod, "export_for_raso", lambda *a, **kw: error_root)
	monkeypatch.setattr(mod, "insert_to_raso", lambda *a, **kw: pytest.fail("error payload must not be sent"))

	with pytest.raises(Exception, match="boom"):
		mod.export_and_send_type("good_prices", force_full_sync=True)


def test_export_and_send_type_sends_valid_payload(fake_frappe, fake_pymssql, monkeypatch):
	mod = import_send_module(fake_frappe, monkeypatch)

	root = ET.Element("GoodsPricesSync", {"FullSync": "1"})
	ET.SubElement(ET.SubElement(root, "GoodsPrices"), "GoodsCode").text = "4770123456789"
	sent = {}

	monkeypatch.setattr(mod, "export_for_raso", lambda *a, **kw: root)
	monkeypatch.setattr(
		mod, "insert_to_raso", lambda data_type, sync_data: sent.update(data_type=data_type, data=sync_data)
	)

	assert mod.export_and_send_type("good_prices", force_full_sync=True) == 1
	assert sent["data_type"] == 4
	assert 'FullSync="1"' in sent["data"]
