from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
import os
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from main.views import (
    EmailTokenObtainPairView,
    ChangePasswordView,
    ForgotPasswordView,
    ResetPasswordView,
    NotificationListView,
    NotificationMarkReadView,
)

urlpatterns = [
    # Remap default Django admin
    path('django-admin/', admin.site.urls),
    
    # Custom Admin API
    path('admin/', include('administrator.urls')),

    # Student API
    path('api/student/', include('student.urls')),

    # Professor API (uses common instructor endpoints)
    path('api/professor/', include('instructor.urls')),

    # Teaching Assistant API (uses common instructor endpoints)
    path('api/ta/', include('instructor.urls')),

    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),

    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('api/auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('api/auth/reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    path('api/notifications/', NotificationListView.as_view(), name='notifications_list'),
    path('api/notifications/mark-read/', NotificationMarkReadView.as_view(), name='notifications_mark_read_all'),
    path('api/notifications/<int:pk>/mark-read/', NotificationMarkReadView.as_view(), name='notifications_mark_read_one'),

    # Serve generated presentations
    re_path(r'^presentations/(?P<path>.*)$', serve, {
        'document_root': os.path.join(settings.BASE_DIR, 'presentations'),
    }),
    
    # Serve media files (profile pictures, etc)
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]
