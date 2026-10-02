"""最小费用流与强连通分量工具。"""
from __future__ import annotations

import heapq

_INF = 1 << 62


class MinCostFlow:
    """最小费用流图（连续最短路算法，势保证约化费用非负）。

    节点以 0..n-1 整数编号。费用可为负，但图中不得有负费用环。
    """

    def __init__(self, num_nodes: int) -> None:
        self._n = num_nodes
        self._to: list[int] = []
        self._cap: list[int] = []
        self._cost: list[int] = []
        self._graph: list[list[int]] = [[] for _ in range(num_nodes)]
        self._potential = [0] * num_nodes

    def add_edge(self, u: int, v: int, cap: int, cost: int) -> int:
        """加入一条边，返回其边编号（偶数，反向边为编号+1）。"""
        eid = len(self._to)
        self._graph[u].append(eid)
        self._graph[v].append(eid + 1)
        self._to.append(v)
        self._cap.append(cap)
        self._cost.append(cost)
        self._to.append(u)
        self._cap.append(0)
        self._cost.append(-cost)
        return eid

    @property
    def num_edges(self) -> int:
        return len(self._to)

    def edge_to(self, eid: int) -> int:
        return self._to[eid]

    def edge_cap(self, eid: int) -> int:
        return self._cap[eid]

    def edge_cost(self, eid: int) -> int:
        return self._cost[eid]

    def edges_from(self, u: int) -> list[int]:
        return self._graph[u]

    def internals(self) -> tuple[list[list[int]], list[int], list[int], list[int]]:
        """返回 (邻接表, 边终点, 残量容量, 费用) 内部数组，供热路径只读访问。"""
        return self._graph, self._to, self._cap, self._cost

    def push(self, eid: int, amount: int) -> None:
        """沿边增广 amount 单位流量（调用方保证容量足够）。"""
        self._cap[eid] -= amount
        self._cap[eid ^ 1] += amount

    def potentials(self) -> list[int]:
        """返回当前势；最优流的残量边上约化费用均非负。"""
        return list(self._potential)

    def recompute_potentials(self) -> None:
        """对当前残量图重算势（SPFA，所有节点初始距离 0）。

        要求残量图无负费用环（当前流已最优时成立）。
        用于在求流结束后加入额外边（如 t->s 回边）的场景。
        """
        from collections import deque

        n = self._n
        dist = [0] * n
        in_queue = [True] * n
        queue = deque(range(n))
        while queue:
            u = queue.popleft()
            in_queue[u] = False
            du = dist[u]
            for eid in self._graph[u]:
                if self._cap[eid] <= 0:
                    continue
                v = self._to[eid]
                nd = du + self._cost[eid]
                if nd < dist[v]:
                    dist[v] = nd
                    if not in_queue[v]:
                        in_queue[v] = True
                        queue.append(v)
        self._potential = dist

    def _init_potentials(self, s: int) -> None:
        # Bellman-Ford：边数少、节点少，一次即可承受。
        n = self._n
        dist = [_INF] * n
        dist[s] = 0
        for _ in range(n - 1):
            updated = False
            for eid in range(0, len(self._to), 2):
                if self._cap[eid] <= 0:
                    continue
                u = self._to[eid + 1]
                v = self._to[eid]
                if dist[u] != _INF and dist[u] + self._cost[eid] < dist[v]:
                    dist[v] = dist[u] + self._cost[eid]
                    updated = True
            if not updated:
                break
        for i in range(n):
            if dist[i] != _INF:
                self._potential[i] = dist[i]

    def min_cost_flow_while_negative(self, s: int, t: int) -> None:
        """不断沿最便宜的 s-t 增广路增广，直到最短路费用非负。

        结束后当前流在所有同值流中费用最小，且不存在负费用
        s-t 增广路；配合 t->s 零费用边即等价于最小费用循环流。
        """
        self._init_potentials(s)
        n = self._n
        to = self._to
        cap = self._cap
        cost = self._cost
        graph = self._graph
        potential = self._potential
        while True:
            dist = [_INF] * n
            prev = [-1] * n
            dist[s] = 0
            heap = [(0, s)]
            while heap:
                d, u = heapq.heappop(heap)
                if d != dist[u]:
                    continue
                for eid in graph[u]:
                    if cap[eid] <= 0:
                        continue
                    v = to[eid]
                    nd = d + cost[eid] + potential[u] - potential[v]
                    if nd < dist[v]:
                        dist[v] = nd
                        prev[v] = eid
                        heapq.heappush(heap, (nd, v))
            if dist[t] == _INF:
                return
            for i in range(n):
                if dist[i] != _INF:
                    potential[i] += dist[i]
            if potential[t] >= 0:
                return
            # 单位容量图，每次增广 1 单位即可。
            v = t
            while v != s:
                eid = prev[v]
                cap[eid] -= 1
                cap[eid ^ 1] += 1
                v = to[eid ^ 1]


def strongly_connected_components(num_nodes: int, edges: list[tuple[int, int]]) -> list[int]:
    """Tarjan 强连通分量（迭代实现），返回每个节点的分量编号。"""
    index_of = [-1] * num_nodes
    lowlink = [0] * num_nodes
    on_stack = [False] * num_nodes
    comp = [-1] * num_nodes
    stack: list[int] = []
    index_counter = 0
    comp_count = 0

    adjacency: list[list[int]] = [[] for _ in range(num_nodes)]
    for u, v in edges:
        adjacency[u].append(v)

    for root in range(num_nodes):
        if index_of[root] != -1:
            continue
        work = [(root, 0)]
        while work:
            node, child_idx = work[-1]
            if child_idx == 0:
                index_of[node] = index_counter
                lowlink[node] = index_counter
                index_counter += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            neighbours = adjacency[node]
            while child_idx < len(neighbours):
                nxt = neighbours[child_idx]
                child_idx += 1
                if index_of[nxt] == -1:
                    work[-1] = (node, child_idx)
                    work.append((nxt, 0))
                    recursed = True
                    break
                if on_stack[nxt] and index_of[nxt] < lowlink[node]:
                    lowlink[node] = index_of[nxt]
            if recursed:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                if lowlink[node] < lowlink[parent]:
                    lowlink[parent] = lowlink[node]
            if lowlink[node] == index_of[node]:
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp[w] = comp_count
                    if w == node:
                        break
                comp_count += 1
    return comp
