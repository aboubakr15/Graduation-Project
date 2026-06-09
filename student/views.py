import logging
import os
import re
import uuid
import mimetypes
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView, RetrieveUpdateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from .serializers import (
    DashboardSerializer, 
    StudentProfileSerializer, 
    CourseListSerializer, 
    CourseDetailSerializer, 
    ToDoItemSerializer, 
    ChatMessageSerializer,
    ChatConversationSerializer,
    EnrollmentSerializer,
    StudentSubmissionSerializer,
    GradeSerializer,
    NotificationSerializer
)
from main.models import (
    User, CourseOffering, Enrollment, TodoItem, ChatConversation, ChatMessage,
    StudentSubmission, Notification, Assignment, Announcement, CourseMaterial
)
from grading.models import GradingResult

logger = logging.getLogger(__name__)

class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.primary_role != User.Role.STUDENT:
            return Response({"error": "User is not a student"}, status=status.HTTP_403_FORBIDDEN)
        
        data = {
            'profile': StudentProfileSerializer(user, context={'request': request}).data,
            'portal_announcements': self._get_portal_announcements(),
            'course_announcements': self._get_course_announcements(user),
            'courses_progress': self._get_courses_progress(user),
            'completed_courses_count': Enrollment.objects.filter(student=user, status=Enrollment.Status.COMPLETED).count(),
            'in_progress_courses_count': Enrollment.objects.filter(student=user, status=Enrollment.Status.ACTIVE).count(),
        }
        return Response(data)

    def _get_portal_announcements(self):
        from .serializers import AnnouncementSerializer
        anns = Announcement.objects.filter(is_global=True, author__primary_role=User.Role.ADMIN).order_by('-created_at')[:3]
        return AnnouncementSerializer(anns, many=True).data

    def _get_course_announcements(self, user):
        from .serializers import AnnouncementSerializer
        enrolled_course_ids = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list('course_offering_id', flat=True)
        anns = Announcement.objects.filter(
            course_offering_id__in=enrolled_course_ids
        ).order_by('-created_at')[:3]
        return AnnouncementSerializer(anns, many=True).data

    def _get_courses_progress(self, user):
        from .serializers import CourseProgressSerializer
        enrollments = Enrollment.objects.filter(student=user, status=Enrollment.Status.ACTIVE)
        course_offerings = [e.course_offering for e in enrollments]
        return CourseProgressSerializer(course_offerings, many=True).data

class StudentCourseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollments = Enrollment.objects.filter(
            student=request.user, 
            status=Enrollment.Status.ACTIVE
        )
        serializer = CourseListSerializer(enrollments, many=True)
        return Response(serializer.data)

    def post(self, request):
        course_offering_id = request.data.get('course_offering_id')
        if not course_offering_id:
            return Response({"error": "course_offering_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        course_offering = get_object_or_404(CourseOffering, pk=course_offering_id, is_active=True)
        
        if Enrollment.objects.filter(student=request.user, course_offering=course_offering).exists():
            return Response({"error": "Already enrolled in this course"}, status=status.HTTP_400_BAD_REQUEST)
        
        if course_offering.enrollment_count >= course_offering.capacity:
            return Response({"error": "Course is full"}, status=status.HTTP_400_BAD_REQUEST)
        
        enrollment = Enrollment.objects.create(
            student=request.user,
            course_offering=course_offering,
            status=Enrollment.Status.ACTIVE
        )
        course_offering.enrollment_count += 1
        course_offering.save()
        
        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)

class StudentCourseDetailView(RetrieveAPIView):
    serializer_class = CourseDetailSerializer
    permission_classes = [IsAuthenticated]
    queryset = CourseOffering.objects.all()

    def get_object(self):
        # Ensure the student is enrolled in this course
        course_id = self.kwargs.get('pk')
        course = get_object_or_404(CourseOffering, pk=course_id)
        # Check enrollment
        if not Enrollment.objects.filter(student=self.request.user, course_offering=course, status=Enrollment.Status.ACTIVE).exists():
            self.permission_denied(self.request, message="You are not enrolled in this course.")
        return course

class StudentToDoListView(ListCreateAPIView):
    serializer_class = ToDoItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TodoItem.objects.filter(student=self.request.user).order_by('due_date')

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

class StudentToDoDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ToDoItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TodoItem.objects.filter(student=self.request.user)

class StudentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = StudentProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        if 'profile_picture' in request.FILES:
            from django.core.files.storage import default_storage
            file = request.FILES['profile_picture']
            path = default_storage.save(f"profiles/{request.user.id}_{file.name}", file)
            request.user.profile_picture_url = request.build_absolute_uri(default_storage.url(path))
            request.user.save()

        serializer = StudentProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StudentChatBotView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return all conversations for the student
        conversations = ChatConversation.objects.filter(student=request.user, is_archived=False)
        serializer = ChatConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        content = request.data.get('content')
        course_id = request.data.get('course_id')
        conversation_id = request.data.get('conversation_id')
        
        if not content:
            return Response({"error": "Content is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create conversation
        if conversation_id:
            conversation = get_object_or_404(ChatConversation, pk=conversation_id, student=request.user)
            course_offering = conversation.course_offering
        elif course_id:
             course_offering = get_object_or_404(CourseOffering, pk=course_id)
             # Create a new conversation for this course
             conversation = ChatConversation.objects.create(
                 student=request.user, 
                 course_offering=course_offering,
                 title=content[:50]  # Use first message as title
             )
        else:
            # Fallback to first active enrollment if provided, otherwise proceed without one
            enrollment = Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE).first()
            course_offering = enrollment.course_offering if enrollment else None
            
            conversation = ChatConversation.objects.create(
                 student=request.user, 
                 course_offering=course_offering,
                 title=content[:50]
            )

        # Fetch last 10 messages for context
        history_msgs = conversation.messages.all().order_by('-timestamp')[:10]
        history = []
        for m in reversed(history_msgs):
            role = "user" if m.role == ChatMessage.Role.USER else "assistant"
            history.append({"role": role, "content": m.content})

        # Save user message
        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=content
        )

        # Execute AI Query
        selected_course = course_offering.course.code if course_offering else None
        
        # Build list of ALL enrolled course identifiers (Codes + Names)
        # This handles cases where Qdrant might be indexed by folder names instead of codes
        enrollments = Enrollment.objects.filter(
            student=request.user,
            status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED],
        ).select_related('course_offering__course')
        
        # Build list of enrolled course identifiers (Codes + Names + Prefixes)
        # If a specific course is selected, we only use its identifiers for strictness
        filter_enrollments = enrollments
        if course_offering:
            filter_enrollments = enrollments.filter(course_offering=course_offering)
            
        enrolled_course_codes = []
        for e in filter_enrollments:
            code = e.course_offering.course.code
            name = e.course_offering.course.name
            enrolled_course_codes.append(code)
            enrolled_course_codes.append(name)
            
            # Add prefix (e.g., 'AI 330' -> 'AI')
            if ' ' in code:
                enrolled_course_codes.append(code.split(' ')[0])
            
            match = re.match(r'^([a-zA-Z]+)', code)
            if match:
                enrolled_course_codes.append(match.group(1))

            # ── KEY FIX: Qdrant indexes docs by UPPERCASE FOLDER NAME (e.g. 'DATA SCIENCE')
            # The DB course name may have a suffix like 'Intro', so we generate all
            # word-prefix n-grams so the exact Qdrant key is always in the filter list.
            # e.g. 'Data Science Intro' → ['DATA', 'DATA SCIENCE', 'DATA SCIENCE INTRO']
            words = name.upper().split()
            for i in range(1, len(words) + 1):
                enrolled_course_codes.append(' '.join(words[:i]))
            
        try:
            from ai_engine.ai_services import get_rag_pipeline
            rag = get_rag_pipeline()

            ai_result = rag.query(
                question=content,
                history=history,
                selected_course=None, # We handle filtering via user_courses list for better matching
                user_courses=enrolled_course_codes
            )
            ai_response_content = ai_result.get("answer", "I'm sorry, I couldn't process that.")
            sources = ai_result.get("sources", [])
        except Exception as e:
            ai_response_content = f"Error: {str(e)}"
            sources = []

        # Save AI Response
        ai_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=ai_response_content,
            sources_used=sources,
            was_from_rag=True
        )
        
        # Update conversation timestamp
        conversation.save() # Updates updated_at
        
        return Response({
            "conversation_id": conversation.id,
            "user_message": ChatMessageSerializer(user_msg).data,
            "ai_message": ChatMessageSerializer(ai_msg).data
        })

class StudentChatConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(ChatConversation, pk=pk, student=request.user)
        messages = conversation.messages.all().order_by('timestamp')
        
        data = ChatConversationSerializer(conversation).data
        data['messages'] = ChatMessageSerializer(messages, many=True).data
        
        return Response(data)

    def delete(self, request, pk):
        conversation = get_object_or_404(ChatConversation, pk=pk, student=request.user)
        conversation.is_archived = True
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentChatMessagesView(APIView):
    """
    GET /api/student/chat/messages/?conversation_id=<id>
    Returns all messages in a conversation in chronological order.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversation_id = request.query_params.get('conversation_id')
        if not conversation_id:
            return Response(
                {'error': 'conversation_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = get_object_or_404(
            ChatConversation, pk=conversation_id, student=request.user
        )
        messages = conversation.messages.all().order_by('timestamp')
        return Response(ChatMessageSerializer(messages, many=True).data)


class StudentConversationView(APIView):
    """
    GET  /api/student/conversations/        — list all non-archived conversations
    POST /api/student/conversations/        — create a new empty conversation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = ChatConversation.objects.filter(
            student=request.user, is_archived=False
        ).order_by('-updated_at')
        return Response(ChatConversationSerializer(conversations, many=True).data)

    def post(self, request):
        title = request.data.get('title', 'New Conversation')
        course_id = request.data.get('course_id')

        course_offering = None
        if course_id:
            course_offering = get_object_or_404(CourseOffering, pk=course_id)

        if not course_offering:
            enrollment = Enrollment.objects.filter(
                student=request.user, status=Enrollment.Status.ACTIVE
            ).first()
            course_offering = enrollment.course_offering if enrollment else None

        conversation = ChatConversation.objects.create(
            student=request.user,
            course_offering=course_offering,
            title=title[:100]
        )
        return Response(
            ChatConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED
        )


