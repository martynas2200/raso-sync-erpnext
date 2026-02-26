from collections import Counter


def summarize_import_results(
	per_record_results,
	*,
	status_templates=None,
	empty_message="No records to process.",
):
	"""Build aggregate status and message for a batch import."""
	if not per_record_results:
		return "success", empty_message

	status_counts = Counter(result.get("status", "unknown") for result in per_record_results)

	default_templates = {
		"success": "{count} imported successfully",
		"accepted": "{count} created but not submitted",
		"skipped": "{count} skipped",
		"error": "{count} failed",
	}
	templates = {**default_templates, **(status_templates or {})}

	parts = []
	for status, template in templates.items():
		count = status_counts.get(status, 0)
		if count and template:
			parts.append(template.format(count=count))

	message = ". ".join(parts) + "." if parts else empty_message

	error_count = status_counts.get("error", 0)
	total = len(per_record_results)

	if error_count == 0:
		aggregate_status = "success"
	elif error_count == total:
		aggregate_status = "error"
	else:
		aggregate_status = "partial_success"

	return aggregate_status, message
