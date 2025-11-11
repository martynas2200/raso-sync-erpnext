"""
Scheduler Management Utilities for RASO Sync
Provides helper functions to manage dynamic scheduler jobs based on settings.
"""

import frappe
from frappe import _


def _get_scheduled_job_by_method(method_path: str):
	name = frappe.db.get_value("Scheduled Job Type", {"method": method_path}, "name")
	if name:
		return frappe.get_doc("Scheduled Job Type", name)
	return None


def cron_format_every_n_minutes(n):
	"""
	Generate a cron format string for every n minutes.
	For intervals > 59 minutes, approximates using hour-based scheduling.

	Args:
		n (int): Interval in minutes

	Returns:
		str: Cron format string
	"""
	if n <= 59:
		# Direct minute-based cron
		return f"*/{n} * * * *"
	else:
		hours = n // 60
		minutes = n % 60
		# Approximate: run every N hours
		# NOTE: not perfect here.
		return f"{minutes} */{hours} * * *"


def create_or_update_scheduled_job(method, interval, description, enabled=True, cron_format=None):
	"""
	Create or update a Scheduled Job Type with the given parameters.

	Args:
		method (str): Python method path to execute (e.g., "raso_sync.tasks.fetch.execute_fetch_task")
		interval (str): Interval in minutes for the cron schedule
		description (str): Human-readable description of the job
		enabled (bool): Whether the job should be active

	Returns:
		dict: Information about the created/updated job
	"""

	try:
		# Validate and convert interval, then build cron format
		interval_int = int(interval)
		if cron_format is not None and cron_format.strip() != "":
			cron_format = cron_format.strip()
		elif interval_int <= 0:
			raise ValueError("Interval must be a positive integer (minutes)")
		else:
			cron_format = cron_format_every_n_minutes(interval_int)

		# Check if job exists
		job = _get_scheduled_job_by_method(method)
		if job:
			# Update existing job
			job.cron_format = cron_format
			job.stopped = 0 if enabled else 1
			job.save(ignore_permissions=True)

			return {"status": "updated", "enabled": enabled, "cron_format": cron_format}
		else:
			# Create new Scheduled Job Type
			job = frappe.new_doc("Scheduled Job Type")
			job.update(
				{
					"method": method,
					"frequency": "Cron",
					"cron_format": cron_format,
					"stopped": 0 if enabled else 1,
				}
			)
			job.insert(ignore_permissions=True)

			return {"status": "created", "enabled": enabled, "cron_format": cron_format}

	except Exception as e:
		frappe.log_error(f"Error creating/updating scheduled job: {e}", "Scheduler Manager")
		raise


def disable_scheduled_job(method):
	"""
	Disable a scheduled job by setting stopped = 1.

	Args:
		method (str): Method path of the job to disable

	Returns:
		bool: True if disabled, False if job doesn't exist
	"""
	name = frappe.db.get_value("Scheduled Job Type", {"method": method}, "name")
	if not name:
		return False
	job = frappe.get_doc("Scheduled Job Type", name)
	job.stopped = 1
	job.save(ignore_permissions=True)
	return True


def enable_scheduled_job(method):
	"""
	Enable a scheduled job by setting stopped = 0.

	Args:
		job_name (str): Name of the job to enable

	Returns:
		bool: True if enabled, False if job doesn't exist
	"""
	name = frappe.db.get_value("Scheduled Job Type", {"method": method}, "name")
	if not name:
		return False
	job = frappe.get_doc("Scheduled Job Type", name)
	job.stopped = 0
	job.save(ignore_permissions=True)
	return True


def delete_scheduled_job(method):
	"""
	Delete a scheduled job completely.

	Args:
		job_name (str): Name of the job to delete

	Returns:
		bool: True if deleted, False if job doesn't exist
	"""
	name = frappe.db.get_value("Scheduled Job Type", {"method": method}, "name")
	if not name:
		return False
	frappe.delete_doc("Scheduled Job Type", name, ignore_permissions=True)
	return True


def get_job_status(method):
	"""
	Get the current status of a scheduled job.

	Args:
		method (str): Method path of the job

	Returns:
		dict: Job status information or None if job doesn't exist
	"""
	name = frappe.db.get_value("Scheduled Job Type", {"method": method}, "name")
	if not name:
		return None
	job = frappe.get_doc("Scheduled Job Type", name)
	return {
		"name": job.name,
		"method": job.method,
		"frequency": job.frequency,
		"cron_format": job.cron_format,
		"enabled": not job.stopped,
		"last_execution": job.last_execution,
		"next_execution": job.next_execution,
	}
