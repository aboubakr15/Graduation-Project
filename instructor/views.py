from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
import mimetypes
import re
import logging

logger = logging.getLogger(__name__)

from main.models import (
    User, CourseOffering, Enrollment, Assignment, CourseMaterial,
    Course, Department, Announcement, ChatConversation, ChatMessage,
    Notification, StudentSubmission
)
from grading.models import GradingResult

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
    InstructorProfileSerializer,
    CourseCreateUploadSerializer,
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
                
                # -------------------------------------------------------------
                # ★ AI Incremental Ingestion ★
                # -------------------------------------------------------------
                try:
                    from ai_engine.ai_services import get_rag_pipeline
                    rag = get_rag_pipeline()
                    
                    # Ensure it's initialized (loads vector store if exists)
                    if not rag.is_initialized:
                        try:
                            rag.vector_store_manager.load_vector_store()
                            rag.is_initialized = True
                        except:
                            logger.warning("Vector store not found during incremental upload. AI will create it.")
                    
                    file_path = material.file.path
                    course_code = material.course_offering.course.code
                    
                    logger.info(f"Triggering AI ingestion for: {file_path} (Course: {course_code})")
                    rag.add_documents(file_path, course_code=course_code)
                except Exception as ai_e:
                    logger.error(f"AI Ingestion failed for {material.title}: {str(ai_e)}")
                    # Note: We don't fail the Django upload if AI indexing fails.
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


# ─────────────────────────────────────────────────────────────────────────────
# ★ Professor Course Upload — create or update a course, upload a lecture ★
# ─────────────────────────────────────────────────────────────────────────────

