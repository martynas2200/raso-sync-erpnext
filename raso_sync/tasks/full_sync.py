"""
Nightly Full Sync Task
"""

import time

import frappe
from frappe.utils.background_jobs import is_job_enqueued

from raso_sync.tasks.fetch import execute_fetch_task_worker
from raso_sync.tasks.send import execute_send_task_worker

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

	Worker function that performs the full sync importing and fetching.
	Task list (just recreating what I see in logs of previous integration, seems like an overkill to me, but no documentation, perhaps there is a reason for that, like deleted records, each send sends full data set):
	    1. Send: Partners
	    2. Send: Partners (FullSync)
	    3. Send: GoodsGroups
	    4. Send: GoodsGroups (FullSync)
	    5. Send: Goods
	    6. Send: Goods (FullSync)
	    7. Send: GoodsPrices
	    8. Fetch: Sales
	"""
	execute_fetch_task_worker()
	time.sleep(10)
	execute_send_task_worker("partners")
	time.sleep(10)
	execute_send_task_worker("good_groups", date_from="2000-01-01")
	time.sleep(10)
	execute_send_task_worker("good_groups")
	time.sleep(10)
	execute_send_task_worker("goods", date_from="2000-01-01")
	time.sleep(10)
	execute_send_task_worker("goods")
	time.sleep(10)
	execute_send_task_worker("goods_prices", date_from="2000-01-01")

	logger.info("Full Sync Task Completed.")
	return {"status": "completed"}
