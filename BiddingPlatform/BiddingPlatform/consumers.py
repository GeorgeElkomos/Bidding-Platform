import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def notify_users(message):
    """Send notification to all users"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "send_notification",
            "message": message,
        },
    )


def notify_users_by_id(message, user_ids):
    """Send notification to specific user IDs"""
    channel_layer = get_channel_layer()
    for user_id in user_ids:
        group_name = f"user_{user_id}_notifications"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "message": message,
            },
        )


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

        # Get user ID from scope (make sure it's authenticated)
        user = self.scope["user"]
        if user.is_authenticated:
            # Add user to their personal notification group
            self.user_group = f"user_{user.User_Id}_notifications"
            await self.channel_layer.group_add(self.user_group, self.channel_name)

            # Add to general notifications group
            self.general_group = "notifications"
            await self.channel_layer.group_add(self.general_group, self.channel_name)

            # Send initial connection success message
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "connection_established",
                        "message": "Connected to notification server",
                        "user_id": user.User_Id,
                    }
                )
            )
        else:
            # Close connection if user is not authenticated
            await self.close()

    async def disconnect(self, close_code):
        # Clean up on disconnect
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if hasattr(self, "general_group"):
            await self.channel_layer.group_discard(
                self.general_group, self.channel_name
            )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            print("Received message:", text_data_json)
        except Exception as e:
            print("Error processing message:", str(e))

    async def send_notification(self, event):
        # Send notification to WebSocket
        await self.send(
            text_data=json.dumps({"type": "notification", "message": event["message"]})
        )
