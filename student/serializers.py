from rest_framework import serializers
from main.models import (
    User, Announcement, CourseOffering, Enrollment, 
    Assignment, TodoItem, ChatMessage, CourseMaterial, StudentSubmission, Notification
)
from django.db.models import Sum

class StudentProfileSerializer(serializers.ModelSerializer):
    enrolled_hours = serializers.SerializerMethodField()
    daily_streak_mock = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'full_name', 'student_id', 'department', 'current_gpa',
            'student_current_level', 'current_streak', 'profile_picture_url', 'enrolled_hours',
            'daily_streak_mock', 'grades'
        ]

    def get_enrolled_hours(self, obj):
        active_enrollments = Enrollment.objects.filter(
            student=obj, status=Enrollment.Status.ACTIVE
        )
        total_hours = sum(e.course_offering.course.credit_hours for e in active_enrollments)
        return total_hours

    def get_daily_streak_mock(self, obj):
        return {
            "Mon": True, "Tue": True, "Wed": False, 
            "Thu": True, "Fri": False, "Sat": False, "Sun": False
        }

    def get_grades(self, obj):
        enrollments = Enrollment.objects.filter(
            student=obj,
            grade__isnull=False
        ).select_related('course_offering__course').order_by('-enrollment_date')
        return [
            {
                'course_name': e.course_offering.course.name,
                'course_code': e.course_offering.course.code,
                'grade': str(e.grade),
                'status': e.status,
                'semester': e.course_offering.semester,
                'year': e.course_offering.year,
            }
            for e in enrollments
        ]

class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    time_since = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'author_name', 'created_at', 'is_TODO', 'time_since']

    def get_time_since(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at)

class CourseProgressSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = ['id', 'course_name', 'course_code', 'progress']

    def get_progress(self, obj):
        # Mock progress calculation. 
        # Ideally, calculate based on completed assignments/materials vs total.
        return 65  # Returning a dummy percentage for UI demo

class DashboardSerializer(serializers.Serializer):
    profile = StudentProfileSerializer(source='*') # Pass the user instance
    portal_announcements = serializers.SerializerMethodField()
    course_announcements = serializers.SerializerMethodField()
    courses_progress = serializers.SerializerMethodField()
    completed_courses_count = serializers.SerializerMethodField()
    in_progress_courses_count = serializers.SerializerMethodField()

    def get_portal_announcements(self, obj):
        # Global announcements
        anns = Announcement.objects.filter(is_global=True).order_by('-created_at')[:3]
        return AnnouncementSerializer(anns, many=True).data

    def get_course_announcements(self, obj):
        # Announcements from enrolled courses
        enrolled_course_ids = Enrollment.objects.filter(
            student=obj, status=Enrollment.Status.ACTIVE
        ).values_list('course_offering_id', flat=True)
        
        anns = Announcement.objects.filter(
            course_offering_id__in=enrolled_course_ids
        ).order_by('-created_at')[:3]
        return AnnouncementSerializer(anns, many=True).data

    def get_courses_progress(self, obj):
        # Active enrollments
        enrollments = Enrollment.objects.filter(student=obj, status=Enrollment.Status.ACTIVE)
        course_offerings = [e.course_offering for e in enrollments]
        return CourseProgressSerializer(course_offerings, many=True).data

    def get_completed_courses_count(self, obj):
        return Enrollment.objects.filter(student=obj, status=Enrollment.Status.COMPLETED).count()

    def get_in_progress_courses_count(self, obj):
        return Enrollment.objects.filter(student=obj, status=Enrollment.Status.ACTIVE).count()

class CourseListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name')
    course_code = serializers.CharField(source='course_offering.course.code')
    instructor_name = serializers.CharField(source='course_offering.instructor.full_name')
    schedule = serializers.JSONField(source='course_offering.course_schedule')
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ['id', 'course_name', 'course_code', 'instructor_name', 'schedule', 'progress']

    def get_progress(self, obj):
        return 45 # Mock value

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseMaterial
        fields = ['id', 'title', 'description', 'material_type', 'file_url', 'is_visible_to_students']

class AssignmentSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ['id', 'title', 'description', 'due_date', 'total_points', 'status']

    def get_status(self, obj):
        # Check if student submitted
        user = self.context.get('request').user
        # This requires the view to pass context={'request': request}
        # For now, return a placeholder if context is missing
        return "Pending"

class CourseDetailSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name')
    course_code = serializers.CharField(source='course.code')
    instructor_name = serializers.CharField(source='instructor.full_name')
    materials = serializers.SerializerMethodField()
    assignments = AssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = CourseOffering
        fields = ['id', 'course_name', 'course_code', 'instructor_name', 'materials', 'assignments']

    def get_materials(self, obj):
        mats = CourseMaterial.objects.filter(course_offering=obj, is_visible_to_students=True)
        return MaterialSerializer(mats, many=True).data

class ToDoItemSerializer(serializers.ModelSerializer):
    course_name = serializers.SerializerMethodField()

    class Meta:
        model = TodoItem
        fields = ['id', 'title', 'description', 'due_date', 'is_completed', 'priority', 'course_name']

    def get_course_name(self, obj):
        if obj.related_assignment:
            return obj.related_assignment.course_offering.course.name
        if obj.announcement and obj.announcement.course_offering:
            return obj.announcement.course_offering.course.name
        return "General"

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp']

class EnrollmentSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    semester = serializers.CharField(source='course_offering.semester', read_only=True)
    year = serializers.IntegerField(source='course_offering.year', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course_offering', 'course_name', 'course_code', 'semester', 'year', 'status', 'grade', 'enrollment_date']

class StudentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    course_name = serializers.CharField(source='assignment.course_offering.course.name', read_only=True)

    class Meta:
        model = StudentSubmission
        fields = ['id', 'assignment', 'assignment_title', 'course_name', 'submission_date', 'file_url', 'status', 'notes']

class GradeSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course_name', 'course_code', 'grade', 'status']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'related_object_type', 'related_object_id', 'is_read', 'created_at']
