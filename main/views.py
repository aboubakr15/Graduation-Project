from django.shortcuts import render
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .serializers import EmailTokenObtainPairSerializer


class EmailTokenObtainPairView(TokenObtainPairView):
    """
    Custom token obtain view that uses email instead of username for authentication.
    """
    serializer_class = EmailTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user
        self._update_streak(user)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    def _update_streak(self, user):
        now = timezone.now()
        today = now.date()
        
        if user.last_login is None:
            user.current_streak = 1
        else:
            last_login_date = user.last_login.date()
            if last_login_date == today:
                # Already logged in today, keep the same streak
                pass
            elif last_login_date == today - timedelta(days=1):
                # Logged in yesterday, increment streak
                user.current_streak += 1
            else:
                # Missed a day, reset streak
                user.current_streak = 1

        if user.current_streak > user.longest_streak:
            user.longest_streak = user.current_streak

        user.last_login = now
        user.save(update_fields=['current_streak', 'longest_streak', 'last_login'])
