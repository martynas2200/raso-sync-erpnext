app_name = "raso_sync"
app_title = "RASO Sync"
app_publisher = "Martynas Miliauskas"
app_description = "RASO POS System Sync API for ERPNext"
app_icon = "refresh-cw"
app_color = "grey"
app_email = "raso@ekranas.info"
app_license = "MIT"

# After app install/update, create custom fields
# If we define it in the fixtures, they will be deleted on uninstall
after_install = "raso_sync.custom_fields.create_custom_fields"
after_migrate = "raso_sync.custom_fields.create_custom_fields"
# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "raso_sync",
# 		"logo": "/assets/raso_sync/logo.png",
# 		"title": "Raso Sync",
# 		"route": "/raso_sync",
# 		"has_permission": "raso_sync.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/raso_sync/css/raso_sync.css"
# app_include_js = "/assets/raso_sync/js/raso_sync.js"

# include js, css files in header of web template
# web_include_css = "/assets/raso_sync/css/raso_sync.css"
# web_include_js = "/assets/raso_sync/js/raso_sync.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "raso_sync/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {
# 	"raso-sync-overview": "public/js/raso-sync-overview.js",
# }

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "raso_sync/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "raso_sync.utils.jinja_methods",
# 	"filters": "raso_sync.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "raso_sync.install.before_install"
# after_install = "raso_sync.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "raso_sync.uninstall.before_uninstall"
# after_uninstall = "raso_sync.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "raso_sync.utils.before_app_install"
# after_app_install = "raso_sync.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "raso_sync.utils.before_app_uninstall"
# after_app_uninstall = "raso_sync.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "raso_sync.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"raso_sync.tasks.all"
# 	],
# 	"daily": [
# 		"raso_sync.tasks.daily"
# 	],
# 	"hourly": [
# 		"raso_sync.tasks.hourly"
# 	],
# 	"weekly": [
# 		"raso_sync.tasks.weekly"
# 	],
# 	"monthly": [
# 		"raso_sync.tasks.monthly"
#   ],
#   "cron": {
#       "*/10 * * * *": [
#           "raso_sync.tasks.fetch.execute_fetch_task"
#       ],
#       "0 6 * * *": [
#           "raso_sync.tasks.send.execute_sent_task"
#       ],
#   },
# }

# Testing
# -------

# before_tests = "raso_sync.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "raso_sync.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "raso_sync.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "raso_sync.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["raso_sync.utils.before_request"]
# after_request = ["raso_sync.utils.after_request"]

# Job Events
# ----------
# before_job = ["raso_sync.utils.before_job"]
# after_job = ["raso_sync.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"raso_sync.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
