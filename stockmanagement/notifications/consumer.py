from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

import jwt
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from stockmanagement import settings

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Récupérer le token depuis l'URL
        query_string = self.scope['query_string'].decode()
        token_key = parse_qs(query_string).get('token', [None])[0]

        if token_key:
            # Valider le token et récupérer l'utilisateur
            self.user = await sync_to_async(self.get_user)(token_key)
        else:
            self.user = AnonymousUser()

        if self.user.is_authenticated:
            self.group_name = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"✅ WebSocket connecté pour {self.user.username}")
        else:
            logger.info('❌ Utilisateur non authentifié, connexion refusée')
            await self.close()

    User = get_user_model()

    def get_user(self, token_key):
        try:
            # Décoder le token en utilisant la clé secrète du projet et l'algorithme approprié
            payload = jwt.decode(token_key, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id') or payload.get('user')  # Adapte selon ton payload
            if user_id:
                return self.User.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, self.User.DoesNotExist) as e:
            logger.info(f"Erreur lors du décodage du token : {str(e)}")
        return AnonymousUser()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        logger.info(f"📥 Message reçu : {data}")
        await self.send(text_data=json.dumps({'message': 'Message reçu'}))

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event['data']))
