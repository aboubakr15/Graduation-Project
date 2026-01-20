from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *

class UserAdmin(BaseUserAdmin):
    # Remove first_name and last_name from fieldsets as they don't exist in our User model
    # base_fieldsets is usually:
    # (
    #   (None, {'fields': ('username', 'password')}), 
    #   ('Personal info', {'fields': ('first_name', 'last_name', 'email')}), 
    #   ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}), 
    #   ('Important dates', {'fields': ('last_login', 'date_joined')})
    # )
    
    # We define our own fieldsets
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('full_name', 'email')}), # Replaced first_name/last_name with full_name
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom Fields', {'fields': ('primary_role', 'department', 'gender', 'profile_picture_url')}),
        ('Student Info', {'fields': ('student_id', 'student_current_level', 'current_gpa', 'current_streak', 'longest_streak')}),
    )
    
    # Also fix list_display to use full_name instead of first_name/last_name
    list_display = ('username', 'email', 'full_name', 'primary_role', 'department', 'is_staff')
    
    # Allow searching by custom fields
    search_fields = ('username', 'full_name', 'email', 'student_id')

# Register your models here.
admin.site.register(User, UserAdmin)
admin.site.register(Course)
admin.site.register(CourseMaterial)
