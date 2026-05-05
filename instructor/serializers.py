from rest_framework import serializers
from main.models import (
    User, CourseOffering, Course, Enrollment, 
    Assignment, CourseMaterial, Announcement, 
    ChatConversation, ChatMessage, Notification,
    StudentSubmission, Department
)
from django.db.models import Sum, Count, Q


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'name_ar', 'code']


class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'code', 'name', 'name_ar', 'description', 'credit_hours', 'department', 'department_name']


class CourseOfferingListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name')
    course_code = serializers.CharField(source='course.code')
    instructor_name = serializers.CharField(source='instructor.full_name')
    enrolled_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseOffering
        fields = ['id', 'course', 'course_name', 'course_code', 'semester', 'year', 'instructor', 'instructor_name', 'capacity', 'enrolled_count', 'course_schedule', 'is_active']
    
    def get_enrolled_count(self, obj):
        return obj.enrollments.filter(status=Enrollment.Status.ACTIVE).count()


class CourseOfferingDetailSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name')
    course_code = serializers.CharField(source='course.code')
    instructor_name = serializers.CharField(source='instructor.full_name')
    tas = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()
    assignments = serializers.SerializerMethodField()
    enrolled_students = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseOffering
        fields = ['id', 'course', 'course_name', 'course_code', 'semester', 'year', 'instructor', 'instructor_name', 'tas', 'capacity', 'enrolled_count', 'course_schedule', 'is_active', 'materials', 'assignments', 'enrolled_students']
    
    def get_tas(self, obj):
        return [{'id': ta.id, 'full_name': ta.full_name} for ta in obj.tas.all()]
    
    def get_enrolled_count(self, obj):
        return obj.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
    
    def get_materials(self, obj):
        mats = obj.materials.all().order_by('-upload_date')
        return MaterialSerializer(mats, many=True).data
    
    def get_assignments(self, obj):
        return AssignmentListSerializer(obj.assignments.all(), many=True).data
    
    def get_enrolled_students(self, obj):
        enrollments = obj.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related('student')
        return [{
            'enrollment_id': e.id,
            'student_id': e.student.id,
            'student_name': e.student.full_name,
            'student_email': e.student.email,
            'status': e.status,
            'grade': e.grade
        } for e in enrollments]


class CourseOfferingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseOffering
        fields = ['course', 'semester', 'year', 'instructor', 'tas', 'capacity', 'course_schedule', 'is_active']


import os

# Per-category file-size limits (bytes)
_MB = 1024 * 1024
_GB = 1024 * _MB

_SIZE_LIMITS = {
    # Office / document types  → 100 MB
    'pdf':  100 * _MB, 'pptx': 100 * _MB, 'ppt':  100 * _MB,
    'docx': 100 * _MB, 'doc':  100 * _MB,
    'xlsx': 100 * _MB, 'xls':  100 * _MB,
    'txt':   10 * _MB,
    # Images → 20 MB
    'png':  20 * _MB, 'jpg':  20 * _MB, 'jpeg': 20 * _MB, 'gif': 20 * _MB,
    # Archives → 500 MB
    'zip': 500 * _MB,
    # Audio → 200 MB
    'mp3': 200 * _MB,
    # Video → 2 GB
    'mp4':   2 * _GB,
}


class MaterialSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    file_download_url = serializers.SerializerMethodField()

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'course_offering', 'course_name', 'title', 'description',
            'material_type', 'file_download_url', 'file_type',
            'file_size', 'uploaded_by', 'uploaded_by_name', 'upload_date',
            'is_visible_to_students', 'order_index',
        ]

    def get_file_download_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if obj.file:
            return request.build_absolute_uri(f'/api/professor/materials/{obj.pk}/download/')
        return None


class MaterialUploadSerializer(serializers.ModelSerializer):
    """
    Accepts multipart/form-data with a real file binary.

    Required  : course_offering, title, material_type, file
    Optional  : description, is_visible_to_students, order_index

    file_type and file_size are derived automatically — do NOT send them.
    """
    file = serializers.FileField(required=True)

    class Meta:
        model = CourseMaterial
        fields = [
            'course_offering', 'title', 'description',
            'material_type', 'file',
            'is_visible_to_students', 'order_index',
        ]

    def validate_file(self, uploaded_file):
        ext = os.path.splitext(uploaded_file.name)[1].lstrip('.').lower()

        if ext not in _SIZE_LIMITS:
            raise serializers.ValidationError(
                f"Unsupported file type '.{ext}'. "
                f"Allowed: {', '.join(sorted(_SIZE_LIMITS.keys()))}"
            )

        limit = _SIZE_LIMITS[ext]
        if uploaded_file.size > limit:
            raise serializers.ValidationError(
                f".{ext} files must be ≤ {limit // _MB} MB "
                f"(uploaded: {uploaded_file.size // _MB} MB)."
            )

        return uploaded_file

    def validate_course_offering(self, course_offering):
        request = self.context.get('request')
        if not request:
            return course_offering
            
        user = request.user
        is_instructor = (course_offering.instructor_id == user.id)
        is_ta = course_offering.tas.filter(id=user.id).exists()
        
        if not (is_instructor or is_ta):
            raise serializers.ValidationError(
                "You must be the instructor or a TA for this course offering to upload materials."
            )
        return course_offering

    def create(self, validated_data):
        uploaded_file = validated_data['file']
        ext = os.path.splitext(uploaded_file.name)[1].lstrip('.').lower()

        return CourseMaterial.objects.create(
            **validated_data,
            file_type=ext,
            file_size=uploaded_file.size,
        )


