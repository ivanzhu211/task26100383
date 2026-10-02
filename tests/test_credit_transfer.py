"""业务规则与正确性测试。"""
from __future__ import annotations

import itertools
import random
import unittest

from credit_transfer import (
    Agreement,
    CourseInfo,
    TranscriptRecord,
    compute_plan,
)
from tests.brute_force import brute_force_plan


def as_map(plan):
    return {
        item.target_course_id: (item.source_school_id, item.source_course_id)
        for item in plan.items
    }


class GradeRuleTest(unittest.TestCase):
    def test_latest_attempt_fails_course(self):
        # 先得 A 后得 F：最近一次不及格，旧成绩不得复用。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 101, 2, "F")],
            [CourseInfo(1, 101, 3), CourseInfo(2, 201, 3)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.items, ())
        self.assertEqual(plan.total_credits, 0)
        self.assertEqual(plan.quality_points, 0)

    def test_latest_attempt_wins_over_earlier_failure(self):
        # 先得 F 后得 C：采用最近的 C。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "F"), TranscriptRecord(1, 101, 2, "C")],
            [CourseInfo(1, 101, 3), CourseInfo(2, 201, 3)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.total_credits, 3)
        self.assertEqual(plan.quality_points, 6)
        self.assertEqual(plan.items[0].attempt, 2)
        self.assertEqual(plan.items[0].grade, "C")

    def test_exact_c_is_eligible(self):
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "C")],
            [CourseInfo(1, 101, 2), CourseInfo(2, 201, 2)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.total_credits, 2)
        self.assertEqual(plan.quality_points, 4)
        self.assertEqual(plan.items[0].grade_points, 2)

    def test_d_is_not_eligible(self):
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "D")],
            [CourseInfo(1, 101, 2), CourseInfo(2, 201, 2)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.items, ())


class CreditRuleTest(unittest.TestCase):
    def test_source_credits_must_cover_target(self):
        # 来源 2 学分不能抵扣 3 学分目标课。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A")],
            [CourseInfo(1, 101, 2), CourseInfo(2, 201, 3)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.items, ())

    def test_excess_source_credits_are_discarded(self):
        # 来源 4 学分抵扣 2 学分目标课：认定 2 学分，多出作废。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "B")],
            [CourseInfo(1, 101, 4), CourseInfo(2, 201, 2)],
            [Agreement(1, 101, 2, 201)],
        )
        self.assertEqual(plan.total_credits, 2)
        self.assertEqual(plan.quality_points, 6)
        self.assertEqual(plan.items[0].source_credits, 4)

    def test_no_combining_sources_for_one_target(self):
        # 两门 2 学分来源课不能拼接满足一门 4 学分目标课。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 102, 1, "A")],
            [CourseInfo(1, 101, 2), CourseInfo(1, 102, 2), CourseInfo(2, 201, 4)],
            [Agreement(1, 101, 2, 201), Agreement(1, 102, 2, 201)],
        )
        self.assertEqual(plan.items, ())

    def test_one_source_matches_at_most_one_target(self):
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A")],
            [CourseInfo(1, 101, 4), CourseInfo(2, 201, 2), CourseInfo(2, 202, 2)],
            [Agreement(1, 101, 2, 201), Agreement(1, 101, 2, 202)],
        )
        self.assertEqual(plan.total_credits, 2)
        self.assertEqual(len(plan.items), 1)


class AgreementDirectionTest(unittest.TestCase):
    def test_reverse_direction_not_used(self):
        # 协议方向为 2->1，对目标学校 2 无效。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A")],
            [CourseInfo(1, 101, 3), CourseInfo(2, 201, 3)],
            [Agreement(2, 201, 1, 101)],
        )
        self.assertEqual(plan.items, ())

    def test_no_transitivity_through_third_school(self):
        # 1->3 与 3->2 的协议不能让学校 1 的课程认定到学校 2。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A")],
            [
                CourseInfo(1, 101, 3),
                CourseInfo(3, 301, 3),
                CourseInfo(2, 201, 3),
            ],
            [Agreement(1, 101, 3, 301), Agreement(3, 301, 2, 201)],
        )
        self.assertEqual(plan.items, ())

    def test_same_number_different_school_not_equivalent(self):
        # 不同学校同号课程不是同一门课。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 201, 1, "A")],
            [CourseInfo(1, 201, 3), CourseInfo(2, 201, 3)],
            [],
        )
        self.assertEqual(plan.items, ())


