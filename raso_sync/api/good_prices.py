from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_prices_internal(full_sync, date_from):
	"""
	GoodsPrices (Item Prices) sync endpoint - DataType 4

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string

	Returns XML document directly
	"""
	filters = {}
	if full_sync == 0 and date_from:
		modified_date = datetime.fromisoformat(date_from)
		filters["modified"] = (">", modified_date)

	item_prices = frappe.get_all(
		"Item Price",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"price_list",
			"price_list_rate",
			"packing_unit",
			"modified",
			"valid_from",
			"selling",
			"valid_upto",
		],
	)

	root = Element("GoodsPricesSync")
	root.set("FullSync", str(full_sync))

	for item_price in item_prices:
		barcode = frappe.db.get_value("Item Barcode", {"parent": item_price.get("item_code")}, "barcode")
		# TODO: use a single SQL query to join the tables
		price_elem = SubElement(root, "GoodsPrices")

		goods_code_elem = SubElement(price_elem, "GoodsCode")
		goods_code_elem.text = barcode

		shop_no_elem = SubElement(price_elem, "ShopNo")
		shop_no_elem.text = "01"

		# TODO: add DateFrom and DateTo

		qty_elem = SubElement(price_elem, "Qty")
		qty_elem.text = str(item_price.get("packing_unit", 0))

		price_elem_inner = SubElement(price_elem, "Price")
		price_elem_inner.text = str(item_price.get("price_list_rate", 0.0))

		enabled_elem = SubElement(price_elem, "Enabled")
		enabled_elem.text = "1"

		change_price_elem = SubElement(price_elem, "ChangePriceManually")
		change_price_elem.text = "0"

		edit_date_elem = SubElement(price_elem, "EditDate")
		if item_price.get("modified"):
			modified_dt = item_price.get("modified")
			if isinstance(modified_dt, str):
				modified_dt = datetime.fromisoformat(modified_dt)
			edit_date_elem.text = modified_dt.strftime("%Y-%m-%dT%H:%M:%S")
		else:
			edit_date_elem.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

	return root
