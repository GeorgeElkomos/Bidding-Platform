import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

# Dictionary to track active connections
active_connections = {}


def notify_users(message):
    """Send notification to all users"""
    if not any(active_connections.values()):  # No active connections
        return False

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "send_notification",
            "message": message,
        },
    )
    return True


def notify_users_by_id(message, user_ids):
    """Send notification to specific user IDs"""
    active_user_ids = [
        uid for uid in user_ids if uid in active_connections and active_connections[uid]
    ]
    if not active_user_ids:  # No active connections for these users
        return False

    channel_layer = get_channel_layer()
    for user_id in active_user_ids:
        group_name = f"user_{user_id}_notifications"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "message": message,
            },
        )
    return True


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            logger.info("WebSocket connection attempt...")

            # Get user from scope
            user = self.scope["user"]
            logger.info(
                f"User from scope: {user}, Authenticated: {user.is_authenticated}"
            )

            if user.is_authenticated:
                await self.accept()
                logger.info(f"WebSocket connection accepted for user: {user.username}")

                # Add user to their personal notification group
                self.user_group = f"user_{user.User_Id}_notifications"
                await self.channel_layer.group_add(self.user_group, self.channel_name)
                logger.info(f"Added to personal group: {self.user_group}")

                # Track active connection
                if user.User_Id not in active_connections:
                    active_connections[user.User_Id] = set()
                active_connections[user.User_Id].add(self.channel_name)
                logger.info(
                    f"Added connection to active_connections for user {user.User_Id}"
                )

                # Add to general notifications group
                self.general_group = "notifications"
                await self.channel_layer.group_add(
                    self.general_group, self.channel_name
                )
                logger.info("Added to general notifications group")

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
                logger.info("Sent connection success message")
            else:
                logger.warning("Unauthenticated connection attempt - closing")
                await self.close(code=4003)
                return

        except Exception as e:
            logger.error(f"Error in connect: {str(e)}")
            await self.close(code=4500)

    async def disconnect(self, close_code):
        try:
            # Remove from active connections
            user = self.scope["user"]
            if user.is_authenticated and user.User_Id in active_connections:
                active_connections[user.User_Id].discard(self.channel_name)
                if not active_connections[user.User_Id]:
                    del active_connections[user.User_Id]
                logger.info(f"Removed connection for user {user.User_Id}")

            # Remove from channel groups
            if hasattr(self, "user_group"):
                await self.channel_layer.group_discard(
                    self.user_group, self.channel_name
                )
            if hasattr(self, "general_group"):
                await self.channel_layer.group_discard(
                    self.general_group, self.channel_name
                )
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error in disconnect: {str(e)}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            logger.info(f"Received message: {text_data_json}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    async def send_notification(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {"type": "notification", "message": event["message"]}
                )
            )
            logger.info("Notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
