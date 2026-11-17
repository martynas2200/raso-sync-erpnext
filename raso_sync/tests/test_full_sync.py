from __future__ import annotations

import importlib
import sys
import types

import pytest


def import_full_sync_module(fake_frappe, monkeypatch):
	background_jobs = types.ModuleType("frappe.utils.background_jobs")
	background_jobs.is_job_enqueued = lambda job_id: False  # type: ignore[attr-defined]
	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.background_jobs = background_jobs  # type: ignore[attr-defined]
	fake_frappe.utils = frappe_utils
	monkeypatch.setitem(sys.modules, "frappe.utils", frappe_utils)
	monkeypatch.setitem(sys.modules, "frappe.utils.background_jobs", background_jobs)

	logger = types.SimpleNamespace(
		info=lambda *a, **kw: None,
		debug=lambda *a, **kw: None,
		warning=lambda *a, **kw: None,
		error=lambda *a, **kw: None,
		exception=lambda *a, **kw: None,
	)
	for name, attrs in {
		"raso_sync.tasks.fetch": {
			"execute_fetch_task_worker": lambda: None,
			"execute_fetch_task": lambda *a, **kw: None,
			"get_exports": lambda *a, **kw: None,
			"process_export_record": lambda *a, **kw: None,
			"update_export_status": lambda *a, **kw: None,
		},
		"raso_sync.tasks.send": {
			"execute_send_task_worker": lambda *a, **kw: None,
			"RASO_TYPES": {},
			"execute_send_task": lambda *a, **kw: None,
			"export_and_send_type": lambda *a, **kw: None,
			"insert_to_raso": lambda *a, **kw: None,
		},
		"raso_sync.utils.app_logging": {"get_logger": lambda name: logger},
	}.items():
		module = types.ModuleType(name)
		for attr, value in attrs.items():
			setattr(module, attr, value)
		monkeypatch.setitem(sys.modules, name, module)

	sys.modules.pop("raso_sync.tasks.full_sync", None)
	return importlib.import_module("raso_sync.tasks.full_sync")


def test_full_sync_sends_prices_as_authoritative_full_sync(fake_frappe, monkeypatch):
	mod = import_full_sync_module(fake_frappe, monkeypatch)
	calls = []
	monkeypatch.setattr(
		mod, "execute_send_task_worker", lambda export_type, **kw: calls.append((export_type, kw))
	)
	monkeypatch.setattr(mod, "execute_fetch_task_worker", lambda: calls.append(("fetch", {})))

	mod.execute_full_sync_task_worker()

	assert calls[0][0] == "fetch"

	group_calls = [call for call in calls if call[0] == "good_groups"]
	# The group import ignores RASO config 65, so FullSync=1 always upserts and
	# disables: a delta pass would write every group twice.
	assert len(group_calls) == 1
	assert "date_from" not in group_calls[0][1]

	price_calls = [call for call in calls if call[0] == "good_prices"]
	# Two passes: the FullSync=0 delta is the only one that refreshes an existing price
	# at RASO config 65 = 0, and the FullSync=1 packet inserts and disables.
	assert len(price_calls) == 2

	delta_kwargs = price_calls[0][1]
	assert delta_kwargs.get("date_from")
	assert not delta_kwargs.get("docnames")

	full_kwargs = price_calls[1][1]
	# export_and_send_type only emits FullSync="1" when neither date_from nor docnames
	# is set (or force_full_sync is requested).
	assert "date_from" not in full_kwargs
	assert not full_kwargs.get("docnames")
	assert full_kwargs.get("full_sync_doctypes") in (None, ["Item Price"])
