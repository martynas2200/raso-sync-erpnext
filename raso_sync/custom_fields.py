import frappe


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
		"label": meta.get("label", fieldname.replace("_", " ").title()),
		"fieldtype": meta.get("fieldtype", "Data"),
	}

	# optional fields
	for key in ("insert_after", "read_only", "translatable", "default", "description"):
		if key in meta:
			doc[key] = meta[key]

	cf = frappe.get_doc(doc)
	cf.insert(ignore_permissions=True)
	# commit to persist immediately (keeps original behaviour)
	frappe.db.commit()
	return True


def create_custom_fields():
	"""Create custom fields for RASO integration and POS-related Item/Item Group fields."""
	definitions = {
		"Sales Invoice": [
			{  # NOTE: Might be unnecessary
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
				"fieldname": "pos_department_no",
				"label": "POS Department No",
				"fieldtype": "Int",
				"insert_after": "is_group",
				"description": "Department number for POS categorization",
				"default": 0,
			},
			{
				"fieldname": "is_refundable",
				"label": "Is Refundable",
				"fieldtype": "Check",
				"insert_after": "pos_department_no",
				"description": "Indicates if items in this group are refundable",
				"default": 0,
			},
			{
				"fieldname": "is_visible_in_catalog",
				"label": "Is Visible in Catalog",
				"fieldtype": "Check",
				"insert_after": "is_refundable",
				"description": "Indicates if items in this group are visible in the POS catalog",
				"default": 1,
			},
		],
	}

	created = []
	for dt, fields in definitions.items():
		for f in fields:
			if _create_custom_field(dt, f):
				created.append((dt, f.get("fieldname")))

	for dt, fname in created:
		print(f"Created custom field: {dt} - {fname}")
