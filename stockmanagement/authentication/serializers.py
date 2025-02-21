from __future__ import annotations

from authentication.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'password', 'role', 'is_active']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    user_id = serializers.CharField(required=True)

    def validate_role(self, value):
        """ Assurer que le rôle est valide avant l'assignation. """
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError('Invalid role.')
        return value


class UserManageSerializer(serializers.Serializer):
    user_id = serializers.CharField(required=True)
