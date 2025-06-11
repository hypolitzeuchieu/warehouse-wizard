from __future__ import annotations

from authentication.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
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

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        current_site = get_current_site(request).domain
        reset_link = f"https://{current_site}/reset-password/?uid={uid}&token={token}"

        subject = 'Password Reset Request'
        message = f"Click the following link to reset your password: {reset_link}"
        html_message = render_to_string(
            'reset_password_email.html', {'reset_url': reset_link}
        )
        send_email.delay(subject, message, [email], html_message=html_message)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, max_length=1024)
    uid = serializers.CharField(required=True, max_length=64)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):

        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')

        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({'uid': 'Invalid user ID'})

        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError({'token': 'Invalid token or link expired.'})
        validate_password(data['new_password'], user)

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.last_password_reset = timezone.now()
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
