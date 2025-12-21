from rest_framework import permissions

from apps.cvprep.models import CVOwner
from apps.users.choices import UserTypes
from apps.users.models import User


class IsSameUser(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsAdminORCVOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """

    def has_object_permission(self, request, view, obj):
        # Write permissions are only allowed to the owner of the snippet.
        print("checking has_object_permission")
        # print("obj id", obj.cv.owner.user_id)
        # print("user id", request.user.id)
        return CVOwner.objects.get(id=obj.owner_id).user.id == request.user.id or request.user.is_superuser


class IsAdminORCVScanOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """

    def has_object_permission(self, request, view, obj):
        # Write permissions are only allowed to the owner of the snippet.
        print("checking has_object_permission")
        # print("obj id", obj.cv.owner.user_id)
        # print("user id", request.user.id)
        return obj.cv.owner.user_id == request.user.id or request.user.is_superuser


class IsCustomer(permissions.DjangoModelPermissions):
    """A customer that is enrolled to a branch."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, User)
            and request.user.user_type == UserTypes.CUSTOMER
        )
