from django.db.models.signals import post_save
from django.dispatch import receiver
from main.models import Announcement, TodoItem, Enrollment, User

@receiver(post_save, sender=Announcement)
def create_todo_from_announcement(sender, instance, created, **kwargs):
    if created and instance.is_TODO:
        # Create TodoItem for enrolled students
        # Strategy:
        # 1. If global, for ALL students? Or just active ones?
        # 2. If course specific, only for enrolled students.
        
        target_students = User.objects.none()
        
        if instance.is_global:
            target_students = User.objects.filter(primary_role=User.Role.STUDENT, is_active=True)
        elif instance.course_offering:
             # Get students enrolled in this course offering
             target_students = User.objects.filter(
                 enrollments__course_offering=instance.course_offering,
                 enrollments__status=Enrollment.Status.ACTIVE
             )
        
        todo_items = [
            TodoItem(
                announcement=instance,
                student=student,
                title=instance.title,
                description=instance.content,
                due_date=instance.expires_at,
                priority=TodoItem.Priority.MEDIUM # Default priority
            )
            for student in target_students
        ]
        
        if todo_items:
            TodoItem.objects.bulk_create(todo_items)
