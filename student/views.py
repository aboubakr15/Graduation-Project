from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView
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
    ChatMessageSerializer
)
from main.models import (
    User, CourseOffering, Enrollment, TodoItem, ChatConversation, ChatMessage
)

class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.primary_role != User.Role.STUDENT:
            return Response({"error": "User is not a student"}, status=status.HTTP_403_FORBIDDEN)
        
        # DashboardSerializer expects a user instance as the source
        serializer = DashboardSerializer(user, context={'request': request})
        # We need to restructure the response to match the fields in DashboardSerializer 
        # because DashboardSerializer is a Serializer, not ModelSerializer, 
        # but it uses 'source="*"' on profile, which might be tricky.
        # Let's simplify: pass the user object to the serializer.
        
        return Response(serializer.data)

class StudentCourseListView(ListAPIView):
    serializer_class = CourseListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(
            student=self.request.user, 
            status=Enrollment.Status.ACTIVE
        )

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

class StudentProfileView(RetrieveAPIView):
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

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
