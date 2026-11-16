from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


def import_good_prices_module(fake_frappe, shop_no):
	sys.modules.pop("raso_sync.api.good_prices", None)

	fake_frappe.get_single = lambda doctype: SimpleNamespace(price_list=None, shop_no=shop_no)
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


def test_good_prices_uses_configured_shop_no(fake_frappe, monkeypatch):
	mod = import_good_prices_module(fake_frappe, shop_no="02")

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "02"


@pytest.mark.parametrize("shop_no", [None, ""])
def test_good_prices_falls_back_to_01_when_shop_no_empty(fake_frappe, monkeypatch, shop_no):
	mod = import_good_prices_module(fake_frappe, shop_no=shop_no)

	root = mod.good_prices_internal(full_sync=1, date_from=None)

	assert root.findtext("GoodsPrices/ShopNo") == "1"
