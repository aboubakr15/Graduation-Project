from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import mimetypes

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
    MaterialUploadSerializer,
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
    NotificationSerializer,
    InstructorProfileSerializer
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
        courses = CourseOffering.objects.filter(
            instructor=request.user
        ) | CourseOffering.objects.filter(tas=request.user)

        course_id = request.query_params.get('course_offering')
        if course_id:
            # Explicitly enforce they only see materials for a course they teach/assist
            courses = courses.filter(id=course_id)
            
        materials = CourseMaterial.objects.filter(course_offering__in=courses.distinct())
        serializer = MaterialSerializer(
            materials.order_by('-upload_date'), many=True, context={'request': request}
        )
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        """
        Upload one or multiple course material files.

        Content-Type : multipart/form-data
        Required fields:
          course_offering  – int   : ID of the CourseOffering
          title            – str
          material_type    – str   : LECTURE | SECTION | ASSIGNMENT_DESC | OTHER
          file             – binary: passing multiple `file` fields uploads in bulk
        Optional fields:
          description, is_visible_to_students, order_index
        """
        files = request.FILES.getlist('file')
        if not files:
            # Fallback to standard validation so standard error messages apply
            serializer = MaterialUploadSerializer(data=request.data, context={'request': request})
            serializer.is_valid()
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_materials = []
        errors = []
        base_title = request.data.get('title')

        for uploaded_file in files:
            # Safely copy scalar data fields. Avoids request.data.copy() which crashes
            # attempting to deep-copy unpicklable file streams like _io.BufferedRandom.
            data = {k: request.data.get(k) for k in request.data.keys() if k != 'file'}
            data['file'] = uploaded_file

            # If uploading multiple files under one request, distinguish titles
            if len(files) > 1:
                if base_title:
                    data['title'] = f"{base_title} - {uploaded_file.name}"
                else:
                    data['title'] = uploaded_file.name

            serializer = MaterialUploadSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                material = serializer.save(uploaded_by=request.user)
                created_materials.append(material)
            else:
                errors.append({
                    "file": uploaded_file.name,
                    "errors": serializer.errors
                })

        if errors:
            # If any single file validation fails (like size/extension or missing reqs)
            # rollback the entire database transaction so we don't partially save files.
            transaction.set_rollback(True)
            return Response({"bulk_errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        # If we succeed, send notifications
        for material in created_materials:
            if material.is_visible_to_students:
                self._notify_enrolled_students(material)

        # Backward compatibility: return single object for single upload, list for bulk upload
        if len(files) == 1:
            return Response(
                MaterialSerializer(created_materials[0], context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                MaterialSerializer(created_materials, many=True, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _notify_enrolled_students(material):
        """
        Create a Notification row for every student actively enrolled in the
        course offering associated with this material.
        """
        active_enrollments = Enrollment.objects.filter(
            course_offering=material.course_offering,
            status=Enrollment.Status.ACTIVE,
        ).select_related('student')

        notifications = [
            Notification(
                user=enrollment.student,
                title=f"New material: {material.title}",
                message=(
                    f"A new {material.get_material_type_display()} has been uploaded "
                    f"for {material.course_offering.course.name}: \"{material.title}\"."
                ),
                notification_type=Notification.NotificationType.MATERIAL_UPLOAD,
                related_object_type='CourseMaterial',
                related_object_id=material.id,
            )
            for enrollment in active_enrollments
        ]
        Notification.objects.bulk_create(notifications)


class MaterialDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        material = get_object_or_404(CourseMaterial, pk=pk)
        
        # Enforce that only the assigned TA or Instructor can modify this material
        is_instructor = (material.course_offering.instructor_id == request.user.id)
        is_ta = material.course_offering.tas.filter(id=request.user.id).exists()
        if not (is_instructor or is_ta):
            return Response({"error": "You do not have permission to modify this material."}, status=status.HTTP_403_FORBIDDEN)
            
        # Re-use MaterialUploadSerializer in partial mode so the same
        # validation rules (extension, size, course permissions) apply on updates too.
        serializer = MaterialUploadSerializer(
            material, 
            data=request.data, 
            partial=True, 
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(MaterialSerializer(material, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        material = get_object_or_404(CourseMaterial, pk=pk)
        
        # Enforce that only the assigned TA or Instructor can delete this material
        is_instructor = (material.course_offering.instructor_id == request.user.id)
        is_ta = material.course_offering.tas.filter(id=request.user.id).exists()
        if not (is_instructor or is_ta):
            return Response({"error": "You do not have permission to delete this material."}, status=status.HTTP_403_FORBIDDEN)
            
        # Remove the file from storage when the record is deleted
        if material.file:
            material.file.delete(save=False)
        material.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MaterialDownloadView(APIView):
    """
    Authenticated, access-controlled file download.

    GET /api/professor/materials/<pk>/download/
    GET /api/ta/materials/<pk>/download/

    Access is granted only to:
      • The course instructor
      • Any TA assigned to the course
      • Any student actively enrolled in the course
            (only when is_visible_to_students = True)

    The file is streamed via Django's FileResponse so large videos
    do not need to be loaded into memory all at once.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        material = get_object_or_404(
            CourseMaterial.objects.select_related(
                'course_offering__instructor', 'course_offering__course'
            ),
            pk=pk,
        )

        user = request.user
        offering = material.course_offering

        is_instructor = (offering.instructor_id == user.pk)
        is_ta = offering.tas.filter(pk=user.pk).exists()
        is_enrolled_student = (
            material.is_visible_to_students
            and Enrollment.objects.filter(
                student=user,
                course_offering=offering,
                status=Enrollment.Status.ACTIVE,
            ).exists()
        )

        if not (is_instructor or is_ta or is_enrolled_student):
            return Response(
                {'detail': 'You do not have access to this material.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not material.file:
            return Response(
                {'detail': 'No file is stored for this material.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Guess MIME type from the stored file name
        mime_type, _ = mimetypes.guess_type(material.file.name)
        mime_type = mime_type or 'application/octet-stream'

        response = FileResponse(
            material.file.open('rb'),
            content_type=mime_type,
            as_attachment=False,   # inline display for PDF/video in browsers
        )
        # Suggest the original filename for downloads
        import os
        filename = os.path.basename(material.file.name)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response


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


class InstructorProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = InstructorProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = InstructorProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
