from __future__ import annotations

import importlib
import re
import sqlite3
import sys
from datetime import date, datetime
from types import SimpleNamespace

import pytest

PARAM_RE = re.compile(r"%\((\w+)\)s")

SCHEMA = """
CREATE TABLE "tabItem" (
	name TEXT PRIMARY KEY,
	item_name TEXT,
	stock_uom TEXT,
	description TEXT,
	disabled INTEGER DEFAULT 0,
	modified TEXT,
	deposit_package_count INTEGER DEFAULT 0,
	item_group TEXT,
	docstatus INTEGER DEFAULT 0
);
CREATE TABLE "tabItem Barcode" (parent TEXT, barcode TEXT, uom TEXT);
CREATE TABLE "tabUOM Conversion Detail" (parent TEXT, uom TEXT, conversion_factor REAL);
CREATE TABLE "tabItem Price" (
	name TEXT,
	item_code TEXT,
	uom TEXT,
	price_list TEXT,
	selling INTEGER,
	price_list_rate REAL,
	packing_unit INTEGER,
	modified TEXT,
	valid_from TEXT,
	valid_upto TEXT
);
"""


class PriceDb:
	"""In-memory stand-in for frappe.db that actually runs the MariaDB-compatible SQL."""

	def __init__(self):
		self.conn = sqlite3.connect(":memory:")
		self.conn.row_factory = sqlite3.Row
		self.conn.executescript(SCHEMA)

	def insert(self, table, **values):
		columns = ", ".join(f'"{column}"' for column in values)
		marks = ", ".join("?" for _ in values)
		self.conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({marks})', list(values.values()))

	def sql(self, query, params=None, as_dict=False, **kwargs):
		args = []

		def bind(match):
			value = (params or {})[match.group(1)]
			if isinstance(value, tuple | list):
				args.extend(value)
				return "(" + ", ".join("?" for _ in value) + ")"
			if isinstance(value, datetime):
				value = value.strftime("%Y-%m-%d %H:%M:%S")
			elif isinstance(value, date):
				value = value.isoformat()
			args.append(value)
			return "?"

		translated = PARAM_RE.sub(bind, query)
		rows = [dict(row) for row in self.conn.execute(translated, args).fetchall()]
		return rows if as_dict else [tuple(row.values()) for row in rows]


@pytest.fixture
def price_module(fake_frappe):
	db = PriceDb()
	fake_frappe.get_single = lambda doctype: SimpleNamespace(price_list="Retail", shop_no="1")
	fake_frappe.db = SimpleNamespace(sql=db.sql)
	sys.modules.pop("raso_sync.api.good_prices", None)
	return db, importlib.import_module("raso_sync.api.good_prices")


def add_item(db, name, stock_uom="Nos"):
	db.insert("tabItem", name=name, item_name=name, stock_uom=stock_uom)


def add_barcode(db, item, barcode, uom):
	db.insert("tabItem Barcode", parent=item, barcode=barcode, uom=uom)


def add_conversion(db, item, uom, factor):
	db.insert("tabUOM Conversion Detail", parent=item, uom=uom, conversion_factor=factor)


def add_price(db, item, uom, rate, **overrides):
	values = {
		"name": f"{item}-{uom}-{rate}",
		"item_code": item,
		"uom": uom,
		"price_list": "Retail",
		"selling": 1,
		"price_list_rate": rate,
		"packing_unit": 0,
		"modified": "2026-01-01 00:00:00",
		"valid_from": "2026-01-01",
		"valid_upto": None,
	}
	values.update(overrides)
	db.insert("tabItem Price", **values)
	return values["name"]


def exported_rows(root):
	return sorted(
		(price.findtext("GoodsCode"), price.findtext("Qty"), price.findtext("Price"))
		for price in root.findall("GoodsPrices")
	)


def test_multiple_items_are_ranked_and_derived(price_module):
	db, mod = price_module

	# A: two valid base prices -> latest valid_from wins; package derives.
	add_item(db, "ITEM-A")
	add_barcode(db, "ITEM-A", "1000000000001", "Nos")
	add_barcode(db, "ITEM-A", "2000000000001", "Pack")
	add_conversion(db, "ITEM-A", "Pack", 6)
	add_price(db, "ITEM-A", "Nos", 1.5, valid_from="2025-01-01")
	add_price(db, "ITEM-A", "Nos", 2.0, valid_from="2026-01-01")

	# B: same valid_from -> latest modified wins; package has its own price.
	add_item(db, "ITEM-B")
	add_barcode(db, "ITEM-B", "1000000000002", "Nos")
	add_barcode(db, "ITEM-B", "2000000000002", "Pack")
	add_conversion(db, "ITEM-B", "Pack", 4)
	add_price(db, "ITEM-B", "Nos", 3.0, modified="2026-01-02 00:00:00")
	add_price(db, "ITEM-B", "Nos", 3.5, modified="2026-01-03 00:00:00")
	add_price(db, "ITEM-B", "Pack", 12.0)

	# C: package without a stock-UOM barcode -> nothing.
	add_item(db, "ITEM-C")
	add_barcode(db, "ITEM-C", "2000000000003", "Pack")
	add_conversion(db, "ITEM-C", "Pack", 4)
	add_price(db, "ITEM-C", "Nos", 9.0)

	# D: package with a stock barcode but no stock price -> no derived price.
	add_item(db, "ITEM-D")
	add_barcode(db, "ITEM-D", "1000000000004", "Nos")
	add_barcode(db, "ITEM-D", "2000000000004", "Pack")
	add_conversion(db, "ITEM-D", "Pack", 4)

	# E: factor 1 -> base price only, no package content.
	add_item(db, "ITEM-E")
	add_barcode(db, "ITEM-E", "1000000000005", "Nos")
	add_barcode(db, "ITEM-E", "2000000000005", "Pack")
	add_conversion(db, "ITEM-E", "Pack", 1)
	add_price(db, "ITEM-E", "Nos", 5.0)

	# F: stock price only in another list -> not exported, nothing to derive from.
	add_item(db, "ITEM-F")
	add_barcode(db, "ITEM-F", "1000000000006", "Nos")
	add_barcode(db, "ITEM-F", "2000000000006", "Pack")
	add_conversion(db, "ITEM-F", "Pack", 4)
	add_price(db, "ITEM-F", "Nos", 6.0, price_list="Other")

	# G: package price only in another list -> does not suppress derivation.
	add_item(db, "ITEM-G")
	add_barcode(db, "ITEM-G", "1000000000007", "Nos")
	add_barcode(db, "ITEM-G", "2000000000007", "Pack")
	add_conversion(db, "ITEM-G", "Pack", 4)
	add_price(db, "ITEM-G", "Nos", 7.0)
	add_price(db, "ITEM-G", "Pack", 30.0, price_list="Other")

	add_item(db, "ITEM-H")
	add_barcode(db, "ITEM-H", "1000000000008", "Nos")
	add_barcode(db, "ITEM-H", "2000000000008", "Pack")
	add_conversion(db, "ITEM-H", "Pack", 3)
	add_price(db, "ITEM-H", "Nos", 2.99)

	assert exported_rows(mod.good_prices_internal(1, None)) == [
		("1000000000001", "0", "2.0"),
		("1000000000002", "0", "3.5"),
		("1000000000005", "0", "5.0"),
		("1000000000007", "0", "7.0"),
		("1000000000008", "0", "2.99"),
		("2000000000001", "0", "12.0"),
		("2000000000002", "0", "12.0"),
		("2000000000007", "0", "28.0"),
		("2000000000008", "0", "8.97"),
	]


