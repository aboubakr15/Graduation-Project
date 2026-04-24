from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from datetime import datetime


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        TA = 'TA', 'Teaching Assistant'
        PROFESSOR = 'PROFESSOR', 'Professor'
        ADMIN = 'ADMIN', 'Admin'
    
    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'

    class Current_Level(models.TextChoices):
        ONE = '1', 'Level 1'
        TWO = '2', 'Level 2'
        THREE = '3', 'Level 3'
        FOUR = '4', 'Level 4'
        FIVE = '5', 'Level 5'
    
    # Remove default first_name and last_name
    first_name = None
    last_name = None
    
    guid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True, null=True)
    primary_role = models.CharField(max_length=20, choices=Role.choices)
    profile_picture_url = models.URLField(blank=True, null=True)
    
    # Student-specific fields
    student_id = models.CharField(max_length=20, null=True, blank=True, unique=True, db_index=True)
    student_current_level = models.IntegerField(choices=Current_Level.choices,null=True, blank=True)
    current_gpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(4.0)]
    )
        
    groups = models.ManyToManyField(
        Group,
        related_name='main_users',
        blank=True,
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name='main_user_permissions',
        blank=True,
    )

    # Streak tracking
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    # already exists in django / last_login = models.DateTimeField(null=True, blank=True)  # To track daily logins for streaks
    
    # Timestamps
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.full_name} ({self.get_primary_role_display()})"
    
    def save(self, *args, **kwargs):
        if self.primary_role == self.Role.STUDENT and not self.student_id:
            self.student_id = self.generate_student_id()
        super().save(*args, **kwargs)
    
    def generate_student_id(self):
        current_year = datetime.now().year
        last_student = User.objects.filter(
            student_id__startswith=str(current_year)).order_by('-student_id').first()
        
        if last_student and last_student.student_id:
            last_sequence = int(last_student.student_id[4:])
            new_sequence = last_sequence + 1
        else:
            new_sequence = 1
        
        return f"{current_year}{new_sequence:04d}"


class Department (models.Model):
    name = models.CharField(max_length=100, unique=True)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    code = models.CharField(max_length=10, unique=True)
    head_of_department = models.ForeignKey('User', on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='headed_departments',
        limit_choices_to={'primary_role': 'PROFESSOR'})
    
    class Meta:
        db_table = 'departments'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='courses')
    credit_hours = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(6)])
    created_at = models.DateTimeField(auto_now_add=True)
    prerequisites = models.ManyToManyField('self', symmetrical=False, related_name='prerequisite_for',blank=True)
    class Meta:
        db_table = 'courses'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class CourseOffering(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offerings')
    semester = models.CharField(max_length=20)  # e.g., "Fall", "Spring"
    year = models.IntegerField()
    instructor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='taught_courses', limit_choices_to={'primary_role': User.Role.PROFESSOR})
    tas = models.ManyToManyField(User, related_name='assisted_courses', limit_choices_to={'primary_role': User.Role.TA}, blank=True)
    capacity = models.IntegerField(default=30)
    enrollment_count = models.IntegerField(default=0)
    course_schedule = models.JSONField(default=list, blank=True)  # [{"day": "Monday", "time": "10:00-11:30"}, ...]
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'course_offerings'
        unique_together = ['course', 'semester', 'year', 'instructor']
        ordering = ['-year', '-semester']
    
    def __str__(self):
        return f"{self.course.code} - {self.semester} {self.year}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DROPPED = 'DROPPED', 'Dropped'
        COMPLETED = 'COMPLETED', 'Completed'
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', limit_choices_to={'primary_role': User.Role.STUDENT})
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    class Meta:
        db_table = 'enrollments'
        unique_together = ['student', 'course_offering']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course_offering', 'status']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.course_offering}"


