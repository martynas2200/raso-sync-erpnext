Raso Sync is a Frappe app that keeps ERPNext master data and RASO POS sales data in sync using resilient background jobs, a persisted send queue, and configurable scheduling.

## Features

- Scheduler-driven automation
- Background jobs for fetch, send, and full-sync flows
- Manual run support
- Settings page for POS integration behavior and sync intervals
- Overview page for day-to-day sync inspection
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

- Make sure the environment has pymssql installed, if it is production environment, it is highly recommended to use custom docker image. More information can be found at [Frappe Docker documentation](https://github.com/frappe/frappe_docker).
- Scheduler must be enabled in Frappe setup to run background jobs.
- Precision of Field `Rate` in `Sales Invoice Item` doctype must be increased to at least 3 decimal places to avoid rounding issues.
- Consider enabling `Allow Negative Stock` if auto submit of Sales Invoices is desired.
- Consider making `uom` field in `Item Barcode` doctype mandatory, otherwise item prices might not be sent.

### Bench Commands for local development
1. Get the app `bench get-app <repository-url>`
2. Enable scheduler: `bench config set-common-config --key enable_scheduler --value true`
3. Install the app on your site: `bench --site <site-name> install-app raso_sync`

## Pages

- `/app/raso-sync` - RASO Sync Home (workspace, only shortcuts)
- `/app/raso-sync-overview` - RASO Sync Dashboard
- `/app/raso-sync-settings` - RASO Sync Settings document

## Constraints

- Items are not sent to RASO if they do not have a barcode and the UOM for that barcode set.
- Item names are cut off after 80 characters so they fit in two lines on the receipt.
- When picking the price, if multiple valid prices exist for the same item and price list, the one with the most recent `valid_from` date is selected; if there are ties, the most recently modified price is used (ordered by `ip.valid_from DESC, ip.modified DESC`).

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

