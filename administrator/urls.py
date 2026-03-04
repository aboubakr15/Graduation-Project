from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardViewSet, CourseViewSet, UserViewSet, 
    AnnouncementViewSet, MaterialViewSet, ChatViewSet, NotificationViewSet,
    DepartmentViewSet, CourseOfferingViewSet, EnrollmentViewSet
)

router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'course-offerings', CourseOfferingViewSet, basename='course-offerings')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollments')
router.register(r'users', UserViewSet, basename='users')
router.register(r'announcements', AnnouncementViewSet, basename='announcements')
router.register(r'materials', MaterialViewSet, basename='materials')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'departments', DepartmentViewSet, basename='departments')

# Dashboard is a ViewSet but dashboard/summary is a custom action. 
# We can register it as a singleton if we want, or just manual path if it's a single endpoint,
# but ViewSet is better for consistency.
router.register(r'dashboard', DashboardViewSet, basename='dashboard')


urlpatterns = [
    path('', include(router.urls)),
]
