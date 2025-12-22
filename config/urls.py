from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular import views as spec_views
from rest_framework.routers import DefaultRouter

from apps.api_auth.apis.common.views import MeCommonViewSet, TokenCommonViewSet
from apps.api_auth.apis.customer.views import AuthCustomerViewSet
from apps.api_auth.apis.cvowner.views import AuthCVOwnerViewSet
from apps.cvprep.views import (
    CVDetailViewSet,
    CVOwnerAPIView,
    CVOwnerListView,
    CVScanDetailView,
    CVScanListView,
    CVUploadView,
    CVViewSet,
    get_csrf,
    get_logged_in_user,
    serve_cvs,
)
from apps.dashboard.apis.common.views import GlobalSettingsCommonViewSet
from apps.users.apis.customer.views import CustomerViewSet
from apps.utils.views import PrefixedDefaultRouter
from config.schema import SpectacularRapiDocView

spectacular_api_view = spec_views.SpectacularAPIView.as_view()
spectacular_api_docs_view = SpectacularRapiDocView.as_view(url_name="schema")


customer_router = PrefixedDefaultRouter("customer")
customer_router.register("auth", AuthCustomerViewSet, basename="auth")
customer_router.register("customers", CustomerViewSet, basename="customers")

cvowner_router = PrefixedDefaultRouter("cvowner")
cvowner_router.register("auth", AuthCVOwnerViewSet, basename="auth")

cv_router = DefaultRouter()
cv_router.register("", CVViewSet, basename="cvs")

cv_detail_router = DefaultRouter()
cv_detail_router.register("", CVDetailViewSet, basename="cvsdetails")


common_router = DefaultRouter()
common_router.register("auth/token", TokenCommonViewSet, basename="common-auth-token")
common_router.register("auth", MeCommonViewSet, basename="common-auth")
common_router.register("settings", GlobalSettingsCommonViewSet, basename="common-settings")

urlpatterns = [
    path("api-auth/", include("rest_framework.urls"), name="rest_framework"),
    path("csrf/", get_csrf, name="get-csrf"),
    path("me/", get_logged_in_user, name="me"),
    path("api/v1/", include(customer_router.urls)),
    path("api/v1/", include(cvowner_router.urls)),
    path("api/v1/", include(common_router.urls)),
    path("api/schema/", spectacular_api_view, name="schema"),
    path("api/docs/", spectacular_api_docs_view, name="api_docs"),
    # Admin site URLs
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="admin:index")),
    path("upload/", CVUploadView.as_view(), name="file_upload"),
    path(
        "scans/",
        view=CVScanListView.as_view(),
        name="scan_results",
    ),
    path(
        "scans/<int:pk>",
        view=CVScanDetailView.as_view(),
        name="scan_results",
    ),
    path("cvs/", include(cv_router.urls)),
    path("cvs/", include(cv_detail_router.urls)),
    # path("cvs/<int:pk>", view=CVDetailView.as_view(), name="cv"),
    path("apiview/cvowners/", view=CVOwnerAPIView.as_view(), name="apiview-cvowners"),
    path(
        "listcreateapiview/cvowners/",
        view=CVOwnerListView.as_view(),
        name="listcreateapiview-cvowners",
    ),
    # redundant and tests
    # path("status/", CVScanViewSet.as_view({"get": "list"}), name="status"),
    # path("target/", view=TargetView.as_view(), name="targer"),
]

if settings.DEBUG:
    # order is important to serve files with proper permission in dev
    urlpatterns += [
        re_path(r"media/uploads/*", view=serve_cvs, name="protected-cvs"),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.USE_DEBUG_TOOLBAR:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
