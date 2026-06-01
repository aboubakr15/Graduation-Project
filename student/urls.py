from django.urls import path
from .views import (
    StudentDashboardView,
    StudentCourseListView,
    StudentCourseDetailView,
    StudentToDoListView,
    StudentProfileView,
    StudentChatBotView,
    StudentChatConversationDetailView,
    StudentChatMessagesView,
    StudentConversationView,
    StudentConversationDetailView,
    StudentEnrollmentView,
    StudentSubmissionView,
    StudentGradesView,
    StudentNotificationsView,
    StudentMaterialDownloadView,
    # Rubric-Driven Auto Revision Engine
    StudentRubricSubmitView,
    StudentGradingResultListView,
    StudentGradingResultDetailView,
)

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('courses/', StudentCourseListView.as_view(), name='student-course-list'),
    path('courses/<int:pk>/', StudentCourseDetailView.as_view(), name='student-course-detail'),
    path('enrollments/', StudentEnrollmentView.as_view(), name='student-enrollments'),
    path('enrollments/<int:pk>/', StudentEnrollmentView.as_view(), name='student-enrollment-detail'),
    path('submissions/', StudentSubmissionView.as_view(), name='student-submissions'),
    path('grades/', StudentGradesView.as_view(), name='student-grades'),
    path('notifications/', StudentNotificationsView.as_view(), name='student-notifications'),
    path('notifications/<int:pk>/', StudentNotificationsView.as_view(), name='student-notification-detail'),
    path('todo/', StudentToDoListView.as_view(), name='student-todo-list'),
    path('profile/', StudentProfileView.as_view(), name='student-profile'),
    path('materials/<int:pk>/download/', StudentMaterialDownloadView.as_view(), name='student-material-download'),

    # ── Chat ────────────────────────────────────────────────────────────────
    # Send message / list conversations (legacy GET on same view)
    path('chat/', StudentChatBotView.as_view(), name='student-chat'),
    # Get a specific conversation with its messages
    path('chat/<int:pk>/', StudentChatConversationDetailView.as_view(), name='student-chat-detail'),
    # Get messages for a conversation via query param: ?conversation_id=X
    path('chat/messages/', StudentChatMessagesView.as_view(), name='student-chat-messages'),

    # Conversation management (create, list, rename, delete)
    path('conversations/', StudentConversationView.as_view(), name='student-conversations'),
    path('conversations/<int:pk>/', StudentConversationDetailView.as_view(), name='student-conversation-detail'),

    # ── Rubric-Driven Auto Revision Engine ──────────────────────────────
    path('rubric-submit/', StudentRubricSubmitView.as_view(), name='student-rubric-submit'),
    path('grading-results/', StudentGradingResultListView.as_view(), name='student-grading-results'),
    path('grading-results/<int:pk>/', StudentGradingResultDetailView.as_view(), name='student-grading-result-detail'),
]


