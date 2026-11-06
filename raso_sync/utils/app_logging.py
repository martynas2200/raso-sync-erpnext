"""Central logger factory for raso_sync."""

import frappe


def get_logger(name: str):
	logger = frappe.logger(name)
	conf = getattr(getattr(frappe, "local", None), "conf", None) or {}
	level = conf.get("raso_sync_log_level", "INFO")
	if isinstance(level, str):
		level = level.upper()
	logger.setLevel(level)
	return logger
