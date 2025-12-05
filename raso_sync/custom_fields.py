import frappe

definitions = {
	"Customer": [
		{
			"fieldname": "business_code",
			"label": "Business Code",
			"fieldtype": "Data",
			"insert_after": "customer_name",
			"description": "Unique business code for RASO system",
		}
	],
	"Sales Invoice": [
		{
			"fieldname": "raso_receipt_no",
			"label": "Receipt No",
			"fieldtype": "Data",
			"insert_after": "paid_amount",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "raso_import_status",
			"label": "RASO Import Status",
			"fieldtype": "Data",
			"insert_after": "raso_receipt_no",
			"read_only": 1,
			"translatable": 1,
		},
	],
	"Item": [
		{
			"fieldname": "deposit_package_count",
			"label": "Deposit Package Count",
			"fieldtype": "Int",
			"default": 0,
			"insert_after": "weight_per_unit",
			"description": "Number of items in a deposit package, e.g., 6 bottles in a pack",
		}
	],
	"Item Group": [
		{
			"fieldname": "pos_section",
			"label": "POS Section",
			"fieldtype": "Section Break",
			"insert_after": "is_group",
			"collapsible": 0,
			"description": "Section for POS related fields",
		},
		{
			"fieldname": "pos_department_no",
			"label": "POS Department No",
			"fieldtype": "Int",
			"insert_after": "pos_section",
			"description": "Department number for POS categorization",
			"default": 1,
		},
		{
			"fieldname": "is_refundable",
			"label": "Is Refundable",
			"fieldtype": "Check",
			"insert_after": "pos_department_no",
			"description": "Indicates if items in this group are refundable",
			"default": 1,
		},
		{
			"fieldname": "is_visible_in_catalog",
			"label": "Is Visible in Catalog",
			"fieldtype": "Check",
			"insert_after": "is_refundable",
			"description": "Indicates if items in this group are visible in the POS catalog",
			"default": 0,
		},
		{
			"fieldname": "column_break_raso",
			"fieldtype": "Column Break",
			"insert_after": "is_visible_in_catalog",
		},
		{
			"fieldname": "raso_id",
			"label": "RASO ID",
			"fieldtype": "Read Only",
			"insert_after": "column_break_raso",
			"description": "Unique identifier for RASO system",
			"autoincrement": 1,
		},
	],
}


def _custom_field_exists(dt, fieldname):
	"""Check existence of a Custom Field by (dt, fieldname) or by combined name 'dt-fieldname'."""
	if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
		return True
	# older code sometimes stored as "DocType-fieldname"
	return frappe.db.exists("Custom Field", f"{dt}-{fieldname}")


def _create_custom_field(dt, meta):
	"""Create a Custom Field doc from meta dict if it doesn't exist."""
	fieldname = meta.get("fieldname")
	if not fieldname:
		raise ValueError("meta must include 'fieldname'")

	if _custom_field_exists(dt, fieldname):
		return False

	doc = {
		"doctype": "Custom Field",
		"dt": dt,
		"fieldname": fieldname,
		"fieldtype": meta.get("fieldtype", "Data"),
	}
	if doc["fieldtype"] != "Column Break":
		doc["label"] = meta.get("label", fieldname.replace("_", " ").title())
	# optional fields
	for key in (
		"insert_after",
		"read_only",
		"translatable",
		"default",
		"description",
		"unique",
		"autoincrement",
		"collapsible",
	):
		if key in meta:
			doc[key] = meta[key]

	cf = frappe.get_doc(doc)
	cf.insert(ignore_permissions=True)
	frappe.db.commit()
	return True


def create_custom_fields():
	"""Create custom fields for RASO integration and POS-related Item/Item Group fields."""
	raso_id_needs_filling = False
	for dt, fields in definitions.items():
		for f in fields:
			if _create_custom_field(dt, f):
				print(f"Created custom field: {dt} - {f.get('fieldname')}")
				if dt == "Item Group" and f.get("fieldname") == "raso_id":
					raso_id_needs_filling = True
	if raso_id_needs_filling:
		# Fill in raso_id for existing Item Groups
		item_groups = frappe.get_all("Item Group", fields=["name"], order_by="creation asc")
		id = 1
		for ig in item_groups:
			raso_id = str(id)
			frappe.db.set_value("Item Group", ig.name, "raso_id", raso_id)
			id += 1
		frappe.db.commit()
		print(f"Filled RASO ID for {len(item_groups)} Item Groups.")
		# set unique on this field
		cf_name = frappe.db.get_value("Custom Field", {"dt": "Item Group", "fieldname": "raso_id"}, "name")
		if cf_name:
			frappe.db.set_value("Custom Field", cf_name, "unique", 1)
			frappe.db.commit()
			print("Set 'Unique' property on Item Group.raso_id custom field.")


def remove_custom_fields():
	"""Remove custom fields created for RASO integration."""
	for dt, fields in definitions.items():
		for f in fields:
			fieldname = f.get("fieldname")
			cf_name = None
			if _custom_field_exists(dt, fieldname):
				cf_name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
			else:
				# older code sometimes stored as "DocType-fieldname"
				combined_name = f"{dt}-{fieldname}"
				if frappe.db.exists("Custom Field", combined_name):
					cf_name = combined_name
			if cf_name:
				frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
				print(f"Deleted custom field: {dt} - {fieldname}")
	frappe.db.commit()
