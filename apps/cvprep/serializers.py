# myapp/serializers.py
import json

from rest_framework import serializers

from apps.api_auth.apis.common.serializers import UserSerializer

from .models import CV, CVOwner, CVScan


class UserCVOwnerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CVOwner
        fields = "__all__"


class CVOwnerSerializer(serializers.ModelSerializer):
    # cv_set = serializers.PrimaryKeyRelatedField(many=True, queryset=CV.objects.all())

    class Meta:
        model = CVOwner
        fields = "__all__"


class PartialCVScanSerializer(serializers.ModelSerializer):
    # uses auto generated get_<choice field name>_display field or method??
    scan_status = serializers.CharField(
        source="get_scan_status_display",
        read_only=True,
    )

    class Meta:
        model = CVScan
        fields = ["id", "title", "created", "scan_status"]


class CVSerializer(serializers.ModelSerializer):
    scans = PartialCVScanSerializer(many=True, read_only=True, source="cvscan_set")
    file = serializers.SerializerMethodField()

    class Meta:
        model = CV
        fields = ["id", "title", "file", "cv_text", "owner_id", "scans"]

    def get_file(self, obj):
        if obj.file:
            return obj.file.url
        return None


class CVScanSerializer(serializers.ModelSerializer):
    cv = CVSerializer(read_only=True)
    identified_hard_skills = serializers.SerializerMethodField()
    identified_soft_skills = serializers.SerializerMethodField()
    hard_skill_analyser_output = serializers.SerializerMethodField()
    soft_skill_analyser_output = serializers.SerializerMethodField()
    summary_generator_output = serializers.SerializerMethodField()
    # scan_status = serializers.ChoiceField(choices=CVScan.ScanStatus.choices)
    # uses auto generated get_<choice field name>_display field or method??
    scan_status = serializers.CharField(
        source="get_scan_status_display",
        read_only=True,
    )

    class Meta:
        model = CVScan
        fields = "__all__"

    def get_identified_hard_skills(self, obj):
        if obj.identified_hard_skills:
            return json.loads(obj.identified_hard_skills)
        return {}

    def get_identified_soft_skills(self, obj):
        if obj.identified_soft_skills:
            return json.loads(obj.identified_soft_skills)
        return {}

    def get_hard_skill_analyser_output(self, obj):
        if obj.hard_skill_analyser_output:
            return json.loads(obj.hard_skill_analyser_output)
        return {}

    def get_soft_skill_analyser_output(self, obj):
        if obj.soft_skill_analyser_output:
            return json.loads(obj.soft_skill_analyser_output)
        return {}

    def get_summary_generator_output(self, obj):
        if obj.summary_generator_output:
            return json.loads(obj.summary_generator_output)
        return {}
