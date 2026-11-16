from __future__ import annotations

import importlib
import sys
from datetime import date
from types import SimpleNamespace

import pytest


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


def test_good_prices_uses_configured_shop_no(fake_frappe, monkeypatch):
	mod = import_good_prices_module(fake_frappe, shop_no="02")

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "02"


@pytest.mark.parametrize("shop_no", [None, ""])
def test_good_prices_falls_back_to_01_when_shop_no_empty(fake_frappe, monkeypatch, shop_no):
	mod = import_good_prices_module(fake_frappe, shop_no=shop_no)

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "1"
