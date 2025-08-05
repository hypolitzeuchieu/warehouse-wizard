# notifications/consumer.py
from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        logger.info(f"User in scope: {self.user}, authenticated: {self.user.is_authenticated}")

        query_string = parse_qs(self.scope['query_string'].decode()) \
            if self.scope['query_string'] else {}
        token = query_string.get('token', [None])[0]

        if token:
            self.user = await self.get_user_from_token(token)
            logger.info(f"Tentative d'authentification par token,"
                        f" résultat: {self.user.is_authenticated}")

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Créer un groupe spécifique à l'utilisateur
        self.group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accepter la connexion WebSocket
        await self.accept()

        # Envoyer les notifications non lues initiales
        notifications = await self.get_unread_notifications()
        await self.send(text_data=json.dumps({
            'type': 'initial_notifications',
            'notifications': notifications
        }))

    async def disconnect(self, close_code):
        # Quitter le groupe si l'utilisateur était dans un groupe
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"❌ WebSocket déconnecté pour {self.user.id}, code: {close_code}")

    async def receive(self, text_data):
        """Traiter les messages reçus du client."""
        try:
            data = json.loads(text_data)
            command = data.get('command')

            if command == 'mark_read':
                # Marquer une notification comme lue
                notification_id = data.get('notification_id')
                success = await self.mark_notification_as_read(notification_id)
                await self.send(text_data=json.dumps({
                    'type': 'mark_read_response',
                    'notification_id': notification_id,
                    'success': success
                }))

            elif command == 'mark_all_read':
                # Marquer toutes les notifications comme lues
                count = await self.mark_all_as_read()
                await self.send(text_data=json.dumps({
                    'type': 'mark_all_read_response',
                    'count': count,
                    'success': True if not isinstance(count, dict) else False
                }))

            elif command == 'get_notifications':
                # Récupérer les notifications (avec filtre de statut optionnel)
                status = data.get('status')
                limit = data.get('limit')
                notifications = await self.get_user_notifications(status, limit)
                await self.send(text_data=json.dumps({
                    'type': 'notifications_list',
                    'notifications': notifications
                }))

            else:
                # Commande inconnue
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f"Commande inconnue: {command}"
                }))

            logger.info(f"📥 Commande {command} traitée pour utilisateur {self.user.id}")

        except json.JSONDecodeError:
            logger.error('📥 Format JSON invalide reçu')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Format de message invalide'
            }))
        except Exception as e:
            logger.error(f"📥 Erreur lors du traitement du message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Erreur serveur: {str(e)}'
            }))

    async def send_notification(self, event):
        """
        Handler appelé lorsqu'une notification est envoyée au groupe.
        Cette méthode est invoquée par l'appel à group_send dans le service.
        """
        # Envoi direct des données au client WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            **event['data']
        }))
        logger.debug(f"📤 Notification envoyée à l'utilisateur {self.user.id}")

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Récupérer l'utilisateur à partir du token JWT."""
        try:
            # Nettoyer le format "Bearer <token>" si présent
            if token.startswith('Bearer '):
                token = token.split(' ')[1]

            # Décodage du token JWT
            from django.conf import settings
            import jwt

            decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = decoded_data.get('user_id')

            if user_id:
                User = get_user_model()
                return User.objects.get(id=user_id)
            else:
                return AnonymousUser()
        except Exception as e:
            logger.error(f"Erreur d'authentification par token JWT: {str(e)}")
            return AnonymousUser()

    @database_sync_to_async
    def get_unread_notifications(self):
        """Récupérer les notifications non lues de l'utilisateur."""
        from apps.notifications.service import NotificationService

        # Utiliser le service existant
        notifications = NotificationService.get_user_notifications(
            user_id=self.user.id,
            status='UNREAD',
            limit=10  # Limiter à 10 dernières notifications
        )

        # Convertir en liste si ce n'est pas une erreur
        if not isinstance(notifications, dict):
            # Formatter pour JSON
            return [
                {
                    'id': str(notif.id),
                    'notification_type': notif.notification_type,
                    'message': notif.message,
                    'product': notif.product.name if notif.product else 'N/A',
                    'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': notif.status
                }
                for notif in notifications
            ]
        return []

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Marquer une notification comme lue."""
        from apps.notifications.service import NotificationService

        result = NotificationService.mark_as_read(notification_id)
        return not isinstance(result, dict)  # True si pas d'erreur

    @database_sync_to_async
    def mark_all_as_read(self):
        """Marquer toutes les notifications de l'utilisateur comme lues."""
        from apps.notifications.service import NotificationService

        return NotificationService.mark_all_as_read(self.user.id)

    @database_sync_to_async
    def get_user_notifications(self, status=None, limit=None):
        """Récupérer les notifications de l'utilisateur."""
        from apps.notifications.service import NotificationService

        notifications = NotificationService.get_user_notifications(
            user_id=self.user.id,
            status=status,
            limit=limit
        )

        # Convertir en liste si ce n'est pas une erreur
        if not isinstance(notifications, dict):
            # Formatter pour JSON
            return [
                {
                    'id': str(notif.id),
                    'notification_type': notif.notification_type,
                    'message': notif.message,
                    'product': notif.product.name if notif.product else 'N/A',
                    'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': notif.status
                }
                for notif in notifications
            ]
        return []
