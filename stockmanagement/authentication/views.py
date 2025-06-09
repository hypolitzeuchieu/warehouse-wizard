from __future__ import annotations

import logging

from authentication.models import User
from authentication.permissions import IsManagerPermission
from authentication.serializers import AssignRoleSerializer
from authentication.serializers import LoginSerializer
from authentication.serializers import PasswordResetConfirmSerializer
from authentication.serializers import PasswordResetRequestSerializer
from authentication.serializers import UserSerializer
from authentication.serializers import UserUpdateSerializer
from authentication.service import UserService
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)


class UserCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=UserSerializer,
        operation_description='Create new user',
        responses={
            201: UserSerializer,
            400: 'Bad request',
            500: 'Internal server error'
        },
    )
    def post(self, request):
        try:
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                refresh_token = str(refresh)

                user_data = UserSerializer(user).data

                return Response({
                    'message': 'User created successfully',
                    'user': user_data,
                    'access': access_token,
                    'refresh': refresh_token,
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Unexpected error occurred.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=LoginSerializer,
        operation_description='Login the User',
        responses={
            200: LoginSerializer,
            400: 'Bad request',
            500: 'Internal server error'
        },
    )
    def post(self, request):
        try:
            username = request.data.get('username')
            password = request.data.get('password')

            user = authenticate(username=username, password=password)
            if user is not None:
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                refresh_token = str(refresh)

                user_data = UserSerializer(user).data

                return Response({
                    'message': 'Login successful',
                    'user': user_data,
                    'access': access_token,
                    'refresh': refresh_token,
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Invalid username or password'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except Exception as e:
            return Response(
                {'error': 'An error occurred during login', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LogoutView(APIView):
    """
    Logout endpoint to invalidate the user's token.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        raw = request.headers.get('X-Refresh-Token')
        print('raw:', raw)
        if not raw or not isinstance(raw, str):
            logger.error('No refresh token found in request headers')
            return Response({'detail': 'Refresh token is required'}, status=400)

        try:
            refresh_token = RefreshToken(raw)
            refresh_token.blacklist()
            logger.info('User logged out successfully.')
            return Response(
                {'message': 'Logout successful'},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return Response(
                {'error': f'Invalid token: {str(e)}'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class RefreshTokenView(APIView):
    """
    View to refresh the user's access token.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        responses={
            200: 'Access token refreshed successfully.',
            400: 'Bad request. Refresh token is required.',
            401: 'Invalid or expired refresh token.'
        },
        operation_description='Refresh the access token using a valid refresh token.'
    )
    def post(self, request):
        raw = request.headers.get('X-Refresh-Token')
        print('raw:', raw)
        if not raw or not isinstance(raw, str):
            logger.error('No refresh token found in request headers')
            return Response({'detail': 'Refresh token is required'}, status=400)

        try:
            old_refresh = RefreshToken(raw)
            old_refresh.blacklist()
            new_refresh = RefreshToken.for_user(request.user)
            data = {
                'access_token': str(new_refresh.access_token),
                'refresh_token': str(new_refresh),
            }
            logger.info('Tokens refreshed successfully')
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return Response(
                {'error': f'Invalid or expired refresh token: {str(e)}'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class UserManagementViewSet(viewsets.ViewSet):
    """
    ViewSet that allows managers to manage users (CRUD + role assignment).
    """

    permission_classes = [IsAuthenticated, IsManagerPermission]

    @swagger_auto_schema(
        responses={200: UserSerializer(many=True)},
        operation_description='Retrieve a list of all users. Accessible only to managers.',
    )
    def list(self, request):
        """ Retrieve all users. """
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        responses={200: UserSerializer()},
        operation_description='Retrieve a specific user by ID.',
    )
    def retrieve(self, request, pk=None):
        """ Retrieve a user by ID. """
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=UserSerializer,
        responses={201: UserSerializer()},
        operation_description='Create a new user (only managers).',
    )
    def create(self, request):
        """ Create a new user. """
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = UserService().create_users(request.user, **serializer.validated_data)
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=UserSerializer,
        responses={200: UserSerializer()},
        operation_description='Update an existing user (only managers).',
    )
    def update(self, request, pk=None):
        """ Update an existing user. """
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = UserService().update_user(
                request.user, user.id, **serializer.validated_data
            )
            return Response(UserSerializer(updated_user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={204: 'User successfully deleted'},
        operation_description='Delete an existing user (only managers).',
    )
    def destroy(self, request, pk=None):
        """ Delete a user. """
        try:
            user = User.objects.get(pk=pk)
            manager = request.user
            UserService().delete_user(manager, user.id)
            return Response(
                {'message': 'User successfully deleted'},
                status=status.HTTP_204_NO_CONTENT
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response(
                {'Unexpected error': {str(e)}}, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        request_body=AssignRoleSerializer,
        responses={
            200: 'Role successfully assigned',
            400: 'Invalid role or user not found',
        },
        operation_description='Assign a role to a user (only managers).',
    )
    @action(methods=['post'], detail=False, url_path='assign-role')
    def assign_role(self, request):
        """ Assign a role to a user. """
        try:
            serializer = AssignRoleSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                role = serializer.validated_data['role']
                user_id = serializer.validated_data['user_id']
                manager = request.user
                UserService.assign_role(manager, user_id, role)
                return Response(
                    {'message': f"Role '{role}' has been assigned to {manager.username}."},
                    status=status.HTTP_200_OK
                )

            return Response(
                {'error': 'Invalid Data'}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=UserUpdateSerializer,
        responses={
            200: 'User updated successfully.',
            400: 'Bad request.',
        },
    )
    def patch(self, request):
        user = request.user
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {'detail': 'User updated successfully.'}, status=status.HTTP_200_OK
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: UserSerializer,
            400: 'Bad request'
        }
    )
    def get(self, request):
        try:
            user = request.user
            user_serializer = UserSerializer(user)
            return Response(user_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f'Error in get user info:{str(e)}')
            return Response(
                {'error': f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=PasswordResetRequestSerializer,
        responses={200: 'Password reset link sent successfully.'},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(request)
            logger.info('Password reset link sent successfully.')
            return Response(
                {'message': 'Password reset link sent successfully.'},
                status=status.HTTP_200_OK
            )
        logger.error(f'Error in password reset link:{serializer.errors}')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=PasswordResetConfirmSerializer,
        responses={200: 'Password reset successfully.'},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            logger.info('Password reset successfully.')
            return Response(
                {'message': 'Password reset successfully.'},
                status=status.HTTP_200_OK
            )
        logger.error(f'Error in password reset confirmation: {serializer.errors}')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
