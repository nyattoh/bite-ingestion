"""Evaluator-local chain-span replacement for dense identifier graphs.

Does not edit frozen sensor source. Semantics: max reachable index minus start,
which equals frozen simple-path max(node-start) on finite directed graphs.
"""

from __future__ import annotations

from collections.abc import Sequence


def chain_span_reachable(n: int, directed: Sequence[tuple[int, int]]) -> int:
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for src, dst in directed:
        if src != dst:
            adj[int(src)].add(int(dst))
    best = 0
    for start in range(n):
        seen = {start}
        stack = [start]
        max_idx = start
        while stack:
            node = stack.pop()
            for nxt in adj[node]:
                if nxt in seen:
                    continue
                seen.add(nxt)
                max_idx = max(max_idx, nxt)
                stack.append(nxt)
        best = max(best, max_idx - start)
    return best


def chain_span_simple_path(n: int, directed: Sequence[tuple[int, int]]) -> int:
    """Frozen _chain_span control flow. Reference copy; sensor file is unchanged."""
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for src, dst in directed:
        adj[int(src)].append(int(dst))
    best = 0
    seen_stack: set[int] = set()

    def dfs(node: int, start: int) -> None:
        nonlocal best
        best = max(best, node - start)
        for nxt in adj[node]:
            if nxt in seen_stack:
                continue
            seen_stack.add(nxt)
            dfs(nxt, start)
            seen_stack.remove(nxt)

    for i in range(n):
        seen_stack = {i}
        dfs(i, i)
    return best


def all_directed_graphs(n: int) -> list[list[tuple[int, int]]]:
    pairs = [(i, j) for i in range(n) for j in range(n)]
    graphs: list[list[tuple[int, int]]] = []
    for mask in range(1 << len(pairs)):
        graphs.append([pairs[k] for k in range(len(pairs)) if mask & (1 << k)])
    return graphs
