import os
from django.views import View
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from apps.api_auth.apis.common.serializers import UserSerializer
from config.settings import MEDIA_ROOT, MEDIA_URL
from .serializers import CVOwnerSerializer, CVSerializer, CVScanSerializer
from rest_framework import status, mixins, generics
from .models import CV, CVOwner, CVScan

import pymupdf
from .tasks import analyze_cv_task

from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponse, HttpResponseBase, JsonResponse
from django.middleware.csrf import get_token

from apps.utils.permissions import IsAdminORCVScanOwner, IsSameUser, IsAdminORCVOwner
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes

from django.contrib.auth import get_user_model

User = get_user_model()


@ensure_csrf_cookie
def get_csrf(request):
    token = get_token(request)
    return JsonResponse({"csrftoken": token})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_logged_in_user(request):
    print("AUTH USER OBJ:", request.user)
    print("AUTH ID:", request.user.id)
    print("AUTH USERNAME:", request.user.username)
    print("IS AUTH:", request.user.is_authenticated)
    user = {"id": request.user.id, "username": request.user.username}
    return JsonResponse(user, safe=False)


class CVUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        data_with_owner = request.data
        print("user", request.user)
        data_with_owner["owner"] = CVOwner.objects.get(user_id=request.user.id).id
        serializer = CVSerializer(data=data_with_owner)
        if serializer.is_valid():
            serializer.save()

            try:
                urlPath: str = serializer.data.get("file")
                path = urlPath.replace(MEDIA_URL, "")
                fileLocation = os.path.join(MEDIA_ROOT, path)

                doc = pymupdf.open(fileLocation)

                text = ""
                # iterate the document pages
                for page in doc:
                    # get plain text encoded as UTF-8
                    text += page.get_text()

            except:
                return Response(
                    {"message": "could not parse text from cv, CV saved"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )

            instance = CV.objects.get(pk=serializer.data.get("id"))
            update_serializer = CVSerializer(
                instance=instance, data={"cv_text": text}, partial=True
            )
            if update_serializer.is_valid():
                update_serializer.save()
                cv_scan = CVScan(
                    scan_status="PENDING",
                    cv=instance,
                    job_description=request.data.get("job_description", ""),
                )
                cv_scan.save()
                cv_scan_serializer = CVScanSerializer(instance=cv_scan)
                analyze_cv_task.delay(
                    update_serializer.data.get("id"), cv_scan_serializer.data.get("id")
                )
                return Response(
                    {
                        "cv": update_serializer.data,
                        "cv_scan": cv_scan_serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"message": "could not save text from cv"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateCVOwner(APIView):
    # creates A User (which is used for auth) and creates CVOwner
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        if not password or not username:
            return Response(
                {"message": "user name or password not given"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(username=username, password=password)
        print("user", user)
        if not user:
            return Response(
                {"message": "could not create user"}, status=status.HTTP_400_BAD_REQUEST
            )

        cvowner_serializer = CVOwnerSerializer(data={"user": user.id})
        if not cvowner_serializer.is_valid():
            return Response(
                cvowner_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        cvowner_serializer.save()
        user_serializer = UserSerializer(instance=user)
        return Response(user_serializer.data, status=status.HTTP_400_BAD_REQUEST)


class CVScanListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = CVScan.objects.all()
    serializer_class = CVScanSerializer


class CVScanDetailView(generics.RetrieveAPIView, generics.UpdateAPIView):
    permission_classes = [IsAdminORCVScanOwner]
    queryset = CVScan.objects.all()
    serializer_class = CVScanSerializer


class CVOwnerListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = CVOwner.objects.all()
    serializer_class = CVOwnerSerializer


class CVViewSet(GenericViewSet):
    permission_classes = [IsSameUser]
    serializer_class = CVSerializer
    queryset = CV.objects.all()

    def list(self, request):
        owner_id = CVOwner.objects.get(user_id=request.user.id)
        user_scans = self.queryset.filter(owner_id=owner_id)
        serializer = self.get_serializer(user_scans, many=True)
        return Response(data=serializer.data)

    def create(self, request):
        data_with_owner = request.data

        # passing owner_id to serializer did not work, manually passing owner to .save() works why?
        # data_with_owner["owner_id"] = CVOwner.objects.get(user_id=request.user.id).id
        # data_with_owner["owner_id"] = request.user.cvowner.id

        serializer = CVSerializer(data=data_with_owner)
        if serializer.is_valid():
            # serializer.save()
            serializer.save(owner=request.user.cvowner)

            try:
                urlPath: str = serializer.data.get("file")
                path = urlPath.replace(MEDIA_URL, "")
                fileLocation = os.path.join(MEDIA_ROOT, path)

                doc = pymupdf.open(fileLocation)

                text = ""
                # iterate the document pages
                for page in doc:
                    # get plain text encoded as UTF-8
                    text += page.get_text()

            except:
                return Response(
                    {"message": "could not parse text from cv, CV saved"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )

            instance = CV.objects.get(pk=serializer.data.get("id"))
            update_serializer = CVSerializer(
                instance=instance, data={"cv_text": text}, partial=True
            )
            if update_serializer.is_valid():
                update_serializer.save()
                cv_scan = CVScan(
                    scan_status="PENDING",
                    cv=instance,
                    job_description=request.data.get("job_description", ""),
                )
                cv_scan.save()
                cv_scan_serializer = CVScanSerializer(instance=cv_scan)
                analyze_cv_task.delay(
                    update_serializer.data.get("id"), cv_scan_serializer.data.get("id")
                )
                return Response(
                    {
                        "cv": update_serializer.data,
                        "cv_scan": cv_scan_serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"message": "could not save text from cv"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )
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

    # def partial_update(self, request, *args, **kwargs):
    #     print(request.user)


class CVDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminORCVOwner]
    queryset = CV.objects.all()
    serializer_class = CVSerializer
