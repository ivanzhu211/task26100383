"""规模测试：10000 条修读记录 / 400 来源课程 / 400 目标课程 / 12000 条抵扣关系。

报告单次计算耗时与峰值内存；要求 10 秒内、256 MiB 以内。
"""

import random
import resource
import time
import tracemalloc

from credit_transfer import (
    AgreementRule,
    CourseInfo,
    TranscriptRecord,
    evaluate,
)

MAX_SECONDS = 10.0
MAX_MIB = 256.0


def build_large_instance():
    rng = random.Random(20261003)
    target_school = 999
    n_sources = 400
    n_targets = 400
    n_records = 10000
    n_rules = 12000

    source_keys = []
    for i in range(n_sources):
        source_keys.append((1 + i % 5, 1 + i // 5))  # 5 个来源学校，各 80 门
    catalog = [CourseInfo(s, c, 1 + (i % 4)) for i, (s, c) in enumerate(source_keys)]
    catalog += [CourseInfo(target_school, t, 1 + (t % 4)) for t in range(1, n_targets + 1)]

    transcript = []
    per_course = n_records // n_sources  # 每门课 25 条修读记录
    for school, course in source_keys:
        for attempt in range(1, per_course + 1):
            transcript.append(
                TranscriptRecord(school, course, attempt, rng.choice("AAAABCDF"))
            )
    rng.shuffle(transcript)

    rules = set()
    while len(rules) < n_rules:
        s, c = source_keys[rng.randrange(n_sources)]
        rules.add((s, c, rng.randint(1, n_targets)))
    agreements = [AgreementRule(s, c, t) for s, c, t in rules]
    return transcript, catalog, agreements, target_school


def test_large_instance_within_budget():
    transcript, catalog, agreements, target = build_large_instance()
    assert len(transcript) == 10000
    assert len(agreements) == 12000

    start = time.perf_counter()
    plan = evaluate(transcript, catalog, agreements, target)
    elapsed = time.perf_counter() - start

    # tracemalloc 插桩会显著拖慢运行，内存测量单独跑一遍、不计时。
    tracemalloc.start()
    evaluate(transcript, catalog, agreements, target)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    peak_mib = peak / (1024 * 1024)
    print(
        f"\n认定 {len(plan.assignments)} 门，总学分 {plan.total_credits}，"
        f"质量分 {plan.total_quality}"
    )
    print(f"耗时 {elapsed:.2f}s，Python 峰值内存 {peak_mib:.1f} MiB，进程峰值 RSS {rss_mib:.1f} MiB")

    assert elapsed < MAX_SECONDS, f"耗时 {elapsed:.2f}s 超过 {MAX_SECONDS}s"
    assert peak_mib < MAX_MIB, f"峰值内存 {peak_mib:.1f} MiB 超过 {MAX_MIB} MiB"
