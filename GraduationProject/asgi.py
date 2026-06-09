"""
ASGI config for GraduationProject — supports both HTTP (Django) and WebSocket (Channels).
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')

# Initialise Django before importing anything that touches models.
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    # Standard HTTP requests handled by Django
    'http': django_asgi_app,
    # WebSocket requests routed through our chat consumer
    # AllowedHostsOriginValidator checks the Origin header against ALLOWED_HOSTS
    'websocket': AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