# Kept for internal / admin use only (URL-based, no file binary).
class MaterialCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseMaterial
        fields = ['course_offering', 'title', 'description', 'material_type', 'file_url', 'file_type', 'file_size', 'is_visible_to_students', 'order_index']


class AssignmentListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    submission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = ['id', 'course_offering', 'course_name', 'title', 'description', 'due_date', 'total_points', 'assignment_type', 'submission_location', 'submission_count', 'created_at']
    
    def get_submission_count(self, obj):
        return obj.submissions.count()


class AssignmentDetailSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    submissions = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = ['id', 'course_offering', 'course_name', 'title', 'description', 'description_material', 'is_auto_correctable', 'questions', 'due_date', 'total_points', 'assignment_type', 'submission_location', 'created_by', 'created_at', 'updated_at', 'submissions']
    
    def get_submissions(self, obj):
        subs = obj.submissions.select_related('student').order_by('-submission_date')
        return SubmissionSerializer(subs, many=True).data


class AssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ['course_offering', 'title', 'description', 'description_material', 'is_auto_correctable', 'questions', 'due_date', 'total_points', 'assignment_type', 'submission_location']


class SubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    course_name = serializers.CharField(source='assignment.course_offering.course.name', read_only=True)
    
    class Meta:
        model = StudentSubmission
        fields = ['id', 'assignment', 'assignment_title', 'course_name', 'student', 'student_name', 'student_email', 'submission_date', 'file_url', 'student_answers', 'status', 'notes']


class GradeSubmissionSerializer(serializers.Serializer):
    grade = serializers.DecimalField(max_digits=5, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)


class StudentSerializer(serializers.ModelSerializer):
    enrolled_courses = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'student_id', 'department', 'current_gpa', 'enrolled_courses']
    
    def get_enrolled_courses(self, obj):
        enrollments = obj.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related('course_offering__course')
        return [{
            'enrollment_id': e.id,
            'course_id': e.course_offering.id,
            'course_name': e.course_offering.course.name,
            'course_code': e.course_offering.course.code,
            'semester': e.course_offering.semester,
            'year': e.course_offering.year
        } for e in enrollments]


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'author', 'author_name', 'course_offering', 'course_name', 'is_global', 'is_TODO', 'created_at', 'expires_at']


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'course_offering', 'is_global', 'is_TODO', 'expires_at']


class ChatConversationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatConversation
        fields = ['id', 'student', 'student_name', 'course_offering', 'course_name', 'title', 'created_at', 'updated_at', 'is_archived', 'last_message', 'unread_count']
    
    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg:
            return {'role': msg.role, 'content': msg.content[:50], 'timestamp': msg.timestamp}
        return None
    
    def get_unread_count(self, obj):
        return 0


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'conversation', 'role', 'content', 'sources_used', 'was_from_rag', 'timestamp', 'tokens_used']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'related_object_type', 'related_object_id', 'is_read', 'created_at']


class InstructorProfileSerializer(serializers.ModelSerializer):
    total_courses = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    upcoming_assignments = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'department', 'profile_picture_url',
            'total_courses', 'total_students', 'upcoming_assignments'
        ]

    def get_total_courses(self, obj):
        return CourseOffering.objects.filter(
            Q(instructor=obj) | Q(tas=obj)
        ).distinct().count()

    def get_total_students(self, obj):
        course_ids = CourseOffering.objects.filter(
            Q(instructor=obj) | Q(tas=obj)
        ).distinct().values_list('id', flat=True)
        return Enrollment.objects.filter(
            course_offering_id__in=course_ids,
            status=Enrollment.Status.ACTIVE
        ).values_list('student_id', flat=True).distinct().count()

    def get_upcoming_assignments(self, obj):
        from django.utils import timezone
        course_ids = CourseOffering.objects.filter(
            Q(instructor=obj) | Q(tas=obj)
        ).distinct().values_list('id', flat=True)
        return Assignment.objects.filter(
            course_offering_id__in=course_ids,
            due_date__gte=timezone.now()
        ).count()


class DashboardSerializer(serializers.Serializer):
    total_courses = serializers.IntegerField()
    total_students = serializers.IntegerField()
    pending_submissions = serializers.IntegerField()
    upcoming_assignments = serializers.IntegerField()
    recent_announcements = AnnouncementSerializer(many=True)
    courses = CourseOfferingListSerializer(many=True)
