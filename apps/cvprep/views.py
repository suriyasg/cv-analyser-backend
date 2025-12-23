import os
import uuid

import pymupdf
from django.contrib.auth import get_user_model
from django.http import FileResponse
from rest_framework import exceptions, generics, mixins, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.cvprep.filter import StandardResultsSetPagination
from apps.utils.permissions import IsAdminORCVOwner, IsAdminORCVScanOwner, IsSameUser
from config import settings
from config.settings import MEDIA_ROOT, MEDIA_URL

from .models import CV, CVOwner, CVScan
from .serializers import CVScanSerializer, CVSerializer
from .tasks import analyze_cv_task

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def serve_cvs(request: Request):
    if request and request.user:
        cv_owner = generics.get_object_or_404(CVOwner, user=request.user)
        cv = generics.get_object_or_404(CV, owner=cv_owner, file=request.path.strip(settings.MEDIA_URL))
        return FileResponse(
            cv.file.open("rb"),
            content_type="application/pdf",
            as_attachment=False,  # True → download, False → open in browser
            filename=os.path.basename(cv.file.name),
        )
    else:
        raise exceptions.NotAuthenticated(detail="user data not available")


class CVScanListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CVScanSerializer
    filterset_fields = ["scan_status"]

    def get_queryset(self):
        return CVScan.objects.prefetch_related("cv")

    def get(self, request, *args, **kwargs):
        if self.request.user.is_staff:
            return super().get(request, *args, **kwargs)
        else:
            raise exceptions.NotAuthenticated(detail="You are not allowed")

    def post(self, request, *args, **kwargs):
        cv_id = request.data.get("cv")
        job_description = request.data.get("job_description")
        scan_title = request.data.get("title")
        print(cv_id)
        print(job_description)
        cv = CV.objects.get(id=cv_id)
        if cv.owner.user.id == request.user.id:
            new_scan = CVScanSerializer(
                data={
                    "job_description": job_description,
                    "scan_status": CVScan.ScanStatus.PENDING,
                    "title": scan_title,
                }
            )
            if new_scan.is_valid():
                new_scan.save(cv=cv)
                analyze_cv_task.delay(cv_id, new_scan.data.get("id"))
            else:
                return Response(data=new_scan.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            raise exceptions.NotAuthenticated(detail="You are not allowed to scan other user cvs")

        return Response(data=new_scan.data, status=status.HTTP_201_CREATED)


class CVScanDetailView(generics.RetrieveAPIView, generics.UpdateAPIView):
    permission_classes = [IsAdminORCVScanOwner]
    queryset = CVScan.objects.all()
    serializer_class = CVScanSerializer


class CVViewSet(mixins.ListModelMixin, GenericViewSet):
    permission_classes = [IsSameUser]
    serializer_class = CVSerializer
    queryset = CV.objects.all()

    from rest_framework import filters

    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]

    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        else:
            user_id = self.request.user.id
            if user_id is None or not isinstance(user_id, (str, uuid.UUID)):
                raise exceptions.ParseError(detail="could not get proper user id", code="error")
            owner_id = CVOwner.objects.get(user_id=user_id)
            return self.queryset.filter(owner_id=owner_id).prefetch_related("cvscan_set")
            # TODO:
            # N+1 query
            # test with bigger database and see performace difference
            # as in this small database time difference is inconsistance
            # return self.queryset.filter(owner_id=owner_id)

    def create(self, request):
        data_with_owner = request.data

        serializer = CVSerializer(data=data_with_owner)
        if serializer.is_valid():
            # serializer.save()
            serializer.save(owner=request.user.cvowner)

            urlPath = serializer.data.get("file")
            if urlPath is None:
                raise exceptions.ValidationError(detail="file name can not be none", code="error")

            try:
                path = urlPath.replace(MEDIA_URL, "")
                fileLocation = os.path.join(MEDIA_ROOT, path)

                doc = pymupdf.open(fileLocation)

                text = ""
                # iterate the document pages
                for page in doc:
                    # get plain text encoded as UTF-8
                    text += page.get_text()

            except Exception:
                raise exceptions.ParseError(detail="Could not parse text from CV, CV is Saved", code="error")

            pk = serializer.data.get("id")
            if pk is None:
                return Response(
                    {"message": "could not get id of CV"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            instance = CV.objects.get(pk=pk)
            update_serializer = CVSerializer(instance=instance, data={"cv_text": text}, partial=True)

            if update_serializer.is_valid():
                update_serializer.save()
                cv_scan = CVScan(
                    scan_status=CVScan.ScanStatus.PENDING,
                    cv=instance,
                    job_description=request.data.get("job_description", ""),
                    title=request.data.get("scan_title", ""),
                )
                cv_scan.save()
                cv_scan_serializer = CVScanSerializer(instance=cv_scan)
                analyze_cv_task.delay(update_serializer.data.get("id"), cv_scan_serializer.data.get("id"))
                return Response(
                    {
                        "cv": update_serializer.data,
                        "cv_scan": cv_scan_serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                Response(update_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CVDetailViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAdminORCVOwner]
    queryset = CV.objects.all()
    serializer_class = CVSerializer
