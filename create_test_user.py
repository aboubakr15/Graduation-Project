import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import User

def create_user():
    username = 'teststudent'
    password = 'TestPassword123'
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, password=password, primary_role=User.Role.STUDENT, full_name='Test Student')
        print(f"User '{username}' created.")
    else:
        print(f"User '{username}' already exists.")

if __name__ == '__main__':
    create_user()
