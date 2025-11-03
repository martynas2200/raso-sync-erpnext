from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def goods_internal(full_sync, date_from):
	"""
	Goods (Items) sync endpoint - DataType 3

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- recentModified: Required when FullSync=0, ISO datetime string

	Returns XML document directly
	"""
	filters = {}
	if full_sync == 0 and date_from:
		modified_date = datetime.fromisoformat(date_from)
		filters["modified"] = (">", modified_date)

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"item_group",
			"stock_uom",
			"description",
			"disabled",
			"modified",
			"deposit_package_count",
		],
		limit_page_length=200,
	)

	root = Element("GoodsSync")
	root.set("FullSync", str(full_sync))

	for item in items:
		if not item.get("item_code") and not item.get("name"):
			continue
		# barcode is mandatory
		barcode = frappe.db.get_value("Item Barcode", {"parent": item.get("name")}, "barcode")
		if not barcode:
			continue

		# check if the item has an Item Price, if not, skip it
		price_exists = frappe.db.exists("Item Price", {"item_code": item.get("item_code"), "selling": 1})
		if not price_exists:
			continue

		if item.get("disabled") and full_sync == 1:
			continue

		goods_elem = SubElement(root, "Goods")

		code_elem = SubElement(goods_elem, "Code")
		code_elem.text = barcode

		vcode_elem = SubElement(goods_elem, "VCode")
		vcode_elem.text = item.get("item_code", barcode)

		name_elem = SubElement(goods_elem, "Name")
		# requires truncation to 80 characters for RASO compatibility
		item_name = item.get("item_name", "") or item.get("item_code", "")
		if len(item_name) > 80:
			item_name = item_name[:80]
		name_elem.text = item_name

		vat_code_elem = SubElement(goods_elem, "VatCode")
		vat_code_elem.text = "3" if barcode == 1100 else "1"
		# TODO: Implement proper field or use tax templates to select VAT code
		# 1 stand for A (21%) in the fiscal module, and so on.
		# So far only, a single item which is 0% VAT

		unit_elem = SubElement(goods_elem, "Unit")
		unit_elem.text = item.get("stock_uom", "")

		extra_info_elem = SubElement(goods_elem, "ExtraInfo")
		refundable_elem = SubElement(goods_elem, "Refundable")

		item_group = item.get("item_group")
		if item_group:
			# Fetch item group information
			item_group_info = frappe.db.sql(
				"""
            SELECT CRC32(ig.name) AS crc32, ig.pos_department_no AS dep_no, ig.is_refundable AS is_refundable
            FROM `tabItem Group` ig WHERE ig.name = %s
            """,
				(item_group,),
				as_dict=True,
			)

			if item_group_info:
				item_group_info = item_group_info[0]
				extra_info_elem.text = str(item_group_info.get("crc32", ""))
				refundable_elem.text = "1" if item_group_info.get("is_refundable") else "0"
				if item_group_info.get("dep_no") and item_group_info.get("dep_no") != 0:
					dep_no_elem = SubElement(goods_elem, "DepNo")
					dep_no_elem.text = str(item_group_info.get("dep_no", 1))
			else:
				extra_info_elem.text = ""
				refundable_elem.text = "0"
		else:
			extra_info_elem.text = ""
			refundable_elem.text = "0"

		if item.get("deposit_package_count") and item.get("deposit_package_count") > 0:
			extra_qty_elem = SubElement(goods_elem, "ExtraQty")
			extra_qty_elem.text = str(item.get("deposit_package_count", 1))  # + ".000000"
			extra_code_elem = SubElement(goods_elem, "ExtraCode")
			extra_code_elem.text = "1100"  # 1100 is the barcode for deposit packages

		if item.get("description"):
			text_elem = SubElement(goods_elem, "Text")
			text_elem.text = item.get("description", "")

		comment_required_elem = SubElement(goods_elem, "CommentRequired")
		comment_required_elem.text = "0"

		is_weighing_elem = SubElement(goods_elem, "IsWeighing")
		is_weighing_elem.text = "1" if item.get("stock_uom") == "Kg" or item.get("stock_uom") == "kg" else "0"

		enabled_elem = SubElement(goods_elem, "Enabled")
		enabled_elem.text = "0" if item.get("disabled") else "1"

		change_price_elem = SubElement(goods_elem, "ChangePriceManually")
		change_price_elem.text = "0"

		edit_date_elem = SubElement(goods_elem, "EditDate")
		if item.get("modified"):
			modified_dt = item.get("modified")
			if isinstance(modified_dt, str):
				modified_dt = datetime.fromisoformat(modified_dt)
			edit_date_elem.text = modified_dt.strftime("%Y-%m-%dT%H:%M:%S")
		else:
			edit_date_elem.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

	return root