class CourseCreateView(APIView):
    """
    POST /api/professor/course-upload/
    Content-Type: multipart/form-data

    Handles two scenarios in one call:
      A) New course  — Course + CourseOffering do not exist yet.
      B) Existing    — Professor adds a new lecture to an existing offering.

    Duplicate guard:
      If a CourseMaterial with the same `lecture_title` already exists
      for the resolved CourseOffering, the request is rejected with 409.
      The check is scoped to (course_offering + title), so two courses
      can each have a "Lecture 1" without conflict.

    On success:
      • File is saved to disk.
      • RAG pipeline embeds the document and pushes it to Qdrant.
      • Enrolled students are notified.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # Only professors (and TAs) may upload course material
        if request.user.primary_role not in (User.Role.PROFESSOR, User.Role.TA):
            return Response(
                {'error': 'Only professors and TAs can upload course materials.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CourseCreateUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        course_code    = data['course_code'].strip().upper()
        course_name    = data.get('course_name', '').strip()
        department     = data.get('department')          # Department instance or None
        credit_hours   = data.get('credit_hours', 3)
        semester       = data.get('semester', 'Fall')
        year           = data.get('year') or datetime.now().year
        lecture_title  = data['lecture_title'].strip()
        material_type  = data['material_type']
        uploaded_file  = data['file']
        is_visible     = data.get('is_visible_to_students', True)

        # ── 1. Find or create the Course ─────────────────────────────────────
        course = Course.objects.filter(code=course_code).first()
        if course is None:
            # Creating a new course requires a name and a department
            if not course_name:
                return Response(
                    {'error': 'course_name is required when creating a new course.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if department is None:
                return Response(
                    {'error': 'department is required when creating a new course.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            course = Course.objects.create(
                code=course_code,
                name=course_name,
                department=department,
                credit_hours=credit_hours,
            )
            logger.info(f"Created new course: {course}")

        # ── 2. Find or create the CourseOffering ─────────────────────────────
        course_offering, offering_created = CourseOffering.objects.get_or_create(
            course=course,
            semester=semester,
            year=year,
            instructor=request.user,
            defaults={
                'capacity': 30,
                'is_active': True,
            },
        )
        if offering_created:
            logger.info(f"Created new CourseOffering: {course_offering}")

        # ── 3. Duplicate lecture guard (scoped to this specific offering) ─────
        #    Two offerings can each have their own "Lecture 1" — the check is
        #    deliberately confined to (course_offering + title).
        if CourseMaterial.objects.filter(
            course_offering=course_offering,
            title__iexact=lecture_title,
        ).exists():
            return Response(
                {
                    'error': 'Lecture already exists for this course offering.',
                    'detail': (
                        f'"{lecture_title}" is already uploaded under '
                        f'{course_offering.course.code} — '
                        f'{course_offering.semester} {course_offering.year}.'
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        # ── 4. Save the file and create the CourseMaterial record ─────────────
        import os
        ext = os.path.splitext(uploaded_file.name)[1].lstrip('.').lower()
        material = CourseMaterial.objects.create(
            course_offering=course_offering,
            title=lecture_title,
            material_type=material_type,
            file=uploaded_file,
            file_url='',
            file_type=ext,
            file_size=uploaded_file.size,
            uploaded_by=request.user,
            is_visible_to_students=is_visible,
        )
        logger.info(f"Material saved: {material.title} (id={material.pk})")

        # ── 5. RAG ingestion → Qdrant ─────────────────────────────────────────
        rag_status = 'ok'
        try:
            from ai_engine.ai_services import get_rag_pipeline
            rag = get_rag_pipeline()

            # Ensure vector store is loaded before incremental add
            if not rag.is_initialized:
                try:
                    rag.vector_store_manager.load_vector_store()
                    rag.is_initialized = True
                except Exception:
                    logger.warning(
                        'Vector store not found during course upload; '
                        'RAG pipeline will create it from scratch.'
                    )

            file_path = material.file.path
            logger.info(
                f'Triggering RAG ingestion: {file_path} '
                f'(course_code={course_code})'
            )
            rag.add_documents(file_path, course_code=course_code)
            logger.info('RAG ingestion complete — document pushed to Qdrant.')
        except Exception as ai_err:
            logger.error(f'RAG ingestion failed for "{material.title}": {ai_err}')
            rag_status = f'warning: RAG ingestion failed — {ai_err}'
            # We do NOT roll back the DB record if AI indexing fails;
            # the file is safely stored and can be re-indexed later.

        # ── 6. Notify enrolled students ───────────────────────────────────────
        if is_visible:
            MaterialListView._notify_enrolled_students(material)

        # ── 7. Return response ────────────────────────────────────────────────
        response_data = MaterialSerializer(material, context={'request': request}).data
        response_data['course_offering_id'] = course_offering.pk
        response_data['course_code'] = course.code
        response_data['course_name'] = course.name
        response_data['offering_created'] = offering_created
        response_data['rag_ingestion'] = rag_status

        return Response(response_data, status=status.HTTP_201_CREATED)


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


class InstructorChatAIView(APIView):
    """
    POST /api/professor/chat/  — Professor sends a message to their own AI assistant.
    GET  /api/professor/chat/  — (kept) List student conversations in instructor's courses.

    For the GET, add ?mode=own to get the professor's own AI conversations instead.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mode = request.query_params.get('mode', 'students')
        if mode == 'own':
            # Return the professor's own AI conversations
            conversations = ChatConversation.objects.filter(
                student=request.user, is_archived=False
            ).order_by('-updated_at')
        else:
            # Legacy: return student conversations in professor's courses
            courses = CourseOffering.objects.filter(
                instructor=request.user
            ) | CourseOffering.objects.filter(tas=request.user)
            conversations = ChatConversation.objects.filter(
                course_offering__in=courses.distinct()
            ).select_related('student', 'course_offering__course')
            conversations = conversations.order_by('-updated_at')
        serializer = ChatConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Professor sends a message to their own AI assistant."""
        content = request.data.get('content')
        course_id = request.data.get('course_id')
        conversation_id = request.data.get('conversation_id')

        if not content:
            return Response(
                {'error': 'content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Resolve course offering
        course_offering = None
        if course_id:
            course_offering = get_object_or_404(CourseOffering, pk=course_id)
        else:
            # Default to first course the instructor teaches
            course_offering = CourseOffering.objects.filter(
                instructor=request.user
            ).first()

        # Get or create conversation (professor is stored as 'student' on the model)
        if conversation_id:
            conversation = get_object_or_404(
                ChatConversation, pk=conversation_id, student=request.user
            )
        else:
            conversation = ChatConversation.objects.create(
                student=request.user,
                course_offering=course_offering,
                title=content[:100]
            )

        # Build conversation history for context
        history_msgs = conversation.messages.all().order_by('-timestamp')[:10]
        history = []
        for m in reversed(history_msgs):
            role = 'user' if m.role == ChatMessage.Role.USER else 'assistant'
            history.append({'role': role, 'content': m.content})

        # Save user message
        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=content
        )

        # Build enrolled course filters (all courses instructor teaches)
        taught_courses = CourseOffering.objects.filter(
            instructor=request.user
        ) | CourseOffering.objects.filter(tas=request.user)
        taught_courses = taught_courses.distinct().select_related('course')

        course_codes = []
        for co in taught_courses:
            code = co.course.code
            name = co.course.name
            course_codes.append(code)
            course_codes.append(name)
            if ' ' in code:
                course_codes.append(code.split(' ')[0])
            match = re.match(r'^([a-zA-Z]+)', code)
            if match:
                course_codes.append(match.group(1))

        # Query the RAG engine
        try:
            from ai_engine.ai_services import get_rag_pipeline
            rag = get_rag_pipeline()
            ai_result = rag.query(
                question=content,
                history=history,
                selected_course=None,
                user_courses=course_codes if course_codes else None
            )
            ai_response_content = ai_result.get('answer', "I'm sorry, I couldn't process that.")
            sources = ai_result.get('sources', [])
        except Exception as e:
            logger.error(f'Professor AI chat error: {e}')
            ai_response_content = f'Error: {str(e)}'
            sources = []

        # Save AI response
        ai_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=ai_response_content,
            sources_used=sources,
            was_from_rag=True
        )

        conversation.save()  # updates updated_at

        return Response({
            'conversation_id': conversation.id,
            'user_message': ChatMessageSerializer(user_msg).data,
            'ai_message': ChatMessageSerializer(ai_msg).data,
        })


class InstructorConversationListView(APIView):
    """
    GET  /api/professor/conversations/  — List professor's own AI conversations.
    POST /api/professor/conversations/  — Create a new empty conversation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = ChatConversation.objects.filter(
            student=request.user, is_archived=False
        ).order_by('-updated_at')
        serializer = ChatConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        title = request.data.get('title', 'New Conversation')
        course_id = request.data.get('course_id')

        course_offering = None
        if course_id:
            course_offering = get_object_or_404(CourseOffering, pk=course_id)
        else:
            course_offering = CourseOffering.objects.filter(
                instructor=request.user
            ).first()

        conversation = ChatConversation.objects.create(
            student=request.user,
            course_offering=course_offering,
            title=title[:100]
        )
        return Response(
            ChatConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED
        )


