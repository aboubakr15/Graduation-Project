from django.urls import path
from .views import (
    StudentDashboardView,
    StudentCourseListView,
    StudentCourseDetailView,
    StudentToDoListView,
    StudentToDoDetailView,
    StudentProfileView,
    StudentChatBotView,
    StudentChatConversationDetailView,
    StudentChatMessagesView,
    StudentConversationView,
    StudentConversationDetailView,
    StudentEnrollmentView,
    StudentSubmissionView,
    StudentGradesView,
    StudentAssignmentListView,
    StudentNotificationsView,
    StudentMaterialDownloadView,
    StudentSubmissionDownloadView,
    StudentAssignmentDownloadView,
    # Rubric-Driven Auto Revision Engine
    StudentRubricSubmitView,
    StudentGradingResultListView,
    StudentGradingResultDetailView,
    StudentCourseChatListView,
)

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('courses/', StudentCourseListView.as_view(), name='student-course-list'),
    path('courses/<int:pk>/', StudentCourseDetailView.as_view(), name='student-course-detail'),
    path('courses/<int:pk>/chat/', StudentCourseChatListView.as_view(), name='student-course-chat'),
    path('enrollments/', StudentEnrollmentView.as_view(), name='student-enrollments'),
    path('enrollments/<int:pk>/', StudentEnrollmentView.as_view(), name='student-enrollment-detail'),
    path('assignments/', StudentAssignmentListView.as_view(), name='student-assignments'),
    path('assignments/<int:pk>/download/', StudentAssignmentDownloadView.as_view(), name='student-assignment-download'),
    path('submissions/', StudentSubmissionView.as_view(), name='student-submissions'),
    path('grades/', StudentGradesView.as_view(), name='student-grades'),
    path('notifications/', StudentNotificationsView.as_view(), name='student-notifications'),
    path('notifications/<int:pk>/', StudentNotificationsView.as_view(), name='student-notification-detail'),
    path('todo/', StudentToDoListView.as_view(), name='student-todo-list'),
    path('todo/<int:pk>/', StudentToDoDetailView.as_view(), name='student-todo-detail'),
    path('profile/', StudentProfileView.as_view(), name='student-profile'),
    path('materials/<int:pk>/download/', StudentMaterialDownloadView.as_view(), name='student-material-download'),
    path('submissions/<int:pk>/download/', StudentSubmissionDownloadView.as_view(), name='student-submission-download'),

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


