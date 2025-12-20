import django_filters

from apps.cvprep.models import CV, CVScan

from rest_framework.pagination import PageNumberPagination

# https://django-filter.readthedocs.io/en/stable/guide/usage.html


class CVFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = CV
        fields = ["title"]
        # fields = {"title": ["exact", "contains"]}


class CVScanFilter(django_filters.FilterSet):
    # title = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = CVScan
        fields = {"scan_status": ["exact"]}


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 10
