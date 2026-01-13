A custom Frappe app that enables ERPNext integration with the RASO RETAIL POS system.

## Features

- Runs background jobs to fetch and send data
- Can be manual or scheduled
- Configurable settings for POS integration
- Employee to Sales Person mapping
- Payment method mapping
- Default item handling for unmatched items


## Types of Data Synced
- One-way sync from ERPNext to RASO:
  - Customer
  - Item Group
  - Item
  - Item Price
- Import of Sales and Returns from RASO to ERPNext, creates Sales Invoices with relevant items and payments

## Installation

- Make sure the environment has pymssql installed, if it is production environment, it is highly recommended to use custom docker image. More information can be found at [Frappe Docker documentation](https://github.com/frappe/frappe_docker/blob/main/docs/container-setup/02-build-setup.md).
- Scheduler must be enabled in Frappe setup to run background jobs.
- Precision of Field `Rate` in `Sales Invoice Item` doctype must be increased to at least 3 decimal places to avoid rounding issues.

### Bench Commands for local development
1. Get the app `bench get-app <repository-url>`
2. Enable scheduler: `bench config set-common-config --key enable_scheduler --value true`
3. Install the app on your site: `bench --site <site-name> install-app raso_sync`

## Pages

- `/app/raso-sync` - RASO Sync Home (workspace, only shortcuts)
- `/app/raso-sync-overview` - RASO Sync Dashboard
- `/app/raso-sync-settings` - RASO Sync Settings document

## Constrains

- Items are not send to RASO if they do not have barcode
- Items names are cut off if it exceeds 80 characters (so we fit in two lines of text fit on the receipt)
- When picking the price, if multiple valid prices exist for the same item and price list, the one with the most recent `valid_from` date is selected; if there are ties, the most recently modified price is used (ordered by `ip.valid_from DESC, ip.modified DESC`).

## Background Jobs & Task Logs

### One-Way Sync Tasks
- **Fetch**: Receives exported data from RASO (reads `ie.usp_SyncDataExport` table)
- **Send**: Sends to RASO (writes to `ie.usp_SyncDataImport` table)
- No bidirectional conflict resolution needed

### Scheduler

- Enqueue Fetch Task (`raso_sync.tasks.fetch.execute_fetch_task`) configured by `fetch_interval_minutes` settings
- Check cache for send markers (`raso_sync.tasks.send.process_cache_marks`) interval is configured by `sending_delay_minutes` settings. The task will:
  - retrieve cache marks
  - for each mark older than `sending_delay_minutes`, enqueue `raso_sync.tasks.send.execute_send_task` task to send relevant documents to RASO
- Enqueue Full Sync Task (`raso_sync.tasks.full_sync.execute_full_sync_task`) once daily at configured time (`full_sync_time` setting)

---

## OPTIONAL API Endpoints (unless using a custom database client)
Syncing is using done via direct database access to RASO's SQL Server database using stored procedures in background worker task.
However, for advanced setups, the app provides XML API endpoints.
In that case, a custom client must be implemented.

### Main Endpoint
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


### Importing to ERPNext

**URL**: `/api/method/raso_sync.api.importer.import_data`
**Method**: POST
**Content-Type**: application/xml
**Request Body**: XML data in SalesSync format
**Supported Types**:
- Type 0: Sales
- Type 3: Returns (detected automatically if items have negative quantities)
**Validation**: the sum of all individual `<Payment>` entries under each `<Sales>` node must match the corresponding `<Payments>` totals under `<SalesSync>`.
**Response**: JSON Object
```json
{
  "status": "success|error",
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
<!-- TODO: needs more clarity on what constitutes a status error -->
<!-- - Items are matched by VCODE if it starts with 'P' or 'I', otherwise by barcode (CODE xml field) -->
- Import status is tracked in a custom field on the Sales Invoice
- Errors are added as comments to the Sales Invoice as well.

