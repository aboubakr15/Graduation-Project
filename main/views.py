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

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from main.models import User, Notification

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response({'error': 'Please provide both old and new passwords.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.check_password(old_password):
            return Response({'error': 'Incorrect old password.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Please provide an email address.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            # The frontend URL for password reset
            frontend_url = request.data.get('frontend_url', 'https://eduera.live')
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            
            subject = "Eduera Password Reset"
            message = f"Hello {user.full_name},\n\nYou requested a password reset. Click the link below to reset your password:\n{reset_link}\n\nIf you did not request this, please ignore this email."
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            
        except User.DoesNotExist:
            # We don't want to leak whether the email exists or not, so we just pass
            pass
            
        return Response({'message': 'If an account exists with that email, a password reset link has been sent.'}, status=status.HTTP_200_OK)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not uidb64 or not token or not new_password:
            return Response({'error': 'Missing data.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            
        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({'message': 'Password reset successful.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = request.user.notifications.all()[:50]
        data = []
        for n in notifications:
            data.append({
                'id': n.id,
                'title': n.title,
                'text': n.message,
                'type': n.notification_type,
                'time': n.created_at.isoformat(),
                'isRead': n.is_read
            })
        return Response(data, status=status.HTTP_200_OK)

class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            try:
                notif = request.user.notifications.get(pk=pk)
                notif.is_read = True
                notif.save()
            except Notification.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            request.user.notifications.filter(is_read=False).update(is_read=True)
            
        return Response({'message': 'Marked as read.'}, status=status.HTTP_200_OK)
