from __future__ import annotations

import importlib
import sys
from datetime import date
from types import SimpleNamespace

import pytest


def import_good_prices_module(fake_frappe, price_list="Retail"):
	sys.modules.pop("raso_sync.api.good_prices", None)
	mod = importlib.import_module("raso_sync.api.good_prices")

	fake_frappe.get_single = lambda doctype: SimpleNamespace(price_list=price_list)
	return mod


def test_dated_prices_are_exported_undated(fake_frappe):
	"""RASO identifies a price row by goods + shop + qty + DateFrom + DateTo.

	If we ever emitted the validity window, an expired discount would leave its own row
	behind and the replacement price would be inserted next to it instead of updating it.
	"""
	mod = import_good_prices_module(fake_frappe)
	captured = {}

	def fake_sql(query, params=None, **kwargs):
		captured["params"] = params
		return [
			{
				"price_list_rate": 1.5,
				"item_code": "ITEM-1",
				"packing_unit": 0,
				"modified": "2026-11-21 06:23:00",
				"valid_from": "2026-01-01",
				"valid_upto": "2026-11-20",
				"barcode": "4770123456789",
			}
		]

	fake_frappe.db = SimpleNamespace(sql=fake_sql)

	root = mod.good_prices_internal(0, "2000-01-01")

	assert captured["params"]["today"] == date.today()
	assert captured["params"]["modified"].year == 2000

	price_elem = root.find("GoodsPrices")
	assert price_elem is not None
	assert price_elem.findtext("GoodsCode") == "4770123456789"
	assert price_elem.findtext("Price") == "1.5"
	assert price_elem.find("DateFrom") is None
	assert price_elem.find("DateTo") is None
