from __future__ import annotations

from datetime import datetime
from datetime import timedelta

import jwt
from authentication.models import User
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from jwt import DecodeError
from jwt import ExpiredSignatureError
from rest_framework import serializers
from tasks.send_mail import send_email


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone_number',
            'password',
            'confirm_password',
            'role',
            'is_active'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'confirm_password': {'write_only': True}
        }

    def validate_password(self, value):

        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        confirm_password = validated_data.pop('confirm_password', None)

        if password != confirm_password:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})

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


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError('No user found with this email.')
        return value

    def save(self, request):
        email = self.validated_data['email']
        user = User.objects.filter(email=email).first()

        payload = {
            'user_id': str(user.id),
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        current_site = get_current_site(request).domain
        reset_link = f"https://{current_site}/reset-password/?token={token}"

        # Email content
        subject = 'Password Reset Request'
        message = f"Click the following link to reset your password: {reset_link}"
        html_message = render_to_string(
            'reset_password_email.html', {'reset_url': reset_link}
        )
        # Send email using the generic function
        send_email.delay(subject, message, [email], html_message=html_message)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, max_length=1024)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):

        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')

        try:
            payload = jwt.decode(
                data['token'],
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except ExpiredSignatureError:
            raise serializers.ValidationError({'token': 'the link is expired.'})
        except DecodeError:
            raise serializers.ValidationError({'token': 'Invalid token.'})

        if datetime.utcnow().timestamp() > payload['exp']:
            raise serializers.ValidationError({'token': 'the link is expired.'})

        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise serializers.ValidationError({'token': 'User not found'})

        user_last_reset = user.last_password_reset.timestamp() if (
            user.last_password_reset
        ) else 0
        if payload['iat'] < user_last_reset:
            raise serializers.ValidationError({'token': 'This link is already used.'})

        validate_password(data['new_password'], user)

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.last_password_reset = datetime.utcnow()
        user.save()


class UserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    current_password = serializers.CharField(write_only=True, required=False)
    new_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone_number',
            'role',
            'is_active',
            'current_password',
            'new_password'
        ]
        extra_kwargs = {
            'current_password': {'write_only': True},
            'new_password': {'write_only': True},
        }

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def update(self, instance, validated_data):
        current_password = validated_data.pop('current_password', None)
        new_password = validated_data.pop('new_password', None)

        if new_password:
            if not current_password:
                raise serializers.ValidationError(
                    {'current_password': 'Current password is required .'})

            if not instance.check_password(current_password):
                raise serializers.ValidationError(
                    {'current_password': 'Current password is incorrect.'}
                )

            instance.set_password(new_password)

        return super().update(instance, validated_data)
