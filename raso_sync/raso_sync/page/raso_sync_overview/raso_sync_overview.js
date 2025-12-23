// Page API documentation: https://frappeframework.com/docs/user/en/api/page
// https://github.com/frappe/erpnext/blob/version-15/erpnext/stock/page/warehouse_capacity_summary/warehouse_capacity_summary.js

// Also consider using frappe.cache to report on the last sync times without querying the database

frappe.pages["raso-sync-overview"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("RASO Sync Overview"),
        single_column: true,
    });

    $(frappe.render_template("raso_sync_overview")).appendTo(page.main);

    if (frappe.raso_sync_overview) {
        frappe.raso_sync_overview.setup(page);
        // Ensure interval cleanup when page is unloaded (navigated away)
        $(wrapper).on("remove", function () {
            frappe.raso_sync_overview.cleanup && frappe.raso_sync_overview.cleanup();
        });
    }

    page.set_primary_action(__("Open Settings"), () => {
        frappe.set_route("Form", "RASO Sync Settings");
    });
};

frappe.raso_sync_overview = {
    setup: function (page) {
        this.page = page;
        this.load_settings();
        this.attach_event_handlers();
        // Clear existing interval if setup re-runs for any reason
        if (this.refresh_interval) {
            clearInterval(this.refresh_interval);
        }
        this.refresh_interval = setInterval(() => {
            this.load_settings(false);
        }, 10000);
    },

    cleanup: function () {
        if (this.refresh_interval) {
            clearInterval(this.refresh_interval);
            this.refresh_interval = null;
        }
    },

    load_settings: function (notification = true) {
        var me = this;
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "RASO Sync Settings",
            },
            callback: function (response) {
                if (response.message) {
                    me.settings = response.message;
                    me.update_ui();
                    if (notification)
                        frappe.show_alert(
                            {
                                message: __("Settings loaded successfully"),
                                indicator: "green",
                            },
                            3
                        );
                }
            },
        });
    },

    attach_event_handlers: function () {
        var me = this;

        // System Actions
        $("#refresh-btn").on("click", () => {
            me.load_settings();
        });
        $("#test-connection-btn").on("click", () => me.test_connection());
        $("#check-logs-btn").on("click", () => me.check_logs());
        $("#open-scheduled-jobs-btn").on("click", function () {
            frappe.set_route("List", "Scheduled Job Type", {
                method: ["like", "%raso%"],
            });
        });

        // Upload Actions
        $("#upload-btn").on("click", function () {
            $("#upload-options").toggleClass("show");
            $("#fetch-options").removeClass("show");
        });

        $("#cancel-upload-btn").on("click", function () {
            $("#upload-options").removeClass("show");
        });

        $("#execute-upload-btn").on("click", () => me.execute_upload());

        // Fetch Actions
        $("#fetch-btn").on("click", function () {
            $("#fetch-options").toggleClass("show");
            $("#upload-options").removeClass("show");
        });

        $("#cancel-fetch-btn").on("click", function () {
            $("#fetch-options").removeClass("show");
        });

        $("#execute-fetch-btn").on("click", () => me.execute_fetch());
    },

    update_ui: function () {
        if (!this.settings) return;

        // Update sync status banner
        const is_running = this.settings.synchronization_is_running;
        const $banner = $("#sync-status-banner");
        const $status_text = $("#sync-status-text");

        if (is_running) {
            $banner.removeClass("idle").addClass("running");
            $status_text.text(__("Synchronization is running"));
        } else {
            $banner.removeClass("running").addClass("idle");
            $status_text.text(__("Synchronization is idle"));
        }

        // Format date
        const format_date = (date_str) => {
            if (!date_str) return __("Never");
            return (
                frappe.datetime.global_date_format(date_str) +
                " " +
                frappe.datetime.str_to_user(date_str).split(" ")[1]
            );
        };

        // Update status cards
        $("#last-sale-import").text(format_date(this.settings.last_sale_import));
        $("#last-data-export").text(format_date(this.settings.last_data_export));
    },

    test_connection: function () {
        frappe.show_alert(
            {
                message: __("Testing connection to RASO..."),
                indicator: "blue",
            },
            3
        );

        frappe.call({
            method: "raso_sync.api.manual.test_connection",
            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.show_alert(
                        {
                            message: __("Connection test successful"),
                            indicator: "green",
                        },
                        5
                    );
                } else {
                    frappe.show_alert(
                        {
                            message:
                                __("Connection test failed: ") +
                                (r.message?.error || __("Unknown error")),
                            indicator: "red",
                        },
                        5
                    );
                }
            },
            error: function () {
                frappe.show_alert(
                    {
                        message: __("Connection test failed"),
                        indicator: "red",
                    },
                    5
                );
            },
        });
    },

    check_logs: function () {
        frappe.set_route("List", "Error Log", {
            error: ["like", "%raso%"],
        });
    },

    execute_upload: function () {
        const upload_type = $("#upload-type").val();
        const upload_mode = $("input[name='upload-mode']:checked").val();

        frappe.confirm(
            __("Are you sure you want to upload {0} using {1} mode?", [upload_type, upload_mode]),
            () => {
                frappe.show_alert(
                    {
                        message: __("Starting upload..."),
                        indicator: "blue",
                    },
                    3
                );

                frappe.call({
                    method: "raso_sync.api.manual.manual_upload",
                    args: {
                        data_type: upload_type,
                        mode: upload_mode,
                    },
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert(
                                {
                                    message: r.message.message || __("Upload queued successfully"),
                                    indicator: "green",
                                },
                                5
                            );
                            $("#upload-options").removeClass("show");
                        } else {
                            frappe.show_alert(
                                {
                                    message:
                                        __("Upload queued failed: ") +
                                        (r.message?.error || "Unknown error"),
                                    indicator: "red",
                                },
                                5
                            );
                        }
                    },
                });
            }
        );
    },

    execute_fetch: function () {
        const fetch_type = $("#fetch-type").val();

        frappe.confirm(__("Are you sure you want to fetch {0} from RASO?", [fetch_type]), () => {
            frappe.show_alert(
                {
                    message: __("Starting fetch..."),
                    indicator: "blue",
                },
                3
            );

            frappe.call({
                method: "raso_sync.api.manual.manual_fetch",
                args: {
                    data_type: fetch_type,
                },
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert(
                            {
                                message: r.message.message || __("Fetch queued successfully"),
                                indicator: "green",
                            },
                            5
                        );
                        $("#fetch-options").removeClass("show");
                    } else {
                        frappe.show_alert(
                            {
                                message:
                                    __("Fetch queued failed: ") +
                                    (r.message?.error || "Unknown error"),
                                indicator: "red",
                            },
                            5
                        );
                    }
                },
            });
        });
    },
};
