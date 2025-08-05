# notifications/middleware.py
from __future__ import annotations

from urllib.parse import parse_qs

import jwt
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()


@database_sync_to_async
def get_user_from_jwt(token_key):
    try:
        # Décodage du token JWT
        decoded_data = jwt.decode(token_key, settings.SECRET_KEY, algorithms=['HS256'])
        # Récupérer l'ID de l'utilisateur depuis le token décodé
        user_id = decoded_data.get('user_id')

        if user_id:
            # Récupérer l'utilisateur par son ID
            return User.objects.get(id=user_id)
        else:
            return AnonymousUser()
    except (jwt.DecodeError, jwt.ExpiredSignatureError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)

        # Tenter d'obtenir le token depuis les paramètres d'URL
        token_key = query_params.get('token', [None])[0]

        if token_key:
            # Nettoyer le format "Bearer <token>" si présent
            if token_key.startswith('Bearer '):
                token_key = token_key.split(' ')[1]

            # Authentifier l'utilisateur avec JWT
            scope['user'] = await get_user_from_jwt(token_key)
        else:
            # Utiliser l'utilisateur qui existe déjà
            # dans le scope (session auth) ou AnonymousUser
            if 'user' not in scope:
                scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
