from django.shortcuts import render
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import EmailTokenObtainPairSerializer

# Create your views here.


class EmailTokenObtainPairView(TokenObtainPairView):
    """
    Custom token obtain view that uses email instead of username for authentication.
    """
    serializer_class = EmailTokenObtainPairSerializer
