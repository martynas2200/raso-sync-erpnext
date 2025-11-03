# raso-sync in development

**This application is currently under development and is not yet used**

A custom Frappe app that enables ERPNext integration with the RASO RETAIL POS system.
It also provides XML API endpoints to use a custom client to sync data from RASO POS system.

## Features

- Runs background jobs to fetch and send data
- Can be manual or scheduled
- Configurable settings for POS integration
- Employee to Sales Person mapping
- Payment method mapping
- Default item handling for unmatched items

## Installation

1. Install the app `bench get-app <repository-url>`
2. Enable scheduler: `bench config set-common-config --key enable_scheduler --value true`

## Pages

`/app/raso-sync` - RASO Sync Home (workspace, only shortcuts)
`/app/raso-sync-overview` - RASO Sync Dashboard
`/app/raso-sync-settings` - RASO Sync Settings document

## Background Jobs & Task Logs

### One-Way Sync Tasks
- **Fetch**: Receives exported data from RASO (reads `ie.usp_SyncDataExport`)
- **Send**: Sends to RASO (writes to `ie.usp_SyncDataImport`)
- No bidirectional conflict resolution needed

### Scheduler

- Fetch Task (`raso_sync_fetch_task_worker` at `raso_sync.tasks.fetch.execute_fetch_task_worker`): runs every x minutes, configured by `fetch_interval_minutes` setting
- Cache Task (`raso_sync_send_debounced` at `raso_sync.tasks.send.process_debounced_sends`): variable interval based on `enqueue_sending_delay_minutes` setting
- If hooks are enabled (`enqueue_sending_delay_minutes > 0`),
  - each time a relevant document is saved, a cache mark is created
  - periodically, a Cache Task will processes marks, and based on delay, will schedule `raso_sync_send_task_worker` task.
<!-- ### Viewing Job Logs
1. Go to Frappe Desk -> Tools -> Background Jobs
2. Look for jobs `raso_sync.tasks.fetch.execute` or `raso_sync.tasks.send.execute` -->



## API Endpoints (optional unless using custom database client)

### Main Endpoint
**URL**: `/api/method/raso_sync.api.exporter.export`
**Method**: GET/POST
**Parameters**:
- `DataType` (required): 1, 2, 3, or 4
- `FullSync` (optional): 1 for full sync, 0 for incremental
<!-- NOTE: ? (default: 1) -->
- `recentModified` (required when FullSync=0): ISO datetime (YYYY-MM-DDTHH:MM:SS)

| DataType | Description    | Frappe DocType    |
|----------|----------------|-------------------|
| 1        | Partners       | `Customer`        |
| 2        | GoodsGroups    | `Item Group`      |
| 3        | Goods          | `Item`            |
| 4        | GoodsPrices    | `Item Price`      |

### Importing to ERPNext

**URL**: `/api/method/raso_sync.api.importer.import_raso_data`
**Method**: POST
**Content-Type**: application/xml
**Request Body**: XML data in SalesSync format
**Validation**: the sum of all individual `<Payment>` entries under each `<Sales>` node must match the corresponding `<Payments>` totals under `<SalesSync>`.
**Response**:
<!-- TODO: DECIDE Response status is crucial here


- Sales invoices are created with title "EKA" + ReceiptNo
- Items are matched by VCODE if it starts with 'P', otherwise by barcode (CODE field)
- Regular quantities/amounts use QTY and AMOUNT fields
- Manual quantities/amounts (QTYMANUAL, AMOUNTMANUAL) are used when provided
- Payment codes 1001 and 1002 represent rounding adjustments (down/up)
- Import status is tracked in a custom field on the Sales Invoice
- Errors are added as comments to the Sales Invoice as well. -->

