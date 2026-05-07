import json
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from main.models import User, Course, CourseOffering, Assignment, StudentSubmission, Enrollment, Department
from grading.models import GradingResult

class GradingEngineTests(APITestCase):
    def setUp(self):
        # 0. Create Department (Required by Course)
        self.dept = Department.objects.create(name='Computer Science', code='CS')

        # 1. Create Users
        self.professor = User.objects.create_user(
            username='prof', email='prof@test.com', password='password123',
            primary_role=User.Role.PROFESSOR, full_name='Dr. Test'
        )
        self.student = User.objects.create_user(
            username='student', email='student@test.com', password='password123',
            primary_role=User.Role.STUDENT, full_name='Student Test'
        )

        # 2. Create Course & Offering
        self.course = Course.objects.create(
            code='CS101', name='Intro to CS', credit_hours=3,
            department=self.dept
        )
        self.offering = CourseOffering.objects.create(
            course=self.course, instructor=self.professor, 
            semester='FALL', year=2024, capacity=30
        )

        # 3. Enroll Student
        Enrollment.objects.create(student=self.student, course_offering=self.offering, status=Enrollment.Status.ACTIVE)

    def test_create_rubric_assignment(self):
        """Test that a professor can create an assignment with a rubric."""
        self.client.force_authenticate(user=self.professor)
        url = reverse('instructor-rubric-assignments')
        data = {
            "course_offering": self.offering.id,
            "title": "Essay on AI Ethics",
            "description": "Write a 500-word essay.",
            "due_date": "2024-12-31T23:59:59Z",
            "total_points": 100,
            "assignment_type": "REPORT",
            "grading_type": "SUBJECTIVE",
            "rubric": [
                {"criteria_name": "Clarity", "max_points": 50, "description": "How clear the essay is."},
                {"criteria_name": "Content", "max_points": 50, "description": "The depth of information."}
            ],
            "model_answer_text": "AI ethics is important because..."
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Assignment.objects.count(), 1)
        self.assertEqual(Assignment.objects.first().grading_type, "SUBJECTIVE")

    @patch('ai_engine.services.grading_service.GradingEngine.grade_submission')
    def test_student_submit_and_auto_grade(self, mock_grade):
        """Test that a student submission triggers auto-grading."""
        # Setup Assignment
        assignment = Assignment.objects.create(
            course_offering=self.offering, title="AI Ethics",
            due_date="2024-12-31T23:59:59Z", total_points=100,
            assignment_type="REPORT", grading_type="SUBJECTIVE",
            rubric=[{"criteria_name": "Clarity", "max_points": 100, "description": "..."}],
            model_answer_text="..."
        )

        # Mock Grading Result using side_effect to link it to the actual submission
        def mock_grade_side_effect(submission_id):
            sub = StudentSubmission.objects.get(pk=submission_id)
            return GradingResult.objects.create(
                submission=sub,
                total_score=85.0, max_score=100.0,
                criteria_breakdown=[{"criteria_name": "Clarity", "points_awarded": 85.0, "max_points": 100.0, "justification": "Good."}],
                feedback_summary="Well done."
            )
        mock_grade.side_effect = mock_grade_side_effect

        # Auth as Student
        self.client.force_authenticate(user=self.student)
        
        url = reverse('student-rubric-submit')
        data = {
            "assignment_id": assignment.id,
            "submitted_text": "This is my essay about AI ethics..."
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StudentSubmission.objects.count(), 1)
        
        # Verify grading result exists
        submission = StudentSubmission.objects.first()
        # Note: In the actual view, we pass submission.pk to engine.grade_submission
        # The mock return value's submission field would need to be updated 
        # but the view logic handles the link. 
        # However, since we mocked the engine, we should check if GradingResult was created.
        self.assertTrue(hasattr(submission, 'grading_result'))
        self.assertEqual(submission.grading_result.total_score, 85.0)

    def test_regrade_submission(self):
        """Test that a professor can re-trigger grading."""
        assignment = Assignment.objects.create(
            course_offering=self.offering, title="AI Ethics",
            due_date="2024-12-31T23:59:59Z", total_points=100,
            assignment_type="REPORT", grading_type="SUBJECTIVE",
            rubric=[{"criteria_name": "Clarity", "max_points": 100, "description": "..."}],
            model_answer_text="..."
        )
        submission = StudentSubmission.objects.create(
            student=self.student, assignment=assignment,
            submitted_text="Existing text", status=StudentSubmission.Status.SUBMITTED
        )

        with patch('ai_engine.services.grading_service.GradingEngine.grade_submission') as mock_grade:
            mock_grade.return_value = GradingResult.objects.create(
                submission=submission, total_score=90.0, max_score=100.0,
                criteria_breakdown=[], feedback_summary="Better."
            )
            
            self.client.force_authenticate(user=self.professor)
            url = reverse('instructor-submission-regrade', kwargs={'pk': submission.pk})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(submission.grading_result.total_score, 90.0)
