from django.db.models import Count
from main.models import (
    User,
    Course,
    CourseOffering,
    Enrollment,
    Department,
    Announcement,
    TodoItem,
    CourseMaterial,
    ChatConversation,
    ChatMessage,
    Notification,
)
from datetime import datetime


class AdminDashboardService:
    @staticmethod
    def get_summary_stats():
        total_students = User.objects.filter(primary_role=User.Role.STUDENT).count()
        total_courses = Course.objects.count()
        total_doctors = User.objects.filter(primary_role=User.Role.PROFESSOR).count()
        total_tas = User.objects.filter(primary_role=User.Role.TA).count()

        gender_stats = (
            User.objects.filter(primary_role=User.Role.STUDENT)
            .values("gender")
            .annotate(count=Count("gender"))
        )
        total_users = sum(item["count"] for item in gender_stats)
        male_count = next(
            (item["count"] for item in gender_stats if item["gender"] == User.Gender.MALE),
            0,
        )
        female_count = next(
            (item["count"] for item in gender_stats if item["gender"] == User.Gender.FEMALE),
            0,
        )

        male_percentage = (male_count / total_users * 100) if total_users > 0 else 0
        female_percentage = (female_count / total_users * 100) if total_users > 0 else 0

        students_per_department = (
            User.objects.filter(primary_role=User.Role.STUDENT)
            .values("department__name", "department__id")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        students_by_dept = {
            item["department__name"] or "Unassigned": item["count"]
            for item in students_per_department
        }

        return {
            "total_students": total_students,
            "total_courses": total_courses,
            "total_doctors": total_doctors,
            "total_tas": total_tas,
            "gender_distribution": {
                "male_percentage": round(male_percentage, 2),
                "female_percentage": round(female_percentage, 2),
            },
            "students_per_department": students_by_dept,
        }


class AdminCourseService:
    @staticmethod
    def get_courses_queryset():
        return Course.objects.select_related("department").all()

    @staticmethod
    def create_course(data):
        prerequisites_ids = data.pop("prerequisites", [])
        course = Course.objects.create(**data)
        if prerequisites_ids:
            course.prerequisites.set(prerequisites_ids)
        return course

    @staticmethod
    def update_course(course, data):
        prerequisites_ids = data.pop("prerequisites", None)
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
        data["primary_role"] = role
        if "username" not in data:
            data["username"] = data.get(
                "email", data.get("student_id", str(datetime.now().timestamp()))
            )

        user = User.objects.create_user(**data)
        
        if role == User.Role.STUDENT and user.email:
            from django.core.mail import send_mail
            from django.conf import settings
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes
            from django.contrib.auth.tokens import default_token_generator
            
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            frontend_url = "https://eduera.live"
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            
            subject = "Welcome to Eduera - Your Account Details"
            message = f"Hello {user.full_name},\n\nYour account has been successfully created.\nYour student ID / username is: {user.username}\n\nPlease set your password by clicking the link below:\n{reset_link}\n\nWelcome to Eduera!"
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True
            )
            
        return user

    @staticmethod
    def get_users_by_role(role):
        return User.objects.filter(primary_role=role).select_related("department")

    @staticmethod
    def update_user(user, data):
        password = data.pop("password", None)
        for key, value in data.items():
            setattr(user, key, value)
        if password:
            user.set_password(password)
        user.save()
        return user

    @staticmethod
    def delete_user(user):
        user.delete()


class AdminAnnouncementService:
    @staticmethod
    def create_announcement(user, data):
        announcement = Announcement.objects.create(author=user, **data)
        
        if announcement.is_global:
            from django.core.mail import send_mail
            from django.conf import settings
            from main.models import User
            
            student_emails = list(User.objects.filter(primary_role=User.Role.STUDENT, is_active=True).values_list('email', flat=True))
            if student_emails:
                subject = f"New Announcement: {announcement.title}"
                message = f"Hello,\n\nA new announcement has been posted by the administration:\n\n{announcement.title}\n{announcement.content}\n\nThank you,\nEduera Administration"
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=student_emails,
                    fail_silently=True
                )
                
        return announcement

    @staticmethod
    def get_announcements():
        return Announcement.objects.select_related("author", "course_offering").all()

    @staticmethod
    def update_announcement(announcement, data):
        for key, value in data.items():
            setattr(announcement, key, value)
        announcement.save()
        return announcement

    @staticmethod
    def delete_announcement(announcement):
        announcement.delete()


