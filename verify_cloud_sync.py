import os
import requests
import django
from pathlib import Path

# Setup Django to find IDs
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import User, CourseOffering, Course, Department

def run_verification():
    print("Starting Cloud Sync Verification...")
    
    # 1. Get Access Token
    print("Authenticating as Professor...")
    login_url = "http://127.0.0.1:8000/api/token/"
    credentials = {
        "email": "prof@eduera.com",
        "password": "TestPassword123"
    }
    
    try:
        response = requests.post(login_url, json=credentials)
        response.raise_for_status()
        token = response.json()["access"]
        print("Authentication Successful!")
    except Exception as e:
        print(f"Authentication Failed: {e}")
        return

    # 2. Ensure a Course Offering exists
    print("Ensuring Course Offering exists...")
    prof = User.objects.get(email="prof@eduera.com")
    dept = Department.objects.first()
    if not dept:
        dept = Department.objects.create(code='GEN', name='General')
        
    course, _ = Course.objects.get_or_create(
        code="DS101", 
        defaults={"name": "Data Science Intro", "department": dept, "credit_hours": 3}
    )
    offering, _ = CourseOffering.objects.get_or_create(
        course=course,
        semester="Fall",
        year=2026,
        instructor=prof,
        defaults={"capacity": 50}
    )
    offering_id = offering.id
    print(f"Using Course Offering ID: {offering_id}")

    # 3. Upload File
    file_path = Path(r"I:\Menna\backend\Graduation-Project-main\ai_engine\data\raw\Data Science\slides01.pdf")
    if not file_path.exists():
        print(f"File not found at: {file_path}")
        return

    print(f"Uploading {file_path.name}...")
    upload_url = "http://127.0.0.1:8000/api/professor/materials/"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "title": f"Cloud Sync Test {os.urandom(2).hex()}",
        "course_offering": offering_id,
        "material_type": "LECTURE"
    }
    
    with open(file_path, 'rb') as f:
        files = {'file': (file_path.name, f, 'application/pdf')}
        try:
            response = requests.post(upload_url, headers=headers, data=data, files=files)
            if response.status_code == 201:
                print("SUCCESS: Material uploaded and synced to Cloud Qdrant!")
                print(f"Response: {response.json()}")
            else:
                print(f"Upload Failed (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"Error during upload: {e}")

if __name__ == '__main__':
    run_verification()
