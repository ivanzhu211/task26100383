"""规模与性能测试：10000 修读记录、400 来源课程、400 目标课程、
12000 条直接抵扣关系，要求 10 秒内完成且峰值内存不超过 256 MiB。"""
from __future__ import annotations

import random
import time
import tracemalloc
import unittest

from credit_transfer import (
    Agreement,
    CourseInfo,
    TranscriptRecord,
    compute_plan,
)

_LIMIT_SECONDS = 10.0
_LIMIT_BYTES = 256 * 1024 * 1024


def _large_instance():
    rng = random.Random(26100383)
    catalog = []
    transcript = []
    for i in range(400):
        credits = rng.randint(1, 4)
        catalog.append(CourseInfo(1, 1000 + i, credits))
        # 每门来源课程 25 条修读记录，共 10000 条
        for attempt in range(1, 26):
            transcript.append(
                TranscriptRecord(1, 1000 + i, attempt, rng.choice("AAAAABCDF"))
            )
    for j in range(400):
        catalog.append(CourseInfo(2, 2000 + j, rng.randint(1, 4)))
    agreements = set()
    while len(agreements) < 12000:
        agreements.add(
            Agreement(1, 1000 + rng.randrange(400), 2, 2000 + rng.randrange(400))
        )
    return transcript, catalog, list(agreements)


class PerformanceTest(unittest.TestCase):
    def test_full_scale(self):
        transcript, catalog, agreements = _large_instance()
        self.assertEqual(len(transcript), 10000)
        self.assertEqual(len(agreements), 12000)

        tracemalloc.start()
        start = time.perf_counter()
        plan = compute_plan(2, transcript, catalog, agreements)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(
            f"\n规模测试：耗时 {elapsed:.2f}s，"
            f"峰值内存 {peak / 1024 / 1024:.1f} MiB，"
            f"认定 {len(plan.items)} 门，"
            f"总学分 {plan.total_credits}，质量分 {plan.quality_points}"
        )
        self.assertLess(elapsed, _LIMIT_SECONDS)
        self.assertLess(peak, _LIMIT_BYTES)
        # 结果基本健全性：认定学分与质量分一致
        self.assertEqual(
            plan.total_credits, sum(item.target_credits for item in plan.items)
        )
        self.assertEqual(
            plan.quality_points,
            sum(item.target_credits * item.grade_points for item in plan.items),
        )


if __name__ == "__main__":
    unittest.main()
