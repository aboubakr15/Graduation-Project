from rest_framework import serializers
from main.models import (
    User,
    Course,
    CourseOffering,
    Enrollment,
    Announcement,
    CourseMaterial,
    ChatConversation,
    ChatMessage,
    Notification,
    Department,
)


class AdminDashboardSummarySerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_doctors = serializers.IntegerField()
    total_tas = serializers.IntegerField()
    gender_distribution = serializers.DictField()


class DepartmentSerializer(serializers.ModelSerializer):
    head_of_department_name = serializers.CharField(
        source="head_of_department.full_name", read_only=True, allow_null=True
    )
    head_of_department = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(primary_role=User.Role.PROFESSOR),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Department
        fields = ["id", "name", "name_ar", "code", "head_of_department", "head_of_department_name"]


class CourseSerializer(serializers.ModelSerializer):
    department_details = DepartmentSerializer(source="department", read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all()
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "code",
            "name",
            "credit_hours",
            "department",
            "department_details",
            "description",
            "prerequisites",
        ]


class UserSerializer(serializers.ModelSerializer):
    department_details = DepartmentSerializer(source="department", read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "primary_role",
            "is_active",
            "department",
            "department_details",
            "profile_picture_url",
            "password",
        ]
        extra_kwargs = {"password": {"write_only": True, "required": False}}


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "is_global",
            "is_TODO",
            "expires_at",
            "created_at",
            "author_name",
            "course_offering",
        ]
        read_only_fields = ["author", "created_at"]


class CourseMaterialSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.full_name", read_only=True
    )

    class Meta:
        model = CourseMaterial
        fields = [
            "id",
            "title",
            "description",
            "material_type",
            "file_url",
            "file",
            "file_type",
            "file_size",
            "is_visible_to_students",
            "course_offering",
            "uploaded_by_name",
            "upload_date",
        ]
        read_only_fields = ["uploaded_by", "upload_date", "file_type", "file_size", "file_url"]

    def validate_file(self, value):
        if not value:
            return value

        limit_mb = 50
        if value.size > limit_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size too large. Size should not exceed {limit_mb} MB."
            )

        import os

        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = [
            ".pdf",
            ".pptx",
            ".doc",
            ".docx",
            ".mp4",
            ".txt",
            ".md",
        ]
        if ext not in valid_extensions:
            raise serializers.ValidationError(
                f"Unsupported file extension. Allowed: {valid_extensions}"
            )

        valid_mime_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "video/mp4",
            "text/plain",
            "text/markdown",
        ]
        content_type = getattr(value, "content_type", None)
        if content_type and content_type not in valid_mime_types and "text/" not in content_type:
            raise serializers.ValidationError(
                f"Unsupported file type: {content_type}"
            )

        return value


class ChatConversationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    course_code = serializers.CharField(
        source="course_offering.course.code", read_only=True
    )

    class Meta:
        model = ChatConversation
        fields = [
            "id",
            "title",
            "student_name",
            "course_code",
            "created_at",
            "updated_at",
            "is_archived",
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "timestamp", "was_from_rag"]


class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "created_at",
            "user_name",
        ]


class CourseOfferingSerializer(serializers.ModelSerializer):
    course_details = serializers.SerializerMethodField()
    instructor_name = serializers.CharField(source="instructor.full_name", read_only=True, allow_null=True)
    tas_names = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "course",
            "course_details",
            "semester",
            "year",
            "instructor",
            "instructor_name",
            "tas",
            "tas_names",
            "capacity",
            "enrollment_count",
            "course_schedule",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["enrollment_count", "created_at"]

    def get_course_details(self, obj):
        return {
            "code": obj.course.code,
            "name": obj.course.name,
            "department": obj.course.department_id
        }

    def get_tas_names(self, obj):
        return list(obj.tas.values_list('full_name', flat=True))


class CourseOfferingCreateUpdateSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    instructor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(primary_role=User.Role.PROFESSOR),
        allow_null=True,
        required=False
    )
    tas = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(primary_role=User.Role.TA),
        many=True,
        required=False
    )

    class Meta:
        model = CourseOffering
        fields = [
            "course",
            "semester",
            "year",
            "instructor",
            "tas",
            "capacity",
            "course_schedule",
            "is_active",
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_id = serializers.CharField(source="student.student_id", read_only=True)
    course_offering_details = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "student_name",
            "student_id",
            "course_offering",
            "course_offering_details",
            "enrollment_date",
            "status",
            "grade",
        ]
        read_only_fields = ["enrollment_date"]

    def get_course_offering_details(self, obj):
        return {
            "course_code": obj.course_offering.course.code,
            "course_name": obj.course_offering.course.name,
            "semester": obj.course_offering.semester,
            "year": obj.course_offering.year,
        }


class EnrollmentCreateUpdateSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(primary_role=User.Role.STUDENT)
    )
    course_offering = serializers.PrimaryKeyRelatedField(
        queryset=CourseOffering.objects.all()
    )

    class Meta:
        model = Enrollment
        fields = [
            "student",
            "course_offering",
            "status",
            "grade",
        ]
