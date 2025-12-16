# myapp/serializers.py
from rest_framework import serializers
from .models import CV, CVScan, CVOwner


class CVOwnerSerializer(serializers.ModelSerializer):
    # cv_set = serializers.PrimaryKeyRelatedField(many=True, queryset=CV.objects.all())

    class Meta:
        model = CVOwner
        fields = "__all__"


class PartialCVScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVScan
        fields = ["id", "created", "scan_status"]


class CVSerializer(serializers.ModelSerializer):
    scans = PartialCVScanSerializer(many=True, read_only=True, source="cvscan_set")

    class Meta:
        model = CV
        fields = ["id", "title", "file", "owner_id", "scans"]


class CVScanSerializer(serializers.ModelSerializer):
    cv = CVSerializer(read_only=True)

    class Meta:
        model = CVScan
        fields = "__all__"
