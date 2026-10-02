"""认定方案求解入口。

算法：
1. 预处理：每门来源课程只保留修读序号最大的成绩，剔除不及格（C 以下）
   及不满足学分条件的抵扣关系。
2. 以最小费用流求“认定总学分最大、其次质量分最大”的方案：
   每条抵扣边费用为 -(目标学分 * BIG + 目标学分 * 绩点)，
   BIG 大于任何可能的质量分总和，保证两级目标的字典序。
3. 在全部最优方案中按目标课程编号升序逐项确定来源：
   最优解之间只相差零约化费用的循环流，因此对每个目标课程
   用一次反向 BFS 找出仍能出现在某个最优方案中的最小来源，
   沿零费用环改派后固定，保证结果与输入排列无关。
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from .flow import MinCostFlow
from .models import (
    GRADE_POINTS,
    MIN_ELIGIBLE_POINTS,
    Agreement,
    CourseInfo,
    RecognitionItem,
    RecognitionPlan,
    TranscriptRecord,
)

# 单项质量分至多为 4 学分 * 4 绩点 = 16，目标课程至多 400 门，
# 质量分总和不超过 6400，BIG 取 10000 足以让总学分优先于质量分。
_BIG = 10_000


def _check_positive_int(value: int, what: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{what} 必须为正整数，得到 {value!r}")


def compute_plan(
    target_school_id: int,
    transcript: Iterable[TranscriptRecord],
    catalog: Iterable[CourseInfo],
    agreements: Iterable[Agreement],
) -> RecognitionPlan:
    """为一名学生、一个目标学校计算完整认定方案。"""
    _check_positive_int(target_school_id, "目标学校编号")

    credits_of = _parse_catalog(catalog)
    best_record = _parse_transcript(transcript, credits_of)
    target_credits, adjacency = _parse_agreements(
        target_school_id, agreements, credits_of, best_record
    )

    if not best_record or not target_credits:
        return RecognitionPlan(target_school_id, (), 0, 0)

    sources = sorted(best_record)  # [(学校编号, 课程编号)]，下标即来源排名
    source_index = {key: i for i, key in enumerate(sources)}
    targets = sorted(target_credits)
    target_index = {key: i for i, key in enumerate(targets)}

    num_sources = len(sources)
    num_targets = len(targets)
    node_s = 0
    node_t = num_sources + num_targets + 1
    flow = MinCostFlow(node_t + 1)

    for i in range(num_sources):
        flow.add_edge(node_s, 1 + i, 1, 0)
    for j in range(num_targets):
        flow.add_edge(1 + num_sources + j, node_t, 1, 0)

    # 每个目标课程的候选来源边：(来源下标, 边编号)，按来源排名升序。
    # edge_info 记录每条候选边对应的 (来源下标, 目标下标)，
    # 用于改派后同步匹配表（零费用环会同时改动环上其他目标的匹配）。
    edge_info: dict[int, tuple[int, int]] = {}
    candidates: list[list[tuple[int, int]]] = [[] for _ in range(num_targets)]
    for src_key, dst_course in adjacency:
        i = source_index[src_key]
        j = target_index[dst_course]
        points = GRADE_POINTS[best_record[src_key].grade]
        cost = -target_credits[dst_course] * (_BIG + points)
        eid = flow.add_edge(1 + i, 1 + num_sources + j, 1, cost)
        candidates[j].append((i, eid))
        edge_info[eid] = (i, j)
    for j in range(num_targets):
        candidates[j].sort()

    flow.min_cost_flow_while_negative(node_s, node_t)
    # t->s 零费用边使任意流值的解都对应同一循环流，便于最优解间转换。
    # 必须在求流之后加入：否则初始残量图存在负费用环，势不可用。
    flow.add_edge(node_t, node_s, num_sources + num_targets, 0)
    # 加入回边后重算势，使全部残量边约化费用非负
    # （最优解集合的零费用环刻画依赖该性质）。
    flow.recompute_potentials()
    potential = flow.potentials()

    match_of_target: list[int | None] = [None] * num_targets
    for j in range(num_targets):
        for i, eid in candidates[j]:
            if flow.edge_cap(eid) == 0:  # 单位容量，容量耗尽即已使用
                match_of_target[j] = i
                break

    _lexicographic_refinement(
        flow, potential, candidates, edge_info, match_of_target, node_t, num_sources
    )

    items: list[RecognitionItem] = []
    total_credits = 0
    quality_points = 0
    for j, course_id in enumerate(targets):
        i = match_of_target[j]
        if i is None:
            continue
        src_school, src_course = sources[i]
        record = best_record[(src_school, src_course)]
        points = GRADE_POINTS[record.grade]
        t_credits = target_credits[course_id]
        items.append(
            RecognitionItem(
                target_school_id=target_school_id,
                target_course_id=course_id,
                target_credits=t_credits,
                source_school_id=src_school,
                source_course_id=src_course,
                source_credits=credits_of[(src_school, src_course)],
                attempt=record.attempt,
                grade=record.grade,
                grade_points=points,
            )
        )
        total_credits += t_credits
        quality_points += t_credits * points
    return RecognitionPlan(target_school_id, tuple(items), total_credits, quality_points)


def _parse_catalog(catalog: Iterable[CourseInfo]) -> dict[tuple[int, int], int]:
    credits_of: dict[tuple[int, int], int] = {}
    for info in catalog:
        _check_positive_int(info.school_id, "学校编号")
        _check_positive_int(info.course_id, "课程编号")
        if not isinstance(info.credits, int) or not 1 <= info.credits <= 4:
            raise ValueError(f"课程学分必须为 1 至 4 的整数，得到 {info.credits!r}")
        key = (info.school_id, info.course_id)
        if key in credits_of:
            raise ValueError(f"课程目录中课程 {key} 重复出现")
        credits_of[key] = info.credits
    return credits_of


def _parse_transcript(
    transcript: Iterable[TranscriptRecord],
    credits_of: dict[tuple[int, int], int],
) -> dict[tuple[int, int], TranscriptRecord]:
    """每门课程只保留修读序号最大的记录，且仅保留有转入资格的成绩。

    最近一次修读不及格的课程整体剔除，不得回退采用更早的好成绩。
    """
    latest: dict[tuple[int, int], TranscriptRecord] = {}
    for record in transcript:
        _check_positive_int(record.school_id, "学校编号")
        _check_positive_int(record.course_id, "课程编号")
        _check_positive_int(record.attempt, "修读序号")
        if record.grade not in GRADE_POINTS:
            raise ValueError(f"无效成绩 {record.grade!r}")
        key = (record.school_id, record.course_id)
        if key not in credits_of:
            raise ValueError(f"课程目录缺少成绩单中的课程 {key}")
        current = latest.get(key)
        if current is not None and record.attempt == current.attempt:
            raise ValueError(f"课程 {key} 的修读序号 {record.attempt} 重复")
        if current is None or record.attempt > current.attempt:
            latest[key] = record
    return {
        key: record
        for key, record in latest.items()
        if GRADE_POINTS[record.grade] >= MIN_ELIGIBLE_POINTS
    }


def _parse_agreements(
    target_school_id: int,
    agreements: Iterable[Agreement],
    credits_of: dict[tuple[int, int], int],
    best_record: dict[tuple[int, int], TranscriptRecord],
) -> tuple[dict[int, int], set[tuple[tuple[int, int], int]]]:
    """筛选适用于当前目标学校的直接抵扣关系。

    返回 (目标课程学分表, 抵扣边集合)；
    抵扣边为 ((来源学校, 来源课程), 目标课程号)。
    """
    target_credits: dict[int, int] = {}
    edges: set[tuple[tuple[int, int], int]] = set()
    for agreement in agreements:
        _check_positive_int(agreement.source_school_id, "学校编号")
        _check_positive_int(agreement.source_course_id, "课程编号")
        _check_positive_int(agreement.target_school_id, "学校编号")
        _check_positive_int(agreement.target_course_id, "课程编号")
        if agreement.target_school_id != target_school_id:
            continue
        src_key = (agreement.source_school_id, agreement.source_course_id)
        if src_key not in best_record:
            continue  # 来源课程无合格成绩
        if src_key not in credits_of:
            raise ValueError(f"课程目录缺少协议中的来源课程 {src_key}")
        dst_key = (target_school_id, agreement.target_course_id)
        if dst_key not in credits_of:
            raise ValueError(f"课程目录缺少协议中的目标课程 {dst_key}")
        if credits_of[src_key] < credits_of[dst_key]:
            continue  # 来源学分不足，不能抵扣
        target_credits[agreement.target_course_id] = credits_of[dst_key]
        edges.add((src_key, agreement.target_course_id))
    return target_credits, edges


def _lexicographic_refinement(
    flow: MinCostFlow,
    potential: list[int],
    candidates: list[list[tuple[int, int]]],
    edge_info: dict[int, tuple[int, int]],
    match_of_target: list[int | None],
    node_t: int,
    num_sources: int,
) -> None:
    """在全部最优方案中，按目标课程编号升序逐项取字典序最小来源。

    对每个目标课程做一次 BFS：从零约化费用残量边能回到某来源，
    当且仅当该来源仍可出现在某个最优方案中。选定后沿零费用环
    改派并固定（节点不再参与后续迭代）。
    """
    num_nodes = node_t + 1
    active = [True] * num_nodes
    graph, edge_to, edge_cap, edge_cost = flow.internals()

    for j in range(len(candidates)):
        target_node = 1 + num_sources + j
        # BFS：收集 target_node 沿零约化费用残量边可达的节点。
        reached = bytearray(num_nodes)
        parent_edge = [-1] * num_nodes
        queue = deque([target_node])
        reached[target_node] = 1
        while queue:
            u = queue.popleft()
            pot_u = potential[u]
            for eid in graph[u]:
                if edge_cap[eid] <= 0:
                    continue
                v = edge_to[eid]
                if reached[v] or not active[v]:
                    continue
                if edge_cost[eid] + pot_u - potential[v] != 0:
                    continue
                reached[v] = 1
                parent_edge[v] = eid
                queue.append(v)

        chosen: int | None = None
        for i, eid in candidates[j]:
            source_node = 1 + i
            if not active[source_node]:
                continue
            if match_of_target[j] == i:
                chosen = i  # 当前匹配必然可行
                break
            reduced = (
                edge_cost[eid]
                + potential[source_node]
                - potential[target_node]
            )
            if reduced == 0 and edge_cap[eid] > 0 and reached[source_node]:
                chosen = i
                break

        if chosen is not None:
            if match_of_target[j] != chosen:
                affected = _augment_cycle(
                    flow, parent_edge, 1 + chosen, target_node, edge_info
                )
                _refresh_matches(flow, candidates, match_of_target, affected)
        elif match_of_target[j] is not None and reached[node_t]:
            # 选择不认定：沿 t->target_node 的零费用环退掉当前匹配。
            affected = _augment_cycle(
                flow, parent_edge, node_t, target_node, edge_info
            )
            _refresh_matches(flow, candidates, match_of_target, affected)
        # 其余情况保持现状（当前匹配或未认定必然可行）。

        active[target_node] = False
        if match_of_target[j] is not None:
            active[1 + match_of_target[j]] = False


def _augment_cycle(
    flow: MinCostFlow,
    parent_edge: list[int],
    start: int,
    target_node: int,
    edge_info: dict[int, tuple[int, int]],
) -> set[int]:
    """沿 start->target_node 残量边与 BFS 树中 target_node 到 start
    的零费用路径增广 1 单位，使 start->target_node 进入匹配。
    返回匹配可能被改动的目标课程下标集合。"""
    forward = None
    for eid in flow.edges_from(start):
        if flow.edge_to(eid) == target_node and flow.edge_cap(eid) > 0:
            forward = eid
            break
    assert forward is not None, "改派边不存在，算法不变量被破坏"
    path = [forward]
    node = start
    while node != target_node:
        eid = parent_edge[node]
        assert eid != -1, "BFS 树不连通，算法不变量被破坏"
        path.append(eid)
        node = flow.edge_to(eid ^ 1)  # parent_edge 指向 node，其父为边的另一端
    affected: set[int] = set()
    for eid in path:
        flow.push(eid, 1)
        if eid in edge_info:
            affected.add(edge_info[eid][1])
        elif (eid ^ 1) in edge_info:
            affected.add(edge_info[eid ^ 1][1])
    return affected


def _refresh_matches(
    flow: MinCostFlow,
    candidates: list[list[tuple[int, int]]],
    match_of_target: list[int | None],
    affected: set[int],
) -> None:
    """按当前流量重算受影响目标课程的匹配。"""
    for j in affected:
        match_of_target[j] = None
        for i, eid in candidates[j]:
            if flow.edge_cap(eid) == 0:  # 单位容量，容量耗尽即已使用
                match_of_target[j] = i
                break
