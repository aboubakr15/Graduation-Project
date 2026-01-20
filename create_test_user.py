import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import User

def create_user():
    username = 'teststudent'
    email = 'test@test.com'
    password = 'TestPassword123'
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, email=email, password=password, primary_role=User.Role.STUDENT, full_name='Test Student')
        print(f"User '{username}' with email '{email}' created.")
    else:
        print(f"User '{username}' already exists. Updating credentials.")
        user = User.objects.get(username=username)
        user.email = email
        user.set_password(password)
        user.save()
        print(f"User '{username}' updated.")
        
    # Verify password immediately
    u = User.objects.get(username=username)
    if u.check_password(password):
        print("DEBUG: Password verification SUCCESS")
    else:
        print("DEBUG: Password verification FAILED")

if __name__ == '__main__':
    create_user()
