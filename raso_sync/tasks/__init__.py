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

import logging

import frappe


class MsgprintHandler(logging.Handler):
	"""Custom logging handler that sends log messages to frappe.msgprint"""

	def emit(self, record):
		try:
			msg = self.format(record)
			frappe.publish_realtime(event="msgprint", message=msg)
		except Exception:
			self.handleError(record)


from .fetch import (
	execute_fetch_task,
	get_new_exports,
	process_export_record,
	update_export_status,
)
from .send import (
	RASO_TYPES,
	execute_send_task,
	export_and_send_type,
	get_raso_settings,
	insert_to_raso,
	store_export_to_disk,
)

__all__ = [
	"RASO_TYPES",
	"MsgprintHandler",
	"execute_fetch_task",
	"execute_send_task",
	"export_and_send_type",
	"get_new_exports",
	"get_raso_settings",
	"insert_to_raso",
	"process_export_record",
	"store_export_to_disk",
	"update_export_status",
]
