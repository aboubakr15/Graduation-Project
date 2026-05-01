from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .permissions import IsAdminOnly
from .serializers import (
    AdminDashboardSummarySerializer,
    CourseSerializer,
    UserSerializer,
    AnnouncementSerializer,
    CourseMaterialSerializer,
    ChatConversationSerializer,
    ChatMessageSerializer,
    NotificationSerializer,
    DepartmentSerializer,
    CourseOfferingSerializer,
    CourseOfferingCreateUpdateSerializer,
    EnrollmentSerializer,
    EnrollmentCreateUpdateSerializer,
    AdminProfileSerializer,
)
from .services import (
    AdminDashboardService,
    AdminCourseService,
    AdminUserService,
    AdminAnnouncementService,
    AdminMaterialService,
    AdminChatService,
    AdminNotificationService,
    AdminDepartmentService,
    AdminCourseOfferingService,
    AdminEnrollmentService,
)
from main.models import User


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminOnly]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        stats = AdminDashboardService.get_summary_stats()
        serializer = AdminDashboardSummarySerializer(stats)
        return Response(serializer.data)


class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = CourseSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "code"]
    filterset_fields = ["department"]

    def get_queryset(self):
        return AdminCourseService.get_courses_queryset()

    def perform_create(self, serializer):
        course = AdminCourseService.create_course(serializer.validated_data)
        serializer.instance = course

    def perform_update(self, serializer):
        course = AdminCourseService.update_course(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = course

    def perform_destroy(self, instance):
        AdminCourseService.delete_course(instance)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["primary_role"]

    def get_queryset(self):
        role = self.request.query_params.get("role")
        if role:
            return AdminUserService.get_users_by_role(role)
        return User.objects.all().select_related("department")

    def perform_update(self, serializer):
        user = AdminUserService.update_user(serializer.instance, serializer.validated_data)
        serializer.instance = user

    def perform_destroy(self, instance):
        AdminUserService.delete_user(instance)

    @action(detail=False, methods=["post"], url_path="instructors")
    def create_instructor(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AdminUserService.create_user(serializer.validated_data, User.Role.PROFESSOR)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="tas")
    def create_ta(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AdminUserService.create_user(serializer.validated_data, User.Role.TA)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class AnnouncementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        return AdminAnnouncementService.get_announcements()

    def perform_create(self, serializer):
        announcement = AdminAnnouncementService.create_announcement(
            self.request.user, serializer.validated_data
        )
        serializer.instance = announcement

    def perform_update(self, serializer):
        announcement = AdminAnnouncementService.update_announcement(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = announcement

    def perform_destroy(self, instance):
        AdminAnnouncementService.delete_announcement(instance)


class MaterialViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = CourseMaterialSerializer

    def get_queryset(self):
        return AdminMaterialService.get_materials()

    def perform_create(self, serializer):
        material = AdminMaterialService.upload_material(
            self.request.user, serializer.validated_data
        )
        serializer.instance = material

    def perform_update(self, serializer):
        material = AdminMaterialService.update_material(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = material

    def perform_destroy(self, instance):
        AdminMaterialService.delete_material(instance)

    @action(detail=False, methods=["post"])
    def upload(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = AdminMaterialService.upload_material(
            request.user, serializer.validated_data
        )
        return Response(CourseMaterialSerializer(material).data, status=status.HTTP_201_CREATED)


class ChatViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = ChatConversationSerializer

    def get_queryset(self):
        return AdminChatService.get_conversations()

    @action(detail=False, methods=["get"])
    def messages(self, request):
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return Response(
                {"error": "conversation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        messages = AdminChatService.get_messages(conversation_id)
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = NotificationSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        return AdminNotificationService.get_notifications(self.request.user)


class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = DepartmentSerializer
    filter_backends = [SearchFilter]
    search_fields = ["name", "code"]

    def get_queryset(self):
        return AdminDepartmentService.get_departments_queryset()

    def perform_create(self, serializer):
        department = AdminDepartmentService.create_department(serializer.validated_data)
        serializer.instance = department

    def perform_update(self, serializer):
        department = AdminDepartmentService.update_department(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = department

    def perform_destroy(self, instance):
        AdminDepartmentService.delete_department(instance)


class CourseOfferingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = CourseOfferingSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["course__name", "course__code"]
    filterset_fields = ["semester", "year", "is_active"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseOfferingCreateUpdateSerializer
        return CourseOfferingSerializer

    def get_queryset(self):
        return AdminCourseOfferingService.get_course_offerings_queryset()

    def perform_create(self, serializer):
        offering = AdminCourseOfferingService.create_course_offering(serializer.validated_data)
        serializer.instance = offering

    def perform_update(self, serializer):
        offering = AdminCourseOfferingService.update_course_offering(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = offering

    def perform_destroy(self, instance):
        AdminCourseOfferingService.delete_course_offering(instance)


class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    serializer_class = EnrollmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "course_offering", "student"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EnrollmentCreateUpdateSerializer
        return EnrollmentSerializer

    def get_queryset(self):
        course_offering_id = self.request.query_params.get("course_offering")
        student_id = self.request.query_params.get("student")
        
        if course_offering_id:
            return AdminEnrollmentService.get_enrollments_by_offering(course_offering_id)
        elif student_id:
            return AdminEnrollmentService.get_enrollments_by_student(student_id)
        return AdminEnrollmentService.get_enrollments_queryset()

    def perform_create(self, serializer):
        enrollment = AdminEnrollmentService.create_enrollment(serializer.validated_data)
        serializer.instance = enrollment

    def perform_update(self, serializer):
        enrollment = AdminEnrollmentService.update_enrollment(
            serializer.instance, serializer.validated_data
        )
        serializer.instance = enrollment

    def perform_destroy(self, instance):
        AdminEnrollmentService.delete_enrollment(instance)


class AdminProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AdminProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = AdminProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
