from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def good_groups_internal(full_sync=1, date_from=None):
	"""
	GoodsGroups (Item Groups) sync endpoint - DataType 2

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string

	Returns XML Element object
	"""
	filters = {}
	if full_sync == 0 and date_from:
		modified_date = datetime.fromisoformat(date_from)
		filters["modified"] = (">", modified_date)

	# item_groups = frappe.get_all(
	#     "Item Group",
	#     filters=filters,
	#     fields=["name", "item_group_name", "is_visible_in_catalog", "modified"]
	# )

	item_groups = frappe.db.sql(
		"""
        SELECT CRC32(ig.name) AS id, ig.name, ig.item_group_name, ig.is_visible_in_catalog, ig.modified
        FROM `tabItem Group` ig
        LEFT JOIN `tabItem Group` parent ON ig.parent_item_group = parent.name
        WHERE (parent.name = 'Prekės' OR parent.parent_item_group = 'Prekės')
        AND ig.is_visible_in_catalog = 0
        {filters_clause}
    """.format(
			filters_clause="AND ig.modified > '{modified}'".format(
				modified=filters["modified"][1].strftime("%Y-%m-%d %H:%M:%S")
			)
			if "modified" in filters
			else ""
		),
		filters,
		as_dict=1,
	)

	root = Element("GoodsGroupsSync")
	root.set("FullSync", str(full_sync))

	for item_group in item_groups:
		group_elem = SubElement(root, "GoodsGroups")

		code_elem = SubElement(group_elem, "Code")
		code_elem.text = item_group.get("id", "")  # TODO: not ideal, check if hash can be used

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
