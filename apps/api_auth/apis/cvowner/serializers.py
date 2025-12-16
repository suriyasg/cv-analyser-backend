from rest_framework import serializers

from apps.users.models import User


class UserAuthCVOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "user_type", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id", "user_type", "username"]


class LoginCVOwnerSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField()


class LoginCVOwnerResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserAuthCVOwnerSerializer()
