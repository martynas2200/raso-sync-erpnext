"""
Scheduler Management Utilities for RASO Sync
Provides helper functions to manage dynamic scheduler jobs based on settings.
"""

import frappe
from frappe import _


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

		if minutes == 0:
			return f"0 */{hours} * * *"
		else:
			# Approximate: run every N hours at a specific minute
			# NOTE: not perfect here.
			return f"{minutes} */{hours} * * *"


def create_or_update_scheduled_job(job_name, method, interval, description, enabled=True):
	"""
	Create or update a Scheduled Job Type with the given parameters.

	Args:
	    job_name (str): Unique identifier for the job
	    method (str): Python method path to execute (e.g., "raso_sync.tasks.fetch.execute_fetch_task")
	    interval (str): Interval in minutes for the cron schedule
	    description (str): Human-readable description of the job
	    enabled (bool): Whether the job should be active

	Returns:
	    dict: Information about the created/updated job
	"""
	try:
		# Use the provided interval as the cron format
		if interval > 1:
			cron_format = cron_format_every_n_minutes(int(interval))

		# Check if job exists
		if frappe.db.exists("Scheduled Job Type", job_name):
			# Update existing job
			job = frappe.get_doc("Scheduled Job Type", job_name)
			job.cron_format = cron_format
			job.stopped = 0 if enabled else 1
			job.save(ignore_permissions=True)

			return {"status": "updated", "job_name": job_name, "enabled": enabled, "cron_format": cron_format}
		else:
			# Create new job
			# First ensure Scheduler Event exists
			scheduler_event_name = ensure_scheduler_event(method, description)

			# Create Scheduled Job Type
			job = frappe.new_doc("Scheduled Job Type")
			job.update(
				{
					"name": job_name,
					"method": method,
					"frequency": "Cron",
					"scheduler_event": scheduler_event_name,
					"cron_format": cron_format,
					"stopped": 0 if enabled else 1,
				}
			)
			job.insert(ignore_permissions=True)

			return {"status": "created", "job_name": job_name, "enabled": enabled, "cron_format": cron_format}

	except Exception as e:
		frappe.log_error(f"Error creating/updating scheduled job: {e}", "Scheduler Manager")
		raise


def ensure_scheduler_event(method, description=""):
	"""
	Ensure a Scheduler Event exists for the given method.

	Args:
	    method (str): Python method path
	    description (str): Description for the event

	Returns:
	    str: Name of the Scheduler Event
	"""
	# Use method path as the event name
	event_name = method

	if not frappe.db.exists("Scheduler Event", event_name):
		event = frappe.new_doc("Scheduler Event")
		event.update(
			{
				"name": event_name,
				"scheduled_against": method,
			}
		)
		event.insert(ignore_permissions=True)

	return event_name


def disable_scheduled_job(job_name):
	"""
	Disable a scheduled job by setting stopped = 1.

	Args:
	    job_name (str): Name of the job to disable

	Returns:
	    bool: True if disabled, False if job doesn't exist
	"""
	if frappe.db.exists("Scheduled Job Type", job_name):
		job = frappe.get_doc("Scheduled Job Type", job_name)
		job.stopped = 1
		job.save(ignore_permissions=True)
		return True
	return False


def enable_scheduled_job(job_name):
	"""
	Enable a scheduled job by setting stopped = 0.

	Args:
	    job_name (str): Name of the job to enable

	Returns:
	    bool: True if enabled, False if job doesn't exist
	"""
	if frappe.db.exists("Scheduled Job Type", job_name):
		job = frappe.get_doc("Scheduled Job Type", job_name)
		job.stopped = 0
		job.save(ignore_permissions=True)
		return True
	return False


def delete_scheduled_job(job_name):
	"""
	Delete a scheduled job completely.

	Args:
	    job_name (str): Name of the job to delete

	Returns:
	    bool: True if deleted, False if job doesn't exist
	"""
	if frappe.db.exists("Scheduled Job Type", job_name):
		frappe.delete_doc("Scheduled Job Type", job_name, ignore_permissions=True)
		return True
	return False


def get_job_status(job_name):
	"""
	Get the current status of a scheduled job.

	Args:
	    job_name (str): Name of the job

	Returns:
	    dict: Job status information or None if job doesn't exist
	"""
	if frappe.db.exists("Scheduled Job Type", job_name):
		job = frappe.get_doc("Scheduled Job Type", job_name)
		return {
			"name": job.name,
			"method": job.method,
			"frequency": job.frequency,
			"cron_format": job.cron_format,
			"enabled": not job.stopped,
			"last_execution": job.last_execution,
			"next_execution": job.next_execution,
		}
	return None
