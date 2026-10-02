"""输入规范化：成绩去重、资格过滤、候选抵扣边构建。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .models import AgreementRule, CourseInfo, TranscriptRecord
from .models import ELIGIBLE_MIN_POINTS, GRADE_POINTS


@dataclass(frozen=True)
class SourceCourse:
    """一门可参与认定的来源课程（已取序号最大的修读记录）。"""

    school_id: int
    course_id: int
    credits: int
    attempt: int
    grade: str
    points: int


@dataclass(frozen=True)
class TargetCourse:
    """目标学校的一门可被抵扣的课程。"""

    course_id: int
    credits: int


@dataclass(frozen=True)
class CandidateEdge:
    """一条合法的候选抵扣：来源课程 -> 目标课程。"""

    source: SourceCourse
    target: TargetCourse


def select_effective_records(
    transcript: Sequence[TranscriptRecord],
) -> Dict[Tuple[int, int], TranscriptRecord]:
    """每门来源课程只保留修读序号最大的一条记录。"""
    effective: Dict[Tuple[int, int], TranscriptRecord] = {}
    for record in transcript:
        key = (record.school_id, record.course_id)
        current = effective.get(key)
        if current is None or record.attempt > current.attempt:
            effective[key] = record
    return effective


def build_problem(
    transcript: Sequence[TranscriptRecord],
    catalog: Sequence[CourseInfo],
    agreements: Sequence[AgreementRule],
    target_school_id: int,
) -> Tuple[List[SourceCourse], List[TargetCourse], List[CandidateEdge]]:
    """过滤出有效来源课程、目标课程与全部合法候选抵扣边。"""
    credits_of: Dict[Tuple[int, int], int] = {}
    for info in catalog:
        credits_of[(info.school_id, info.course_id)] = info.credits

    # 有效来源课程：取序号最大的成绩，且 C 及以上、目录中存在。
    sources: List[SourceCourse] = []
    for key, record in select_effective_records(transcript).items():
        points = GRADE_POINTS[record.grade]
        if points < ELIGIBLE_MIN_POINTS:
            continue
        credits = credits_of.get(key)
        if credits is None:
            continue
        sources.append(
            SourceCourse(
                school_id=record.school_id,
                course_id=record.course_id,
                credits=credits,
                attempt=record.attempt,
                grade=record.grade,
                points=points,
            )
        )
    source_by_key = {(s.school_id, s.course_id): s for s in sources}

    # 目标课程：目标学校在目录中的全部课程。
    targets: List[TargetCourse] = []
    for (school_id, course_id), credits in credits_of.items():
        if school_id == target_school_id:
            targets.append(TargetCourse(course_id=course_id, credits=credits))
    target_by_id = {t.course_id: t for t in targets}

    # 候选抵扣边：直接协议 + 来源学分不少于目标学分；去重。
    edges: List[CandidateEdge] = []
    seen = set()
    for rule in agreements:
        pair = (rule.from_school_id, rule.from_course_id, rule.to_course_id)
        if pair in seen:
            continue
        seen.add(pair)
        source = source_by_key.get((rule.from_school_id, rule.from_course_id))
        target = target_by_id.get(rule.to_course_id)
        if source is None or target is None:
            continue
        if source.credits < target.credits:
            continue
        edges.append(CandidateEdge(source=source, target=target))

    return sources, targets, edges
