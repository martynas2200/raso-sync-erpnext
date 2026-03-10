// Page API documentation: https://frappeframework.com/docs/user/en/api/page

frappe.pages["raso-sync-overview"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("RASO Sync Overview"),
        single_column: true,
    });

    $(frappe.render_template("raso_sync_overview")).appendTo(page.main);

    if (frappe.raso_sync_overview) {
        frappe.raso_sync_overview.setup(page);
    }

    page.set_primary_action(__("Open Settings"), () => {
        frappe.set_route("Form", "RASO Sync Settings");
    });
};

frappe.pages["raso-sync-overview"].refresh = function (wrapper) {
    if (frappe.raso_sync_overview) {
        frappe.raso_sync_overview.load_settings();
    }
};

frappe.raso_sync_overview = {
    realtime_callback: null,

    setup: function (page) {
        this.page = page;
        this.load_settings();
        this.attach_event_handlers();
        this.setup_realtime_updates();
    },

    load_settings: function () {
        if (!$(this.page.wrapper).is(":visible")) {
            return;
        }
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
                }
            },
        });
    },

    attach_event_handlers: function () {
        var me = this;

        // System Actions
        $("#test-connection-btn").on("click", () => me.test_connection());
        $("#check-logs-btn").on("click", () => me.check_logs());
        $("#open-scheduled-jobs-btn").on("click", function () {
            frappe.set_route("List", "Scheduled Job Type", {
                method: ["like", "%raso%"],
            });
        });

        // Upload Actions
        $("#upload-btn").on("click", function () {
            $("#sync-buttons").hide();
            $("#upload-options").toggleClass("show");
            $("#fetch-options").removeClass("show");
        });

        $("#cancel-upload-btn").on("click", function () {
            $("#sync-buttons").show();
            $("#upload-options").removeClass("show");
        });

        $("#execute-upload-btn").on("click", () => me.execute_upload());

        // Fetch
        $("#fetch-btn").on("click", () => me.execute_fetch());
    },

    setup_realtime_updates: function () {
        var me = this;
        // Unsubscribe previous callback if exists
        if (this.realtime_callback) {
            frappe.realtime.off("raso_sync_status_update", this.realtime_callback);
        }
        this.realtime_callback = function (data) {
            if (!me.settings || !data) {
                return;
            }

            // Update all provided fields
            Object.assign(me.settings, data);
            me.update_ui();
        };
        frappe.realtime.on("raso_sync_status_update", this.realtime_callback);
    },

    update_ui: function () {
        if (!this.settings) return;

        const is_running = this.settings.is_running;
        const $banner = $("#sync-status-banner");
        const $status_text = $("#sync-status-text");

        if (is_running) {
            $banner.removeClass("idle").addClass("running");
            $status_text.text(__("Synchronization is running"));
        } else {
            $banner.removeClass("running").addClass("idle");
            $status_text.text(__("Synchronization is idle"));
        }

        $("#last-sale-import").text(this.format_date(this.settings.last_sale_import));
        $("#last-data-export").text(this.format_date(this.settings.last_data_export));
    },
    format_date: (date_str) => {
        if (!date_str) return __("Never");
        return frappe.datetime.str_to_user(date_str);
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
                            message: r.message.message || __("Connection test successful"),
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
                    $("#sync-buttons").show();
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
    },

    execute_fetch: function () {
        frappe.confirm(
            __(
                "Are you sure you want to fetch data from RASO POS server?<br>Supported data types: Sales, Returns, Z Reports"
            ),
            () => {
                frappe.call({
                    method: "raso_sync.api.manual.manual_fetch",
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert(
                                {
                                    message: r.message.message || __("Fetch queued successfully"),
                                    indicator: "green",
                                },
                                5
                            );
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
            }
        );
    },
};
