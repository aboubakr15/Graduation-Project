from django.urls import path
from .views import (
    InstructorDashboardView,
    InstructorProfileView,
    CourseOfferingListView,
    CourseOfferingDetailView,
    MaterialListView,
    MaterialDetailView,
    MaterialDownloadView,
    AssignmentListView,
    AssignmentDetailView,
    SubmissionListView,
    SubmissionGradeView,
    StudentListView,
    AnnouncementListView,
    AnnouncementDetailView,
    ChatConversationListView,
    ChatMessageListView,
    InstructorChatAIView,
    InstructorConversationListView,
    InstructorConversationDetailView,
    NotificationListView,
    RubricAssignmentListCreateView,
    RubricAssignmentDetailView,
    RegradeSubmissionView,
    InstructorGradingResultView,
)

urlpatterns = [
    # Dashboard & Profile
    path('dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('profile/', InstructorProfileView.as_view(), name='instructor-profile'),
    
    # Course Offerings
    path('courses/', CourseOfferingListView.as_view(), name='instructor-courses'),
    path('courses/<int:pk>/', CourseOfferingDetailView.as_view(), name='instructor-course-detail'),
    
    # Materials
    path('materials/', MaterialListView.as_view(), name='instructor-materials'),
    path('materials/<int:pk>/', MaterialDetailView.as_view(), name='instructor-material-detail'),
    path('materials/<int:pk>/download/', MaterialDownloadView.as_view(), name='instructor-material-download'),
    
    # Assignments
    path('assignments/', AssignmentListView.as_view(), name='instructor-assignments'),
    path('assignments/<int:pk>/', AssignmentDetailView.as_view(), name='instructor-assignment-detail'),
    
    # Submissions
    path('submissions/', SubmissionListView.as_view(), name='instructor-submissions'),
    path('submissions/<int:pk>/grade/', SubmissionGradeView.as_view(), name='instructor-submission-grade'),
    
    # Students
    path('students/', StudentListView.as_view(), name='instructor-students'),
    
    # Announcements
    path('announcements/', AnnouncementListView.as_view(), name='instructor-announcements'),
    path('announcements/<int:pk>/', AnnouncementDetailView.as_view(), name='instructor-announcement-detail'),

    # ── Chat ─────────────────────────────────────────────────────────────────
    # Monitor student conversations (GET) + Professor's own AI assistant (POST)
    path('chat/', InstructorChatAIView.as_view(), name='instructor-chat'),
    # Get messages for any conversation by ID
    path('chat/messages/', ChatMessageListView.as_view(), name='instructor-chat-messages'),
    # Professor's own AI conversations (create, list, rename, delete)
    path('conversations/', InstructorConversationListView.as_view(), name='instructor-conversations'),
    path('conversations/<int:pk>/', InstructorConversationDetailView.as_view(), name='instructor-conversation-detail'),

    # Notifications
    path('notifications/', NotificationListView.as_view(), name='instructor-notifications'),

    # ── Rubric-Driven Auto Revision Engine ──────────────────────────────
    path('rubric-assignments/', RubricAssignmentListCreateView.as_view(), name='instructor-rubric-assignments'),
    path('rubric-assignments/<int:pk>/', RubricAssignmentDetailView.as_view(), name='instructor-rubric-assignment-detail'),
    path('submissions/<int:pk>/regrade/', RegradeSubmissionView.as_view(), name='instructor-submission-regrade'),
    path('grading-results/<int:pk>/', InstructorGradingResultView.as_view(), name='instructor-grading-result'),
]


