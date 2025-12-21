# cv/tasks.py
from celery import shared_task

from agent.steam_line_workflow import State, steam_line_workflow

from .models import CV, CVScan


@shared_task(bind=True)
def analyze_cv_task(self, cv_id, scan_id):
    try:
        cv = CV.objects.get(pk=cv_id)
        cv_scan = CVScan.objects.get(pk=scan_id)
        cv_scan.scan_status = CVScan.ScanStatus.STARTED
        cv_scan.save()

        # raw_cv_text = """
        # Python developer with Django experience.
        # """

        # job_description = """
        # FullStack developer using Python, Django, Docker, React.
        # """

        # result: State = steam_line_workflow.invoke(
        #     {"raw_cv_text": raw_cv_text, "job_description": job_description}
        # )

        result: State = steam_line_workflow.invoke(
            {"raw_cv_text": cv.cv_text, "job_description": cv_scan.job_description}
        )

        cv_scan.scan_result = result["summary_generator_output"]
        cv_scan.anonymized_cv_text = result["anonymized_cv_text"]
        cv_scan.preprocessed_cv_text = result["preprocessed_cv_text"]
        cv_scan.identified_hard_skills = result["identified_hard_skills"]
        cv_scan.identified_soft_skills = result["identified_soft_skills"]
        cv_scan.hard_skill_analyser_output = result["hard_skill_analyser_output"]
        cv_scan.soft_skill_analyser_output = result["soft_skill_analyser_output"]
        cv_scan.summary_generator_output = result["summary_generator_output"]
        cv_scan.scan_status = CVScan.ScanStatus.FINISHED
        cv_scan.save()

        return {"cv_id": cv_id, "status": "done"}

    except Exception as e:
        # Optional retry logic
        raise self.retry(exc=e, countdown=5, max_retries=3)
