from datetime import datetime
from xml.etree.ElementTree import Element, SubElement

import frappe


def partners_internal(full_sync, date_from, docnames=None):
	"""
	Returns XML document of Partners (Clients) - DataType 1

	Parameters:
	- FullSync: 1 for full sync, 0 for incremental
	- date_from: Required when FullSync=0, ISO datetime string
	"""
	filters = {"disabled": 0}  # Only enabled customers

	if full_sync == 0 and date_from:
		modified_date = datetime.fromisoformat(date_from)
		filters["modified"] = (">", modified_date)

	if docnames:
		filters["name"] = ("in", docnames)

	# Fetch customers
	try:
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
	except Exception:
		customers = []

	root = Element("PartnersSync")
	root.set("FullSync", str(full_sync))

	for customer in customers:
		# Code here is used as unique identifier, skip if missing
		if not customer.get("customer_name") or customer.get("business_code") is None:
			continue

		partner_elem = SubElement(root, "Partners")

		code_elem = SubElement(partner_elem, "Code")
		code_elem.text = customer.get("business_code", "")

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
