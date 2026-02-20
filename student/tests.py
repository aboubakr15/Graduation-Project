from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from main.models import User, Course, CourseOffering, Enrollment, Announcement, Department

class StudentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.department = Department.objects.create(name="CS", code="CS101")
        self.student_user = User.objects.create_user(
            username='student1', 
            password='password123',
            primary_role=User.Role.STUDENT,
            full_name="John Doe",
            department=self.department
        )
        self.client.force_authenticate(user=self.student_user)

        self.course = Course.objects.create(
            name="Intro to CS", code="CS101", credit_hours=3, department=self.department
        )
        self.professor = User.objects.create_user(
            username='prof1', 
            password='password123',
            primary_role=User.Role.PROFESSOR,
            full_name="Dr. Smith"
        )
        self.offering = CourseOffering.objects.create(
            course=self.course, semester="Fall", year=2024, instructor=self.professor
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student_user, course_offering=self.offering
        )
        self.announcement = Announcement.objects.create(
            title="Welcome", content="Welcome to the portal", author=self.professor, is_global=True
        )

    def test_dashboard(self):
        url = reverse('student-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)
        self.assertIn('portal_announcements', response.data)
        self.assertIn('courses_progress', response.data)

    def test_course_list(self):
        url = reverse('student-course-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['course_code'], 'CS101')

    def test_course_detail(self):
        url = reverse('student-course-detail', args=[self.offering.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['course_code'], 'CS101')

    def test_profile(self):
        url = reverse('student-profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], "John Doe")

    def test_chat_creation(self):
        url = reverse('student-chat')
        data = {'content': 'Hello AI', 'course_id': self.offering.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_message', response.data)
        self.assertIn('ai_message', response.data)
