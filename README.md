Raso Sync is a Frappe app that keeps ERPNext master data and RASO POS sales data in sync using resilient background jobs, a persisted send queue, and configurable scheduling.

## Features

- Scheduler-driven automation
- Background jobs for fetch, send, and full-sync flows
- Manual run support
- Settings page for POS integration behaviour and sync intervals
- Dashboard workspace with sales and Z report metrics
- Reconciliation report comparing Z reports against imported Sales Invoices
- Status page indicating last import/export times with links to do diagnostics
- Logging
- Employee to Sales Person mapping
- Payment Method mapping
- Default item handling for unmatched items


## Types of Data Synced

- One-way sync from ERPNext to RASO:
  - Customer
  - Item Group
  - Item
  - Item Price
- Import of Sales and Returns from RASO to ERPNext, creating Sales Invoices with relevant items and payments
- Import of Z Reports from RASO into the `Z Report` doctype

## Installation

- Scheduler must be enabled in Frappe setup to run background jobs.
- Logging verbosity is controlled per site by `raso_sync_log_level` in `site_config.json` — one of `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`. Each task writes to its own file under site logs directory, e.g. `logs/raso_sync.fetch.log`.
- Precision of Field `Rate` in `Sales Invoice Item` doctype must be increased to at least 3 decimal places to avoid rounding issues.
- Consider enabling `Allow Negative Stock` if auto submit of Sales Invoices is desired.
- Consider making `uom` field in `Item Barcode` doctype mandatory, otherwise item prices might not be sent.
- In RASO Retail Server: consider setting the value of config 180 to 13 unless the barcodes entered in ERPNext omit the control digits.

