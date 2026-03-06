from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from main.models import (
    User, CourseOffering, Enrollment, Assignment, CourseMaterial,
    Announcement, ChatConversation, ChatMessage, Notification, StudentSubmission
)

from .serializers import (
    DashboardSerializer,
    CourseOfferingListSerializer,
    CourseOfferingDetailSerializer,
    CourseOfferingCreateSerializer,
    MaterialSerializer,
    MaterialCreateSerializer,
    AssignmentListSerializer,
    AssignmentDetailSerializer,
    AssignmentCreateSerializer,
    SubmissionSerializer,
    GradeSubmissionSerializer,
    StudentSerializer,
    AnnouncementSerializer,
    AnnouncementCreateSerializer,
    ChatConversationSerializer,
    ChatMessageSerializer,
    NotificationSerializer
)


class InstructorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        courses = CourseOffering.objects.filter(
            instructor=user
        ) | CourseOffering.objects.filter(tas=user)
        courses = courses.distinct()
        
        total_courses = courses.count()
        
        student_ids = Enrollment.objects.filter(
            course_offering__in=courses,
            status=Enrollment.Status.ACTIVE
        ).values_list('student_id', flat=True).distinct()
        total_students = student_ids.count()
        
        upcoming_assignments = Assignment.objects.filter(
            course_offering__in=courses,
            due_date__gte=timezone.now()
        ).count()
        
        pending_submissions = StudentSubmission.objects.filter(
            assignment__course_offering__in=courses,
            status=StudentSubmission.Status.SUBMITTED
        ).count()
        
        recent_announcements = Announcement.objects.filter(
            course_offering__in=courses
        ).order_by('-created_at')[:5]
        
        data = {
            'total_courses': total_courses,
            'total_students': total_students,
            'pending_submissions': pending_submissions,
            'upcoming_assignments': upcoming_assignments,
            'recent_announcements': AnnouncementSerializer(recent_announcements, many=True).data,
            'courses': CourseOfferingListSerializer(courses[:5], many=True).data
        }
        return Response(data)


class CourseOfferingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        courses = CourseOffering.objects.filter(
            instructor=request.user
        ) | CourseOffering.objects.filter(tas=request.user)
        courses = courses.distinct().order_by('-year', '-semester')
        serializer = CourseOfferingListSerializer(courses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CourseOfferingCreateSerializer(data=request.data)
        if serializer.is_valid():
            course = serializer.save(instructor=request.user)
            return Response(CourseOfferingDetailSerializer(course).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CourseOfferingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        course = get_object_or_404(CourseOffering, pk=pk)
        serializer = CourseOfferingDetailSerializer(course)
        return Response(serializer.data)

    def patch(self, request, pk):
        course = get_object_or_404(CourseOffering, pk=pk)
        serializer = CourseOfferingCreateSerializer(course, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(CourseOfferingDetailSerializer(course).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        course = get_object_or_404(CourseOffering, pk=pk)
        course.is_active = False
        course.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MaterialListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get('course_offering')
        if course_id:
            materials = CourseMaterial.objects.filter(course_offering=course_id)
        else:
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            materials = CourseMaterial.objects.filter(course_offering__in=courses.distinct())
        serializer = MaterialSerializer(materials.order_by('-upload_date'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MaterialCreateSerializer(data=request.data)
        if serializer.is_valid():
            material = serializer.save(uploaded_by=request.user)
            return Response(MaterialSerializer(material).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MaterialDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        material = get_object_or_404(CourseMaterial, pk=pk)
        serializer = MaterialCreateSerializer(material, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(MaterialSerializer(material).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        material = get_object_or_404(CourseMaterial, pk=pk)
        material.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get('course_offering')
        if course_id:
            assignments = Assignment.objects.filter(course_offering=course_id)
        else:
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            assignments = Assignment.objects.filter(course_offering__in=courses.distinct())
        serializer = AssignmentListSerializer(assignments.order_by('due_date'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            assignment = serializer.save(created_by=request.user)
            return Response(AssignmentDetailSerializer(assignment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        serializer = AssignmentDetailSerializer(assignment)
        return Response(serializer.data)

    def patch(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        serializer = AssignmentCreateSerializer(assignment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AssignmentDetailSerializer(assignment).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubmissionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assignment_id = request.query_params.get('assignment_id')
        course_id = request.query_params.get('course_offering')
        
        if assignment_id:
            submissions = StudentSubmission.objects.filter(assignment_id=assignment_id)
        elif course_id:
            submissions = StudentSubmission.objects.filter(assignment__course_offering_id=course_id)
        else:
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            submissions = StudentSubmission.objects.filter(
                assignment__course_offering__in=courses.distinct()
            )
        
        submissions = submissions.select_related('student', 'assignment__course_offering__course')
        serializer = SubmissionSerializer(submissions.order_by('-submission_date'), many=True)
        return Response(serializer.data)


class SubmissionGradeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        submission = get_object_or_404(StudentSubmission, pk=pk)
        serializer = GradeSubmissionSerializer(data=request.data)
        
        if serializer.is_valid():
            grade = serializer.validated_data['grade']
            notes = serializer.validated_data.get('notes', '')
            
            submission.grade = grade
            submission.notes = notes
            submission.status = StudentSubmission.Status.GRADED
            submission.save()
            
            enrollment = Enrollment.objects.filter(
                student=submission.student,
                course_offering=submission.assignment.course_offering
            ).first()
            if enrollment:
                self._update_enrollment_grade(enrollment)
            
            return Response(SubmissionSerializer(submission).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _update_enrollment_grade(self, enrollment):
        assignments = Assignment.objects.filter(course_offering=enrollment.course_offering)
        total_points = sum(a.total_points for a in assignments)
        
        if total_points > 0:
            submissions = StudentSubmission.objects.filter(
                student=enrollment.student,
                assignment__course_offering=enrollment.course_offering,
                status=StudentSubmission.Status.GRADED
            )
            earned_points = sum(float(s.grade or 0) for s in submissions)
            enrollment.grade = (earned_points / total_points) * 100
            enrollment.save()


class StudentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get('course_offering')
        
        if course_id:
            enrollments = Enrollment.objects.filter(
                course_offering_id=course_id,
                status=Enrollment.Status.ACTIVE
            ).select_related('student', 'course_offering__course')
        else:
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            enrollments = Enrollment.objects.filter(
                course_offering__in=courses.distinct(),
                status=Enrollment.Status.ACTIVE
            ).select_related('student', 'course_offering__course')
        
        students_data = {}
        for e in enrollments:
            if e.student.id not in students_data:
                students_data[e.student.id] = {
                    'id': e.student.id,
                    'email': e.student.email,
                    'full_name': e.student.full_name,
                    'student_id': e.student.student_id,
                    'department': e.student.department_id,
                    'current_gpa': e.student.current_gpa,
                    'enrolled_courses': []
                }
            students_data[e.student.id]['enrolled_courses'].append({
                'enrollment_id': e.id,
                'course_id': e.course_offering.id,
                'course_name': e.course_offering.course.name,
                'course_code': e.course_offering.course.code,
                'semester': e.course_offering.semester,
                'year': e.course_offering.year,
                'grade': e.grade
            })
        
        return Response(list(students_data.values()))


class AnnouncementListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get('course_offering')
        
        if course_id:
            announcements = Announcement.objects.filter(course_offering_id=course_id)
        else:
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            announcements = Announcement.objects.filter(
                course_offering__in=courses.distinct()
            ) | Announcement.objects.filter(is_global=True)
        
        serializer = AnnouncementSerializer(announcements.order_by('-created_at'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AnnouncementCreateSerializer(data=request.data)
        if serializer.is_valid():
            announcement = serializer.save(author=request.user)
            return Response(AnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        serializer = AnnouncementSerializer(announcement)
        return Response(serializer.data)

    def patch(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        serializer = AnnouncementCreateSerializer(announcement, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AnnouncementSerializer(announcement).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        announcement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        courses = CourseOffering.objects.filter(
            instructor=request.user
        ) | CourseOffering.objects.filter(tas=request.user)
        
        conversations = ChatConversation.objects.filter(
            course_offering__in=courses.distinct()
        ).select_related('student', 'course_offering__course')
        
        serializer = ChatConversationSerializer(conversations.order_by('-updated_at'), many=True)
        return Response(serializer.data)


class ChatMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversation_id = request.query_params.get('conversation_id')
        if not conversation_id:
            return Response({'error': 'conversation_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        conversation = get_object_or_404(ChatConversation, pk=conversation_id)
        messages = conversation.messages.order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = request.data.get('is_read', notification.is_read)
        notification.save()
        return Response(NotificationSerializer(notification).data)
