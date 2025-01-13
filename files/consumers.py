import logging
import json
from channels.generic.websocket import AsyncWebsocketConsumer

# 设置日志
logger = logging.getLogger("files")       

class V2HTaskStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 定义频道名称并连接, 从 URL 中提取房间名
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"room_{self.room_name}"

        # 将当前 WebSocket 连接加入房间组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 接受 WebSocket 连接
        await self.accept()
        logger.info(f"WebSocket connected: {self.channel_name} joined {self.room_group_name}")

    async def disconnect(self, close_code):
        """
        处理 WebSocket 断开。
        """
        # 从房间组移除当前 WebSocket 连接
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.channel_name} left {self.room_group_name}")

    async def receive(self, text_data):
        """
        接收客户端通过 WebSocket 发送的消息。
        """
        logger.info(f"Received message: {text_data}")

    async def updata_task_status(self, event):
        """
        处理来自房间组的消息，并将其发送到 WebSocket 客户端。
        """
        message = event['message']
        logger.info(f"Sending message to WebSocket: {message}")
        # 发送给 WebSocket 客户端
        await self.send(text_data=json.dumps({
            'message': message,
        }))
        

