"""对外入口：为一名学生、一个目标学校计算完整认定方案。"""

from __future__ import annotations

from typing import Sequence

from .core import build_problem
from .models import AgreementRule, CourseInfo, RecognitionPlan, TranscriptRecord
from .models import Assignment
from .solver import solve_optimal_matching


def evaluate(
    transcript: Sequence[TranscriptRecord],
    catalog: Sequence[CourseInfo],
    agreements: Sequence[AgreementRule],
    target_school_id: int,
) -> RecognitionPlan:
    """计算严格最优的学分认定方案。数据仅保存在内存。"""
    sources, targets, edges = build_problem(
        transcript, catalog, agreements, target_school_id
    )
    matches = solve_optimal_matching(sources, targets, edges)

    assignments = [
        Assignment(
            target_school_id=target_school_id,
            target_course_id=t.course_id,
            source_school_id=s.school_id,
            source_course_id=s.course_id,
            attempt=s.attempt,
            grade=s.grade,
            credits_awarded=t.credits,
            quality=t.credits * s.points,
        )
        for s, t in matches
    ]
    assignments.sort(key=lambda a: a.target_course_id)
    return RecognitionPlan(
        target_school_id=target_school_id,
        assignments=assignments,
        total_credits=sum(a.credits_awarded for a in assignments),
        total_quality=sum(a.quality for a in assignments),
    )
