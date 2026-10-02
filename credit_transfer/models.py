"""跨校学分认定库的数据类型定义。

所有编号均为正整数；课程由 (学校编号, 课程编号) 共同标识。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# 成绩字母到绩点的映射；只有 C 及以上（绩点 >= 2）具有转入资格。
GRADE_POINTS: Dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
ELIGIBLE_MIN_POINTS = 2  # C 及以上


@dataclass(frozen=True)
class TranscriptRecord:
    """一条修读记录。attempt 为该课程内唯一的修读序号。"""

    school_id: int
    course_id: int
    attempt: int
    grade: str


@dataclass(frozen=True)
class CourseInfo:
    """课程目录条目：某学校某门课程的学分（1 至 4 的整数）。"""

    school_id: int
    course_id: int
    credits: int


@dataclass(frozen=True)
class AgreementRule:
    """直接抵扣关系：来源学校的一门课程可抵扣目标学校的一门课程。"""

    from_school_id: int
    from_course_id: int
    to_course_id: int


@dataclass(frozen=True)
class Assignment:
    """一项已认定的抵扣，可追溯到被采用的修读记录。"""

    target_school_id: int
    target_course_id: int
    source_school_id: int
    source_course_id: int
    attempt: int
    grade: str
    credits_awarded: int  # 等于目标课程学分
    quality: int  # 目标课程学分 * 来源成绩绩点


@dataclass
class RecognitionPlan:
    """一名学生在一个目标学校的完整认定方案。"""

    target_school_id: int
    assignments: List[Assignment] = field(default_factory=list)
    total_credits: int = 0
    total_quality: int = 0
