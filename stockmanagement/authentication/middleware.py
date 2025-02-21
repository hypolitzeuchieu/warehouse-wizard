from __future__ import annotations

from authentication.models import RevokedToken
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken


class TokenRevocationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Bearer '):
            access_token = auth_header.split(' ')[1]

            try:
                token = AccessToken(access_token)

                if RevokedToken.objects.filter(token=token).exists():
                    return JsonResponse(
                        {'error': 'Token missing or has been revoked'},
                        status=401
                    )
            except Exception as e:
                return JsonResponse(
                    {'error': f'An unexpected error occurred {str(e)}'},
                    status=500
                )
            return None
