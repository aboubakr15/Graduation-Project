"""
DRF Serializers for the Rubric-Driven Auto Revision Engine.

Three main serializer groups:
1. Assignment Serializers — For TAs to create/manage rubric-graded assignments.
2. Submission Serializers — For students to submit text/code (triggers auto-grading).
3. GradingResult Serializers — Read-only views of grading feedback.
"""

from rest_framework import serializers
from .models import GradingResult
from main.models import (
    Assignment, StudentSubmission,
    CourseOffering, Enrollment, User
)


# ══════════════════════════════════════════════════════════════════════════════
# Rubric Validation Helpers
# ══════════════════════════════════════════════════════════════════════════════

def validate_rubric_structure(rubric_data):
    """
    Validate that the rubric JSON matches the expected format:
    [
        {"criteria_name": str, "max_points": number, "description": str},
        ...
    ]
    """
    if not isinstance(rubric_data, list):
        raise serializers.ValidationError("Rubric must be a JSON array.")

    if len(rubric_data) == 0:
        raise serializers.ValidationError("Rubric must have at least one criterion.")

    required_keys = {'criteria_name', 'max_points', 'description'}
    for i, criterion in enumerate(rubric_data):
        if not isinstance(criterion, dict):
            raise serializers.ValidationError(
                f"Rubric item {i} must be a JSON object, got {type(criterion).__name__}."
            )
        missing = required_keys - set(criterion.keys())
        if missing:
            raise serializers.ValidationError(
                f"Rubric item {i} is missing required keys: {missing}"
            )
        if not isinstance(criterion['max_points'], (int, float)) or criterion['max_points'] <= 0:
            raise serializers.ValidationError(
                f"Rubric item {i}: 'max_points' must be a positive number."
            )

    return rubric_data


# ══════════════════════════════════════════════════════════════════════════════
# Assignment Serializers (TA / Professor)
# ══════════════════════════════════════════════════════════════════════════════

class RubricAssignmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for TAs/Professors to create assignments with rubric grading.
    
    Required fields:
        - course_offering, title, due_date, total_points, assignment_type
        - grading_type: 'SUBJECTIVE' or 'OBJECTIVE'
        - rubric: JSON array of criteria
        - model_answer_text: Reference model answer
    
    Optional:
        - test_cases: Required for OBJECTIVE assignments
        - description, description_material
    """

    class Meta:
        model = Assignment
        fields = [
            'course_offering', 'title', 'description', 'description_material',
            'due_date', 'total_points', 'assignment_type', 'submission_location',
            'grading_type', 'rubric', 'model_answer_text', 'test_cases',
            'is_auto_correctable', 'questions',
        ]

    def validate_rubric(self, value):
        """Enforce rubric structure validation."""
        return validate_rubric_structure(value)

    def validate(self, attrs):
        """Cross-field validation for grading configuration."""
        grading_type = attrs.get('grading_type')

        if grading_type and not attrs.get('rubric'):
            raise serializers.ValidationError({
                'rubric': 'Rubric is required when grading_type is set.'
            })

        if grading_type == 'OBJECTIVE' and not attrs.get('test_cases'):
            raise serializers.ValidationError({
                'test_cases': 'Test cases are required for OBJECTIVE grading type.'
            })

        if grading_type and not attrs.get('model_answer_text'):
            raise serializers.ValidationError({
                'model_answer_text': 'Model answer text is required for rubric grading.'
            })

        return attrs


class RubricAssignmentListSerializer(serializers.ModelSerializer):
    """Read serializer for listing rubric-graded assignments."""
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    submission_count = serializers.SerializerMethodField()
    rubric_criteria_count = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'course_offering', 'course_name', 'course_code',
            'title', 'description', 'due_date', 'total_points',
            'assignment_type', 'grading_type', 'submission_count',
            'rubric_criteria_count', 'created_by', 'created_by_name',
            'created_at',
        ]

    def get_submission_count(self, obj):
        return obj.submissions.count()

    def get_rubric_criteria_count(self, obj):
        return len(obj.rubric) if obj.rubric else 0


class RubricAssignmentDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer including rubric, model answer, and submissions."""
    course_name = serializers.CharField(source='course_offering.course.name', read_only=True)
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    submissions = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'course_offering', 'course_name', 'course_code',
            'title', 'description', 'due_date', 'total_points',
            'assignment_type', 'grading_type', 'rubric',
            'model_answer_text', 'test_cases',
            'created_by', 'created_by_name',
            'created_at', 'updated_at', 'submissions',
        ]

    def get_submissions(self, obj):
        subs = obj.submissions.select_related('student').order_by('-submission_date')
        return GradedSubmissionSerializer(subs, many=True).data


# ══════════════════════════════════════════════════════════════════════════════
# Submission Serializers (Students)
# ══════════════════════════════════════════════════════════════════════════════

class SubmissionCreateSerializer(serializers.Serializer):
    """
    Serializer for students to submit their text/code.
    Auto-grading is triggered after successful creation.
    """
    assignment_id = serializers.IntegerField()
    submitted_text = serializers.CharField()

    def validate_assignment_id(self, value):
        try:
            assignment = Assignment.objects.get(pk=value)
        except Assignment.DoesNotExist:
            raise serializers.ValidationError("Assignment not found.")

        if not assignment.grading_type or not assignment.rubric:
            raise serializers.ValidationError(
                "This assignment does not have rubric grading enabled."
            )

        return value


class GradedSubmissionSerializer(serializers.ModelSerializer):
    """Submission with grading result attached."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    grading_result = serializers.SerializerMethodField()

    class Meta:
        model = StudentSubmission
        fields = [
            'id', 'assignment', 'student', 'student_name', 'student_email',
            'submitted_text', 'submission_date', 'status', 'grading_result',
        ]

    def get_grading_result(self, obj):
        try:
            result = obj.grading_result
            return GradingResultSerializer(result).data
        except GradingResult.DoesNotExist:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# Grading Result Serializers (Read-Only)
# ══════════════════════════════════════════════════════════════════════════════

class CriteriaBreakdownSerializer(serializers.Serializer):
    """Individual criterion score — nested inside GradingResultSerializer."""
    criteria_name = serializers.CharField()
    points_awarded = serializers.FloatField()
    max_points = serializers.FloatField()
    justification = serializers.CharField()


class GradingResultSerializer(serializers.ModelSerializer):
    """Full grading result with criteria breakdown."""
    percentage = serializers.FloatField(read_only=True)
    assignment_title = serializers.CharField(
        source='submission.assignment.title', read_only=True
    )
    student_name = serializers.CharField(
        source='submission.student.full_name', read_only=True
    )

    class Meta:
        model = GradingResult
        fields = [
            'id', 'submission', 'assignment_title', 'student_name',
            'total_score', 'max_score', 'percentage',
            'criteria_breakdown', 'feedback_summary',
            'graded_at',
        ]
        # raw_llm_response is excluded — it's for debugging only (admin/internal use).


class GradingResultDebugSerializer(serializers.ModelSerializer):
    """
    Extended serializer that includes raw_llm_response.
    Only accessible to TAs/Professors for debugging.
    """
    percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = GradingResult
        fields = [
            'id', 'submission', 'total_score', 'max_score', 'percentage',
            'criteria_breakdown', 'feedback_summary',
            'raw_llm_response', 'graded_at',
        ]
