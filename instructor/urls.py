from django.urls import path
from .views import (
    InstructorDashboardView,
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
    NotificationListView,
    InstructorProfileView
)

urlpatterns = [
    # Dashboard
    path('dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    
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
    
    # Chat
    path('chat/', ChatConversationListView.as_view(), name='instructor-chat'),
    path('chat/messages/', ChatMessageListView.as_view(), name='instructor-chat-messages'),
    
    # Notifications
    path('notifications/', NotificationListView.as_view(), name='instructor-notifications'),
    path('profile/', InstructorProfileView.as_view(), name='instructor-profile'),
]
