import frappe
from frappe import _
from frappe.model.document import Document

from raso_sync.utils.scheduler_manager import create_or_update_scheduled_job, disable_scheduled_job


class RASOSyncSettings(Document):
	def validate(self):
		"""
		Validate settings before saving
		"""
		# Validate fetch_sales_interval_minutes
		if self.fetch_sales_interval_minutes is not None:
			interval = self.fetch_sales_interval_minutes
			if interval != 0 and (interval < 10 or interval > 1440):
				frappe.throw(
					_("Fetch Sales Interval must be either 0 (disabled) or between 10 and 1440 minutes")
				)

	def on_update(self):
		"""
		Update scheduler jobs when settings are saved
		"""
		self.update_scheduler(
			interval_field="fetch_sales_interval_minutes",
			method="raso_sync.tasks.fetch.execute_fetch_task",
			description="Fetch sales documents from RASO to ERPNext",
			name="fetch",
		)
		self.update_scheduler(
			interval_field="send_check_interval_minutes",
			method="raso_sync.tasks.send.process_debounced_sends",
			description="Process debounced send events for RASO export",
			name="send",
		)
		self.update_scheduler(
			interval_field="",
			cron_field="full_sync_time",
			method="raso_sync.tasks.full_sync.execute_full_sync_task",
			description="Execute full sync from RASO to ERPNext",
			name="full_sync",
		)

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
	def get_payment_method_mapping(payment_code: str):
		"""
		Get the Frappe payment method for a RASO payment code
		"""
		settings = RASOSyncSettings.get_settings()

		# Check if there's a custom mapping
		for mapping in settings.payment_mappings:
			if mapping.raso_payment_code == payment_code:
				return mapping

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
				return {"frappe_payment_method": default_payment_method}
			else:
				frappe.log_error(
					"Fallback failed - missing Payment Method",
					f"Payment Method '{default_payment_method}' for RASO code '{payment_code}' is missing. Using first available payment method.",
				)
				return {"frappe_payment_method": frappe_payment_methods[0]}
		return None

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

	def update_scheduler(
		self, interval_field: str, method: str, description: str, name: str, cron_field: str | None
	):
		"""
		Create or update a scheduler job.
		If the interval is 0 or None, disables the scheduler.

		Args:
			interval_field: Name of the field containing the interval in minutes
			method: The method to be called by the scheduler
			description: Description of the scheduler job
			name: Human-readable name for logging purposes
		"""
		interval = getattr(self, interval_field, None)

		if interval and interval > 0:
			result = create_or_update_scheduled_job(
				method=method,
				interval=interval,
				description=description,
				enabled=True,
				cron_format=getattr(self, cron_field, None),
			)
			frappe.logger().info(f"{name.capitalize()} scheduler {result['status']}: {interval} minutes")
		else:
			if disable_scheduled_job(method):
				frappe.logger().info(f"Disabled {name} scheduler")
