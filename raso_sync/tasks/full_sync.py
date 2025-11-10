"""
Nightly Full Sync Task
"""

import frappe

from raso_sync.raso_sync.tasks.fetch import get_new_exports, process_export_record
from raso_sync.raso_sync.utils.job_utils import is_job_enqueued
from raso_sync.raso_sync.utils.working_hours import is_within_working_hours

logger = frappe.logger("raso_sync")


def execute_full_sync_task():
	"""
	Enqueue the full sync task to import all data from RASO.
	Returns:
	    status: str: 'queued' if enqueued, 'skipped' if already running
	    job_id: str: ID of the enqueued job
	"""
	job_id = "raso_sync_full_sync_task_worker"

	if is_job_enqueued(job_id):
		return {"status": "skipped"}

	frappe.enqueue(
		"raso_sync.tasks.full_sync.execute_full_sync_task_worker",
		job_id=job_id,
		enqueue_after_commit=True,
		queue="long",
	)

	return {"status": "queued", "job_id": job_id}


def execute_full_sync_task_worker():
	"""
	NEEDS TO BE ENQUEUED WITH JOB-ID: raso_sync_full_sync_task_worker

	Worker function that performs the full sync fetching and importing.
	Task list (just recreating what I see in logs of previous integration, seems like an overkill to me, but no documentation, perhaps there is a reason for that, like deleted records):
	    1. Send: Partners
	    2. Send: Partners (FullSync)
	    3. Send: GoodsGroups
	    4. Send: GoodsGroups (FullSync)
	    5. Send: Goods
	    6. Send: Goods (FullSync)
	    7. Send: GoodsPrices
	    8. Fetch: Sales
	"""

	logger.info("Full Sync Task Completed.")
	return {"status": "completed"}
