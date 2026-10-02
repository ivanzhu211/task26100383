"""业务规则测试：成绩采用、资格门槛、改派链、抵扣约束。"""

from credit_transfer import (
    AgreementRule,
    CourseInfo,
    TranscriptRecord,
    evaluate,
)


def make_catalog(entries):
    return [CourseInfo(s, c, cr) for s, c, cr in entries]


def test_latest_attempt_wins_even_when_failing():
    # 先得 A 后得 F：只能采用序号最大的 F，旧成绩不能复用。
    transcript = [
        TranscriptRecord(1, 10, 1, "A"),
        TranscriptRecord(1, 10, 2, "F"),
    ]
    catalog = make_catalog([(1, 10, 3), (9, 1, 3)])
    agreements = [AgreementRule(1, 10, 1)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 0
    assert plan.total_quality == 0
    assert plan.assignments == []


def test_latest_attempt_can_rescue_earlier_failure():
    # 先 F 后 A：采用最近的 A。
    transcript = [
        TranscriptRecord(1, 10, 1, "F"),
        TranscriptRecord(1, 10, 2, "A"),
    ]
    catalog = make_catalog([(1, 10, 3), (9, 1, 3)])
    agreements = [AgreementRule(1, 10, 1)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 3
    assert plan.assignments[0].attempt == 2
    assert plan.assignments[0].grade == "A"


def test_exactly_c_is_eligible_and_d_is_not():
    transcript = [
        TranscriptRecord(1, 10, 1, "C"),
        TranscriptRecord(1, 11, 1, "D"),
    ]
    catalog = make_catalog([(1, 10, 2), (1, 11, 2), (9, 1, 2), (9, 2, 2)])
    agreements = [AgreementRule(1, 10, 1), AgreementRule(1, 11, 2)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert len(plan.assignments) == 1
    a = plan.assignments[0]
    assert a.source_course_id == 10
    assert a.grade == "C"
    assert a.quality == 2 * 2  # 目标学分 * C 的绩点


def test_chain_reassignment_beats_greedy():
    # s1->t1, s2->t1, s2->t2：逐门贪心先让 s2 占 t1 会卡住，
    # 最优需要把 t1 改派给 s1、s2 改去 t2，共认定两门。
    transcript = [TranscriptRecord(1, 1, 1, "B"), TranscriptRecord(1, 2, 1, "B")]
    catalog = make_catalog([(1, 1, 3), (1, 2, 3), (9, 1, 3), (9, 2, 3)])
    agreements = [
        AgreementRule(1, 1, 1),
        AgreementRule(1, 2, 1),
        AgreementRule(1, 2, 2),
    ]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 6
    pairs = {(a.source_course_id, a.target_course_id) for a in plan.assignments}
    assert pairs == {(1, 1), (2, 2)}


def test_longer_reassignment_chain():
    # 4 门源课程、4 门目标课程构成需要连续改派 3 次的链。
    transcript = [TranscriptRecord(1, i, 1, "A") for i in range(1, 5)]
    catalog = make_catalog(
        [(1, i, 2) for i in range(1, 5)] + [(9, i, 2) for i in range(1, 5)]
    )
    agreements = []
    for i in range(1, 5):
        agreements.append(AgreementRule(1, i, i))
        if i < 4:
            agreements.append(AgreementRule(1, i + 1, i))
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 8
    assert len(plan.assignments) == 4


def test_source_credits_must_cover_target():
    # 来源 2 学分不能抵扣 3 学分目标；也不能拼接两门来源凑一门目标。
    transcript = [TranscriptRecord(1, 1, 1, "A"), TranscriptRecord(1, 2, 1, "A")]
    catalog = make_catalog([(1, 1, 2), (1, 2, 2), (9, 1, 3)])
    agreements = [AgreementRule(1, 1, 1), AgreementRule(1, 2, 1)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 0


def test_surplus_source_credits_are_discarded():
    # 4 学分来源抵 2 学分目标，认定学分 = 目标学分，多出作废。
    transcript = [TranscriptRecord(1, 1, 1, "A")]
    catalog = make_catalog([(1, 1, 4), (9, 1, 2)])
    agreements = [AgreementRule(1, 1, 1)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 2
    assert plan.assignments[0].credits_awarded == 2
    assert plan.total_quality == 2 * 4


def test_one_to_one_constraint():
    # 一门来源最多抵一门目标；一门目标最多被抵一次。
    transcript = [TranscriptRecord(1, 1, 1, "A")]
    catalog = make_catalog([(1, 1, 3), (9, 1, 3), (9, 2, 3)])
    agreements = [AgreementRule(1, 1, 1), AgreementRule(1, 1, 2)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert len(plan.assignments) == 1
    assert plan.total_credits == 3


def test_agreement_direction_and_no_transitivity():
    # 目标学校 2 只与学校 9 有直接协议；学生修的是学校 1 的课，
    # 即使学校 1->9 的协议存在，也不能经学校 9 传递认定资格。
    transcript = [TranscriptRecord(1, 1, 1, "A")]
    catalog = make_catalog([(1, 1, 3), (9, 1, 3), (2, 1, 3)])
    agreements = [AgreementRule(9, 1, 1)]
    plan = evaluate(transcript, catalog, agreements, 2)
    assert plan.total_credits == 0


def test_agreement_not_applied_in_reverse():
    # 协议是学校 9 的课 -> 目标课程；学生修的是学校 1 的同目标协议之外的课。
    transcript = [TranscriptRecord(1, 1, 1, "A")]
    catalog = make_catalog([(1, 1, 3), (9, 1, 3), (9, 2, 3)])
    agreements = [AgreementRule(9, 1, 2)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 0


def test_same_course_number_different_school_is_distinct():
    # 不同学校同号课程不是同一门课：协议针对学校 2 的课，学校 1 的同号课不适用。
    transcript = [TranscriptRecord(1, 7, 1, "A")]
    catalog = make_catalog([(1, 7, 3), (2, 7, 3), (9, 1, 3)])
    agreements = [AgreementRule(2, 7, 1)]
    plan = evaluate(transcript, catalog, agreements, 9)
    assert plan.total_credits == 0


def test_empty_input_gives_zero_totals():
    plan = evaluate([], [], [], 9)
    assert plan.total_credits == 0
    assert plan.total_quality == 0
    assert plan.assignments == []
