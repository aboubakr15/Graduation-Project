import os
import requests
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import User, CourseOffering, Enrollment

def run_chat_test():
    print("Starting AI Chat Verification...")

    # 1. Ensure Student exists and is enrolled
    print("Setting up test student...")
    student_email = "student@eduera.com"
    student_pass = "TestPassword123"
    
    student, created = User.objects.get_or_create(
        username="student_test",
        email=student_email,
        defaults={
            "password": student_pass,
            "primary_role": User.Role.STUDENT,
            "full_name": "Test Student"
        }
    )
    if created:
        student.set_password(student_pass)
        student.save()
        print("Created new test student.")
    
    # Enroll in the course we used for upload (DS101)
    offering = CourseOffering.objects.filter(course__code="DS101").first()
    if not offering:
        print("Course offering DS101 not found. Run verify_cloud_sync.py first.")
        return
        
    Enrollment.objects.get_or_create(
        student=student,
        course_offering=offering,
        defaults={"status": Enrollment.Status.ACTIVE}
    )
    print(f"Student enrolled in {offering}")

    # 2. Get Student Token
    print("Authenticating as Student...")
    login_url = "http://127.0.0.1:8000/api/token/"
    try:
        response = requests.post(login_url, json={"email": student_email, "password": student_pass})
        response.raise_for_status()
        token = response.json()["access"]
        print("Authentication Successful!")
    except Exception as e:
        print(f"Authentication Failed: {e}")
        return

    # 3. Send Chat Query
    print("Sending question to AI (Retrieving from Cloud Qdrant)...")
    chat_url = "http://127.0.0.1:8000/api/student/chat/"
    headers = {"Authorization": f"Bearer {token}"}
    
    # The fields expected by StudentChatBotView are 'content' and 'course_id'
    query_data = {
        "course_id": offering.id,
        "content": "What is the main topic of the uploaded Data Science slides?"
    }
    
    try:
        response = requests.post(chat_url, headers=headers, json=query_data)
        if response.status_code == 200:
            result = response.json()
            ai_msg = result.get("ai_message", {})
            print("\n--- AI RESPONSE ---")
            print(ai_msg.get("content"))
            print("\n--- SOURCES ---")
            for src in ai_msg.get("sources_used", []):
                print(f"- {src}")
            print("\nSUCCESS: RAG is working with Cloud Qdrant!")
        else:
            print(f"Chat Failed (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"Error during chat: {e}")

if __name__ == '__main__':
    run_chat_test()
