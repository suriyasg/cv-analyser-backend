# cv/tasks.py
from celery import shared_task
from .models import CV, CVScan
from agent.steam_line_agents import State, steam_line_agents_app


@shared_task(bind=True)
def analyze_cv_task(self, cv_id, scan_id):
    try:
        cv = CV.objects.get(pk=cv_id)
        cv_scan = CVScan.objects.get(pk=scan_id)
        cv_scan.scan_status = "STARTED"
        cv_scan.save()

        result: State = steam_line_agents_app.invoke(
            {"raw_cv_text": cv.cv_text, "job_description": cv_scan.job_description}
        )

        cv_scan.scan_result = result["summary_generator_output"]
        cv_scan.scan_status = "COMPLETED"
        cv_scan.save()

        return {"cv_id": cv_id, "status": "done"}

    except Exception as e:
        # Optional retry logic
        raise self.retry(exc=e, countdown=5, max_retries=3)
