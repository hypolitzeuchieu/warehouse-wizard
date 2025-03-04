from __future__ import annotations

from authentication.models import PasswordResetToken
from authentication.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import serializers
from tasks.send_mail import send_email


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'password', 'role', 'is_active']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_password(self, value):

        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

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


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError('No user found with this email.')
        return value

    def save(self, request):
        email = self.validated_data['email']
        user = User.objects.get(email=email)

        PasswordResetToken.objects.filter(user=user).delete()
        # Generate a unique token
        token = PasswordResetToken.objects.create(user=user)

        # Build the reset link
        current_site = get_current_site(request).domain
        reset_link = f"http://{current_site}{reverse(
            'password-reset-confirm')}?token={token.token}"

        # Email content
        subject = 'Password Reset Request'
        message = f"Click the following link to reset your password: {reset_link}"
        html_message = f"""
        <p>Hello,</p>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_link}">{reset_link}</a>
        <p>If you did not request a password reset, please ignore this email.</p>
        """

        # Send email using the generic function
        send_email.delay(subject, message, [email], html_message=html_message)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):

        token = data.get('token')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')

        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired token.')

        if reset_token.is_expired():
            raise serializers.ValidationError('This token has expired.')

        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})

        data['user'] = reset_token.user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        PasswordResetToken.objects.filter(user=user).delete()
