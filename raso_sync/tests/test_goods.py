from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


class FakeSettings:
	def __init__(self, price_list=None, deposit_package_item=None):
		self.price_list = price_list
		self.deposit_package_item = deposit_package_item
		self.item_tax_template_mappings = []

	def get(self, key, default=None):
		return getattr(self, key, default)


def import_goods_module(fake_frappe, price_list="Retail", deposit_package_item=None):
	sys.modules.pop("raso_sync.api.goods", None)
	mod = importlib.import_module("raso_sync.api.goods")
	fake_frappe.get_single = lambda doctype: FakeSettings(
		price_list=price_list, deposit_package_item=deposit_package_item
	)
	return mod


def goods_row(**overrides):
	row = {
		"name": "ITEM-1",
		"item_code": "ITEM-1",
		"item_name": "Item 1",
		"stock_uom": "Nos",
		"description": None,
		"disabled": 0,
		"modified": "2026-01-01 10:00:00",
		"deposit_package_count": 0,
		"barcode": "PACK-BARCODE",
		"uom": "Pack",
		"pos_department_no": 0,
		"is_refundable": 0,
		"raso_id": 1,
		"item_tax_templates": None,
	}
	row.update(overrides)
	return row


def package_row(**overrides):
	row = {
		"item_code": "ITEM-1",
		"uom": "Pack",
		"conversion_factor": 6,
		"base_barcode": "BASE-BARCODE",
		"has_active_price": 0,
	}
	row.update(overrides)
	return row


def install_db(fake_frappe, goods_rows, package_rows, deposit_barcode=None):
	calls = {}

	def fake_sql(query, params=None, **kwargs):
		if "tabUOM Conversion Detail" in query:
			calls["package"] = params
			return package_rows
		calls["goods"] = params
		return goods_rows

	fake_frappe.db = SimpleNamespace(sql=fake_sql, get_value=lambda *args, **kwargs: deposit_barcode)
	return calls


def test_package_barcode_gets_base_barcode_and_content_qty(fake_frappe):
	mod = import_goods_module(fake_frappe)
	calls = install_db(fake_frappe, [goods_row()], [package_row()])

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.findtext("Unit") == "Pack"
	assert goods.findtext("PackageContentBarcode") == "BASE-BARCODE"
	assert goods.findtext("PackageContentQty") == "6"
	assert calls["package"]["price_list"] == "Retail"


def test_package_content_omitted_when_active_price_exists(fake_frappe):
	"""A custom package price must win over multiplication from the base goods."""
	mod = import_goods_module(fake_frappe)
	install_db(fake_frappe, [goods_row()], [package_row(has_active_price=1)])

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.find("PackageContentBarcode") is None
	assert goods.find("PackageContentQty") is None


def test_package_content_omitted_without_base_barcode(fake_frappe):
	mod = import_goods_module(fake_frappe)
	install_db(fake_frappe, [goods_row()], [package_row(base_barcode=None)])

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.find("PackageContentBarcode") is None
	assert goods.find("PackageContentQty") is None


def test_package_content_omitted_for_conversion_factor_of_one(fake_frappe):
	mod = import_goods_module(fake_frappe)
	install_db(fake_frappe, [goods_row()], [package_row(conversion_factor=1)])

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.find("PackageContentBarcode") is None
	assert goods.find("PackageContentQty") is None


def test_stock_uom_barcode_is_not_a_package(fake_frappe):
	mod = import_goods_module(fake_frappe)
	calls = install_db(fake_frappe, [goods_row(uom="Nos", barcode="BASE-BARCODE")], [])

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.findtext("Unit") == "Nos"
	assert goods.find("PackageContentBarcode") is None
	assert "package" not in calls


def test_deposit_qty_multiplied_for_package_barcode(fake_frappe):
	"""deposit_package_count is per stock UOM, so a pack holds factor times as many."""
	mod = import_goods_module(fake_frappe, deposit_package_item="DEPOSIT")
	install_db(
		fake_frappe,
		[goods_row(deposit_package_count=2)],
		[package_row()],
		deposit_barcode="DEP-BARCODE",
	)

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.findtext("ExtraQty") == "12"
	assert goods.findtext("ExtraCode") == "DEP-BARCODE"


def test_deposit_qty_unchanged_for_stock_uom_barcode(fake_frappe):
	mod = import_goods_module(fake_frappe, deposit_package_item="DEPOSIT")
	install_db(
		fake_frappe,
		[goods_row(uom="Nos", barcode="BASE-BARCODE", deposit_package_count=2)],
		[],
		deposit_barcode="DEP-BARCODE",
	)

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.findtext("ExtraQty") == "2"


def test_deposit_qty_multiplied_even_when_package_price_exists(fake_frappe):
	mod = import_goods_module(fake_frappe, deposit_package_item="DEPOSIT")
	install_db(
		fake_frappe,
		[goods_row(deposit_package_count=2)],
		[package_row(has_active_price=1)],
		deposit_barcode="DEP-BARCODE",
	)

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.find("PackageContentBarcode") is None
	assert goods.findtext("ExtraQty") == "12"


def test_deposit_qty_not_zeroed_without_conversion(fake_frappe):
	mod = import_goods_module(fake_frappe, deposit_package_item="DEPOSIT")
	install_db(
		fake_frappe,
		[goods_row(deposit_package_count=2)],
		[package_row(conversion_factor=None)],
		deposit_barcode="DEP-BARCODE",
	)

	goods = mod.goods_internal(1, None).find("Goods")

	assert goods.findtext("ExtraQty") == "2"
