from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def goods_internal(full_sync, date_from):
	"""
	Returns XML document of Goods (Items) - DataType 3

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- recentModified: Required when FullSync=0, ISO datetime string

	"""
	root = Element("GoodsSync")
	root.set("FullSync", str(full_sync))

	date_filter = ""
	if full_sync == 0 and date_from:
		modified_date = datetime.fromisoformat(date_from)
		date_filter = f"AND `tabItem`.`modified` > '{modified_date.strftime('%Y-%m-%d %H:%M:%S')}'"
	# GROUP_CONCAT to get all tax templates assigned to the item in case of multiple assignments.
	sql = f"""
        SELECT
            `tabItem`.`name`,
            `tabItem`.`item_code`,
            `tabItem`.`item_name`,
            `tabItem`.`stock_uom`,
            `tabItem`.`description`,
            `tabItem`.`disabled`,
            `tabItem`.`modified`,
            `tabItem`.`deposit_package_count`,
            `tabItem Barcode`.`barcode`,
            `tabItem Group`.`pos_department_no`,
            `tabItem Group`.`is_refundable`,
            `tabItem Group`.`raso_id`,
            GROUP_CONCAT(DISTINCT `tabItem Tax`.`item_tax_template`) as item_tax_templates
        FROM `tabItem`
        INNER JOIN `tabItem Barcode` ON `tabItem`.`name` = `tabItem Barcode`.`parent`
        LEFT JOIN `tabItem Group` ON `tabItem`.`item_group` = `tabItem Group`.`name`
        LEFT JOIN `tabItem Tax` ON `tabItem`.`name` = `tabItem Tax`.`parent`
        WHERE `tabItem`.`docstatus` != 2
        {date_filter}
        GROUP BY `tabItem Barcode`.`barcode`
    """

	results = frappe.db.sql(sql, as_dict=True)

	settings = frappe.get_single("RASO Sync Settings")
	deposit_package_item = settings.get("deposit_package_item")
	deposit_barcode = None
	if deposit_package_item:
		deposit_barcode = frappe.db.get_value("Item Barcode", {"parent": deposit_package_item}, "barcode")
	tax_template_vat_map = {}
	if settings.get("item_tax_template_mappings"):
		for mapping in settings.get("item_tax_template_mappings"):
			tax_template = mapping.get("item_tax_template")
			vat_code = mapping.get("fiscal_vat_code")
			if tax_template and vat_code:
				# extract just the number from "1 (A)" format
				vat_code_num = vat_code.split()[0]
				tax_template_vat_map[tax_template] = vat_code_num

	for row in results:
		if row.get("disabled") and full_sync == 1:
			continue

		goods_elem = SubElement(root, "Goods")
		goods_elem.set("taxType", row.get("item_tax_template") or "")

		code_elem = SubElement(goods_elem, "Code")
		code_elem.text = row.get("barcode")

		vcode_elem = SubElement(goods_elem, "VCode")  # our internal item code
		vcode_elem.text = row.get("item_code", "")

		name_elem = SubElement(goods_elem, "Name")
		# NOTE: requires truncation to 80 characters for RASO compatibility
		item_name_text = row.get("item_name", "") or row.get("item_code", "")
		if len(item_name_text) > 80:
			item_name_text = item_name_text[:80]
		name_elem.text = item_name_text

		vat_code_elem = SubElement(goods_elem, "VatCode")
		# determine VAT code from tax template mapping or use default
		vat_code = "1"
		item_tax_templates = (row.get("item_tax_templates") or "").split(",")
		for tax_template in item_tax_templates:
			if tax_template in tax_template_vat_map:
				vat_code = tax_template_vat_map[tax_template]
				break

		vat_code_elem.text = vat_code

		unit_elem = SubElement(goods_elem, "Unit")
		unit_elem.text = row.get("stock_uom", "")
		# TODO: check barcode uom first

		extra_info_elem = SubElement(goods_elem, "ExtraInfo")
		refundable_elem = SubElement(goods_elem, "Refundable")

		if row.get("name"):  # item has an item_group
			extra_info_elem.text = str(row.get("raso_id") or "1")
			refundable_elem.text = "1" if row.get("is_refundable") else "0"
			if row.get("pos_department_no") and row.get("pos_department_no") != 0:
				dep_no_elem = SubElement(goods_elem, "DepNo")
				dep_no_elem.text = str(row.get("pos_department_no", 1))
		else:
			extra_info_elem.text = "1"
			refundable_elem.text = "0"

		if row.get("deposit_package_count") and row.get("deposit_package_count") > 0 and deposit_barcode:
			extra_qty_elem = SubElement(goods_elem, "ExtraQty")
			extra_qty_elem.text = str(row.get("deposit_package_count", 1))
			extra_code_elem = SubElement(goods_elem, "ExtraCode")
			extra_code_elem.text = deposit_barcode

		if row.get("description"):
			text_elem = SubElement(goods_elem, "Text")
			text_elem.text = row.get("description", "")

		comment_required_elem = SubElement(goods_elem, "CommentRequired")
		comment_required_elem.text = "0"

		is_weighing_elem = SubElement(goods_elem, "IsWeighing")
		is_weighing_elem.text = (
			"1" if row.get("stock_uom") and "kg" in row.get("stock_uom", "").lower() else "0"
		)

		enabled_elem = SubElement(goods_elem, "Enabled")
		enabled_elem.text = "0" if row.get("disabled") else "1"

		change_price_elem = SubElement(goods_elem, "ChangePriceManually")
		change_price_elem.text = "0"

		edit_date_elem = SubElement(goods_elem, "EditDate")
		if row.get("modified"):
			modified_dt = row.get("modified")
			if isinstance(modified_dt, str):
				modified_dt = datetime.fromisoformat(modified_dt)
			edit_date_elem.text = modified_dt.strftime("%Y-%m-%dT%H:%M:%S")
		else:
			edit_date_elem.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

	return root
