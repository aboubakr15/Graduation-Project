import os
import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GraduationProject.settings")
django.setup()

try:
    from administrator import models, views, urls, serializers, services, permissions, signals
    print("Successfully imported administrator modules.")
except ImportError as e:
    print(f"Error importing administrator modules: {e}")

try:
    from django.urls import resolve
    print("Checking URL patterns...")
    match = resolve('/admin/dashboard/summary/')
    print(f"Found match for /admin/dashboard/summary/: {match.view_name}")
    
    match = resolve('/admin/courses/')
    print(f"Found match for /admin/courses/: {match.view_name}")

    match = resolve('/django-admin/')
    print(f"Found match for /django-admin/: {match.view_name}")

except Exception as e:
    print(f"Error resolving URLs: {e}")
