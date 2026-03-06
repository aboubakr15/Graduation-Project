from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from main.views import EmailTokenObtainPairView

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
]
