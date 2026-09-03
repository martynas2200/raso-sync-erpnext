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

        const $banner = this.$("#sync-status-banner");
        if (this.settings.is_running) {
            $banner.removeClass("idle").addClass("running");
        } else {
            $banner.removeClass("running").addClass("idle");
        }

        this.render_timestamp_card("#last-sale-import", this.settings.last_sale_import);
        this.render_timestamp_card("#last-data-export", this.settings.last_data_export);

        this.render_queue(this.settings.queued_doc_rows || []);
    },

    STALE_HOURS: 15,

    render_timestamp_card: function (selector, value) {
        const $value = this.$(selector);
        $value.removeClass("stale").empty();

        if (!value) {
            $value.text(__("Never"));
            return;
        }

        const ts = moment.tz(value, frappe.defaultDatetimeFormat, frappe.boot.time_zone.system);
        const stale = ts.isValid() && moment().diff(ts) > this.STALE_HOURS * 60 * 60 * 1000;

        $value.html(comment_when(value));

        if (stale) {
            $value.addClass("stale");
        }
    },

    ceil_to_next_minute: (date_obj) => {
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

    build_auto_send_message: function (send_job) {
        if (!send_job) {
            return __(
                "No scheduled job is configured. Save the settings to create a scheduled job for automatic sending."
            );
        }
        if (send_job.stopped) {
            return __("Automatic sending is disabled.");
        }

        const now = moment();

        if (send_job.next_execution) {
            const next_run = moment.tz(
                send_job.next_execution,
                frappe.defaultDatetimeFormat,
                frappe.boot.time_zone.system
            );
            if (next_run.isAfter(now)) {
                const eta_minutes = Math.max(0, Math.ceil(next_run.diff(now, "minutes", true)));
                const next_run_display = next_run.tz(frappe.boot.time_zone.user).format("HH:mm");

                if (eta_minutes <= 1) {
                    return __("Data should be sent on the next scheduler check (about 1 minute).");
                }

                return (
                    __("Data should be sent automatically in about") +
                    ` ${eta_minutes} ` +
                    __("min.") +
                    ` (${__("next check")}: ${next_run_display}).`
                );
            }
        }
        return "";
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

        const send_job = this.settings?.send_job || null;
        const indicator_message = this.build_auto_send_message(send_job);
        $indicator.removeClass("hidden").text(indicator_message);

        let html = `<table class="table table-hover queued-docs-table"><thead><tr>
            <th>${__("DocType")}</th>
            <th>${__("Document Name")}</th>
            <th>${__("Event")}</th>
            <th>${__("Marked At")}</th>
        </tr></thead><tbody>`;

        for (const row of safe_rows) {
            const marked_at = row.marked_at ? comment_when(row.marked_at, true) : "";
            const safe_doctype = frappe.utils.escape_html(frappe._(row.source_doctype));
            const safe_name = frappe.utils.escape_html(row.source_name);
            const safe_event = frappe.utils.escape_html(this.format_event(row.last_event));

            let name_cell = safe_name;
            if (row.source_name && row.source_name !== "—") {
                const doctype_route = frappe.router.slug(row.source_doctype);
                const doc_route = encodeURIComponent(row.source_name);
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
    format_event: (event_str) => {
        if (!event_str) return "—";
        if (event_str == "after_insert") return frappe._("Created");
        if (event_str == "on_update") return frappe._("Updated");
        if (event_str == "on_trash" || event_str == "after_delete") return frappe._("Deleted");
        return frappe._(event_str);
    },

    nl2br: (text) => {
        if (!text) return "";
        return frappe.utils
            .escape_html(String(text))
            .replace(/\\n/g, "<br>")
            .replace(/\n/g, "<br>");
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
            callback: (r) => {
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
                            message: this.nl2br(r.message?.error || __("Unknown error")),
                            indicator: "red",
                        },
                        5
                    );
                }
            },
            error: function () {
                frappe.show_alert(
                    {
                        message: __("Connection test failed: {0}").format(__("Unknown error")),
                        indicator: "red",
                    },
                    5
                );
            },
        });
    },

    check_logs: () => {
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
                            message: this.nl2br(
                                __("Send queued failed: ") + (r.message?.error || "Unknown error")
                            ),
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
                    callback: (r) => {
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
                                    message: this.nl2br(
                                        __("Fetch queued failed: ") +
                                            (r.message?.error || "Unknown error")
                                    ),
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
