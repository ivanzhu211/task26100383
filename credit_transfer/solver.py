"""严格最优求解：把三级目标编码为大整数权重，跑最小费用流。"""

from __future__ import annotations

import heapq
from typing import List, Sequence, Tuple

from .core import CandidateEdge, SourceCourse, TargetCourse


def solve_optimal_matching(
    sources: Sequence[SourceCourse],
    targets: Sequence[TargetCourse],
    edges: Sequence[CandidateEdge],
) -> List[Tuple[SourceCourse, TargetCourse]]:
    """返回 (来源课程, 目标课程) 配对列表，满足三级优化目标。"""
    if not sources or not targets or not edges:
        return []

    # --- 权重编码 -------------------------------------------------------
    # 目标课程按编号升序排列，位置越靠前权重越高（字典序比较）。
    ordered_targets = sorted(targets, key=lambda t: t.course_id)
    position_of = {t.course_id: p for p, t in enumerate(ordered_targets)}
    n = len(ordered_targets)

    max_course_id = max(s.course_id for s in sources)
    course_base = max_course_id + 1

    def code_of(source: SourceCourse) -> int:
        # 与 (学校编号, 课程编号) 数值字典序同构的编码。
        return source.school_id * course_base + source.course_id

    unmatched = max(code_of(s) for s in sources) + 1  # 未认定视为大于任何来源
    base = (unmatched + 1) * (n + 1)  # 位置进制：保证低位无法溢出到高位
    quality_scale = base ** n  # 质量分 1 分之差压过全部字典序项
    max_quality_sum = 4 * 4 * n  # 质量分总和上界（4 学分 * 4 绩点 * n 项）
    credit_scale = (max_quality_sum + 1) * quality_scale  # 学分 1 分压过全部质量分

    # 位置 p 的位权：越靠前越大。
    positional = [base ** (n - 1 - p) for p in range(n)]

    # --- 建图 -----------------------------------------------------------
    src_index = {id(s): i for i, s in enumerate(sources)}
    source_of_edge_node: List[SourceCourse] = list(sources)
    tgt_node = {t.course_id: len(sources) + i for i, t in enumerate(ordered_targets)}
    node_count = len(sources) + len(ordered_targets) + 2
    S = node_count - 2
    T = node_count - 1

    # 邻接表：to, cap, cost, 反向边下标
    graph: List[List[list]] = [[] for _ in range(node_count)]

    def add_edge(frm: int, to: int, cap: int, cost: int) -> None:
        graph[frm].append([to, cap, cost, len(graph[to])])
        graph[to].append([frm, 0, -cost, len(graph[frm]) - 1])

    for i in range(len(sources)):
        add_edge(S, i, 1, 0)
    for t in ordered_targets:
        add_edge(tgt_node[t.course_id], T, 1, 0)

    edge_records: List[Tuple[int, int, int]] = []  # (源节点, 边下标, 目标课程编号)
    for edge in edges:
        s = edge.source
        t = edge.target
        p = position_of[t.course_id]
        cost = (
            (code_of(s) - unmatched) * positional[p]
            - t.credits * (credit_scale + s.points * quality_scale)
        )
        u = src_index[id(s)]
        v = tgt_node[t.course_id]
        edge_records.append((u, len(graph[u]), t.course_id))
        add_edge(u, v, 1, cost)

    # --- 初始势能（图分三层，可直接求最短路，避免 Bellman-Ford） --------
    potential = [0] * node_count
    for u, edge_idx, _ in edge_records:
        e = graph[u][edge_idx]
        v = e[0]
        if potential[v] == 0 or e[2] < potential[v]:
            potential[v] = e[2]
    potential[T] = min(potential[tgt_node[t.course_id]] for t in ordered_targets)

    # ---  successive shortest paths ------------------------------------
    while True:
        dist = [None] * node_count
        dist[S] = 0
        prev: List[Tuple[int, int] | None] = [None] * node_count
        heap = [(0, S)]
        while heap:
            d, u = heapq.heappop(heap)
            if dist[u] is not None and d > dist[u]:
                continue
            for i, e in enumerate(graph[u]):
                if e[1] <= 0:
                    continue
                v = e[0]
                nd = d + e[2] + potential[u] - potential[v]
                if dist[v] is None or nd < dist[v]:
                    dist[v] = nd
                    prev[v] = (u, i)
                    heapq.heappush(heap, (nd, v))
        if dist[T] is None:
            break
        real_cost = dist[T] + potential[T] - potential[S]
        if real_cost >= 0:
            break  # 再增广不会更优
        for v in range(node_count):
            if dist[v] is not None:
                potential[v] += dist[v]
        # 沿最短路增广 1 单位
        v = T
        while v != S:
            u, i = prev[v]
            e = graph[u][i]
            e[1] -= 1
            graph[v][e[3]][1] += 1
            v = u

    # --- 提取配对 -------------------------------------------------------
    result: List[Tuple[SourceCourse, TargetCourse]] = []
    target_by_id = {t.course_id: t for t in ordered_targets}
    for u, edge_idx, course_id in edge_records:
        if graph[u][edge_idx][1] == 0:  # 容量被用掉 => 已匹配
            result.append((source_of_edge_node[u], target_by_id[course_id]))
    return result
