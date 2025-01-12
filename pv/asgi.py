"""
ASGI config for pv project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import django
import pv.routing
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pv.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # 处理HTTP请求
    "websocket": AuthMiddlewareStack(  # 处理WebSocket连接
        URLRouter(
            pv.routing.websocket_urlpatterns  # 将路由传递给 WebSocket 路由
        )
    ),
})