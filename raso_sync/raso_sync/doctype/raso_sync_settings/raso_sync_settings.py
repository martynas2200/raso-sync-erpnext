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
		self.update_fetch_scheduler()
		self.update_send_hooks()
		self.update_send_scheduler()

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

	def update_fetch_scheduler(self):
		"""
		Create or update the scheduler for fetching sales from RASO.
		If fetch_sales_interval_minutes is 0, disables the scheduler.
		"""
		job_name = "raso_sync_fetch_sales"
		method = "raso_sync.tasks.fetch.execute_fetch_task"

		if self.fetch_sales_interval_minutes and self.fetch_sales_interval_minutes > 0:
			result = create_or_update_scheduled_job(
				job_name=job_name,
				method=method,
				interval=self.fetch_sales_interval_minutes,
				description="Fetch sales documents from RASO to ERPNext",
				enabled=True,
			)
			frappe.logger().info(f"Fetch scheduler {result['status']}: {self.fetch_sales_interval_minutes}")
		else:
			if disable_scheduled_job(job_name):
				frappe.logger().info("Disabled fetch scheduler")

	def update_send_hooks(self):
		"""
		Setup or remove document event hooks on Item, Item Price, Item Group, and Customer.
		If enqueue_sending_delay_minutes is 0, disables the hooks on these doctypes.
		Otherwise, enables the hooks to trigger sending to RASO.
		"""

		doctypes_to_hook = ["Item", "Item Price", "Item Group", "Customer"]

		if self.enqueue_sending_delay_minutes and self.enqueue_sending_delay_minutes > 0:
			for doctype in doctypes_to_hook:
				# Use debounced marking handler; actual enqueue will be scheduled
				send_method = "raso_sync.tasks.send.execute_send_task_on_doc_event"
				self.setup_doc_event_hook(doctype, send_method)
			# frappe.logger().info(f"Send hooks enabled with delay: {self.enqueue_sending_delay_minutes} minutes")
		else:
			# Disable hooks
			for doctype in doctypes_to_hook:
				self.remove_doc_event_hook(doctype)
			frappe.logger().info("Send hooks disabled")

	def update_send_scheduler(self):
		"""
		Create or update the scheduler that processes debounced send events.
		Runs every 5 minutes when enqueue_sending_delay_minutes > 0.
		"""
		job_name = "raso_sync_send_debounced"
		method = "raso_sync.tasks.send.process_debounced_sends"

		if self.enqueue_sending_delay_minutes and self.enqueue_sending_delay_minutes > 0:
			result = create_or_update_scheduled_job(
				job_name=job_name,
				method=method,
				interval=5
				if self.enqueue_sending_delay_minutes <= 5
				else 5 + int(self.enqueue_sending_delay_minutes * 0.3),
				# NOTE: The formula above is a random one, need to think on it.
				description="Process debounced send events for RASO export",
				enabled=True,
			)
			frappe.logger().info(
				f"Send scheduler {result['status']}: every 5 minutes (debounce delay {self.enqueue_sending_delay_minutes}m)"
			)
		else:
			if disable_scheduled_job(job_name):
				frappe.logger().info("Disabled send scheduler")

	def setup_doc_event_hook(self, doctype, method):
		"""
		Setup document event hooks for after_insert, after_update, and after_delete events.

		Args:
		    doctype (str): DocType name
		    method (str): Method path to call on the events
		"""
		events = ["after_insert", "after_update", "after_delete"]
		for event in events:
			hook_name = f"raso_sync_{doctype.lower().replace(' ', '_')}_{event}"
			if not frappe.db.exists("Document Event Hook", hook_name):
				hook = frappe.new_doc("Document Event Hook")
				hook.update(
					{"name": hook_name, "doctype": doctype, "event": event, "method": method, "enabled": 1}
				)
				hook.insert(ignore_permissions=True)

	def remove_doc_event_hook(self, doctype):
		"""
		Remove document event hooks for a doctype.

		Args:
		    doctype (str): DocType name
		"""
		events = ["after_insert", "after_update", "after_delete"]
		for event in events:
			hook_name = f"raso_sync_{doctype.lower().replace(' ', '_')}_{event}"
			if frappe.db.exists("Document Event Hook", hook_name):
				frappe.delete_doc("Document Event Hook", hook_name, ignore_permissions=True)
