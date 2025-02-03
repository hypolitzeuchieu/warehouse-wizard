from __future__ import annotations

from authentication.models import User
from authentication.serializers import LoginSerializer
from authentication.serializers import RegisterSalesAgentSerializer
from authentication.serializers import RegisterWholesaleClientSerializer
from authentication.serializers import UserSerializer
from django.contrib.auth import authenticate
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.tokens import Token


class RegisterWholesaleClientView(APIView):
    @swagger_auto_schema(
        request_body=RegisterWholesaleClientSerializer,
        responses={201: RegisterWholesaleClientSerializer},
    )
    def post(self, request):
        try:
            serializer = RegisterWholesaleClientSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED
                )
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return Response(
                {'error': 'unexpected error occurred.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RegisterSalesAgentView(APIView):
    @swagger_auto_schema(
        request_body=RegisterSalesAgentSerializer,
        responses={201: RegisterSalesAgentSerializer},
    )
    def post(self, request):
        try:
            serializer = RegisterSalesAgentSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED
                )
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return Response(
                {'error': 'unexpected error occurred.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserCreateView(CreateAPIView):
    """
    API View to create a user. Automatically assigns a default password '12345678'
    if the role is CLIENT and no password is provided.
    """

    permission_classes = [AllowAny]
    queryset = User.objects.all()
    serializer_class = UserSerializer


class LoginView(APIView):
    """
    API View for user login. Returns tokens and user data upon successful login.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Login user and return access and refresh tokens',
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description='Login successful', schema=LoginSerializer
            )
        },
    )
    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                username = request.data.get('username')
                password = request.data.get('password')

                user = authenticate(
                    request, username=username, password=password
                )
                print('======', user)
                if user is not None:
                    # Generate JWT tokens
                    refresh = RefreshToken.for_user(user)
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)

                    user_data = UserSerializer(user).data

                    return Response(
                        {
                            'message': 'Login successful',
                            'user': user_data,
                            'access': access_token,
                            'refresh': refresh_token,
                        },
                        status=status.HTTP_200_OK,
                    )
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

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Bearer token missing or invalid'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token_key = auth_header.split(' ')[1]

        try:
            token = Token.objects.get(key=token_key)
            token.delete()
            return Response(
                {'message': 'Logout successful'}, status=status.HTTP_200_OK
            )
        except Token.DoesNotExist:
            return Response(
                {'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED
            )
