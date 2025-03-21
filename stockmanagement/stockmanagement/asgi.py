# asgi.py
from __future__ import annotations

from channels.routing import ProtocolTypeRouter
from channels.routing import URLRouter
from django.core.asgi import get_asgi_application
from notifications.middleware import JWTAuthMiddlewareStack
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
