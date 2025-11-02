import frappe
from frappe.model.document import Document


class RASOSyncSettings(Document):
	def validate(self):
		"""
		Validate settings before saving
		"""
		pass

	# TODO: Add validation

	@staticmethod
	def get_settings():
		"""
		Returns the RASO Sync Settings as a dict
		If settings don't exist, creates default settings
		"""
		try:
			settings = frappe.get_doc("RASO Sync Settings")
			return settings
		except frappe.DoesNotExistError:
			settings = frappe.new_doc("RASO Sync Settings")
			settings.insert(ignore_permissions=True)
			return settings

	@staticmethod
	def update_last_sale_import():
		"""
		Update the last sale import timestamp
		"""
		settings = RASOSyncSettings.get_settings()
		settings.last_sale_import = frappe.utils.now_datetime()
		settings.save(ignore_permissions=True)

	@staticmethod
	def update_last_data_export():
		"""
		Update the last data export timestamp
		"""
		settings = RASOSyncSettings.get_settings()
		settings.last_data_export = frappe.utils.now_datetime()
		settings.save(ignore_permissions=True)

	@staticmethod
	def get_payment_method_mapping(payment_code):
		"""
		Get the Frappe payment method for a RASO payment code
		"""
		settings = RASOSyncSettings.get_settings()

		# Check if there's a custom mapping
		for mapping in settings.payment_mappings:
			if mapping.raso_payment_code == payment_code:
				return mapping.frappe_payment_method

		frappe.log_error("Missing payment mapping", f"RASO payment code: {payment_code}")

		# Get default mapping or try to fallback
		default_mappings = {
			"0": "Cash",
			"2": "Credit Card",
		}

		default_payment_method = default_mappings.get(payment_code, "Other")

		# Check if the default mapping even exists in Frappe DB
		frappe_payment_methods = [pm.name for pm in frappe.get_all("Payment Method")]
		if frappe_payment_methods:
			if default_payment_method in frappe_payment_methods:
				return default_payment_method
			else:
				frappe.log_error(
					"Fallback failed - missing Payment Method",
					f"Payment Method '{default_payment_method}' for RASO code '{payment_code}' is missing. Using first available payment method.",
				)
				return frappe_payment_methods[0]
		else:
			frappe.log_error("No payment methods found in the system", "Returning 'Other' as fallback")
			return "Other"

	@staticmethod
	def get_sales_person_from_employee(employee_code):
		"""
		Get the sales person linked to a RASO employee code
		"""
		settings = RASOSyncSettings.get_settings()

		for mapping in settings.employee_mappings:
			if mapping.raso_employee_code == employee_code:
				return mapping.sales_person

		return None
