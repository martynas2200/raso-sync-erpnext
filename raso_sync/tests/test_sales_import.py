from __future__ import annotations

import importlib
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest


def import_sales_module(fake_frappe, monkeypatch):
	for key in [
		"raso_sync.data_imports.sales",
		"raso_sync.data_imports",
		"raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings",
	]:
		sys.modules.pop(key, None)

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.flt = lambda value: float(value)
	monkeypatch.setitem(sys.modules, "frappe.utils", frappe_utils)
	fake_frappe.utils = frappe_utils

	settings_module = types.ModuleType("raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings")
	settings_module.RASOSyncSettings = type(
		"RASOSyncSettings",
		(),
		{"get_settings": staticmethod(lambda: SimpleNamespace(default_item="DEFAULT-ITEM"))},
	)
	monkeypatch.setitem(
		sys.modules,
		"raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings",
		settings_module,
	)

	return importlib.import_module("raso_sync.data_imports.sales")


def test_sales_fixture_payment_totals_match(fake_frappe, monkeypatch):
	mod = import_sales_module(fake_frappe, monkeypatch)
	root = load_sales_fixture()

	result = mod.validate_sales_payments(root)

	assert result["valid"] is True
	assert result["error"] == ""
	assert result["sales_payments"] == pytest.approx({"2": 12.1, "0": 5.2, "1001": 0.03})
	assert result["total_payments"] == pytest.approx({"2": 12.1, "0": 5.2, "1001": 0.03})


def load_sales_fixture():
	xml_path = Path(__file__).with_name("sales.xml")
	return ET.fromstring(xml_path.read_text(encoding="utf-8"))


def fixture_sale_by_code(code):
	for sale in load_sales_fixture().findall("Sales/Sale"):
		if sale.findtext("CODE") == code:
			return sale
	raise AssertionError(f"Fixture sale with code {code} was not found")


class InvoiceSpy:
	def __init__(self):
		self.items = []

	def append(self, fieldname, value):
		assert fieldname == "items"
		self.items.append(value)


class SalesDbSpy:
	def __init__(self, barcode_values=None, existing_items=None):
		self.barcode_values = barcode_values or {}
		self.existing_items = existing_items or set()
		self.barcode_queries = []
		self.exists_queries = []

	def get_value(self, doctype, filters, fields):
		assert doctype == "Item Barcode"
		self.barcode_queries.append(filters["barcode"])
		return self.barcode_values.get(filters["barcode"])

	def exists(self, doctype, item_code):
		assert doctype == "Item"
		self.exists_queries.append(item_code)
		return item_code in self.existing_items


@pytest.mark.parametrize(
	("barcode_values", "existing_items", "expected_item", "expected_uom", "expected_queries"),
	[
		({"2201100": ("ITEM-STRIPPED", "Kg")}, set(), "ITEM-STRIPPED", "Kg", ["2201100"]),
		(
			{"0000002201100": ("ITEM-FULL", "Nos")},
			set(),
			"ITEM-FULL",
			"Nos",
			["2201100", "0000002201100"],
		),
		({}, {"P0001"}, "P0001", "Nos", ["2201100", "0000002201100"]),
	],
)
def test_add_item_to_invoice_selects_item_by_priority(
	fake_frappe,
	monkeypatch,
	barcode_values,
	existing_items,
	expected_item,
	expected_uom,
	expected_queries,
):
	mod = import_sales_module(fake_frappe, monkeypatch)
	db = SalesDbSpy(barcode_values=barcode_values, existing_items=existing_items)
	fake_frappe.db = db
	monkeypatch.setattr(
		mod.RASOSyncSettings,
		"get_settings",
		staticmethod(lambda: SimpleNamespace(default_item="DEFAULT-ITEM")),
	)
	fake_frappe.get_doc = lambda doctype, item_code: SimpleNamespace(stock_uom="Nos")
	invoice = InvoiceSpy()

	mod.add_item_to_invoice(invoice, fixture_sale_by_code("0000002201100"))

	assert invoice.items[0]["item_code"] == expected_item
	assert invoice.items[0]["stock_uom"] == expected_uom
	assert db.barcode_queries == expected_queries


def test_add_item_to_invoice_uses_default_item_when_lookup_fails(fake_frappe, monkeypatch):
	mod = import_sales_module(fake_frappe, monkeypatch)
	db = SalesDbSpy()
	fake_frappe.db = db
	monkeypatch.setattr(
		mod.RASOSyncSettings,
		"get_settings",
		staticmethod(lambda: SimpleNamespace(default_item="DEFAULT-ITEM")),
	)
	fake_frappe.get_doc = lambda doctype, item_code: SimpleNamespace(stock_uom="Nos")
	invoice = InvoiceSpy()

	mod.add_item_to_invoice(invoice, fixture_sale_by_code("0000002201100"))

	assert invoice.items[0]["item_code"] == "DEFAULT-ITEM"
	assert hasattr(invoice, "_item_lookup_errors")
	assert fake_frappe.logged_errors[0][0] == "RASO Import - No item"
