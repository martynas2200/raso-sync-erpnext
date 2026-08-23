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
            method: "raso_sync.api.manual.get_sync_status",
            callback: (response) => {
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

        this.render_queue(this.settings.queued_doc_rows || []);
    },

    parse_server_datetime: function (date_str) {
        if (!date_str || typeof date_str !== "string") return null;

        if (frappe?.datetime?.str_to_obj) {
            const parsed = frappe.datetime.str_to_obj(date_str);
            if (parsed instanceof Date && !isNaN(parsed.getTime())) {
                return parsed;
            }
        }

        const match = date_str.match(/^(\d{4})-(\d{2})-(\d{2})\s(\d{2}):(\d{2}):(\d{2})$/);
        if (!match) return null;

        const [, year, month, day, hours, minutes, seconds] = match;
        const parsed = new Date(
            Number(year),
            Number(month) - 1,
            Number(day),
            Number(hours),
            Number(minutes),
            Number(seconds)
        );

        return isNaN(parsed.getTime()) ? null : parsed;
    },

    ceil_to_next_minute: function (date_obj) {
        const rounded = new Date(date_obj.getTime());
        rounded.setSeconds(0, 0);
        if (rounded < date_obj) {
            rounded.setMinutes(rounded.getMinutes() + 1);
        }
        return rounded;
    },

    get_next_scheduler_run: function (from_date, interval_minutes) {
        const interval = Number(interval_minutes || 0);
        if (interval <= 0 || !from_date) {
            return null;
        }

        const candidate = this.ceil_to_next_minute(from_date);

        if (interval <= 59) {
            while (candidate.getMinutes() % interval !== 0) {
                candidate.setMinutes(candidate.getMinutes() + 1);
            }
            return candidate;
        }

        const hours_step = Math.floor(interval / 60);
        const minute_offset = interval % 60;

        candidate.setMinutes(minute_offset, 0, 0);
        if (candidate < from_date) {
            candidate.setHours(candidate.getHours() + 1);
        }

        while (candidate.getHours() % hours_step !== 0 || candidate < from_date) {
            candidate.setHours(candidate.getHours() + 1, minute_offset, 0, 0);
        }

        return candidate;
    },

    build_auto_send_message: function (rows) {
        const check_interval_minutes = Number(this.settings?.send_check_interval_minutes || 0);

        if (check_interval_minutes <= 0) {
            return __("Automatic sending is currently disabled (Send Check Interval is 0).");
        }

        const now = new Date();
        const next_run = this.get_next_scheduler_run(now, check_interval_minutes);
        if (!next_run) {
            return __("Data is queued and will be sent automatically.");
        }

        const eta_minutes = Math.max(0, Math.ceil((next_run.getTime() - now.getTime()) / 60000));
        const next_run_display = next_run.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });

        if (eta_minutes <= 1) {
            return __("Data should be sent on the next scheduler check (about 1 minute).");
        }

        return (
            __("Data should be sent automatically in about") +
            ` ${eta_minutes} ` +
            __("min.") +
            ` (${__("next check")}: ${next_run_display}).`
        );
    },

    render_queue: function (rows) {
        const $container = this.$("#queued-docs-container");
        const $indicator = this.$("#queued-docs-indicator");
        const safe_rows = Array.isArray(rows) ? rows : [];

        if (safe_rows.length === 0) {
            $indicator.addClass("hidden").text("");
            $container.html(
                '<p class="empty-state">' + __("No pending documents to be sent") + "</p>"
            );
            return;
        }

        const indicator_message = this.build_auto_send_message(safe_rows);
        $indicator.removeClass("hidden").text(indicator_message);

        let html = `<table class="table table-hover queued-docs-table"><thead><tr>
            <th>${__("DocType")}</th>
            <th>${__("Document Name")}</th>
            <th>${__("Event")}</th>
            <th>${__("Marked At")}</th>
        </tr></thead><tbody>`;

        for (const row of safe_rows) {
            const marked_at = this.format_date(row.marked_at);
            const safe_doctype = frappe.utils.escape_html(frappe._(row.doctype));
            const safe_name = frappe.utils.escape_html(row.name);
            const safe_event = frappe.utils.escape_html(this.format_event(row.last_event));

            let name_cell = safe_name;
            if (row.name && row.name !== "—") {
                const doctype_route = frappe.router.slug(row.doctype);
                const doc_route = encodeURIComponent(row.name);
                const href = frappe.utils.escape_html(`/app/${doctype_route}/${doc_route}`);
                name_cell = `<a href="${href}" target="_blank" rel="noopener noreferrer">${safe_name}</a>`;
            }

            html += `<tr>
                <td>${safe_doctype}</td>
                <td>${name_cell}</td>
                <td>${safe_event}</td>
                <td>${marked_at}</td>
            </tr>`;
        }

        html += "</tbody></table>";
        $container.html(html);
    },
    format_date: (date_str) => {
        if (!date_str) return __("Never");
        return frappe.datetime.str_to_user(date_str);
    },
    format_event: (event_str) => {
        if (!event_str) return "—";
        if (event_str == "after_insert") return frappe._("Created");
        if (event_str == "on_update") return frappe._("Updated");
        if (event_str == "on_trash" || event_str == "after_delete") return frappe._("Deleted");
        return frappe._(event_str);
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
