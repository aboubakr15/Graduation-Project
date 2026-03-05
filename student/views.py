from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import (
    DashboardSerializer, 
    StudentProfileSerializer, 
    CourseListSerializer, 
    CourseDetailSerializer, 
    ToDoItemSerializer, 
    ChatMessageSerializer,
    EnrollmentSerializer,
    StudentSubmissionSerializer,
    GradeSerializer,
    NotificationSerializer
)
from main.models import (
    User, CourseOffering, Enrollment, TodoItem, ChatConversation, ChatMessage,
    StudentSubmission, Notification, Assignment, Announcement
)

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
        anns = Announcement.objects.filter(is_global=True).order_by('-created_at')[:3]
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

class StudentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = StudentProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = StudentProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StudentChatBotView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return simplified chat history for the last conversation or all conversations
        # For now, let's just return the last conversation's messages
        conversation = ChatConversation.objects.filter(student=request.user).order_by('-updated_at').first()
        if not conversation:
            return Response([])
        
        messages = conversation.messages.all().order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        content = request.data.get('content')
        course_id = request.data.get('course_id') # Optional, if chatting about a specific course
        
        if not content:
            return Response({"error": "Content is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create conversation
        if course_id:
             course = get_object_or_404(CourseOffering, pk=course_id)
             conversation, created = ChatConversation.objects.get_or_create(
                 student=request.user, course_offering=course
             )
        else:
            # General conversation - maybe link to a dummy "General" course or make course nullable in ChatConversation?
            # Model says course_offering is required. 
            # For now, let's pick the first active course or handle this edge case.
            # Ideally model should allow null course_offering for general chat.
            # I will query the first available course for now to avoid errors, or fail if no enrollment.
            enrollment = Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE).first()
            if not enrollment:
                 return Response({"error": "No active enrollments to start chat context"}, status=status.HTTP_400_BAD_REQUEST)
            conversation, created = ChatConversation.objects.get_or_create(
                 student=request.user, course_offering=enrollment.course_offering
            )

        # Helper to create message
        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=content
        )

        # Mock AI Response
        ai_response_content = f"This is a mock response to '{content}'. I am a student assistant AI."
        ai_msg = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=ai_response_content
        )
        
        return Response({
            "user_message": ChatMessageSerializer(user_msg).data,
            "ai_message": ChatMessageSerializer(ai_msg).data
        })

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
        
        if not assignment_id:
            return Response({"error": "assignment_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        assignment = get_object_or_404(Assignment, pk=assignment_id)
        
        if not Enrollment.objects.filter(student=request.user, course_offering=assignment.course_offering, status=Enrollment.Status.ACTIVE).exists():
            return Response({"error": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
        
        submission, created = StudentSubmission.objects.update_or_create(
            student=request.user,
            assignment=assignment,
            defaults={
                'file_url': file_url,
                'status': StudentSubmission.Status.SUBMITTED
            }
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
