"""Helpers for creating desk notifications."""

import frappe
from frappe import _
from frappe.translate import get_user_lang

DEFAULT_NOTIFICATION_ROLE = "Raso Sync User"
SERVER_UNAVAILABLE_DEDUP_KEY = "raso_sync:server_unavailable_notified"
SERVER_UNAVAILABLE_DEDUP_HOURS = 5


def _default_notification_users() -> list[str]:
	"""All enabled users holding the RASO Sync User role, plus Administrator."""
	from frappe.utils.user import get_users_with_role

	users = set(get_users_with_role(DEFAULT_NOTIFICATION_ROLE))
	users.add("Administrator")
	return sorted(users)


def _localized_text(text: str | None, user: str) -> str | None:
	"""Translate text into the user's preferred language."""
	if not text:
		return None
	return _(text, lang=get_user_lang(user))


def notify_server_unavailable() -> None:
	"""
	    Create a system notification for a RASO server-unavailable failure.

	Deduplicated with redis cache.
	"""
	if frappe.cache.get_value(SERVER_UNAVAILABLE_DEDUP_KEY):
		return

	create_system_notification(
		subject="Sync could not be executed",
		message="Raso Retail server appears to be offline or unreachable.",
	)

	frappe.cache.set_value(
		SERVER_UNAVAILABLE_DEDUP_KEY,
		1,
		expires_in_sec=SERVER_UNAVAILABLE_DEDUP_HOURS * 60 * 60,
	)


def clear_server_unavailable_notification_mark() -> None:
	"""Clear the dedup mark once the RASO server is reachable again."""
	try:
		frappe.cache.delete_value(SERVER_UNAVAILABLE_DEDUP_KEY)
	except Exception:
		# Cache may be unavailable in some contexts; never fail cleanup.
		pass


def create_system_notification(
	subject: str, message: str | None = None, for_users: list[str] | None = None
) -> None:
	"""
	Create a Notification Log entry.

	Args:
	    subject: Short notification title.
	    message: Optional body text.
	    for_users: Optional list of users to notify.
	"""
	users = for_users or _default_notification_users()

	for user in users:
		subject_text = _localized_text(subject, user)
		message_text = _localized_text(message, user)

		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject_text,
				"email_content": message_text,
				"for_user": user,
				"type": "Alert",
			}
		).insert(ignore_permissions=True)