class InstructorConversationDetailView(APIView):
    """
    GET    /api/professor/conversations/<id>/  — Get conversation + messages.
    PATCH  /api/professor/conversations/<id>/  — Rename title.
    DELETE /api/professor/conversations/<id>/  — Archive conversation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(
            ChatConversation, pk=pk, student=request.user
        )
        messages = conversation.messages.all().order_by('timestamp')
        data = ChatConversationSerializer(conversation).data
        data['messages'] = ChatMessageSerializer(messages, many=True).data
        return Response(data)

    def patch(self, request, pk):
        conversation = get_object_or_404(
            ChatConversation, pk=pk, student=request.user
        )
        title = request.data.get('title')
        if not title:
            return Response(
                {'error': 'title is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation.title = title[:100]
        conversation.save()
        return Response(ChatConversationSerializer(conversation).data)

    def delete(self, request, pk):
        conversation = get_object_or_404(
            ChatConversation, pk=pk, student=request.user
        )
        conversation.is_archived = True
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


# ══════════════════════════════════════════════════════════════════════════════
# Rubric-Driven Auto Revision Engine — TA / Professor Views
# ══════════════════════════════════════════════════════════════════════════════
#
# These views use models from main/ and serializers from grading/.
# The grading app itself registers NO URLs (Hollow App pattern).
# ══════════════════════════════════════════════════════════════════════════════

from grading.serializers import (
    RubricAssignmentCreateSerializer,
    RubricAssignmentListSerializer,
    RubricAssignmentDetailSerializer,
    GradedSubmissionSerializer,
    GradingResultSerializer,
    GradingResultDebugSerializer,
)

# logger already defined at module level above


def _is_ta_or_professor(user):
    """Check if the user has TA or Professor role."""
    return user.primary_role in (User.Role.TA, User.Role.PROFESSOR)


class RubricAssignmentListCreateView(APIView):
    """
    GET  → List all rubric-graded assignments for the instructor's courses.
    POST → Create a new assignment with rubric grading enabled.

    Access: TA / Professor only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can view rubric assignments."},
                status=status.HTTP_403_FORBIDDEN
            )

        courses = CourseOffering.objects.filter(
            instructor=request.user
        ) | CourseOffering.objects.filter(tas=request.user)
        courses = courses.distinct()

        assignments = Assignment.objects.filter(
            course_offering__in=courses,
            grading_type__isnull=False
        ).select_related(
            'course_offering__course', 'created_by'
        ).order_by('-created_at')

        course_id = request.query_params.get('course_offering')
        if course_id:
            assignments = assignments.filter(course_offering_id=course_id)

        serializer = RubricAssignmentListSerializer(assignments, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can create rubric assignments."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = RubricAssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            assignment = serializer.save(created_by=request.user)
            logger.info(
                f"Rubric assignment created: '{assignment.title}' "
                f"(type={assignment.grading_type}) by {request.user.full_name}"
            )
            return Response(
                RubricAssignmentDetailSerializer(assignment).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RubricAssignmentDetailView(APIView):
    """
    GET    → Full assignment detail with submissions and grading results.
    PATCH  → Update assignment fields (rubric, model answer, etc.).
    DELETE → Delete assignment.

    Access: TA / Professor only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can view assignment details."},
                status=status.HTTP_403_FORBIDDEN
            )
        assignment = get_object_or_404(Assignment, pk=pk)
        serializer = RubricAssignmentDetailSerializer(assignment)
        return Response(serializer.data)

    def patch(self, request, pk):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can update assignments."},
                status=status.HTTP_403_FORBIDDEN
            )
        assignment = get_object_or_404(Assignment, pk=pk)
        serializer = RubricAssignmentCreateSerializer(
            assignment, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(RubricAssignmentDetailSerializer(assignment).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can delete assignments."},
                status=status.HTTP_403_FORBIDDEN
            )
        assignment = get_object_or_404(Assignment, pk=pk)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegradeSubmissionView(APIView):
    """
    POST → Re-trigger AI grading for a specific submission.
           Useful when rubric was updated or LLM result was unsatisfactory.

    Access: TA / Professor only.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can re-trigger grading."},
                status=status.HTTP_403_FORBIDDEN
            )

        submission = get_object_or_404(StudentSubmission, pk=pk)

        if not submission.submitted_text:
            return Response(
                {"error": "This submission has no text content to grade."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from ai_engine.services.grading_service import get_grading_engine
            engine = get_grading_engine()
            grading_result = engine.grade_submission(submission.pk)

            return Response({
                "message": "Re-grading complete.",
                "result": GradingResultDebugSerializer(grading_result).data,
            })
        except Exception as e:
            logger.error(f"Re-grading failed for submission #{pk}: {e}")
            return Response(
                {"error": f"Re-grading failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InstructorGradingResultView(APIView):
    """
    GET → View a specific grading result with debug info (raw_llm_response).

    Access: TA / Professor only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _is_ta_or_professor(request.user):
            return Response(
                {"error": "Only TAs and Professors can view grading debug info."},
                status=status.HTTP_403_FORBIDDEN
            )

        result = get_object_or_404(
            GradingResult.objects.select_related(
                'submission__student', 'submission__assignment'
            ),
            pk=pk
        )
        serializer = GradingResultDebugSerializer(result)
        return Response(serializer.data)


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
