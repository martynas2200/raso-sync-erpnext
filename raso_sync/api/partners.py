from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def partners_internal(full_sync, recent_modified):
	"""
	Partners (Clients) sync endpoint - DataType 1

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- recentModified: Required when FullSync=0, ISO datetime string

	Returns XML document directly
	"""
	filters = {"disabled": 0}  # Only enabled customers

	if full_sync == 0 and recent_modified:
		modified_date = datetime.fromisoformat(recent_modified)
		filters["modified"] = (">", modified_date)

	# Fetch customers
	customers = frappe.get_all(
		"Customer",
		filters=filters,
		fields=[
			"business_code",
			"customer_name",
			"tax_id",
			"customer_primary_address",
			"disabled",
			"modified",
		],
	)
	root = Element("PartnersSync")
	root.set("FullSync", str(full_sync))

	for customer in customers:
		if not customer.get("customer_name") or customer.get("business_code") is None:
			continue  # Code here is used as unique identifier, skip if missing

		partner_elem = SubElement(root, "Partners")

		code_elem = SubElement(partner_elem, "Code")
		code_elem.text = customer.get("business_code", "")  # Using custom field 'business_code' as Code

		name_elem = SubElement(partner_elem, "Name")
		name_elem.text = customer.get("customer_name", "")

		vat_elem = SubElement(partner_elem, "VATCode")
		vat_elem.text = customer.get("tax_id", "")

		address_text = ""
		if customer.get("customer_primary_address"):
			try:
				address_doc = frappe.get_doc("Address", customer.get("customer_primary_address"))
				address_parts = []
				if address_doc.address_line1:
					address_parts.append(address_doc.address_line1)
				if address_doc.address_line2:
					address_parts.append(address_doc.address_line2)
				if address_doc.city:
					address_parts.append(address_doc.city)
				if address_doc.country:
					address_parts.append(address_doc.country)
				address_text = ", ".join(address_parts)
			except Exception:
				address_text = ""

		address_elem = SubElement(partner_elem, "Address")
		address_elem.text = address_text

		enabled_elem = SubElement(partner_elem, "Enabled")
		enabled_elem.text = "0" if customer.get("disabled") else "1"

	return root
