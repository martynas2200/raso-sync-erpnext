"""
Make this app's module name one spelling everywhere it is stored.

`Module Def.module_name` is unique, and every Frappe column is `utf8mb4_unicode_ci`, so
`Raso Sync` and `RASO Sync` are one row to MySQL and two different strings to Python.
A site that renamed the module by editing the JSON files alone therefore ends up with the row spelled one way and the `module` links spelled another, and `Sidebar` then refuses to save:
`shell_holding_slug` compares module names in Python, sees the row as a second shell holding
the same URL, and throws "already answers to the URL /desk/raso-sync".

"""

import re

import frappe

CANONICAL = "Raso Sync"

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]*$")

_MODULE_LINK_DOCTYPES: list[str] | None = None


def execute():
	variants = module_def_names()
	if not variants:
		# fresh install
		return

	keeper = keeper_of(variants)

	for name in variants:
		if name != keeper and not is_linked(name):
			frappe.db.sql("delete from `tabModule Def` where binary name = %s", name)

	if not exists_exactly(CANONICAL):
		frappe.db.sql(
			"update `tabModule Def` set name = %s, module_name = %s where binary name = %s",
			(CANONICAL, CANONICAL, keeper),
		)

	repoint_links()
	frappe.clear_cache()


def module_def_names() -> list[str]:
	return frappe.db.sql(
		"""
		select name from `tabModule Def`
		where lower(name) = lower(%s) or lower(module_name) = lower(%s)
		order by name asc
		""",
		(CANONICAL, CANONICAL),
		pluck=True,
	)


def keeper_of(variants: list[str]) -> str:
	if CANONICAL in variants:
		return CANONICAL

	return max(variants, key=link_count)


def exists_exactly(name: str) -> bool:
	return bool(frappe.db.sql("select 1 from `tabModule Def` where binary name = %s", name))


def is_linked(name: str) -> bool:
	"""Whether any document still names this module, compared byte for byte."""
	return any(link_count_for(doctype, name) for doctype in module_link_doctypes())


def link_count(name: str) -> int:
	return sum(link_count_for(doctype, name) for doctype in module_link_doctypes())


def link_count_for(doctype: str, name: str) -> int:
	return frappe.db.sql(
		f"select count(*) from `tab{doctype}` where binary module = %s",  # nosemgrep
		name,
	)[0][0]


def repoint_links() -> None:
	for doctype in module_link_doctypes():
		frappe.db.sql(
			f"""
			update `tab{doctype}` set module = %s
			where module is not null
			  and lower(module) = lower(%s)
			  and binary module != %s
			""",  # nosemgrep
			(CANONICAL, CANONICAL, CANONICAL),
		)


def module_link_doctypes() -> list[str]:
	global _MODULE_LINK_DOCTYPES
	if _MODULE_LINK_DOCTYPES is not None:
		return _MODULE_LINK_DOCTYPES

	parents = frappe.db.sql(
		"""
		select distinct parent from `tabDocField`
		where parenttype = 'DocType' and fieldname = 'module' and options = 'Module Def'
		""",
		pluck=True,
	)

	_MODULE_LINK_DOCTYPES = [
		parent
		for parent in parents
		if IDENTIFIER.match(parent or "")
		and frappe.db.table_exists(parent)
		and frappe.db.has_column(parent, "module")
	]
	return _MODULE_LINK_DOCTYPES
