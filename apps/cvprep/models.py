from django.db import models
from apps.users.models import User


class TimeStampedModel(models.Model):
    """
    An abstract base class model that provides self-
    updating ``created`` and ``modified`` fields. - Two scoops of django
    """

    class Meta:
        # migration won't create table for this
        abstract = True

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


class CVOwner(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    pass


class CV(TimeStampedModel):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="uploads/")
    cv_text = models.TextField(blank=True)
    owner = models.ForeignKey(CVOwner, on_delete=models.CASCADE)


class CVScan(TimeStampedModel):
    cv = models.ForeignKey(CV, on_delete=models.CASCADE)
    job_description = models.TextField(blank=True)
    CV_STATUS = [
        ("pe", "PENDING"),
        ("st", "STARTED"),
        ("pr", "PROCESSING"),
        ("fi", "FINISHED"),
    ]
    scan_status = models.CharField(max_length=2, choices=CV_STATUS, default="pe")
    scan_result = models.TextField(blank=True)
