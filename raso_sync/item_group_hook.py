import frappe


def _raso_id_field_exists() -> bool:
	try:
		meta = frappe.get_meta("Item Group")
		return any(df.fieldname == "raso_id" for df in meta.fields)
	except Exception:
		# If meta fetch fails for any reason, don't block the save
		return False


def ensure_raso_id(doc, method=None):
	"""
	before_save hook for Item Group.
	Ensures `raso_id` is set to a monotonically increasing integer (as string) if missing.
	- Computes next value as MAX(raso_id) + 1 across all Item Groups.
	"""
	if not _raso_id_field_exists():
		return

	if getattr(doc, "raso_id", None):
		return

	# CAST handles any legacy non-numeric values by treating them as 0
	max_row = frappe.db.sql(
		"""
        SELECT COALESCE(MAX(CAST(raso_id AS UNSIGNED)), 0)
        FROM `tabItem Group`
        """,
		as_list=True,
	)
	current_max = max_row[0][0] if max_row and max_row[0] and max_row[0][0] is not None else 0
	next_id = int(current_max) + 1
	doc.raso_id = str(next_id)
