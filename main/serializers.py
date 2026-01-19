from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions, serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that uses email instead of username for authentication."""
    
    email = serializers.EmailField(required=True)
    username = None  # Remove the username field
    
    def validate(self, attrs):
        # Get the email from attrs
        email = attrs.get('email')
        password = attrs.get('password')
        
        # Try to find active user by email
        try:
            # Filter by is_active=True to only allow active users
            user = User.objects.get(email=email, is_active=True)
            # Replace 'email' with 'username' using actual username for parent validation
            attrs['username'] = user.username
            # Remove email from attrs as parent class expects username
            attrs.pop('email', None)
        except User.DoesNotExist:
            # User not found by email or user is inactive - raise authentication error
            raise exceptions.AuthenticationFailed(
                self.error_messages['no_active_account'],
                'no_active_account',
            )
        except User.MultipleObjectsReturned:
            # Multiple active users with same email (shouldn't happen if email is unique)
            # Get the first active user
            user = User.objects.filter(email=email, is_active=True).first()
            if user:
                attrs['username'] = user.username
                attrs.pop('email', None)
            else:
                raise exceptions.AuthenticationFailed(
                    self.error_messages['no_active_account'],
                    'no_active_account',
                )
        
        # Call parent validation to authenticate with username and password
        return super().validate(attrs)
