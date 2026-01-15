from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_prices_internal(full_sync, date_from):
	"""
	Returns XML document directly of GoodsPrices (Item Prices) - DataType 4

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string

	"""
	settings = frappe.get_single("RASO Sync Settings")
	today = datetime.now().date()

	where_conditions = [
		"ip.selling = 1",
		"(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)",
		"(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)",
	]
	params = {"today": today}

	if full_sync == 0 and date_from:
		where_conditions.append("ip.modified >= %(modified)s")
		params["modified"] = datetime.fromisoformat(date_from)

	if settings.price_list:
		where_conditions.append("ip.price_list = %(price_list)s")
		params["price_list"] = settings.price_list

	where_clause = " AND ".join(where_conditions)

	# NOTE: Subquery is needed in case of multiple valid prices per item/barcode to get the latest one
	item_prices = frappe.db.sql(
		f"""
		SELECT
			price_list_rate,
			item_code,
			packing_unit,
			modified,
			valid_from,
			valid_upto,
			barcode
		FROM (
			SELECT
				ip.price_list_rate,
				ip.item_code,
				ip.packing_unit,
				ip.modified,
				ip.valid_from,
				ip.valid_upto,
			    ib.barcode,
				ROW_NUMBER() OVER (PARTITION BY ib.barcode ORDER BY ip.valid_from DESC, ip.modified DESC) as rn
			FROM `tabItem Price` ip
			INNER JOIN `tabItem Barcode` ib ON ip.item_code = ib.parent AND ip.uom = ib.uom
			WHERE {where_clause} AND ib.barcode IS NOT NULL
		) ranked
		WHERE rn = 1
	""",
		params,
		as_dict=True,
	)

	root = Element("GoodsPricesSync")
	root.set("FullSync", str(full_sync))

	for item_price in item_prices:
		price_elem = SubElement(root, "GoodsPrices")

		goods_code_elem = SubElement(price_elem, "GoodsCode")
		goods_code_elem.text = item_price.get("barcode", "")

		shop_no_elem = SubElement(price_elem, "ShopNo")
		shop_no_elem.text = "01"

		#! Needs to be tested if raso can accept multiple prices, so in that case,
		#! we would not need a send the list each night, no subquery needed then.
		# if item_price.get("valid_from"):
		#     date_from_elem = SubElement(price_elem, "DateFrom")
		#     valid_from_dt = item_price.get("valid_from")
		#     if isinstance(valid_from_dt, str):
		#         valid_from_dt = datetime.fromisoformat(valid_from_dt)
		#     date_from_elem.text = valid_from_dt.strftime("%Y-%m-%dT%H:%M:%S")

		# if item_price.get("valid_upto"):
		#     date_to_elem = SubElement(price_elem, "DateTo")
		#     valid_upto_dt = item_price.get("valid_upto")
		#     if isinstance(valid_upto_dt, str):
		#         valid_upto_dt = datetime.fromisoformat(valid_upto_dt)
		#     date_to_elem.text = valid_upto_dt.strftime("%Y-%m-%dT%H:%M:%S")

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
