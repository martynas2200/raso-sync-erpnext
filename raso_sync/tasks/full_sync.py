"""
Nightly Full Sync Task
"""

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from raso_sync.tasks.fetch import execute_fetch_task_worker
from raso_sync.tasks.send import execute_send_task_worker
from raso_sync.utils.app_logging import get_logger

logger = get_logger("raso_sync.full_sync")


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

	Worker function that performs the full sync importing and fetching.
	"""
	execute_fetch_task_worker()
	execute_send_task_worker("partners")
	# GoodsGroups ignores config 65, thus FullSync=1 always upserts and disables
	execute_send_task_worker("good_groups")
	execute_send_task_worker("goods", date_from="2000-01-01")
	execute_send_task_worker("goods")
	execute_send_task_worker("good_prices", date_from="2000-01-01")
	execute_send_task_worker("good_prices")

	logger.info("Full Sync Task Completed.")
	return {"status": "completed"}
