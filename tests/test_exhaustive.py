"""小规模随机案例与独立穷举结果完全一致，且输入重排不改变结果。"""

import itertools
import random

from credit_transfer import (
    AgreementRule,
    CourseInfo,
    TranscriptRecord,
    evaluate,
)
from credit_transfer.models import GRADE_POINTS

INF = (10 ** 18, 10 ** 18)  # 未认定位置视为大于任何来源课程


def brute_force(transcript, catalog, agreements, target_school_id):
    """独立穷举：枚举全部合法匹配，按三级目标取最优。"""
    credits_of = {(c.school_id, c.course_id): c.credits for c in catalog}
    effective = {}
    for r in transcript:
        key = (r.school_id, r.course_id)
        if key not in effective or r.attempt > effective[key].attempt:
            effective[key] = r
    sources = {
        k: r
        for k, r in effective.items()
        if GRADE_POINTS[r.grade] >= 2 and k in credits_of
    }
    targets = sorted(
        c.course_id for c in catalog if c.school_id == target_school_id
    )
    candidates = {t: [] for t in targets}
    for rule in agreements:
        skey = (rule.from_school_id, rule.from_course_id)
        if skey in sources and rule.to_course_id in candidates:
            if credits_of[skey] >= credits_of[(target_school_id, rule.to_course_id)]:
                candidates[rule.to_course_id].append(skey)

    best = None  # (总学分, 总质量, 字典序键, 匹配dict)
    # 枚举：每门目标课程选择不匹配或匹配一门未用的来源课程
    def lex_key(match):
        return tuple(match.get(t, INF) for t in targets)

    def objective(match):
        credits = sum(credits_of[(target_school_id, t)] for t in match)
        quality = sum(
            credits_of[(target_school_id, t)] * GRADE_POINTS[sources[s].grade]
            for t, s in match.items()
        )
        return credits, quality

    def better(match, incumbent):
        if incumbent is None:
            return True
        c1, q1 = objective(match)
        c2, q2 = objective(incumbent)
        if c1 != c2:
            return c1 > c2
        if q1 != q2:
            return q1 > q2
        return lex_key(match) < lex_key(incumbent)

    def dfs(i, used, match):
        nonlocal best
        if i == len(targets):
            if better(match, best):
                best = dict(match)
            return
        t = targets[i]
        dfs(i + 1, used, match)  # 不匹配
        for s in candidates[t]:
            if s not in used:
                match[t] = s
                dfs(i + 1, used | {s}, match)
                del match[t]

    dfs(0, set(), {})
    return best or {}


def random_instance(rng, n_source_schools=2, n_sources=4, n_targets=4):
    target_school = 99
    catalog = []
    source_keys = []
    for _ in range(n_sources):
        school = rng.randint(1, n_source_schools)
        course = rng.randint(1, 6)
        key = (school, course)
        if key in source_keys or school == target_school:
            continue
        source_keys.append(key)
        catalog.append(CourseInfo(school, course, rng.randint(1, 4)))
    target_ids = random.sample(range(1, 8), min(n_targets, 7))
    for t in target_ids:
        catalog.append(CourseInfo(target_school, t, rng.randint(1, 4)))
    transcript = []
    for school, course in source_keys:
        for attempt in range(1, rng.randint(1, 3) + 1):
            transcript.append(
                TranscriptRecord(school, course, attempt, rng.choice("ABCDF"))
            )
    agreements = []
    for school, course in source_keys:
        for t in target_ids:
            if rng.random() < 0.5:
                agreements.append(AgreementRule(school, course, t))
    return transcript, catalog, agreements, target_school


def normalize(plan):
    return (
        plan.total_credits,
        plan.total_quality,
        tuple(
            (a.target_course_id, a.source_school_id, a.source_course_id)
            for a in plan.assignments
        ),
    )


def from_brute(match, catalog, transcript, target_school_id):
    credits_of = {(c.school_id, c.course_id): c.credits for c in catalog}
    effective = {}
    for r in transcript:
        key = (r.school_id, r.course_id)
        if key not in effective or r.attempt > effective[key].attempt:
            effective[key] = r
    items = []
    for t, s in sorted(match.items()):
        items.append((t, s[0], s[1]))
    credits = sum(credits_of[(target_school_id, t)] for t, _, _ in items)
    quality = sum(
        credits_of[(target_school_id, t)] * GRADE_POINTS[effective[(s1, s2)].grade]
        for t, s1, s2 in items
    )
    return credits, quality, tuple(items)


def test_matches_brute_force_on_random_instances():
    rng = random.Random(20261003)
    for trial in range(300):
        transcript, catalog, agreements, target = random_instance(rng)
        plan = evaluate(transcript, catalog, agreements, target)
        expected = from_brute(
            brute_force(transcript, catalog, agreements, target),
            catalog,
            transcript,
            target,
        )
        assert normalize(plan) == expected, f"trial {trial}"


def test_input_permutation_does_not_change_result():
    rng = random.Random(777)
    for trial in range(100):
        transcript, catalog, agreements, target = random_instance(rng)
        baseline = normalize(evaluate(transcript, catalog, agreements, target))
        for _ in range(3):
            tr = list(transcript)
            cat = list(catalog)
            ag = list(agreements)
            rng.shuffle(tr)
            rng.shuffle(cat)
            rng.shuffle(ag)
            assert normalize(evaluate(tr, cat, ag, target)) == baseline
