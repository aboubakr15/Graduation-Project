import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import CourseChatMessage
msgs = CourseChatMessage.objects.all().order_by('-created_at')[:10]
for m in msgs:
    print(m.id, m.content)
