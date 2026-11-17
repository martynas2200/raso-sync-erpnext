from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_prices_internal(full_sync, date_from, docnames=None):
	"""
	Returns XML document directly of GoodsPrices (Item Prices) - DataType 4
	ERPNext is the authority for which price applies right now, so rows are always
	sent undated and only prices valid on the current date are exported.

	Parameters:
	- full_sync: 1 for full sync, 0 for incremental
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

	if docnames:
		where_conditions.append("ip.name IN %(docnames)s")
		params["docnames"] = tuple(docnames)

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

		#! Do NOT emit DateFrom/DateTo here.
		# RASO routes each DataType to exactly one import procedure, so dated rows in a DataType 4 packet are silently dropped.
		# DataType 7 prices identify a row by goods + shop + qty + DateFrom + DateTo, so changing a validity window inserts a new row and leaves the old one enabled, where overlapping windows resolve to the cheapest price.
		# ERPNext is the authority instead: it decides which price applies today and that single undated row is what we send.

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