class ChainReassignmentTest(unittest.TestCase):
    def test_long_augmenting_chain(self):
        # s_i 可抵 t_i 与 t_{i+1}（i=1..n-1），s_n 只能抵 t_n。
        # 逐门贪心（s_1 占 t_1、s_2 占 t_2……）会损失一半认定；
        # 最优需要连续改派：s_1->t_1, s_2->t_2, ..., s_n->t_n 全部认定。
        n = 50
        transcript = [TranscriptRecord(1, 100 + i, 1, "A") for i in range(1, n + 1)]
        catalog = [CourseInfo(1, 100 + i, 2) for i in range(1, n + 1)]
        catalog += [CourseInfo(2, 200 + j, 2) for j in range(1, n + 1)]
        agreements = []
        for i in range(1, n):
            agreements.append(Agreement(1, 100 + i, 2, 200 + i))
            agreements.append(Agreement(1, 100 + i, 2, 200 + i + 1))
        agreements.append(Agreement(1, 100 + n, 2, 200 + n))
        plan = compute_plan(2, transcript, catalog, agreements)
        self.assertEqual(plan.total_credits, 2 * n)
        self.assertEqual(len(plan.items), n)
        for item in plan.items:
            self.assertEqual(item.source_course_id, item.target_course_id - 100)

    def test_greedy_would_fail(self):
        # s1(4学分,A) 可抵 t1,t2；s2(4学分,B) 只能抵 t1。
        # 若 s1 先占 t1，则 s2 无处可去，总学分 4；
        # 最优为 s1->t2、s2->t1，总学分 8。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 102, 1, "B")],
            [CourseInfo(1, 101, 4), CourseInfo(1, 102, 4),
             CourseInfo(2, 201, 4), CourseInfo(2, 202, 4)],
            [Agreement(1, 101, 2, 201), Agreement(1, 101, 2, 202),
             Agreement(1, 102, 2, 201)],
        )
        self.assertEqual(plan.total_credits, 8)
        self.assertEqual(as_map(plan), {201: (1, 102), 202: (1, 101)})


class QualityAndTieBreakTest(unittest.TestCase):
    def test_quality_breaks_credit_tie(self):
        # 两种方案总学分相同，选质量分大的：A(4) 配 4 学分优于 B(3)。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 102, 1, "B")],
            [CourseInfo(1, 101, 4), CourseInfo(1, 102, 4),
             CourseInfo(2, 201, 4), CourseInfo(2, 202, 4)],
            [Agreement(1, 101, 2, 201), Agreement(1, 102, 2, 201),
             Agreement(1, 101, 2, 202)],
        )
        self.assertEqual(plan.total_credits, 8)
        self.assertEqual(plan.quality_points, 4 * 4 + 4 * 3)
        self.assertEqual(as_map(plan), {201: (1, 102), 202: (1, 101)})

    def test_lexicographic_tie_break(self):
        # 总学分与质量分都相同：目标课编号小的位置优先取来源编号小者。
        # s1=课程101、s2=课程102 均可抵 t1=201 或 t2=202，成绩学分全同。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 102, 1, "A")],
            [CourseInfo(1, 101, 2), CourseInfo(1, 102, 2),
             CourseInfo(2, 201, 2), CourseInfo(2, 202, 2)],
            [Agreement(1, 101, 2, 201), Agreement(1, 101, 2, 202),
             Agreement(1, 102, 2, 201), Agreement(1, 102, 2, 202)],
        )
        self.assertEqual(as_map(plan), {201: (1, 101), 202: (1, 102)})

    def test_lexicographic_school_before_course(self):
        # 来源学校编号优先于课程编号比较。
        plan = compute_plan(
            2,
            [TranscriptRecord(5, 101, 1, "A"), TranscriptRecord(3, 999, 1, "A")],
            [CourseInfo(5, 101, 2), CourseInfo(3, 999, 2), CourseInfo(2, 201, 2)],
            [Agreement(5, 101, 2, 201), Agreement(3, 999, 2, 201)],
        )
        self.assertEqual(as_map(plan), {201: (3, 999)})

    def test_unmatched_position_is_worst(self):
        # 两门目标课争一门来源课：宁可使小编号目标课被认定。
        plan = compute_plan(
            2,
            [TranscriptRecord(1, 101, 1, "A")],
            [CourseInfo(1, 101, 2), CourseInfo(2, 201, 2), CourseInfo(2, 202, 2)],
            [Agreement(1, 101, 2, 201), Agreement(1, 101, 2, 202)],
        )
        self.assertEqual(as_map(plan), {201: (1, 101)})


