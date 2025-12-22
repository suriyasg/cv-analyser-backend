import os

import pymupdf
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import exceptions, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_auth.apis.common.serializers import UserSerializer
from apps.users.choices import UserTypes
from config.settings import MEDIA_ROOT, MEDIA_URL

from .models import CV, CVOwner, CVScan
from .serializers import (
    CVOwnerSerializer,
    CVScanSerializer,
    CVSerializer,
    UserCVOwnerSerializer,
)
from .tasks import analyze_cv_task

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
                urlPath = serializer.data.get("file")
                if urlPath is None:
                    raise exceptions.ParseError(detail="file name can not be none", code="error")

                path = urlPath.replace(MEDIA_URL, "")
                fileLocation = os.path.join(MEDIA_ROOT, path)

                doc = pymupdf.open(fileLocation)

                text = ""
                # iterate the document pages
                for page in doc:
                    # get plain text encoded as UTF-8
                    text += page.get_text()

            except Exception:
                return Response(
                    {"message": "could not parse text from cv, CV saved"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )

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
                return Response(
                    {"message": "could not save text from cv"},
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CVOwnerAPIView(APIView):
    # permission_classes = []

    def get_authenticators(self):
        if self.request and self.request.method == "POST":
            return []
        else:
            return super().get_authenticators()

    def get_permissions(self):
        if self.request and self.request.method == "POST":
            return [AllowAny()]
        else:
            return super().get_permissions()

    def get(self, request):
        cvowners = CVOwner.objects.all()
        serializer = UserCVOwnerSerializer(instance=cvowners, many=True)
        return Response(data=serializer.data)

    # creates A User (which is used for auth) and creates CVOwner
    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")
        if not password or not username:
            return Response(
                {"message": "user name or password not given"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            user_type=UserTypes.CVOWNER,
        )
        print("user", user)
        if not user:
            return Response({"message": "could not create user"}, status=status.HTTP_400_BAD_REQUEST)

        cvowner_serializer = CVOwnerSerializer(data={"user": user.id})
        if not cvowner_serializer.is_valid():
            return Response(cvowner_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        cvowner_serializer.save()
        user_serializer = UserSerializer(instance=user)
        return Response(user_serializer.data, status=status.HTTP_400_BAD_REQUEST)


class CVOwnerListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = CVOwner.objects.all()
    serializer_class = CVOwnerSerializer
