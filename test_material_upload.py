"""
End-to-end test for the material upload feature.
Run with: python test_material_upload.py
"""
import os, io, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')

import django
django.setup()

# Allow the Django test client's default host
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import Client
from main.models import User, Department, Course, CourseOffering, CourseMaterial, Enrollment, Notification

# ─── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}"); sys.exit(1)
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def section(title): print(f"\n{YELLOW}{'─'*60}{RESET}\n{YELLOW}{title}{RESET}")

client = Client()

# ═══════════════════════════════════════════════════════════════════════════════
section("1. Setup — create fixtures")

dept, _ = Department.objects.get_or_create(name="Computer Science", defaults={"code": "CS"})
info(f"Department: {dept}")

course, _ = Course.objects.get_or_create(
    code="CS_UPLOAD_TEST",
    defaults={"name": "Upload Test Course", "credit_hours": 3, "department": dept},
)
info(f"Course: {course}")

professor, _ = User.objects.get_or_create(
    username="test_prof_upload",
    defaults={
        "email": "prof_upload@test.com",
        "full_name": "Dr. Upload Test",
        "primary_role": User.Role.PROFESSOR,
    },
)
professor.set_password("Test@1234")
professor.save()
info(f"Professor: {professor.email}")

ta, _ = User.objects.get_or_create(
    username="test_ta_upload",
    defaults={
        "email": "ta_upload@test.com",
        "full_name": "TA Upload Test",
        "primary_role": User.Role.TA,
    },
)
ta.set_password("Test@1234")
ta.save()
info(f"TA: {ta.email}")

student, _ = User.objects.get_or_create(
    username="test_student_upload",
    defaults={
        "email": "student_upload@test.com",
        "full_name": "Student Upload Test",
        "primary_role": User.Role.STUDENT,
    },
)
student.set_password("Test@1234")
student.save()
info(f"Student: {student.email}")

offering, _ = CourseOffering.objects.get_or_create(
    course=course,
    semester="Spring",
    year=2026,
    instructor=professor,
    defaults={"capacity": 30},
)
offering.tas.add(ta)
info(f"Course Offering ID: {offering.id}")

enrollment, _ = Enrollment.objects.get_or_create(
    student=student,
    course_offering=offering,
    defaults={"status": Enrollment.Status.ACTIVE},
)
info(f"Student enrolled: {enrollment.status}")

# ═══════════════════════════════════════════════════════════════════════════════
section("2. Login as professor — obtain JWT token")

resp = client.post(
    "/api/token/",
    data=json.dumps({"email": "prof_upload@test.com", "password": "Test@1234"}),
    content_type="application/json",
)
info(f"POST /api/token/ → {resp.status_code}")
if resp.status_code != 200:
    fail(f"Login failed: {resp.content.decode()}")
tokens = resp.json()
access_token = tokens["access"]
ok(f"Got access token (first 40 chars): {access_token[:40]}...")

AUTH = {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}

# ═══════════════════════════════════════════════════════════════════════════════
section("3. Upload a file — POST /api/professor/materials/")

fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content for testing " * 50)
fake_pdf.name = "lecture_1.pdf"

resp = client.post(
    "/api/professor/materials/",
    data={
        "course_offering": offering.id,
        "title": "Lecture 1 — Introduction",
        "material_type": "LECTURE",
        "description": "First lecture of the semester",
        "is_visible_to_students": True,
    },
    **AUTH,
)
info(f"POST without file → {resp.status_code}")
body = resp.json()
if resp.status_code == 400 and "file" in body:
    ok(f"Correctly rejected empty upload: {body['file']}")
else:
    fail(f"Expected 400 for missing file, got {resp.status_code}: {body}")

# Now with the real file
fake_pdf.seek(0)
resp = client.post(
    "/api/professor/materials/",
    data={
        "course_offering": offering.id,
        "title": "Lecture 1 — Introduction",
        "material_type": "LECTURE",
        "description": "First lecture of the semester",
        "is_visible_to_students": True,
        "file": fake_pdf,
    },
    **AUTH,
)
info(f"POST with file → {resp.status_code}")
if resp.status_code != 201:
    fail(f"Upload failed: {resp.content.decode()}")

material_data = resp.json()
material_id = material_data["id"]
ok(f"Material created! ID = {material_id}")
ok(f"file_type auto-detected : {material_data['file_type']}")
ok(f"file_size auto-detected : {material_data['file_size']} bytes")
ok(f"file_download_url       : {material_data['file_download_url']}")
print(f"\n  Full response:\n  {json.dumps(material_data, indent=4, default=str)}")

# ═══════════════════════════════════════════════════════════════════════════════
section("4. Verify file was saved on disk")

material_obj = CourseMaterial.objects.get(pk=material_id)
info(f"DB file path: {material_obj.file.name}")
if material_obj.file and material_obj.file.storage.exists(material_obj.file.name):
    ok("File exists on filesystem ✓")
else:
    fail("File NOT found on filesystem after upload!")

# ═══════════════════════════════════════════════════════════════════════════════
section("5. Verify student notifications were created")

notifications = Notification.objects.filter(
    user=student,
    notification_type=Notification.NotificationType.MATERIAL_UPLOAD,
    related_object_id=material_id,
)
count = notifications.count()
if count > 0:
    ok(f"{count} notification(s) created for enrolled students")
    info(f"Notification title: {notifications.first().title}")
    info(f"Notification message: {notifications.first().message}")
else:
    fail("No notifications created!")

