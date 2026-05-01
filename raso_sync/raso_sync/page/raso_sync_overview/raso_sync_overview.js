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
    event_namespace: ".raso_sync_overview",

    setup: function (page) {
        this.page = page;
        this.$wrapper = $(page.wrapper);
        this.load_settings();
        this.attach_event_handlers();
        this.setup_realtime_updates();
    },

    $: function (selector) {
        return this.$wrapper.find(selector);
    },

    load_settings: function () {
        if (!this.$wrapper.is(":visible")) {
            return;
        }
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "RASO Sync Settings",
            },
            callback: function (response) {
                if (response.message) {
                    this.settings = response.message;
                    this.update_ui();
                }
            },
        });
    },

    attach_event_handlers: function () {
        const events = this.event_namespace;

        this.$("#test-connection-btn")
            .off(events)
            .on(`click${events}`, () => this.test_connection());
        this.$("#check-logs-btn")
            .off(events)
            .on(`click${events}`, () => this.check_logs());
        this.$("#open-scheduled-jobs-btn")
            .off(events)
            .on(`click${events}`, () => {
                frappe.set_route("List", "Scheduled Job Type", {
                    method: ["like", "%raso%"],
                });
            });

        this.$("#send-btn")
            .off(events)
            .on(`click${events}`, () => {
                this.$("#sync-buttons").hide();
                this.$("#send-options").toggleClass("show");
            });

        this.$("#cancel-send-btn")
            .off(events)
            .on(`click${events}`, () => {
                this.$("#sync-buttons").show();
                this.$("#send-options").removeClass("show");
            });

        this.$("#execute-send-btn")
            .off(events)
            .on(`click${events}`, () => this.execute_send());
        this.$("#fetch-btn")
            .off(events)
            .on(`click${events}`, () => this.execute_fetch());
    },

    setup_realtime_updates: function () {
        // Unsubscribe previous callback if exists
        if (this.realtime_callback) {
            frappe.realtime.off("raso_sync_status_update", this.realtime_callback);
        }
        this.realtime_callback = (data) => {
            if (!this.settings || !data) {
                return;
            }

            // Update all provided fields
            Object.assign(this.settings, data);
            this.update_ui();
        };
        frappe.realtime.on("raso_sync_status_update", this.realtime_callback);
    },

    update_ui: function () {
        if (!this.settings) return;

        const is_running = this.settings.is_running;
        const $banner = this.$("#sync-status-banner");
        const $status_text = this.$("#sync-status-text");

        if (is_running) {
            $banner.removeClass("idle").addClass("running");
            $status_text.text(__("Synchronization is running"));
        } else {
            $banner.removeClass("running").addClass("idle");
            $status_text.text(__("Synchronization is idle"));
        }

        this.$("#last-sale-import").text(this.format_date(this.settings.last_sale_import));
        this.$("#last-data-export").text(this.format_date(this.settings.last_data_export));
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

    execute_send: function () {
        const send_type = this.$("#send-type").val();
        const send_mode = this.$("input[name='send-mode']:checked").val();

        frappe.call({
            method: "raso_sync.api.manual.manual_send",
            args: {
                data_type: send_type,
                mode: send_mode,
            },
            callback: (r) => {
                if (r.message && r.message.success) {
                    frappe.show_alert(
                        {
                            message: r.message.message || __("Send queued successfully"),
                            indicator: "green",
                        },
                        5
                    );
                    this.$("#send-options").removeClass("show");
                    this.$("#sync-buttons").show();
                } else {
                    frappe.show_alert(
                        {
                            message:
                                __("Send queued failed: ") + (r.message?.error || "Unknown error"),
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