class PermutationInvarianceTest(unittest.TestCase):
    def test_input_order_does_not_matter(self):
        rng = random.Random(20261003)
        transcript, catalog, agreements = _random_instance(rng, 12, 10, 40)
        expected = compute_plan(2, transcript, catalog, agreements)
        for _ in range(20):
            t2, c2, a2 = list(transcript), list(catalog), list(agreements)
            rng.shuffle(t2)
            rng.shuffle(c2)
            rng.shuffle(a2)
            actual = compute_plan(2, t2, c2, a2)
            self.assertEqual(actual, expected)


class BruteForceConsistencyTest(unittest.TestCase):
    def test_random_small_instances_match_brute_force(self):
        rng = random.Random(7)
        for trial in range(300):
            transcript, catalog, agreements = _random_instance(
                rng, n_sources=5, n_targets=5, n_agreements=12
            )
            plan = compute_plan(2, transcript, catalog, agreements)
            assign, total_credits, quality = brute_force_plan(
                2, transcript, catalog, agreements
            )
            self.assertEqual(plan.total_credits, total_credits, f"trial {trial}")
            self.assertEqual(plan.quality_points, quality, f"trial {trial}")
            self.assertEqual(as_map(plan), assign, f"trial {trial}")


class ValidationTest(unittest.TestCase):
    def test_invalid_ids_rejected(self):
        with self.assertRaises(ValueError):
            compute_plan(0, [], [], [])
        with self.assertRaises(ValueError):
            compute_plan(2, [TranscriptRecord(1, 101, 1, "A")],
                         [CourseInfo(1, 0, 1)], [])

    def test_invalid_credits_rejected(self):
        with self.assertRaises(ValueError):
            compute_plan(2, [], [CourseInfo(1, 101, 5)], [])

    def test_duplicate_attempt_rejected(self):
        with self.assertRaises(ValueError):
            compute_plan(
                2,
                [TranscriptRecord(1, 101, 1, "A"), TranscriptRecord(1, 101, 1, "B")],
                [CourseInfo(1, 101, 2)],
                [],
            )

    def test_missing_catalog_entry_rejected(self):
        with self.assertRaises(ValueError):
            compute_plan(2, [TranscriptRecord(1, 101, 1, "A")], [], [])


def _random_instance(rng, n_sources, n_targets, n_agreements):
    """生成随机小规模实例：含多学校、多修读记录与随机学分。"""
    catalog = []
    transcript = []
    for i in range(n_sources):
        school = rng.choice([1, 3, 5])
        course = 100 + i
        catalog.append(CourseInfo(school, course, rng.randint(1, 4)))
        for attempt in range(1, rng.randint(1, 3) + 1):
            transcript.append(
                TranscriptRecord(school, course, attempt, rng.choice("ABCDF"))
            )
    for j in range(n_targets):
        catalog.append(CourseInfo(2, 200 + j, rng.randint(1, 4)))
    src_keys = [(c.school_id, c.course_id) for c in catalog if c.school_id != 2]
    agreements = set()
    while len(agreements) < n_agreements:
        s_school, s_course = rng.choice(src_keys)
        agreements.add((s_school, s_course, 200 + rng.randrange(n_targets)))
    return (
        transcript,
        catalog,
        [Agreement(s, c, 2, t) for s, c, t in agreements],
    )


if __name__ == "__main__":
    unittest.main()
