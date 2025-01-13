# routing.py
from django.urls import re_path, path
from files import consumers

websocket_urlpatterns = [
    re_path(r'ws/task_status/(?P<room_name>\w+)/$', consumers.V2HTaskStatusConsumer.as_asgi()),  # 确保路径与前端一致
]