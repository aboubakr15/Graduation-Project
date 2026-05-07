from django.contrib import admin
from .models import GradingResult
from main.models import Assignment


class GradingResultAdmin(admin.ModelAdmin):
    list_display = ('submission', 'total_score', 'max_score', 'graded_at')
    list_filter = ('graded_at',)
    search_fields = (
        'submission__student__full_name',
        'submission__assignment__title',
    )
    readonly_fields = ('raw_llm_response', 'criteria_breakdown', 'graded_at')


admin.site.register(GradingResult, GradingResultAdmin)
