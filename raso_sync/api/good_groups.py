from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_groups_internal(full_sync=1, date_from=None):
	"""
	Returns XML document of GoodsGroups - DataType 2 (Item Groups)

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string
	"""
	where_conditions = []
	params = {}
	settings = frappe.get_single("RASO Sync Settings")
	if settings.parent_item_group:
		where_conditions = [
			"(parent.name = %(parent_group)s OR parent.parent_item_group = %(parent_group)s OR grandparent.name = %(parent_group)s)"
		]
		params = {"parent_group": settings.parent_item_group}

	if full_sync == 0 and date_from:
		where_conditions.append("ig.modified >= %(modified)s")
		params["modified"] = datetime.fromisoformat(date_from)

	where_clause = " AND ".join(where_conditions)

	item_groups = frappe.db.sql(
		f"""
        SELECT ig.raso_id AS id, ig.name, ig.item_group_name, ig.is_visible_in_catalog, ig.modified
        FROM `tabItem Group` ig
        LEFT JOIN `tabItem Group` parent ON ig.parent_item_group = parent.name
        LEFT JOIN `tabItem Group` grandparent ON parent.parent_item_group = grandparent.name
        {f"WHERE {where_clause}" if where_clause else ""}
    """,
		params,
		as_dict=1,
	)

	root = Element("GoodsGroupsSync")
	root.set("FullSync", str(full_sync))

	for item_group in item_groups:
		if not item_group.get("id"):
			continue

		group_elem = SubElement(root, "GoodsGroups")

		code_elem = SubElement(group_elem, "Code")
		code_elem.text = item_group.get("id", "")

		name_elem = SubElement(group_elem, "Name")
		name_elem.text = item_group.get("item_group_name", "")

		refundable_elem = SubElement(group_elem, "Refundable")
		refundable_elem.text = "1"

		enabled_elem = SubElement(group_elem, "Enabled")
		enabled_elem.text = "1" if item_group.get("is_visible_in_catalog") else "0"

		edit_date_elem = SubElement(group_elem, "EditDate")
		if item_group.get("modified"):
			modified_dt = item_group.get("modified")
			if isinstance(modified_dt, str):
				modified_dt = datetime.fromisoformat(modified_dt)
			edit_date_elem.text = modified_dt.strftime("%Y-%m-%dT%H:%M:%S")
		else:
			edit_date_elem.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

	return root