class CourseMaterial(models.Model):
    class MaterialType(models.TextChoices):
        LECTURE = 'LECTURE', 'Lecture'
        SECTION = 'SECTION', 'Section Material'
        ASSIGNMENT_DESC = 'ASSIGNMENT_DESC', 'Assignment Description'
        OTHER = 'OTHER', 'Other'
    
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MaterialType.choices)
    file_url = models.URLField(blank=True)          # kept for backward-compat / external URLs
    file = models.FileField(                        # actual uploaded file (new)
        upload_to='course_materials/%Y/%m/',
        null=True,
        blank=True,
    )
    file_type = models.CharField(max_length=20)  # pdf, pptx, docx, mp4, etc.
    file_size = models.BigIntegerField(null=True, blank=True)  # in bytes
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_materials')
    upload_date = models.DateTimeField(auto_now_add=True)
    is_visible_to_students = models.BooleanField(default=True)
    order_index = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'course_materials'
        ordering = ['order_index', '-upload_date']
        indexes = [
            models.Index(fields=['course_offering', 'material_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.course_offering})"


class Assignment(models.Model):
    class AssignmentType(models.TextChoices):
        QUIZ = 'QUIZ', 'Quiz'
        EXAM = 'EXAM', 'Exam'
        PROJECT = 'PROJECT', 'Project'
        REPORT = 'REPORT', 'Report'
    
    class SubmissionLocation(models.TextChoices):
        ONLINE = 'ONLINE', 'Online'
        IN_UNIVERSITY = 'IN_UNIVERSITY', 'In University'
    
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    description_material = models.ForeignKey(CourseMaterial, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_assignments')

    # if auto correctable, store questions and model answers as JSON
    is_auto_correctable = models.BooleanField(default=False)
    questions = models.JSONField(default=list, blank=True)  # Structured representation of questions if assignment type is QUIZ/EXAM
    model_answers = models.JSONField(default=dict, blank=True)  # Structured data for auto-grading
    
    due_date = models.DateTimeField()
    total_points = models.DecimalField(max_digits=6, decimal_places=2,validators=[MinValueValidator(0)])
    assignment_type = models.CharField(max_length=20, choices=AssignmentType.choices)
    submission_location = models.CharField(max_length=20, choices=SubmissionLocation.choices, default=SubmissionLocation.ONLINE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'assignments'
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['course_offering', 'due_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.course_offering}"


class StudentSubmission(models.Model):
    class Status(models.TextChoices):
        NOT_SUBMITTED = 'PENDING', 'Pending'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        GRADED = 'GRADED', 'Graded'
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE,related_name='submissions', limit_choices_to={'primary_role': User.Role.STUDENT})
    submission_date = models.DateTimeField(auto_now_add=True)
    file_url = models.URLField(null=True, blank=True)
    student_answers = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'student_submissions'
        unique_together = ['assignment', 'student']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['assignment', 'status']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.assignment.title}"


class AutoCorrectionResult(models.Model):
    submission = models.OneToOneField(StudentSubmission, on_delete=models.CASCADE, related_name='correction_result')
    score = models.DecimalField(max_digits=6, decimal_places=2)
    max_score = models.DecimalField(max_digits=6, decimal_places=2)
    corrected_at = models.DateTimeField(auto_now_add=True)
    corrected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name='corrections')  # Null if AI-corrected
    
    class Meta:
        db_table = 'auto_correction_results'
    
    def __str__(self):
        return f"Result for {self.submission}"
    
    @property
    def percentage(self):
        if self.max_score > 0:
            return (self.score / self.max_score) * 100
        return 0


class ChatConversation(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_conversations', limit_choices_to={'primary_role': User.Role.STUDENT})
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='chat_conversations')
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'chat_conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['student', 'course_offering']),
        ]
    
    def __str__(self):
        return f"Chat: {self.title or f'Conversation {self.id}'}"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'USER', 'User'
        ASSISTANT = 'ASSISTANT', 'Assistant'
    
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    sources_used = models.JSONField(default=list, blank=True)  # Array of material IDs
    was_from_rag = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class FrequentQuestion(models.Model):
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='frequent_questions')
    question_text = models.TextField()
    question_embedding = models.BinaryField(null=True, blank=True)
    frequency_count = models.IntegerField(default=1)
    related_materials = models.JSONField(default=list, blank=True)  # Material IDs
    first_asked_at = models.DateTimeField(auto_now_add=True)
    last_asked_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'frequent_questions'
        ordering = ['-frequency_count', '-last_asked_at']
        indexes = [
            models.Index(fields=['course_offering', '-frequency_count']),
        ]
    
    def __str__(self):
        return f"{self.question_text[:100]} (x{self.frequency_count})"


class Announcement(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    course_offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name='announcements', null=True, blank=True)
    is_global = models.BooleanField(default=False)  # True if it is a general announcement
    is_TODO = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['course_offering', '-created_at']),
        ]
    
    def __str__(self):
        scope = "Global" if self.is_global else str(self.course_offering)
        return f"{self.title} ({scope})"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        MATERIAL_UPLOAD = 'MATERIAL_UPLOAD', 'Material Upload'
        ASSIGNMENT_DUE = 'ASSIGNMENT_DUE', 'Assignment Due'
        GRADE_POSTED = 'GRADE_POSTED', 'Grade Posted'
        GENERAL = 'GENERAL', 'General'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    related_object_type = models.CharField(max_length=50, blank=True)  # "Assignment", "Announcement"
    related_object_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.full_name}"


class TodoItem(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='todo_items', null=True, blank=True)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_items', limit_choices_to={'primary_role': User.Role.STUDENT})
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    related_assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name='todo_items')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.LOW)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'todo_items'
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['student', 'is_completed']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.student.full_name}"


class SemesterGPA(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='semester_gpas', limit_choices_to={'primary_role': User.Role.STUDENT})
    semester = models.CharField(max_length=20)
    year = models.IntegerField()
    gpa = models.DecimalField(max_digits=4, decimal_places=2, validators=[MinValueValidator(0.0), MaxValueValidator(4.0)])
    total_credit_hours = models.IntegerField()
    
    class Meta:
        db_table = 'semester_gpas'
        unique_together = ['student', 'semester', 'year']
        ordering = ['-year', '-semester']
    
    def __str__(self):
        return f"{self.student.full_name} - {self.semester} {self.year}: {self.gpa}"

