"""
Pydantic schemas for the Rubric-Driven Auto Revision Engine.

These schemas are passed to `ChatGroq.with_structured_output()` to enforce
that the LLM returns its grading in a strict, validated JSON format.
No manual text parsing is needed — LangChain handles it via tool-calling
or JSON-mode under the hood.
"""

from pydantic import BaseModel, Field
from typing import List


class CriteriaScore(BaseModel):
    """Score for a single rubric criterion."""
    criteria_name: str = Field(
        ..., description="Name of the rubric criterion being evaluated."
    )
    points_awarded: float = Field(
        ..., description="Points awarded for this criterion."
    )
    max_points: float = Field(
        ..., description="Maximum possible points for this criterion."
    )
    justification: str = Field(
        ..., description="Brief explanation of why this score was given."
    )


class GradingOutput(BaseModel):
    """
    Structured grading output enforced by LangChain's with_structured_output().
    The LLM MUST return data matching this exact schema.
    """
    criteria_breakdown: List[CriteriaScore] = Field(
        ..., description="Per-criterion scores and justifications."
    )
    overall_feedback: str = Field(
        ..., description="Overall feedback summary for the student."
    )
    total_score: float = Field(
        ..., description="Total score across all criteria."
    )