# ═══════════════════════════════════════════════════════════════════════════════
section("6. Test PROFESSOR download — GET /api/professor/materials/{id}/download/")

resp = client.get(f"/api/professor/materials/{material_id}/download/", **AUTH)
info(f"Status: {resp.status_code}")
info(f"Content-Type: {resp.get('Content-Type')}")
info(f"Content-Disposition: {resp.get('Content-Disposition')}")
if resp.status_code == 200:
    ok("Professor can download the file ✓")
else:
    fail(f"Professor download failed: {resp.content.decode()}")

# ═══════════════════════════════════════════════════════════════════════════════
section("7. Test STUDENT download — GET /api/student/materials/{id}/download/")

resp_student_login = client.post(
    "/api/token/",
    data=json.dumps({"email": "student_upload@test.com", "password": "Test@1234"}),
    content_type="application/json",
)
if resp_student_login.status_code != 200:
    fail(f"Student login failed: {resp_student_login.content.decode()}")
student_token = resp_student_login.json()["access"]
STUDENT_AUTH = {"HTTP_AUTHORIZATION": f"Bearer {student_token}"}

resp = client.get(f"/api/student/materials/{material_id}/download/", **STUDENT_AUTH)
info(f"Status: {resp.status_code}")
info(f"Content-Type: {resp.get('Content-Type')}")
if resp.status_code == 200:
    ok("Enrolled student can download the file ✓")
else:
    fail(f"Student download failed: {resp.content.decode()}")

# ═══════════════════════════════════════════════════════════════════════════════
section("8. Access control — random user CANNOT download")

stranger, _ = User.objects.get_or_create(
    username="stranger_user",
    defaults={
        "email": "stranger@test.com",
        "full_name": "Stranger",
        "primary_role": User.Role.STUDENT,
    },
)
stranger.set_password("Test@1234")
stranger.save()

resp_stranger_login = client.post(
    "/api/token/",
    data=json.dumps({"email": "stranger@test.com", "password": "Test@1234"}),
    content_type="application/json",
)
stranger_token = resp_stranger_login.json()["access"]
STRANGER_AUTH = {"HTTP_AUTHORIZATION": f"Bearer {stranger_token}"}

resp = client.get(f"/api/student/materials/{material_id}/download/", **STRANGER_AUTH)
info(f"Download Status: {resp.status_code}")
if resp.status_code == 403:
    ok("Non-enrolled user correctly blocked from downloading (403 Forbidden) ✓")
else:
    fail(f"Expected 403, got {resp.status_code}: {resp.content.decode()}")


# ═══════════════════════════════════════════════════════════════════════════════
section("9. Test TA upload (should succeed)")

resp_ta_login = client.post(
    "/api/token/",
    data=json.dumps({"email": "ta_upload@test.com", "password": "Test@1234"}),
    content_type="application/json",
)
ta_token = resp_ta_login.json()["access"]
TA_AUTH = {"HTTP_AUTHORIZATION": f"Bearer {ta_token}"}

ta_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content for TA " * 50)
ta_pdf.name = "ta_lecture.pdf"

resp = client.post(
    "/api/professor/materials/",
    data={
        "course_offering": offering.id,
        "title": "TA Uploaded Lecture",
        "material_type": "SECTION",
        "file": ta_pdf,
    },
    **TA_AUTH,
)
if resp.status_code != 201:
    fail(f"TA Upload failed: {resp.content.decode()}")
else:
    ok(f"TA allowed to upload. Material ID = {resp.json()['id']} ✓")

CourseMaterial.objects.filter(pk=resp.json()["id"]).delete()

# ═══════════════════════════════════════════════════════════════════════════════
section("10. Access control — random user CANNOT upload")

bad_pdf = io.BytesIO(b"%PDF-1.4 fake ")
bad_pdf.name = "hack.pdf"
resp = client.post(
    "/api/professor/materials/",
    data={
        "course_offering": offering.id,
        "title": "Hack",
        "material_type": "OTHER",
        "file": bad_pdf,
    },
    **STRANGER_AUTH, # Try to upload as stranger
)
info(f"Upload Status: {resp.status_code}")
# The response should return a 400 validation error explicitly blocking the course_offering.
if resp.status_code == 400 and ("course_offering" in str(resp.json()) or "bulk_errors" in str(resp.json())):
    ok("Stranger securely blocked from uploading to a course they don't own ✓")
else:
    fail(f"Expected 400 course_offering validation block, got: {resp.content.decode()}")


# ═══════════════════════════════════════════════════════════════════════════════
section("11. File type validation — bad extension rejected")

bad_file = io.BytesIO(b"echo hello")
bad_file.name = "malware.exe"

resp = client.post(
    "/api/professor/materials/",
    data={
        "course_offering": offering.id,
        "title": "Bad File",
        "material_type": "OTHER",
        "file": bad_file,
    },
    **AUTH,
)
info(f"Status: {resp.status_code}")
body = resp.json()
if resp.status_code == 400 and ("file" in body or "bulk_errors" in body):
    ok(f"Correctly rejected .exe: {body}")
else:
    fail(f"Expected 400 for .exe, got {resp.status_code}: {resp.content.decode()}")

# ═══════════════════════════════════════════════════════════════════════════════
section("12. Cleanup")

CourseMaterial.objects.filter(pk=material_id).delete()
ok("Test material deleted from DB and filesystem")

print(f"\n{GREEN}{'═'*60}{RESET}")
print(f"{GREEN}  ALL TESTS PASSED ✓{RESET}")
print(f"{GREEN}{'═'*60}{RESET}\n")
