from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *

class UserAdmin(BaseUserAdmin):
    # Add custom fields to fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('primary_role', 'department', 'gender', 'profile_picture_url')}),
        ('Student Info', {'fields': ('student_id', 'student_current_level', 'current_gpa', 'current_streak', 'longest_streak')}),
    )
    # Add custom fields to list_display
    list_display = BaseUserAdmin.list_display + ('primary_role', 'department')
    
    # Allow searching by custom fields
    search_fields = BaseUserAdmin.search_fields + ('student_id',)

# Register your models here.
admin.site.register(User, UserAdmin)
admin.site.register(Course)
admin.site.register(CourseMaterial)
