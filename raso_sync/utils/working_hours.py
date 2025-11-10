"""Working Hours Utilities"""

import frappe
from frappe.utils import get_datetime, nowtime

from raso_sync.raso_sync.doctype.raso_sync_settings.raso_sync_settings import RASOSyncSettings


def is_within_working_hours():
	"""
	Check if the current time is within the working hours defined in RASO Sync Settings.

	Returns:
	    bool: True if within working hours or if working hours are not set, False otherwise.
	"""
	settings = RASOSyncSettings.get_settings()

	# If no working hours are set, always consider it as within working hours
	if not settings.working_hours_from and not settings.working_hours_to:
		return True

	# If only one is set, it's ambiguous, so we treat it as no restriction
	if not settings.working_hours_from or not settings.working_hours_to:
		return True

	try:
		start_time = get_datetime(settings.working_hours_from).time()
		end_time = get_datetime(settings.working_hours_to).time()
		current_time = get_datetime(nowtime()).time()

		if start_time <= end_time:
			# Normal case: 09:00 to 17:00
			return start_time <= current_time <= end_time
		else:
			# Overnight case: 22:00 to 06:00
			return current_time >= start_time or current_time <= end_time

	except Exception as e:
		frappe.log_error(f"Error checking working hours: {e!s}")
		return True  # Do not block the task in case of error