class AdminMaterialService:
    @staticmethod
    def upload_material(user, data, file_obj=None):
        file_obj = data.pop("file", file_obj)

        if file_obj:
            data["file_url"] = f"https://storage.example.com/{file_obj.name}"
            data["file_size"] = file_obj.size
            import os

            _, ext = os.path.splitext(file_obj.name)
            data["file_type"] = ext.replace(".", "").lower() or "unknown"

        return CourseMaterial.objects.create(uploaded_by=user, **data)

    @staticmethod
    def update_material(material, data, file_obj=None):
        file_obj = data.pop("file", file_obj)

        if file_obj:
            data["file_url"] = f"https://storage.example.com/{file_obj.name}"
            data["file_size"] = file_obj.size
            import os

            _, ext = os.path.splitext(file_obj.name)
            data["file_type"] = ext.replace(".", "").lower() or "unknown"

        for key, value in data.items():
            setattr(material, key, value)
        material.save()
        return material

    @staticmethod
    def delete_material(material):
        material.delete()

    @staticmethod
    def get_materials():
        return CourseMaterial.objects.select_related(
            "course_offering", "uploaded_by"
        ).all()


class AdminChatService:
    @staticmethod
    def get_conversations():
        return ChatConversation.objects.select_related("student", "course_offering").all()

    @staticmethod
    def get_messages(conversation_id):
        return ChatMessage.objects.filter(conversation_id=conversation_id).select_related(
            "conversation"
        )


class AdminNotificationService:
    @staticmethod
    def get_notifications(user):
        return Notification.objects.all().select_related("user")


class AdminDepartmentService:
    @staticmethod
    def get_departments_queryset():
        return Department.objects.select_related("head_of_department").all()

    @staticmethod
    def create_department(data):
        return Department.objects.create(**data)

    @staticmethod
    def update_department(department, data):
        for key, value in data.items():
            setattr(department, key, value)
        department.save()
        return department

    @staticmethod
    def delete_department(department):
        department.delete()


class AdminCourseOfferingService:
    @staticmethod
    def get_course_offerings_queryset():
        return CourseOffering.objects.select_related(
            "course", "instructor"
        ).prefetch_related("tas").all()

    @staticmethod
    def get_course_offering_by_id(offering_id):
        return CourseOffering.objects.select_related(
            "course", "instructor"
        ).prefetch_related("tas").get(pk=offering_id)

    @staticmethod
    def create_course_offering(data):
        tas = data.pop("tas", [])
        course_offering = CourseOffering.objects.create(**data)
        if tas:
            course_offering.tas.set(tas)
        return course_offering

    @staticmethod
    def update_course_offering(course_offering, data):
        tas = data.pop("tas", None)
        for key, value in data.items():
            setattr(course_offering, key, value)
        course_offering.save()
        if tas is not None:
            course_offering.tas.set(tas)
        return course_offering

    @staticmethod
    def delete_course_offering(course_offering):
        course_offering.delete()


class AdminEnrollmentService:
    @staticmethod
    def get_enrollments_queryset():
        return Enrollment.objects.select_related(
            "student", "course_offering", "course_offering__course"
        ).all()

    @staticmethod
    def get_enrollments_by_offering(course_offering_id):
        return Enrollment.objects.filter(
            course_offering_id=course_offering_id
        ).select_related("student", "course_offering__course")

    @staticmethod
    def get_enrollments_by_student(student_id):
        return Enrollment.objects.filter(
            student_id=student_id
        ).select_related("course_offering__course")

    @staticmethod
    def create_enrollment(data):
        enrollment = Enrollment.objects.create(**data)
        if enrollment.status == Enrollment.Status.ACTIVE:
            enrollment.course_offering.enrollment_count += 1
            enrollment.course_offering.save()
        return enrollment

    @staticmethod
    def update_enrollment(enrollment, data):
        old_status = enrollment.status
        for key, value in data.items():
            setattr(enrollment, key, value)
        enrollment.save()
        
        new_status = enrollment.status
        offering = enrollment.course_offering
        
        if old_status == Enrollment.Status.ACTIVE and new_status != Enrollment.Status.ACTIVE:
            offering.enrollment_count = max(0, offering.enrollment_count - 1)
            offering.save()
        elif old_status != Enrollment.Status.ACTIVE and new_status == Enrollment.Status.ACTIVE:
            offering.enrollment_count += 1
            offering.save()
        
        return enrollment

    @staticmethod
    def delete_enrollment(enrollment):
        offering = enrollment.course_offering
        if enrollment.status == Enrollment.Status.ACTIVE:
            offering.enrollment_count = max(0, offering.enrollment_count - 1)
            offering.save()
        enrollment.delete()