Python dependencies are installed by bench itself. A custom image (see [Frappe Docker documentation](https://github.com/frappe/frappe_docker)) is only required when pip cannot find a wheel for the target platform.

### Bench Commands for local development

1. Get the app `bench get-app https://github.com/martynas2200/raso-sync-erpnext`
2. Enable scheduler: `bench config set-common-config --key enable_scheduler --value true`
3. Install the app on your site: `bench --site <site-name> install-app raso_sync`

## Pages

- `/desk/raso-dashboard` - RASO Dashboard workspace: gives figures on turnover, receipts and refunds.
- `/desk/raso-sync-status` - RASO Sync status page: last import/export, manual send and fetch, pending documents, diagnostics
- `/desk/query-report/RASO Reconciliation` - RASO Reconciliation report: per-day comparison of Z report turnover and receipt counts against the imported Sales Invoices
- `/desk/raso-sync-settings` - RASO Sync Settings

## Constraints

- Items are not sent to RASO if they do not have a barcode and the UOM for that barcode set.
- A barcode whose `UOM` differs from the item's stock UOM is exported as a package, so RASO can derive the package price by multiplication. Package content attributes are omitted when the item has no stock-UOM barcode, when the conversion factor is not greater than 1, or when an active selling price (valid today, in the configured `price_list`) exists for the package UOM, in which case that custom price replaces the derived one.
- `ExtraQty` (usually deposit packages) is `deposit_package_count` multiplied by that same conversion factor when the barcode is sold in a non-stock UOM.
- Item names are cut off after 80 characters so they fit in two lines on the receipt.
- When picking the price, if multiple valid prices exist for the same item and price list, the one with the most recent `valid_from` date is selected; if there are ties, the most recently modified price is used (ordered by `ip.valid_from DESC, ip.modified DESC`).
- Item prices are always sent without `DateFrom`/`DateTo` (DataType 4). ERPNext resolves which price is effective on the current date and RASO receives that single price, so the POS never has to interpret validity windows. Dated rows belong to DataType 7, where the dates are part of the row identity; a packet mixing both date classes is discarded by RASO.
- A price change takes effect at the next send. Editing an `Item Price` queues it immediately, but a price that changes purely because a `valid_from`/`valid_upto` window opened or closed fires no document event, so the nightly full sync is what propagates it. Keep `full_sync_time` enabled when using validity windows, otherwise an expiring `valid_upto` never reaches RASO and the discount price stays on the till.

## Background Jobs & Task Logs

### One-Way Sync Tasks

- **Fetch**: Receives exported data from RASO (reads `ie.usp_SyncDataExport` table)
- **Send**: Sends to RASO (writes to `ie.usp_SyncDataImport` table)

### Scheduler

- Fetch Task `raso_sync.tasks.fetch.execute_fetch_task`
  - The interval is configured by `fetch_interval_minutes` option.
- Send Queue Check `raso_sync.tasks.send.process_queued_marks`
  - The interval is configured by `send_check_interval_minutes` settings.
  - The task reads `RASO Sync Queue Doc` rows and possibly enqueues `raso_sync.tasks.send.execute_send_task` for relevant documents.
  - This replaces the earlier approach that used cache marks + a 15-minute recent-modified window. No oversending, and the DB-backed queue is more trustworthy and resilient because pending changes survive process restarts, scheduler delays, worker failures, etc.
- Full Sync Task `raso_sync.tasks.full_sync.execute_full_sync_task`
  - Run once daily at configured time (`full_sync_time` setting), mostly needed for item price records so the day to day price changes are reflected in RASO (fields of `valid_from`, `valid_to`).
  - RASO config `65` ("ar naudoti pilną prekių sinchronizaciją") decides what `FullSync=1` does: at `1` it upserts **and** disables, at `0` (the shipped default) it only **inserts** missing rows and **disables** the ones absent from the packet, so existing rows are never refreshed. Despite the "goods only" wording the flag gates the goods import, both price imports and the discount imports — but **not** `GoodsGroups`.
  - Item prices are sent as two passes, and both are load-bearing at config `65 = 0`. Because prices carry no `DateFrom`/`DateTo`, a barcode keeps **one** RASO row for its whole life, so a row left over from an expired discount is *matched*, never missing:
    - the `date_from` pass (`FullSync=0`) is the only one that **updates** it to the price that is valid now — that is how a discount ending and the price going back up reaches the till;
    - the plain pass (`FullSync=1`) **inserts** prices that just became valid and **disables** rows for products ERPNext no longer prices.
  - Items and prices change price validity by the passage of time alone, which fires no document event, so the nightly run is the only thing that propagates an expiring `valid_upto`.
  - `GoodsGroups` are sent once. The group import never reads config `65`, so `FullSync=1` always upserts and disables and a `date_from` pass would only write the same groups twice.
  - Goods (`Item`) are sent twice for the same reason: the `date_from` pass (`FullSync=0`) is the only one that **updates** existing goods and re-enables goods that came back into the assortment, while the plain pass (`FullSync=1`) only inserts goods missing from RASO and **disables** the goods absent from the packet (deleted or `disabled` items).
  - If RASO config `65` is `1`, the full packet already refreshes existing rows too, so the `date_from` pass is redundant for goods and prices. The app does cannot read or mirror that flag as `ms.ConfigValues` is not present in the database this app connects to. Both passes are therefore always sent, which is correct for `65 = 0` and merely redundant for `65 = 1`.
- Maintenance Task `raso_sync.tasks.maintenance.execute_maintenance_task`
  - Runs daily to check for previous import errors (RASO export Status 3 "Error" and 4 "Partial Success") and retry processing them.

---

## OPTIONAL XML API Endpoints for Custom Client Integration
Syncing is using done via direct database access to RASO's SQL Server database using stored procedures in background worker task.
However, for advanced setups, the app provides XML API endpoints; In that case, a custom client must be implemented.

### Export Endpoint
**URL**: `/api/method/raso_sync.api.exporter.export`
**Method**: GET/POST
**Parameters**:
- `DataType` (required): 1, 2, 3, or 4
- `FullSync` (optional): 1 for full sync, 0 for incremental
- `recentModified` (required when FullSync=0): ISO datetime

| DataType | Description    | Frappe DocType    |
|----------|----------------|-------------------|
| 1        | Partners       | `Customer`        |
| 2        | GoodsGroups    | `Item Group`      |
| 3        | Goods          | `Item`            |
| 4        | GoodsPrices    | `Item Price`      |


### Import Endpoint

**URL**: `/api/method/raso_sync.api.importer.import_data`
**Method**: POST
**Content-Type**: application/xml
**Request Body**: XML payload (raw body)
**Type Detection**: inferred from XML root element (request `DataType` is not used by this endpoint)
- `SalesSync` → processed by sales importer (sales/returns are inferred later per record)
- `SalesZReportsDataSync` → processed by Z-report importer
**Supported Internal Types**:
- Type 0: SalesSync payload route
- Type 3: Return records (handled within sales import flow)
- Type 5: SalesZReportsDataSync payload route
**Validation / Request Errors**:
- Rejects request if `Content-Type` is not exactly `application/xml`
- Rejects request if body is empty
- Rejects request if XML is malformed
- Rejects request if type cannot be inferred from XML root
**Response**: JSON Object
```json
{
  "status": "success|partial_success|error",
  "message": "...",
  "results": [
    {
      "receipt_no": "12345",
      "status": "success|accepted|skipped|error",
      "message": "..."
    }
  ]
}
```
- Status semantics:
  - Top-level `status`:
    - `success`: no per-record errors
    - `partial_success`: mix of successful and failed records
    - `error`: all processed records failed, or request-level validation failed before processing
  - Per-record `status`:
    - `success`: invoice created and submitted
    - `accepted`: invoice created but submission failed
    - `skipped`: receipt already imported (duplicate)
    - `error`: record processing failed
- Item matching order for Sales import:
  - If `VCODE` starts with a letter and matches an existing ERPNext Item, use it as `item_code`
  - Otherwise try Item Barcode lookup by `CODE` with leading zeros stripped
  - Then try Item Barcode lookup by raw `CODE`
  - If still not found, use `default_item` from RASO Sync Settings (or fail if not configured)
- Errors saved in error log, and if it is possible, might be also added as comments to the Sales Invoice.

