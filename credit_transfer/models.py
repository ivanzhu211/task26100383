"""数据模型：成绩单记录、课程目录、转学协议与认定结果。"""
from __future__ import annotations

from dataclasses import dataclass

GRADE_POINTS: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
MIN_ELIGIBLE_POINTS = 2  # C 及以上才具有转入资格


@dataclass(frozen=True)
class TranscriptRecord:
    """一条修读记录；attempt 为该课程内唯一的修读序号。"""

    school_id: int
    course_id: int
    attempt: int
    grade: str


@dataclass(frozen=True)
class CourseInfo:
    """课程目录条目：某学校某门课程的学分（1 至 4）。"""

    school_id: int
    course_id: int
    credits: int


@dataclass(frozen=True)
class Agreement:
    """一条直接抵扣关系：来源课程可抵扣目标课程。"""

    source_school_id: int
    source_course_id: int
    target_school_id: int
    target_course_id: int


@dataclass(frozen=True)
class RecognitionItem:
    """一项认定结果，可追溯到被采用的修读记录。"""

    target_school_id: int
    target_course_id: int
    target_credits: int
    source_school_id: int
    source_course_id: int
    source_credits: int
    attempt: int
    grade: str
    grade_points: int


@dataclass(frozen=True)
class RecognitionPlan:
    """完整认定方案：认定项按目标课程编号升序排列。"""

    target_school_id: int
    items: tuple[RecognitionItem, ...]
    total_credits: int
    quality_points: int