class StudentConversationDetailView(APIView):
    """
    GET    /api/student/conversations/<id>/  — get conversation + its messages
    PATCH  /api/student/conversations/<id>/  — rename conversation title
    DELETE /api/student/conversations/<id>/  — archive conversation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(ChatConversation, pk=pk, student=request.user)
        messages = conversation.messages.all().order_by('timestamp')
        data = ChatConversationSerializer(conversation).data
        data['messages'] = ChatMessageSerializer(messages, many=True).data
        return Response(data)

    def patch(self, request, pk):
        conversation = get_object_or_404(ChatConversation, pk=pk, student=request.user)
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
        conversation = get_object_or_404(ChatConversation, pk=pk, student=request.user)
        conversation.is_archived = True
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentCourseChatListView(APIView):
    """
    GET  /api/student/courses/<id>/chat/  — Return the last 100 messages for the course.
    POST /api/student/courses/<id>/chat/  — Send a new message to the course chat.

    Access: Students actively enrolled in the course only.
    """
    permission_classes = [IsAuthenticated]

    def _check_enrollment(self, user, course_id):
        """Return the CourseOffering if user is enrolled (ACTIVE), else None."""
        offering = get_object_or_404(CourseOffering, pk=course_id)
        enrolled = Enrollment.objects.filter(
            student=user,
            course_offering=offering,
            status=Enrollment.Status.ACTIVE,
        ).exists()
        return offering if enrolled else None

    def get(self, request, pk):
        """Return last 100 messages chronologically for the course."""
        from main.models import CourseChatMessage
        from instructor.serializers import CourseChatMessageSerializer
        offering = self._check_enrollment(request.user, pk)
        if offering is None:
            return Response({'detail': 'You are not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        msgs = CourseChatMessage.objects.filter(
            course_offering=offering
        ).order_by('created_at').select_related('sender')[:100]
        return Response(CourseChatMessageSerializer(msgs, many=True).data)

    def post(self, request, pk):
        """Send a new message to the course group chat."""
        from main.models import CourseChatMessage
        from instructor.serializers import CourseChatMessageSerializer
        offering = self._check_enrollment(request.user, pk)
        if offering is None:
            return Response({'detail': 'You are not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        content = (request.data.get('content') or '').strip()
        if not content:
            return Response({'detail': 'content is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not offering.is_chat_active:
            return Response({'detail': 'Chat is currently disabled for this course.'}, status=status.HTTP_403_FORBIDDEN)

        msg = CourseChatMessage.objects.create(
            course_offering=offering,
            sender=request.user,
            sender_name=request.user.full_name,
            sender_role=request.user.primary_role,
            content=content,
        )
        return Response(CourseChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class StudentEnrollmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        queryset = Enrollment.objects.filter(student=request.user)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        serializer = EnrollmentSerializer(queryset, many=True)
        return Response(serializer.data)

    def delete(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk, student=request.user)
        course_offering = enrollment.course_offering
        enrollment.status = Enrollment.Status.DROPPED
        enrollment.save()
        course_offering.enrollment_count = max(0, course_offering.enrollment_count - 1)
        course_offering.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class StudentSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        submissions = StudentSubmission.objects.filter(student=request.user).order_by('-submission_date')
        serializer = StudentSubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        file_url = request.data.get('file_url')
        uploaded_file = request.FILES.get('file')

        if not assignment_id:
            return Response({"error": "assignment_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        assignment = get_object_or_404(Assignment, pk=assignment_id)

        if not Enrollment.objects.filter(student=request.user, course_offering=assignment.course_offering, status=Enrollment.Status.ACTIVE).exists():
            return Response({"error": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)

        defaults = {
            'file_url': file_url or '',
            'status': StudentSubmission.Status.SUBMITTED
        }
        if uploaded_file:
            defaults['file'] = uploaded_file

        submission, created = StudentSubmission.objects.update_or_create(
            student=request.user,
            assignment=assignment,
            defaults=defaults
        )
        return Response(StudentSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

class StudentGradesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollments = Enrollment.objects.filter(
            student=request.user,
            status__in=[Enrollment.Status.COMPLETED, Enrollment.Status.ACTIVE],
            grade__isnull=False
        ).order_by('-enrollment_date')
        serializer = GradeSerializer(enrollments, many=True)
        return Response(serializer.data)

class StudentAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrolled_offering_ids = Enrollment.objects.filter(
            student=request.user,
            status=Enrollment.Status.ACTIVE
        ).values_list('course_offering_id', flat=True)
        assignments = Assignment.objects.filter(
            course_offering_id__in=enrolled_offering_ids
        ).order_by('due_date')
        from .serializers import StudentAssignmentListSerializer
        serializer = StudentAssignmentListSerializer(assignments, many=True)
        return Response(serializer.data)

class StudentNotificationsView(APIView):
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


class StudentMaterialDownloadView(APIView):
    """
    Authenticated, enrollment-checked file download for students.

    GET /api/student/materials/<pk>/download/

    Conditions for access:
      • The student must be actively enrolled in the material’s course.
      • is_visible_to_students must be True.

    The file is streamed via FileResponse (chunked) so large videos
    don’t need to be buffered in memory.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        material = get_object_or_404(
            CourseMaterial.objects.select_related('course_offering__course'),
            pk=pk,
        )

        if not material.is_visible_to_students:
            return Response(
                {'detail': 'You do not have access to this material.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course_offering=material.course_offering,
            status=Enrollment.Status.ACTIVE,
        ).exists()

        if not is_enrolled:
            return Response(
                {'detail': 'You are not enrolled in this course.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not material.file:
            return Response(
                {'detail': 'No file is stored for this material.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        mime_type, _ = mimetypes.guess_type(material.file.name)
        mime_type = mime_type or 'application/octet-stream'

        response = FileResponse(
            material.file.open('rb'),
            content_type=mime_type,
            as_attachment=False,
        )
        filename = os.path.basename(material.file.name)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class StudentAssignmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        assignment = get_object_or_404(
            Assignment.objects.select_related('course_offering'),
            pk=pk,
        )
        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course_offering=assignment.course_offering,
            status=Enrollment.Status.ACTIVE,
        ).exists()

        if not is_enrolled:
            return Response(
                {'detail': 'You are not enrolled in this course.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not getattr(assignment, 'file', None):
            return Response(
                {'detail': 'No file is stored for this assignment.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        mime_type, _ = mimetypes.guess_type(assignment.file.name)
        mime_type = mime_type or 'application/octet-stream'

        response = FileResponse(
            assignment.file.open('rb'),
            content_type=mime_type,
            as_attachment=False,
        )
        import os
        filename = os.path.basename(assignment.file.name)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class StudentSubmissionDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        submission = get_object_or_404(
            StudentSubmission.objects.select_related('assignment__course_offering'),
            pk=pk,
            student=request.user,
        )
        file_path = submission.file_url
        if getattr(submission, 'file', None):
            mime_type, _ = mimetypes.guess_type(submission.file.name)
            mime_type = mime_type or 'application/octet-stream'
            response = FileResponse(
                submission.file.open('rb'),
                content_type=mime_type,
                as_attachment=False,
            )
            import os
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(submission.file.name)}"'
            return response
            
        if not file_path:
            return Response(
                {'detail': 'No file for this submission.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        # file_url is either /media/submissions/... or an external URL
        if file_path.startswith('/media/'):
            from django.conf import settings
            import os
            full_path = os.path.join(str(settings.MEDIA_ROOT), file_path.replace('/media/', '').lstrip('/'))
            if not os.path.exists(full_path):
                return Response(
                    {'detail': 'File not found on server.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            mime_type, _ = mimetypes.guess_type(full_path)
            mime_type = mime_type or 'application/octet-stream'
            response = FileResponse(
                open(full_path, 'rb'),
                content_type=mime_type,
                as_attachment=False,
            )
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(full_path)}"'
            return response
        # external URL – redirect
        from django.shortcuts import redirect
        return redirect(file_path)

# ══════════════════════════════════════════════════════════════════════════════
# Rubric-Driven Auto Revision Engine — Student Views
# ══════════════════════════════════════════════════════════════════════════════
#
# These views use models from main/ and serializers from grading/.
# The grading app itself registers NO URLs (Hollow App pattern).
# ══════════════════════════════════════════════════════════════════════════════

from grading.serializers import (
    SubmissionCreateSerializer,
    GradedSubmissionSerializer,
    GradingResultSerializer,
)

import logging
logger_grading = logging.getLogger("grading")


class StudentRubricSubmitView(APIView):
    """
    POST → Student submits their text/code for a rubric-graded assignment.
           The system automatically grades the submission using the AI engine.

    Flow:
        1. Validate the student is enrolled in the course.
        2. Create or update the StudentSubmission.
        3. Trigger the GradingEngine to auto-grade.
        4. Return the submission with grading results.

    Access: Students only.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.primary_role != User.Role.STUDENT:
            return Response(
                {"error": "Only students can submit assignments."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        assignment_id = serializer.validated_data['assignment_id']
        submitted_text = serializer.validated_data['submitted_text']

        assignment = get_object_or_404(Assignment, pk=assignment_id)

        # Verify enrollment
        if not Enrollment.objects.filter(
            student=request.user,
            course_offering=assignment.course_offering,
            status=Enrollment.Status.ACTIVE
        ).exists():
            return Response(
                {"error": "You are not enrolled in this course."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create or update submission
        submission, created = StudentSubmission.objects.update_or_create(
            student=request.user,
            assignment=assignment,
            defaults={
                'submitted_text': submitted_text,
                'status': StudentSubmission.Status.SUBMITTED,
            }
        )

        logger_grading.info(
            f"Submission {'created' if created else 'updated'}: "
            f"#{submission.pk} by {request.user.full_name} "
            f"for '{assignment.title}'"
        )

        # ── Auto-Grade ─────────────────────────────────────────────────────────
        # Trigger the GradingEngine synchronously on submission.
        # For production, consider Celery for async task processing.
        # ────────────────────────────────────────────────────────────────────
        try:
            from ai_engine.services.grading_service import get_grading_engine
            engine = get_grading_engine()
            grading_result = engine.grade_submission(submission.pk)

            logger_grading.info(
                f"Auto-grading complete: {grading_result.total_score}/{grading_result.max_score}"
            )
        except Exception as e:
            logger_grading.error(f"Auto-grading failed for submission #{submission.pk}: {e}")
            # Return the submission even if grading failed — don't lose student work
            return Response(
                {
                    "submission": GradedSubmissionSerializer(submission).data,
                    "grading_error": str(e),
                    "message": "Submission saved but auto-grading encountered an error. "
                               "A TA will review manually.",
                },
                status=status.HTTP_201_CREATED
            )

        # Refresh to pick up the grading_result relation
        submission.refresh_from_db()

        return Response(
            {
                "submission": GradedSubmissionSerializer(submission).data,
                "message": "Submission received and graded successfully.",
            },
            status=status.HTTP_201_CREATED
        )


class StudentGradingResultListView(APIView):
    """
    GET → Students see all their rubric grading results across all courses.

    Optional query params:
        - assignment_id: Filter to a specific assignment.
        - course_offering: Filter to a specific course.

    Access: Students only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.primary_role != User.Role.STUDENT:
            return Response(
                {"error": "This endpoint is for students only."},
                status=status.HTTP_403_FORBIDDEN
            )

        results = GradingResult.objects.filter(
            submission__student=request.user
        ).select_related(
            'submission__assignment__course_offering__course',
            'submission__student'
        ).order_by('-graded_at')

        assignment_id = request.query_params.get('assignment_id')
        if assignment_id:
            results = results.filter(submission__assignment_id=assignment_id)

        course_id = request.query_params.get('course_offering')
        if course_id:
            results = results.filter(
                submission__assignment__course_offering_id=course_id
            )

        serializer = GradingResultSerializer(results, many=True)
        return Response(serializer.data)


class StudentGradingResultDetailView(APIView):
    """
    GET → View a single grading result detail.

    Access: Students can only see their own results.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        result = get_object_or_404(
            GradingResult.objects.select_related(
                'submission__student', 'submission__assignment'
            ),
            pk=pk
        )

        # Students can only see their own results
        if result.submission.student_id != request.user.id:
            return Response(
                {"error": "You can only view your own grading results."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GradingResultSerializer(result)
        return Response(serializer.data)
