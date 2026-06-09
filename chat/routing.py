"""WebSocket URL routing for the chat app."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/course-chat/(?P<course_id>\d+)/$', consumers.CourseChatConsumer.as_asgi()),
]
