"""Birthday boy: does the student's Bellman-Ford get the right distances?

The input format has no weights (`S D` per edge), so every edge counts 1 and a plain BFS gives the right
answer to compare with. Every graph is connected (doubts Q5). The report and plots are marked by hand; this
only checks the algorithm.
"""

import random
from collections import deque
from dataclasses import dataclass


@dataclass
class Case:
    name: str
    v: int
    edges: list
    source: int
    threads: int

    @property
    def runs(self):
        return 1 if self.threads == 1 else 3  # a race may only show up on some runs

    @property
    def text(self):
        head = f"{self.v} {len(self.edges)} {self.source} {self.threads}\n"
        return head + "".join(f"{a} {b}\n" for a, b in self.edges)

    def expected(self):
        adj = [[] for _ in range(self.v)]
        for a, b in self.edges:
            adj[a].append(b)
            adj[b].append(a)
        dist = [-1] * self.v
        dist[self.source] = 0
        queue = deque([self.source])
        while queue:
            u = queue.popleft()
            for w in adj[u]:
                if dist[w] < 0:
                    dist[w] = dist[u] + 1
                    queue.append(w)
        return dist


def judge(case, stdout):
    """None if the output is right, otherwise what is wrong with it. Whitespace is not judged."""
    tokens = stdout.split()
    if not tokens:
        return "printed nothing"
    try:
        got = [int(t) for t in tokens]
    except ValueError:
        return f"not all integers: {stdout[:40]!r}"
    want = case.expected()
    if len(got) != len(want):
        return f"printed {len(got)} numbers for {len(want)} vertices"
    for i, (g, w) in enumerate(zip(got, want)):
        if g != w:
            return f"distance to vertex {i} is {g}, should be {w}"
    return None


# ---------------------------------------------------------------- graphs

def _shuffled(rnd, v, edges):
    """The same graph with random labels, edge order and edge direction."""
    label = list(range(v))
    rnd.shuffle(label)
    out = [(label[a], label[b]) if rnd.random() < 0.5 else (label[b], label[a]) for a, b in edges]
    rnd.shuffle(out)
    return out


def _path(v):
    return [(i, i + 1) for i in range(v - 1)]


def _cycle(v):
    return _path(v) + [(v - 1, 0)]


def _star(v):
    return [(0, i) for i in range(1, v)]


def _grid(side):
    at = lambda r, c: r * side + c
    return [(at(r, c), at(r, c + 1)) for r in range(side) for c in range(side - 1)] + \
           [(at(r, c), at(r + 1, c)) for r in range(side - 1) for c in range(side)]


def _random_connected(rnd, v, e):
    edges = {tuple(sorted((rnd.randrange(i), i))) for i in range(1, v)}  # a random spanning tree first
    while len(edges) < e:
        a, b = rnd.sample(range(v), 2)
        edges.add(tuple(sorted((a, b))))
    return sorted(edges)


def _cases():
    rnd = random.Random(3301)
    yield Case("assignment example", 6, [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (1, 2), (4, 5)], 0, 4)
    yield Case("single vertex", 1, [], 0, 1)
    yield Case("single edge, source is vertex 1", 2, [(0, 1)], 1, 2)
    yield Case("more threads than vertices", 5, _path(5), 2, 16)
    yield Case("edges listed backwards", 40, [(i + 1, i) for i in range(39)][::-1], 0, 4)
    yield Case("shuffled path, source mid-way", 300, _shuffled(rnd, 300, _path(300)), 150, 4)
    yield Case("long path: needs all V-1 rounds", 2000, _path(2000), 0, 8)
    yield Case("cycle: two ways round", 301, _cycle(301), 17, 3)
    yield Case("star from a leaf", 500, _star(500), 123, 6)
    yield Case("grid: many equal shortest paths", 1600, _shuffled(rnd, 1600, _grid(40)), 0, 4)
    for threads in (1, 2, 8):
        yield Case(f"sparse random, {threads} thread(s)", 800, _random_connected(random.Random(7), 800, 1600), 0, threads)
    yield Case("dense random", 150, _random_connected(rnd, 150, 6000), 3, 8)


CASES = list(_cases())