def test_docnames_scope_derived_rows_to_touched_items(price_module):
	db, mod = price_module

	add_item(db, "ITEM-A")
	add_barcode(db, "ITEM-A", "1000000000001", "Nos")
	add_barcode(db, "ITEM-A", "2000000000001", "Pack")
	add_conversion(db, "ITEM-A", "Pack", 6)
	price_a = add_price(db, "ITEM-A", "Nos", 2.0)

	add_item(db, "ITEM-B")
	add_barcode(db, "ITEM-B", "1000000000002", "Nos")
	add_barcode(db, "ITEM-B", "2000000000002", "Pack")
	add_conversion(db, "ITEM-B", "Pack", 4)
	price_b = add_price(db, "ITEM-B", "Nos", 3.0)
	expired_pack_b = add_price(db, "ITEM-B", "Pack", 12.5, valid_upto="2020-01-01")

	assert exported_rows(mod.good_prices_internal(0, None, docnames=[expired_pack_b])) == [
		("2000000000002", "0", "12.0"),
	]
	assert exported_rows(mod.good_prices_internal(0, None, docnames=[price_a])) == [
		("1000000000001", "0", "2.0"),
		("2000000000001", "0", "12.0"),
	]
	assert exported_rows(mod.good_prices_internal(0, None, docnames=[price_b])) == [
		("1000000000002", "0", "3.0"),
		("2000000000002", "0", "12.0"),
	]
	assert exported_rows(mod.good_prices_internal(1, None)) == [
		("1000000000001", "0", "2.0"),
		("1000000000002", "0", "3.0"),
		("2000000000001", "0", "12.0"),
		("2000000000002", "0", "12.0"),
	]


def test_incremental_window_and_validity_filters(price_module):
	db, mod = price_module
	for item, barcode in (
		("ITEM-OLD", "1100000000001"),
		("ITEM-NEW", "1100000000002"),
		("ITEM-EXPIRED", "1100000000003"),
	):
		add_item(db, item)
		add_barcode(db, item, barcode, "Nos")

	# Prices apply to the item + UOM, so each item needs its own barcode to isolate the filter.
	add_price(db, "ITEM-OLD", "Nos", 1.0, name="OLD", modified="2025-12-31 00:00:00")
	add_price(db, "ITEM-NEW", "Nos", 2.0, name="NEW", modified="2026-01-02 00:00:00")
	add_price(
		db,
		"ITEM-EXPIRED",
		"Nos",
		0.5,
		name="EXPIRED",
		modified="2026-01-02 00:00:00",
		valid_upto="2020-01-01",
	)

	root = mod.good_prices_internal(0, "2026-01-01")

	assert exported_rows(root) == [("1100000000002", "0", "2.0")]
	for price in root.findall("GoodsPrices"):
		assert price.find("DateFrom") is None
		assert price.find("DateTo") is None


def test_good_prices_uses_configured_shop_no(fake_frappe, monkeypatch):
	mod = import_good_prices_module(fake_frappe, shop_no="02")

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "02"


@pytest.mark.parametrize("shop_no", [None, ""])
def test_good_prices_falls_back_to_01_when_shop_no_empty(fake_frappe, monkeypatch, shop_no):
	mod = import_good_prices_module(fake_frappe, shop_no=shop_no)

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "1"


def import_good_prices_module(fake_frappe, price_list=None, shop_no="1"):
	sys.modules.pop("raso_sync.api.good_prices", None)

	fake_frappe.get_single = lambda doctype: SimpleNamespace(price_list=price_list, shop_no=shop_no)
	fake_frappe.db = SimpleNamespace(
		sql=lambda *args, **kwargs: [
			{
				"barcode": "1234567890123",
				"price_list_rate": 1.5,
				"packing_unit": 1,
				"modified": None,
			}
		]
	)

	return importlib.import_module("raso_sync.api.good_prices")
