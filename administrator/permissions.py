from rest_framework.permissions import BasePermission
from main.models import User

class IsAdminOnly(BasePermission):
    """
    Custom permission to only allow users with primary_role = 'ADMIN'
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.primary_role == User.Role.ADMIN
        )
