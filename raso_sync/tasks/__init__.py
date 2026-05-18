"""
Background Tasks
----------------
1. Fetch Task (fetch.py)
   - Retrieves exported data from RASO
   - Imports to ERPNext
   - Updates status in RASO database
   - ONE-WAY: RASO → ERPNext

2. Send Task (send.py)
   - Exports data from ERPNext
   - Sends to RASO
   - ONE-WAY: ERPNext → RASO
"""

import functools
import logging

import frappe


class MsgprintHandler(logging.Handler):
	"""Custom logging handler that sends log messages as toasts to frontend"""

	def emit(self, record):
		try:
			msg = self.format(record)
			frappe.msgprint(msg, realtime=True, alert=True)
		except Exception:
			self.handleError(record)


def with_msgprint_logging(logger):
	"""Decorator to send log messages to users if inform_user=True"""

	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			msgprint_handler = None
			if kwargs.get("inform_user"):
				msgprint_handler = MsgprintHandler()
				msgprint_handler.setLevel(logging.INFO)
				logger.addHandler(msgprint_handler)
			try:
				return func(*args, **kwargs)
			finally:
				if msgprint_handler:
					logger.removeHandler(msgprint_handler)

		return wrapper

	return decorator


from .fetch import (
	execute_fetch_task,
	get_exports,
	process_export_record,
	update_export_status,
)
from .send import (
	RASO_TYPES,
	execute_send_task,
	export_and_send_type,
	get_raso_settings,
	insert_to_raso,
)

__all__ = [
	"RASO_TYPES",
	"MsgprintHandler",
	"execute_fetch_task",
	"execute_send_task",
	"export_and_send_type",
	"get_exports",
	"get_raso_settings",
	"insert_to_raso",
	"process_export_record",
	"update_export_status",
	"with_msgprint_logging",
]
