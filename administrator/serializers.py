from rest_framework import serializers
from main.models import User, Course, Announcement, CourseMaterial, ChatConversation, ChatMessage, Notification, Department

class AdminDashboardSummarySerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    total_doctors = serializers.IntegerField()
    total_tas = serializers.IntegerField()
    gender_distribution = serializers.DictField()

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code']

class CourseSerializer(serializers.ModelSerializer):
    department_details = DepartmentSerializer(source='department', read_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), write_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'code', 'name', 'credit_hours', 'department', 'department_details', 'description', 'prerequisites']

class UserSerializer(serializers.ModelSerializer):
    department_details = DepartmentSerializer(source='department', read_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), allow_null=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'primary_role', 'is_active', 'department', 'department_details', 'profile_picture_url']
        extra_kwargs = {'password': {'write_only': True}}
    
    def create(self, validated_data):
        # This will be handled by service, acting as a validator here mostly
        return validated_data

class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'is_global', 'is_TODO', 'expires_at', 'created_at', 'author_name']
        read_only_fields = ['author', 'created_at']

class CourseMaterialSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    
    class Meta:
        model = CourseMaterial
        fields = ['id', 'title', 'description', 'material_type', 'file_url', 'file_type', 'file_size', 'is_visible_to_students', 'course_offering', 'uploaded_by_name', 'upload_date']
        read_only_fields = ['uploaded_by', 'upload_date']

class ChatConversationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)

    class Meta:
        model = ChatConversation
        fields = ['id', 'title', 'student_name', 'course_code', 'created_at', 'updated_at', 'is_archived']

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp', 'was_from_rag']

class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'is_read', 'created_at', 'user_name']
