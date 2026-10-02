"""独立穷举参考实现：直接按业务规则枚举全部合法方案取最优。"""
from __future__ import annotations

from credit_transfer import (
    GRADE_POINTS,
    MIN_ELIGIBLE_POINTS,
    Agreement,
    CourseInfo,
    TranscriptRecord,
)

_UNMATCHED = (1, 0, 0)  # 未认定视为大于任何来源


def brute_force_plan(
    target_school_id: int,
    transcript: list[TranscriptRecord],
    catalog: list[CourseInfo],
    agreements: list[Agreement],
):
    """返回 (认定关系 dict[(目标课程)->(来源学校,来源课程)], 总学分, 质量分)。"""
    credits_of = {(c.school_id, c.course_id): c.credits for c in catalog}

    latest: dict[tuple[int, int], TranscriptRecord] = {}
    for record in transcript:
        key = (record.school_id, record.course_id)
        if key not in latest or record.attempt > latest[key].attempt:
            latest[key] = record
    eligible = {
        key: rec
        for key, rec in latest.items()
        if GRADE_POINTS[rec.grade] >= MIN_ELIGIBLE_POINTS
    }

    edges: dict[int, list[tuple[int, int]]] = {}
    target_credits: dict[int, int] = {}
    for ag in agreements:
        if ag.target_school_id != target_school_id:
            continue
        src = (ag.source_school_id, ag.source_course_id)
        if src not in eligible:
            continue
        if credits_of[src] < credits_of[(target_school_id, ag.target_course_id)]:
            continue
        edges.setdefault(ag.target_course_id, [])
        if src not in edges[ag.target_course_id]:
            edges[ag.target_course_id].append(src)
        target_credits[ag.target_course_id] = credits_of[
            (target_school_id, ag.target_course_id)
        ]

    targets = sorted(target_credits)
    best_key = None
    best_assign: dict[int, tuple[int, int]] = {}

    def evaluate(assign: dict[int, tuple[int, int]]):
        nonlocal best_key, best_assign
        total_credits = sum(target_credits[t] for t in assign)
        quality = sum(
            target_credits[t] * GRADE_POINTS[eligible[src].grade]
            for t, src in assign.items()
        )
        sequence = tuple(
            (0, assign[t][0], assign[t][1]) if t in assign else _UNMATCHED
            for t in targets
        )
        key = (total_credits, quality, tuple(_neg(x) for x in sequence))
        if best_key is None or key > best_key:
            best_key = key
            best_assign = dict(assign)

    def _neg(parts):
        # 序列需取字典序最小：映射为取最大时用的相反序
        return tuple(-x for x in parts)

    def search(idx: int, used: set, assign: dict[int, tuple[int, int]]):
        if idx == len(targets):
            evaluate(assign)
            return
        t = targets[idx]
        search(idx + 1, used, assign)  # 不认定
        for src in edges.get(t, []):
            if src in used:
                continue
            used.add(src)
            assign[t] = src
            search(idx + 1, used, assign)
            del assign[t]
            used.discard(src)

    search(0, set(), {})
    total_credits = sum(target_credits[t] for t in best_assign)
    quality = sum(
        target_credits[t] * GRADE_POINTS[eligible[src].grade]
        for t, src in best_assign.items()
    )
    return best_assign, total_credits, quality
