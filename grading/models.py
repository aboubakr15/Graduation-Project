from django.db import models
from main.models import StudentSubmission

# ══════════════════════════════════════════════════════════════════════════════
# Rubric-Driven Auto Revision Engine — GradingResult
# ══════════════════════════════════════════════════════════════════════════════

class GradingResult(models.Model):
    """
    Stores the AI-generated grading output for a student submission.
    Created automatically when a student submits to an assignment
    that has a rubric (grading_type is set).
    """
    submission = models.OneToOneField(
        StudentSubmission,
        on_delete=models.CASCADE,
        related_name='grading_result'
    )
    total_score = models.FloatField(
        help_text='Total points awarded by the AI grader.'
    )
    max_score = models.FloatField(
        help_text='Maximum possible points from the rubric.'
    )
    # Detailed per-criteria breakdown:
    # [{"criteria_name": str, "points_awarded": float, "max_points": float, "justification": str}, ...]
    criteria_breakdown = models.JSONField(
        default=list,
        help_text='Per-criteria scoring and justification from the AI.'
    )
    feedback_summary = models.TextField(
        blank=True,
        help_text='Overall feedback / summary from the AI grader.'
    )
    # Raw LLM response stored for debugging and audit purposes.
    raw_llm_response = models.JSONField(
        default=dict,
        blank=True,
        help_text='Raw structured response from the LLM for debugging.'
    )
    graded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'grading_results'
        indexes = [
            models.Index(fields=['submission']),
        ]

    def __str__(self):
        return f"GradingResult for {self.submission} — {self.total_score}/{self.max_score}"

    @property
    def percentage(self):
        if self.max_score > 0:
            return (self.total_score / self.max_score) * 100
        return 0
