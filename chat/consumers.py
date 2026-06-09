"""
WebSocket consumer for real-time course group chat.

Each course offering has its own channel group: `course_chat_<course_offering_id>`.
Authentication is done via JWT token passed as a query-string parameter:
    ws://host/ws/course-chat/<course_id>/?token=<access_token>

Members allowed:
  - The course instructor
  - Any TA of the course
  - Any actively enrolled student
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


class CourseChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for the per-course group chat.

    On connect:
        1. Authenticate via JWT in the query string.
        2. Check the user is a member of the course (student/TA/instructor).
        3. Join the channel group for the course.
    On receive (text):
        Parse JSON `{content: "..."}`, persist the message, broadcast to the group.
    On disconnect:
        Leave the channel group.
    """

    async def connect(self):
        """Authenticate, verify membership, and accept the connection."""
        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.group_name = f'course_chat_{self.course_id}'

        # -- Authenticate via query-string JWT --
        query_string = self.scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [])

        if not token_list:
            logger.warning('WS rejected: no token provided')
            await self.close(code=4001)
            return

        token = token_list[0]
        self.user = await self._get_user_from_token(token)

        if self.user is None:
            logger.warning('WS rejected: invalid token')
            await self.close(code=4001)
            return

        # -- Verify course membership --
        allowed = await self._user_can_access_course(self.user, self.course_id)
        if not allowed:
            logger.warning(f'WS rejected: user {self.user.id} not a member of course {self.course_id}')
            await self.close(code=4003)
            return

        # Join the group and accept
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f'WS connected: user {self.user.id} joined {self.group_name}')

    async def disconnect(self, close_code):
        """Leave the channel group on disconnect."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Receive a message from the WebSocket, persist, and broadcast."""
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        content = (data.get('content') or '').strip()
        if not content:
            return

        # Persist the message
        msg = await self._save_message(self.user, self.course_id, content)
        if msg is None:
            return

        # Broadcast to all members of the course group
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'id': msg['id'],
                'sender_id': msg['sender_id'],
                'sender_name': msg['sender_name'],
                'sender_role': msg['sender_role'],
                'content': msg['content'],
                'created_at': msg['created_at'],
            }
        )

    async def chat_message(self, event):
        """Handler called by group_send. Forwards the message to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'sender_role': event['sender_role'],
            'content': event['content'],
            'created_at': event['created_at'],
        }))

    # ── Database helpers (run in thread pool via database_sync_to_async) ──

    @database_sync_to_async
    def _get_user_from_token(self, token):
        """Decode a SimpleJWT access token and return the associated User, or None."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from main.models import User
            decoded = AccessToken(token)
            user_id = decoded.get('user_id')
            return User.objects.get(id=user_id, is_active=True)
        except Exception as e:
            logger.debug(f'Token validation failed: {e}')
            return None

    @database_sync_to_async
    def _user_can_access_course(self, user, course_id):
        """
        Return True if the user is the instructor, a TA, or an active student
        of the given course offering.
        """
        from main.models import CourseOffering, Enrollment
        try:
            offering = CourseOffering.objects.get(pk=course_id)
        except CourseOffering.DoesNotExist:
            return False

        if offering.instructor_id == user.pk:
            return True
        if offering.tas.filter(pk=user.pk).exists():
            return True
        return Enrollment.objects.filter(
            student=user,
            course_offering=offering,
            status=Enrollment.Status.ACTIVE,
        ).exists()

    @database_sync_to_async
    def _save_message(self, user, course_id, content):
        """Persist the message to DB and return a plain dict (JSON-serializable)."""
        from main.models import CourseChatMessage, CourseOffering
        try:
            offering = CourseOffering.objects.get(pk=course_id)
            msg = CourseChatMessage.objects.create(
                course_offering=offering,
                sender=user,
                sender_name=user.full_name,
                sender_role=user.primary_role,
                content=content,
            )
            return {
                'id': msg.id,
                'sender_id': user.id,
                'sender_name': user.full_name,
                'sender_role': user.primary_role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
            }
        except Exception as e:
            logger.error(f'Failed to save chat message: {e}')
            return None
