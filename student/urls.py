from django.urls import path
from .views import (
    StudentDashboardView,
    StudentCourseListView,
    StudentCourseDetailView,
    StudentToDoListView,
    StudentProfileView,
    StudentChatBotView
)

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('courses/', StudentCourseListView.as_view(), name='student-course-list'),
    path('courses/<int:pk>/', StudentCourseDetailView.as_view(), name='student-course-detail'),
    path('todo/', StudentToDoListView.as_view(), name='student-todo-list'),
    path('profile/', StudentProfileView.as_view(), name='student-profile'),
    path('chat/', StudentChatBotView.as_view(), name='student-chat'),
]
