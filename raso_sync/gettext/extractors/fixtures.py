"""
Babel extractor for fixture files.

Fixtures are exported as a JSON list of documents, which none of the built-in
extractors handle.
"""

import json

from frappe.gettext.extractors.utils import get_line_number

LABEL_KEYS = ("label", "chart_name")
WORKSPACE_CHILD_TABLES = ("charts", "number_cards", "links", "shortcuts")


def extract(fileobj, *args, **kwargs):
	"""Extract translatable labels from a fixtures JSON file."""
	text = fileobj.read().decode()
	data = json.loads(text)

	if not isinstance(data, list):
		return

	for doc in data:
		if not isinstance(doc, dict):
			continue

		doctype = doc.get("doctype", "Document")
		name = doc.get("name", "")

		for key in LABEL_KEYS:
			value = doc.get(key)
			if value:
				yield _message(text, key, value, f"{key.replace('_', ' ').title()} of {doctype} '{name}'")

		if doctype != "Workspace":
			continue

		for table in WORKSPACE_CHILD_TABLES:
			for row in doc.get(table) or []:
				value = row.get("label") if isinstance(row, dict) else None
				if value:
					yield _message(
						text,
						"label",
						value,
						f"Label of a {table} row in Workspace '{name}'",
					)


def _message(text: str, key: str, value: str, comment: str):
	return get_line_number(text, key, value), "_", value, [comment]
