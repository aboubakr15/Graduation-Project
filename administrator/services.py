from django.db.models import Count, Q
from django.db import transaction
from main.models import (
    User, Course, CourseOffering, Enrollment, Department, 
    Announcement, TodoItem, CourseMaterial, ChatConversation, Notification
)
from datetime import datetime

class AdminDashboardService:
    @staticmethod
    def get_summary_stats():
        total_students = User.objects.filter(primary_role=User.Role.STUDENT).count()
        total_courses = Course.objects.count()
        total_doctors = User.objects.filter(primary_role=User.Role.PROFESSOR).count()
        total_tas = User.objects.filter(primary_role=User.Role.TA).count()
        
        # Gender distribution
        gender_stats = User.objects.values('gender').annotate(count=Count('gender'))
        total_users = sum(item['count'] for item in gender_stats)
        male_count = next((item['count'] for item in gender_stats if item['gender'] == User.Gender.MALE), 0)
        female_count = next((item['count'] for item in gender_stats if item['gender'] == User.Gender.FEMALE), 0)
        
        male_percentage = (male_count / total_users * 100) if total_users > 0 else 0
        female_percentage = (female_count / total_users * 100) if total_users > 0 else 0
        
        return {
            "total_students": total_students,
            "total_courses": total_courses,
            "total_doctors": total_doctors,
            "total_tas": total_tas,
            "gender_distribution": {
                "male_percentage": round(male_percentage, 2),
                "female_percentage": round(female_percentage, 2)
            }
        }

class AdminCourseService:
    @staticmethod
    def get_courses_queryset():
        return Course.objects.select_related('department').all()

    @staticmethod
    def create_course(data):
        prerequisites_ids = data.pop('prerequisites', [])
        course = Course.objects.create(**data)
        if prerequisites_ids:
            course.prerequisites.set(prerequisites_ids)
        return course

    @staticmethod
    def update_course(course, data):
        prerequisites_ids = data.pop('prerequisites', None)
        for key, value in data.items():
            setattr(course, key, value)
        course.save()
        if prerequisites_ids is not None:
             course.prerequisites.set(prerequisites_ids)
        return course
    
    @staticmethod
    def delete_course(course):
        course.delete()

class AdminUserService:
    @staticmethod
    def create_user(data, role):
        data['primary_role'] = role
        # Ensure username is set if not provided (using email or generating one)
        # Assuming simplejwt User model or AbstractUser
        if 'username' not in data:
             data['username'] = data.get('email', data.get('student_id', str(datetime.now().timestamp())))
        
        user = User.objects.create_user(**data)
        return user

    @staticmethod
    def get_users_by_role(role):
        return User.objects.filter(primary_role=role).select_related('department')

    @staticmethod
    def update_user(user, data):
        for key, value in data.items():
             setattr(user, key, value)
        user.save()
        return user

class AdminAnnouncementService:
    @staticmethod
    def create_announcement(user, data):
        return Announcement.objects.create(author=user, **data)

    @staticmethod
    def get_announcements():
        return Announcement.objects.select_related('author', 'course_offering').all()

class AdminMaterialService:
    @staticmethod
    def upload_material(user, data):
        # Admin uploads are typically global or for chatbot RAG
        # The Current Model CourseMaterial is tied to CourseOffering.
        # However, the requirement says "Admin uploads materials that feed chatbot RAG".
        # We might need to handle this. For now, assuming standard creation or we need to relax constraints.
        # But the Requirement says "Create endpoint... POST /admin/materials/upload/"
        return CourseMaterial.objects.create(uploaded_by=user, **data)

    @staticmethod
    def get_materials():
         return CourseMaterial.objects.select_related('course_offering', 'uploaded_by').all()

class AdminChatService:
    @staticmethod
    def get_conversations():
        return ChatConversation.objects.select_related('student', 'course_offering').all()
    
    @staticmethod
    def get_messages(conversation_id):
        return ChatMessage.objects.filter(conversation_id=conversation_id).select_related('conversation')

class AdminNotificationService:
    @staticmethod
    def get_notifications(user):
        # Admin might want to see all system notifications or their own? 
        # Requirement: GET /admin/notifications/ created automatically via signals.
        # Assuming admin can view global notifications or notifications sent to them.
        return Notification.objects.all().select_related('user')
