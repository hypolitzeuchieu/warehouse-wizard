from __future__ import annotations

import logging

from authentication.models import RevokedToken
from django.http import JsonResponse
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


class TokenRevocationMiddleware(MiddlewareMixin):

    def process_request(self, request):

        resolver_match = resolve(request.path)
        ignored_views = ['LogoutView']
        if (resolver_match.view_name in ignored_views
                or request.path.startswith('/api/v1/logout/')):
            return None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1]

            try:
                AccessToken(token_str)

                if RevokedToken.is_revoked(token_str):
                    logger.warning('Token has been revoked.')
                    return JsonResponse(
                        {'error': 'Token has been revoked.'},
                        status=401
                    )

            except Exception as e:
                logger.error(f"Invalid or malformed token: {str(e)}")
                return JsonResponse(
                    {'error': 'Invalid token.'},
                    status=401
                )

        return None
