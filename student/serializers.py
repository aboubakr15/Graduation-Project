from rest_framework import serializers
from main.models import (
    User, Announcement, CourseOffering, Enrollment, 
    Assignment, TodoItem, ChatConversation, ChatMessage, CourseMaterial, StudentSubmission, Notification
)
from django.db.models import Sum

def percentage_to_grade_point(pct):
    if pct is None:
        return 0.0
    if pct >= 90:
        return 4.0
    elif pct >= 85:
        return 3.7
    elif pct >= 80:
        return 3.3
    elif pct >= 77:
        return 2.7
    elif pct >= 73:
        return 2.3
    elif pct >= 70:
        return 2.0
    elif pct >= 67:
        return 1.7
    elif pct >= 63:
        return 1.3
    elif pct >= 60:
        return 1.0
    else:
        return 0.0

def compute_cumulative_gpa(student):
    enrollments = Enrollment.objects.filter(
        student=student,
        status=Enrollment.Status.COMPLETED,
        grade__isnull=False
    ).select_related('course_offering__course')
    total_quality_points = 0.0
    total_credits = 0
    for enrollment in enrollments:
        pct = float(enrollment.grade)
        grade_point = percentage_to_grade_point(pct)
        credits = enrollment.course_offering.course.credit_hours
        total_quality_points += grade_point * credits
        total_credits += credits
    if total_credits == 0:
        return 0.0
    gpa = round(total_quality_points / total_credits, 2)
    return min(gpa, 4.0)

class StudentProfileSerializer(serializers.ModelSerializer):
    enrolled_hours = serializers.SerializerMethodField()
    daily_streak_mock = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    current_gpa = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'full_name', 'student_id', 'department_name', 'current_gpa',
            'student_current_level', 'current_streak', 'profile_picture_url', 'enrolled_hours',
            'daily_streak_mock', 'grades'
        ]

    def get_current_gpa(self, obj):
        return compute_cumulative_gpa(obj)

    def get_enrolled_hours(self, obj):
        # Calculate total credit hours for active enrollments
        active_enrollments = Enrollment.objects.filter(
            student=obj, status=Enrollment.Status.ACTIVE
        )
        total_hours = sum(e.course_offering.course.credit_hours for e in active_enrollments)
        return total_hours

    def get_daily_streak_mock(self, obj):
        from django.utils import timezone
        import datetime
        
        now = timezone.now().date()
        last_login = obj.last_login.date() if obj.last_login else None
        streak = obj.current_streak
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        result = {day: False for day in days}
        
        if not last_login or streak == 0:
            return result
            
        # Determine active days based on last_login and current_streak
        week_start = now - datetime.timedelta(days=now.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        
        for i in range(streak):
            login_date = last_login - datetime.timedelta(days=i)
            if week_start <= login_date <= week_end:
                result[days[login_date.weekday()]] = True
                
        return result

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

    def get_department_name(self, obj):
        return obj.department.name if obj.department else None

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
    is_chat_active = serializers.BooleanField(source='course_offering.is_chat_active', read_only=True)
    semester = serializers.CharField(source='course_offering.semester', read_only=True)
    year = serializers.IntegerField(source='course_offering.year', read_only=True)
    enrolled_count = serializers.IntegerField(source='course_offering.enrollments.count', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course_offering', 'course_name', 'course_code', 'instructor_name', 'schedule', 'is_chat_active', 'semester', 'year', 'enrolled_count']


class MaterialSerializer(serializers.ModelSerializer):
    file_download_url = serializers.SerializerMethodField()

    class Meta:
        model = CourseMaterial
        fields = ['id', 'title', 'description', 'material_type', 'file_download_url', 'file_type', 'is_visible_to_students']

    def get_file_download_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if obj.file:
            return request.build_absolute_uri(f'/api/student/materials/{obj.pk}/download/')
        return None

class AssignmentSerializer(serializers.ModelSerializer):
    submitted = serializers.SerializerMethodField()
    file_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ['id', 'title', 'description', 'due_date', 'total_points', 'submitted', 'file_download_url']

    def get_submitted(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        return StudentSubmission.objects.filter(
            assignment=obj, student=request.user
        ).exists()

    def get_file_download_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if getattr(obj, 'file', None):
            return request.build_absolute_uri(f'/api/student/assignments/{obj.pk}/download/')
        return None

class CourseDetailSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name')
    course_code = serializers.CharField(source='course.code')
    instructor_name = serializers.CharField(source='instructor.full_name')
    tas_names = serializers.SerializerMethodField()
    enrollment_status = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()
    assignments = AssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = CourseOffering
        fields = ['id', 'course_name', 'course_code', 'semester', 'year', 'instructor_name', 'tas_names', 'enrollment_status', 'materials', 'assignments']

    def get_materials(self, obj):
        mats = CourseMaterial.objects.filter(course_offering=obj, is_visible_to_students=True)
        return MaterialSerializer(mats, many=True, context=self.context).data

    def get_tas_names(self, obj):
        return list(obj.tas.values_list('full_name', flat=True))

    def get_enrollment_status(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        enrollment = Enrollment.objects.filter(student=request.user, course_offering=obj).first()
        return enrollment.status if enrollment else None

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
        fields = ['id', 'role', 'content', 'timestamp', 'sources_used', 'was_from_rag']

class ChatConversationSerializer(serializers.ModelSerializer):
    course_name = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    # Keep backward-compat alias
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatConversation
        fields = ['id', 'course_offering', 'course_name', 'title', 'created_at', 'updated_at',
                  'last_message_preview', 'last_message']

    def get_course_name(self, obj):
        if obj.course_offering and obj.course_offering.course:
            return obj.course_offering.course.name
        return None

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.all().order_by('-timestamp').first()
        if last_msg:
            return last_msg.content[:100]
        return ""

    def get_last_message(self, obj):
        """Backward-compat alias for last_message_preview."""
        return self.get_last_message_preview(obj)

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
    file_download_url = serializers.SerializerMethodField()
    assignment_file_download_url = serializers.SerializerMethodField()

    class Meta:
        model = StudentSubmission
        fields = ['id', 'assignment', 'assignment_title', 'course_name', 'submission_date', 'file_url', 'file_download_url', 'status', 'notes', 'assignment_file_download_url']

    def get_file_download_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if getattr(obj, 'file', None):
            return request.build_absolute_uri(f'/api/student/submissions/{obj.pk}/download/')
        if obj.file_url and obj.file_url.startswith('/media/'):
            return request.build_absolute_uri(f'/api/student/submissions/{obj.pk}/download/')
        return obj.file_url or None

    def get_assignment_file_download_url(self, obj):
        request = self.context.get('request')
        if not request or not getattr(obj, 'assignment', None):
            return None
        if getattr(obj.assignment, 'file', None):
            return request.build_absolute_uri(f'/api/student/assignments/{obj.assignment.pk}/download/')
        return None

class GradeSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course_name', 'course_code', 'grade', 'status']

class StudentAssignmentListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    file_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ['id', 'title', 'course_offering', 'course_name', 'due_date', 'total_points', 'file_download_url']

    def get_file_download_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        if getattr(obj, 'file', None):
            return request.build_absolute_uri(f'/api/student/assignments/{obj.pk}/download/')
        return None

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'related_object_type', 'related_object_id', 'is_read', 'created_at']
