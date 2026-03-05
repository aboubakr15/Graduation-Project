from django.urls import path
from .views import (
    StudentDashboardView,
    StudentCourseListView,
    StudentCourseDetailView,
    StudentToDoListView,
    StudentProfileView,
    StudentChatBotView,
    StudentEnrollmentView,
    StudentSubmissionView,
    StudentGradesView,
    StudentNotificationsView
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
    path('chat/', StudentChatBotView.as_view(), name='student-chat'),
]
