app_name = "raso_sync"
app_title = "RASO Sync"
app_publisher = "Martynas Miliauskas"
app_description = "RASO POS System Sync API for ERPNext"
app_email = "raso@ekranas.info"
app_license = "MIT"
app_logo_url = "/assets/raso_sync/raso_icon.svg"
app_home = "/desk/raso-dashboard"

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			["dt", "in", ["Customer", "Sales Invoice", "Item", "Item Group"]],
			[
				"fieldname",
				"in",
				[
					"business_code",
					"raso_receipt_no",
					"deposit_package_count",
					"pos_section",
					"pos_department_no",
					"is_refundable",
					"is_visible_in_catalog",
					"column_break_raso",
					"raso_id",
				],
			],
		],
	},
	{"dt": "Number Card", "filters": [["module", "=", "Raso Sync"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "Raso Sync"]]},
	{"dt": "Workspace", "filters": [["module", "=", "Raso Sync"]]},
]

after_sync = "raso_sync.migrations.fill_missing_raso_ids"
after_migrate = "raso_sync.migrations.run_migrations"
before_uninstall = "raso_sync.migrations.remove_custom_fields"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": "RASO",
		"route": app_home,
		"has_permission": "raso_sync.api.permission.has_app_permission",
		"sequence_id": 900,  # low priority
	}
]

# app_include_icons = "raso_sync/public/icons.svg"

doc_events = {
	"Item": {
		"after_insert": "raso_sync.tasks.send.mark_doctype_for_sync",
		"on_update": "raso_sync.tasks.send.mark_doctype_for_sync",
		"after_delete": "raso_sync.tasks.send.mark_doctype_for_sync",
	},
	"Item Price": {
		"after_insert": "raso_sync.tasks.send.mark_doctype_for_sync",
		"on_update": "raso_sync.tasks.send.mark_doctype_for_sync",
		"after_delete": "raso_sync.tasks.send.mark_doctype_for_sync",
	},
	"Item Group": {
		"before_save": "raso_sync.item_group_hook.ensure_raso_id",
		"after_insert": "raso_sync.tasks.send.mark_doctype_for_sync",
		"on_update": "raso_sync.tasks.send.mark_doctype_for_sync",
		"after_delete": "raso_sync.tasks.send.mark_doctype_for_sync",
	},
	"Customer": {
		"after_insert": "raso_sync.tasks.send.mark_doctype_for_sync",
		"on_update": "raso_sync.tasks.send.mark_doctype_for_sync",
		"after_delete": "raso_sync.tasks.send.mark_doctype_for_sync",
	},
}

scheduler_events = {"daily_maintenance": ["raso_sync.tasks.maintenance.execute_maintenance_task"]}
# Other tasks scheduled dynamically in RasoSyncSettings.on_update()
