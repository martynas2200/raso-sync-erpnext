from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_prices_internal(full_sync, date_from, docnames=None):
	"""
	Returns XML document directly of GoodsPrices (Item Prices) - DataType 4
	ERPNext is the authority for which price applies right now, so rows are always
	sent undated and only prices valid on the current date are exported.

	Barcodes whose price is derived from package content are sent with
	the stock-UOM price multiplied by the conversion factor.
	This is a safety net as RASO checks a barcode's price before
	its package attributes, while the POS recalculates the amount
	from the package content itself.

	Parameters:
	- full_sync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string

	"""
	settings = frappe.get_single("RASO Sync Settings")
	today = datetime.now().date()
	shop_no = settings.shop_no or "1"

	where_conditions = [
		"ip.selling = 1",
		"(ip.valid_from IS NULL OR ip.valid_from <= %(today)s)",
		"(ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)",
	]
	params = {"today": today, "price_list": settings.price_list or None}

	if full_sync == 0 and date_from:
		where_conditions.append("ip.modified >= %(modified)s")
		params["modified"] = datetime.fromisoformat(date_from)

	if docnames:
		where_conditions.append("ip.name IN %(docnames)s")
		params["docnames"] = tuple(docnames)

	if settings.price_list:
		where_conditions.append("ip.price_list = %(price_list)s")

	where_clause = " AND ".join(where_conditions)

	derived_scope = ""
	if docnames:
		derived_scope = """
					AND ib.parent IN (
						SELECT ip2.item_code
						FROM `tabItem Price` ip2
						WHERE ip2.name IN %(docnames)s
					)"""

	# NOTE: The first subquery is needed in case of multiple valid prices per item/barcode to get the latest one.
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
				u.*,
				ROW_NUMBER() OVER (
					PARTITION BY u.barcode
					ORDER BY u.is_derived, u.valid_from DESC, u.modified DESC
				) AS rn
			FROM (
				SELECT
					ip.price_list_rate,
					ip.item_code,
					ip.packing_unit,
					ip.modified,
					ip.valid_from,
					ip.valid_upto,
					ib.barcode,
					0 AS is_derived
				FROM `tabItem Price` ip
				INNER JOIN `tabItem Barcode` ib ON ip.item_code = ib.parent AND ip.uom = ib.uom
				WHERE {where_clause} AND ib.barcode IS NOT NULL

				UNION ALL

				SELECT
					ROUND(
						(
							SELECT ip.price_list_rate
							FROM `tabItem Price` ip
							WHERE ip.item_code = ib.parent
								AND ip.uom = i.stock_uom
								AND ip.selling = 1
								AND (ip.valid_from IS NULL OR ip.valid_from <= %(today)s)
								AND (ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)
								AND (%(price_list)s IS NULL OR ip.price_list = %(price_list)s)
							ORDER BY ip.valid_from DESC, ip.modified DESC
							LIMIT 1
						) * ucd.conversion_factor,
						2
					) AS price_list_rate,
					ib.parent AS item_code,
					0 AS packing_unit,
					NULL AS modified,
					NULL AS valid_from,
					NULL AS valid_upto,
					ib.barcode,
					1 AS is_derived
				FROM `tabItem Barcode` ib
				INNER JOIN `tabItem` i ON i.name = ib.parent
				LEFT JOIN `tabUOM Conversion Detail` ucd
					ON ucd.parent = ib.parent AND ucd.uom = ib.uom
				WHERE ib.barcode IS NOT NULL
					AND ib.barcode != ''
					AND ib.uom IS NOT NULL
					AND ib.uom != ''
					AND ib.uom != i.stock_uom
					AND ucd.conversion_factor > 1{derived_scope}
					AND EXISTS (
						SELECT 1
						FROM `tabItem Barcode` base
						WHERE base.parent = ib.parent
							AND base.uom = i.stock_uom
							AND base.barcode IS NOT NULL
							AND base.barcode != ''
					)
					AND NOT EXISTS (
						SELECT 1
						FROM `tabItem Price` ip
						WHERE ip.item_code = ib.parent
							AND ip.uom = ib.uom
							AND ip.selling = 1
							AND (ip.valid_from IS NULL OR ip.valid_from <= %(today)s)
							AND (ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)
							AND (%(price_list)s IS NULL OR ip.price_list = %(price_list)s)
					)
					AND EXISTS (
						SELECT 1
						FROM `tabItem Price` ip
						WHERE ip.item_code = ib.parent
							AND ip.uom = i.stock_uom
							AND ip.selling = 1
							AND (ip.valid_from IS NULL OR ip.valid_from <= %(today)s)
							AND (ip.valid_upto IS NULL OR ip.valid_upto >= %(today)s)
							AND (%(price_list)s IS NULL OR ip.price_list = %(price_list)s)
					)
			) u
		) ranked
		WHERE rn = 1
	""",
		params,
		as_dict=True,
	)

	root = Element("GoodsPricesSync")
	root.set("FullSync", str(full_sync))

	for item_price in item_prices:
		_append_price_row(
			root,
			shop_no=shop_no,
			barcode=item_price.get("barcode", ""),
			qty=item_price.get("packing_unit", 0),
			price=item_price.get("price_list_rate", 0.0),
			modified=item_price.get("modified"),
		)

	return root


def _append_price_row(root, shop_no, barcode, qty, price, modified=None):
	price_elem = SubElement(root, "GoodsPrices")

	goods_code_elem = SubElement(price_elem, "GoodsCode")
	goods_code_elem.text = barcode

	shop_no_elem = SubElement(price_elem, "ShopNo")
	shop_no_elem.text = shop_no

	#! Do NOT emit DateFrom/DateTo here.
	# RASO routes each DataType to exactly one import procedure, so dated rows in a DataType 4 packet are silently dropped.
	# DataType 7 prices identify a row by goods + shop + qty + DateFrom + DateTo, so changing a validity window inserts a new row and leaves the old one enabled, where overlapping windows resolve to the cheapest price.
	# ERPNext is the authority instead: it decides which price applies today and that single undated row is what we send.

	qty_elem = SubElement(price_elem, "Qty")
	qty_elem.text = str(qty)

	price_elem_inner = SubElement(price_elem, "Price")
	price_elem_inner.text = str(price)

	enabled_elem = SubElement(price_elem, "Enabled")
	enabled_elem.text = "1"

	change_price_elem = SubElement(price_elem, "ChangePriceManually")
	change_price_elem.text = "0"

	edit_date_elem = SubElement(price_elem, "EditDate")
	if modified:
		modified_dt = modified
		if isinstance(modified_dt, str):
			modified_dt = datetime.fromisoformat(modified_dt)
		edit_date_elem.text = modified_dt.strftime("%Y-%m-%dT%H:%M:%S")
	else:
		edit_date_elem.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
