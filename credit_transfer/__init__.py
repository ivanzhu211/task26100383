"""跨校学分认定库。"""
from .models import (
    GRADE_POINTS,
    MIN_ELIGIBLE_POINTS,
    Agreement,
    CourseInfo,
    RecognitionItem,
    RecognitionPlan,
    TranscriptRecord,
)
from .solver import compute_plan

__all__ = [
    "GRADE_POINTS",
    "MIN_ELIGIBLE_POINTS",
    "Agreement",
    "CourseInfo",
    "RecognitionItem",
    "RecognitionPlan",
    "TranscriptRecord",
    "compute_plan",
]
