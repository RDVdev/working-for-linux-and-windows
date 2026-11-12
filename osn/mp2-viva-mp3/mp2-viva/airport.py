"""Airport troubles: check one run's printed timeline against the 8 constraints.

No I/O here. `check(input_text, output_text)` returns a Report; `CASES` are the inputs run.py feeds
each student's program. Rules that come from the doubts doc rather than the assignment text:

  - A timestamp is when an action STARTS. It ends DUR ticks later, and whatever depends on it can
    start from that tick on (Q8).
  - The officer is in the hall from the END of her `enters` to the END of her `leaves` (Q23 and the
    example run). A student may still start entering or leaving on the tick she starts entering.
  - Same-tick `enters` follow input order (Q12), input need not be sorted (Q7), and each visit
    finishes before the next one starts (Q9).

Every "A must finish before B starts" rule is charged to exactly one constraint, so one off-by-one
costs one constraint. An output that leaves out actions proves nothing, so a constraint also fails
if any line it needs to see is missing: an empty output fails all eight.
"""

import itertools
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field

DUR = {"scans passport": 2}  # every other action takes 1 tick
SCANNERS, BELT, HANDLERS = 3, 2, (1, 2)
OFFICER_ID = 1

CONSTRAINTS = {
    "C1": "hall closed while officer inside",
    "C2": "officer waits for scans, one batch",
    "C3": "stamp after approval, officer leaves",
    "C4": "stamp before leaving hall",
    "C5": "load after stamp, belt holds 2",
    "C6": "collect after leaving and loading",
    "C7": "every bag loaded and collected once",
    "C8": "action times, 3 scanners, 2 handlers",
}

# ---------------------------------------------------------------- parsing

_LINE = (r"(?P<t>\d+) (?P<actor>Student) (?P<who>\d+) (?P<action>enters|scans passport|receives stamp|leaves hall"
         r"|collects bag)",
         r"(?P<t>\d+) (?P<actor>Immigration officer) (?P<who>\d+) (?P<action>enters|approves|leaves)",
         r"(?P<t>\d+) (?P<actor>Baggage handler) (?P<who>\d+) (?P<action>loads bag) for Student (?P<student>\d+)")
STRICT = [re.compile(p) for p in _LINE]
LOOSE = [re.compile(p, re.I) for p in _LINE]


@dataclass
class Arrival:
    t: int
    actor: str
    who: int
    index: int  # position in the input, breaks ties between equal arrival times


@dataclass
class Event:
    t: int
    actor: str
    who: int
    action: str
    line: int  # 1-based line of the output
    student: int | None = None  # a handler's "loads bag for Student i"

    @property
    def end(self):
        return self.t + DUR.get(self.action, 1)

    def __str__(self):
        bag = f" for Student {self.student}" if self.student is not None else ""
        return f"{self.t} {self.actor} {self.who} {self.action}{bag}"


def parse_input(text):
    arrivals = []
    for i, line in enumerate(text.strip().splitlines()[1:]):
        m = re.fullmatch(r"(\d+)\s+(Student|Immigration officer)\s+(\d+)", line.strip())
        if not m:
            raise ValueError(f"bad input line: {line!r}")
        arrivals.append(Arrival(int(m[1]), m[2], int(m[3]), i))
    return arrivals


def parse_output(text):
    """(events in print order, format problems). Sloppy lines still count, but are reported."""
    events, problems = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        m = next(filter(None, (p.fullmatch(raw) for p in STRICT)), None)
        if m is None:
            m = next(filter(None, (p.fullmatch(" ".join(raw.split())) for p in LOOSE)), None)
            if m is None:
                problems.append(f"line {n}: cannot parse {raw[:70]!r}")
                continue
            problems.append(f"line {n}: not in the exact format: {raw[:70]!r}")
        student = m.groupdict().get("student")
        events.append(Event(int(m["t"]), m["actor"].capitalize(), int(m["who"]), m["action"].lower(), n,
                            int(student) if student else None))
    return events, problems


# ---------------------------------------------------------------- the timeline, by actor

@dataclass
class Student:
    id: int
    actions: dict = field(default_factory=lambda: defaultdict(list))  # includes "loads bag", the handler's line

    def first(self, action):
        xs = self.actions[action]
        return xs[0] if xs else None


@dataclass
class Visit:
    enter: Event
    approves: list = field(default_factory=list)
    leaves: list = field(default_factory=list)

    @property
    def approve(self):
        return self.approves[0] if self.approves else None

    @property
    def leave(self):
        return self.leaves[0] if self.leaves else None


class Timeline:
    def __init__(self, arrivals, events):
        self.students = {a.who: Student(a.who) for a in arrivals if a.actor == "Student"}
        self.expected_visits = sum(a.actor != "Student" for a in arrivals)
        self.visits, self.stray_officer, self.stray_bags = [], [], []
        self.unknown_students, self.handlers = set(), defaultdict(list)
        for e in sorted(events, key=lambda e: (e.t, e.line)):
            if e.actor == "Student":
                if e.who in self.students:
                    self.students[e.who].actions[e.action].append(e)
                else:
                    self.unknown_students.add(e.who)
            elif e.actor == "Baggage handler":
                self.handlers[e.who].append(e)
                if e.student in self.students:
                    self.students[e.student].actions[e.action].append(e)
                else:
                    self.stray_bags.append(e)
            elif e.action == "enters":
                self.visits.append(Visit(e))
            elif self.visits:
                (self.visits[-1].approves if e.action == "approves" else self.visits[-1].leaves).append(e)
            else:
                self.stray_officer.append(e)

    def batch(self, s):
        """The first visit approving after s has finished entering: everyone in the hall is in it."""
        enter = s.first("enters")
        if enter is None:
            return None
        return next((v for v in self.visits if v.approve and v.approve.t >= enter.end), None)


def peak(spans):
    """Most [start, end) spans open at once, and the first tick that happens. Ends sort before starts."""
    edges = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
    best, cur, when = 0, 0, None
    for t, delta in edges:
        cur += delta
        if cur > best:
            best, when = cur, t
    return best, when


# ---------------------------------------------------------------- the 8 constraints

def c1(tl):
    """While the officer is in the hall, no one may enter and students may not leave."""
    for v in tl.visits:
        if v.leave is None:
            continue
        for s in tl.students.values():
            for action in ("enters", "leaves hall"):
                e = s.first(action)
                if e and v.enter.t < e.t <= v.leave.t:
                    yield f"Student {s.id} {action} at t={e.t} while the officer is inside (t={v.enter.end}..{v.leave.t})"


def c2(tl):
    """The officer waits until every student in the hall has scanned, then approves them as one batch."""
    for v in tl.visits:
        if len(v.approves) > 1:
            yield f"visit at t={v.enter.t}: {len(v.approves)} approvals instead of one batch"
    approvals = [v.approve for v in tl.visits if v.approve]
    for s in tl.students.values():
        v = tl.batch(s)
        if v is None:
            continue
        scan, stamp = s.first("scans passport"), s.first("receives stamp")
        if scan and scan.end > v.approve.t:
            yield f"Student {s.id} is in the hall but their scan ends at t={scan.end}, after the approval at t={v.approve.t}"
        later = next((a for a in approvals if a.t > v.approve.t), None)
        if stamp and later and stamp.t >= later.end:
            yield (f"Student {s.id} was in the hall for the approval at t={v.approve.t} but gets a stamp only at "
                   f"t={stamp.t}, after the next approval: left out of the batch")


def c3(tl):
    """A stamp comes only after approval; the officer leaves right after approving, even an empty batch."""
    for s in tl.students.values():
        stamp = s.first("receives stamp")
        if stamp is None or s.first("enters") is None:
            continue
        v = tl.batch(s)
        if v is None:
            yield f"Student {s.id} receives a stamp at t={stamp.t} but no approval follows their entry"
        elif stamp.t < v.approve.end:
            yield f"Student {s.id} receives a stamp at t={stamp.t}, before the approval at t={v.approve.t} has finished"
    for v in tl.visits:
        if v.approve and v.leave and v.leave.t != v.approve.end:
            yield f"officer approves at t={v.approve.t} but leaves at t={v.leave.t}: must leave right after approving"
        if len(v.leaves) > 1:
            yield f"visit at t={v.enter.t}: officer leaves {len(v.leaves)} times"


def c4(tl):
    """Students cannot leave the hall until they have received a stamp."""
    for s in tl.students.values():
        stamp, leave = s.first("receives stamp"), s.first("leaves hall")
        if stamp and leave and leave.t < stamp.end:
            yield f"Student {s.id} leaves the hall at t={leave.t} before their stamp (t={stamp.t}) has finished"


def c5(tl):
    """A handler loads a bag only after its owner has the stamp; the belt holds at most 2 bags."""
    spans = []
    for s in tl.students.values():
        stamp, load, collect = s.first("receives stamp"), s.first("loads bag"), s.first("collects bag")
        if stamp and load and load.t < stamp.end:
            yield f"bag of Student {s.id} loaded at t={load.t} before their stamp (t={stamp.t}) has finished"
        if load and collect and collect.end > load.t:
            spans.append((load.t, collect.end))
    bags, when = peak(spans)
    if bags > BELT:
        yield f"{bags} bags on the belt at t={when} (it holds {BELT}; a slot frees when the collect ends)"


def c6(tl):
    """A student collects their own bag, only after leaving the hall and after the bag is on the belt."""
    for s in tl.students.values():
        leave, load, collect = s.first("leaves hall"), s.first("loads bag"), s.first("collects bag")
        if collect and leave and collect.t < leave.end:
            yield f"Student {s.id} collects at t={collect.t} before leaving the hall has finished (t={leave.t})"
        if collect and load and collect.t < load.end:
            yield f"Student {s.id} collects at t={collect.t} before their bag's load has finished (t={load.t})"


def c7(tl):
    """Every bag whose owner has a stamp is loaded and collected exactly once. No other bag is loaded."""
    for s in tl.students.values():
        loads, collects = len(s.actions["loads bag"]), len(s.actions["collects bag"])
        if s.actions["receives stamp"]:
            if loads > 1:
                yield f"bag of Student {s.id} loaded {loads} times"
            if collects > 1:
                yield f"Student {s.id} collects {collects} times"
        elif loads or collects:
            yield f"bag of Student {s.id} loaded/collected ({loads}/{collects}) but they never got a stamp"
    for e in tl.stray_bags:
        yield f"bag loaded at t={e.t} for Student {e.student}, who is not in the input"


def c8(tl):
    """Every action takes 1 tick except `scans passport` (2). One actor, one action at a time. 3 scanners, 2 handlers."""
    spans = []
    for s in tl.students.values():
        enter, scan = s.first("enters"), s.first("scans passport")
        if enter and scan and scan.t < enter.end:
            yield f"Student {s.id} scans at t={scan.t} before entering has finished (t={enter.t})"
        if scan:
            spans.append((scan.t, scan.end))
        for action in ("enters", "scans passport", "receives stamp", "leaves hall"):
            if len(s.actions[action]) > 1:
                yield f"Student {s.id} '{action}' {len(s.actions[action])} times"
    busy, when = peak(spans)
    if busy > SCANNERS:
        yield f"{busy} scans in progress at t={when} ({SCANNERS} scanners, each scan holds one for {DUR['scans passport']} ticks)"
    for v in tl.visits:
        if v.approve and v.approve.t < v.enter.end:
            yield f"officer approves at t={v.approve.t} before entering has finished (t={v.enter.t})"
    for a, b in zip(tl.visits, tl.visits[1:]):
        if a.leave and b.enter.t < a.leave.end:
            yield f"officer enters at t={b.enter.t} before the previous visit is over (leaves at t={a.leave.t})"
    for e in tl.stray_officer:
        yield f"officer '{e.action}' at t={e.t} before any 'enters'"
    if len(tl.visits) > tl.expected_visits:
        yield f"{len(tl.visits)} officer visits printed, the input has {tl.expected_visits}"
    for who, loads in tl.handlers.items():
        if who not in HANDLERS:
            yield f"handler {who} loads at t={loads[0].t}: the only handlers are {HANDLERS}"
        for a, b in zip(loads, loads[1:]):
            if b.t < a.end:
                yield f"handler {who} starts a load at t={b.t} while its load at t={a.t} is still running"


CHECKS = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7, "C8": c8}

# the lines each constraint has to see, or it proves nothing
NEEDS = {"C1": ("enters", "leaves hall"), "C2": ("enters", "scans passport"), "C3": ("enters", "receives stamp"),
         "C4": ("receives stamp", "leaves hall"), "C5": ("receives stamp", "loads bag"),
         "C6": ("leaves hall", "loads bag", "collects bag"), "C7": ("receives stamp", "loads bag", "collects bag"),
         "C8": ("enters", "scans passport", "receives stamp", "leaves hall", "loads bag", "collects bag")}
VISIT_NEEDS = {"C1": ("leaves",), "C2": ("approves",), "C3": ("approves", "leaves"), "C8": ("approves", "leaves")}


def incomplete(tl, c):
    for s in tl.students.values():
        for action in NEEDS[c]:
            if not s.actions[action]:
                yield f"Student {s.id}: no '{action}' line"
    if c in VISIT_NEEDS:
        # A visit she skipped breaks "she still approves an empty batch"; the other rules just have
        # less to look at. Only with students but no visits at all can they not be judged.
        if len(tl.visits) < tl.expected_visits and (c == "C3" or (not tl.visits and tl.students)):
            yield f"only {len(tl.visits)} of {tl.expected_visits} officer visits printed"
        for v in tl.visits:
            for action, xs in (("approves", v.approves), ("leaves", v.leaves)):
                if action in VISIT_NEEDS[c] and not xs:
                    yield f"visit at t={v.enter.t}: no '{action}' line"


# ---------------------------------------------------------------- outside the 8

def follows_input(tl, arrivals, events):
    """Worth a look but carries no marks: does the timeline actually simulate this input?"""
    last = None
    for e in events:
        if last is not None and e.t < last:
            yield f"output not in time order: line {e.line} ({e}) comes after t={last}"
            break
        last = e.t
    if ids := {e.who for e in events if e.actor == "Immigration officer"} - {OFFICER_ID}:
        yield f"officer id(s) {sorted(ids)}: there is only officer {OFFICER_ID}"
    if tl.unknown_students:
        yield f"student(s) not in the input: {sorted(tl.unknown_students)[:8]}"

    ordered = sorted(arrivals, key=lambda a: (a.t, a.index))
    officers = [a for a in ordered if a.actor != "Student"]
    closed = [(v.enter.t, v.leave.t) for v in tl.visits if v.leave]
    entered = {}  # arrival index -> its `enters` event
    for a, v in zip(officers, tl.visits):
        entered[a.index] = v.enter
        if v.enter.t != a.t:
            yield f"officer arrives at t={a.t} but enters at t={v.enter.t}"

    def next_open(t):
        for e, l in closed:
            if e < t <= l:
                t = l + 1
        return t

    for a in ordered:
        s = tl.students.get(a.who) if a.actor == "Student" else None
        e = s.first("enters") if s else None
        if e is None:
            continue
        entered[a.index] = e
        allowed = {next_open(a.t)}
        if any(o.t == a.t and o.index < a.index for o in officers):  # officer listed first: either reading is fine
            allowed.add(next_open(a.t + 1))
        if e.t < a.t:
            yield f"Student {a.who} arrives at t={a.t} but enters at t={e.t}"
        elif e.t not in allowed:
            yield f"Student {a.who} arrives at t={a.t}, could enter at t={min(allowed)} but enters at t={e.t}"

    by_time = defaultdict(list)
    for a in ordered:
        if a.index in entered:
            by_time[a.t].append(entered[a.index])
    for group in by_time.values():
        for x, y in itertools.combinations(group, 2):
            if x.t == y.t and x.line > y.line:
                yield f"same-tick arrivals must enter in input order: '{y}' is printed before '{x}'"


@dataclass
class Report:
    violations: dict  # "C1".."C8" -> messages; empty means satisfied
    other: list  # format and input-following problems, no marks attached

    @property
    def ok(self):
        return not any(self.violations.values())


def check(input_text, output_text):
    arrivals = parse_input(input_text)
    events, problems = parse_output(output_text)
    tl = Timeline(arrivals, events)
    violations = {c: [*incomplete(tl, c), *fn(tl)] for c, fn in CHECKS.items()}
    return Report(violations, [*problems, *follows_input(tl, arrivals, events)])


# ---------------------------------------------------------------- inputs

def S(t, i):
    return f"{t} Student {i}"


def O(t):
    return f"{t} Immigration officer 1"


@dataclass
class Case:
    name: str
    lines: list
    runs: int = 5  # the program is non-deterministic: every run has to hold up
    edge: bool = False  # promised by the doubts doc, but judged apart from the 8 constraints

    @property
    def text(self):
        return f"{len(self.lines)}\n" + "\n".join(self.lines) + "\n"


def stress(name, seed, students, visits):
    rnd = random.Random(seed)
    gap = 2 * (students // 3 + 1) + 10  # longer than any visit can last, so visits never overlap (Q9)
    ids = rnd.sample(range(1, 10 * students), students)
    rows = [(rnd.randrange(gap * visits), rnd.random(), i) for i in ids] + \
           [(gap * v, rnd.random(), None) for v in range(1, visits + 1)]
    return Case(name, [O(t) if i is None else S(t, i) for t, _, i in sorted(rows, key=lambda r: r[:2])], runs=3)


EXAMPLE = [S(0, 1), S(0, 2), S(0, 3), S(1, 4), O(3), S(4, 5), O(9)]

CASES = [
    Case("assignment example", EXAMPLE),
    Case("one student", [S(0, 1), O(10)]),
    Case("student and officer together, student listed first (Q23)", [S(0, 1), O(0), O(30)]),
    Case("student and officer together, officer listed first (Q12)", [O(0), S(0, 1), O(30)]),
    Case("officer alone: empty batch", [O(5)]),
    Case("empty batch before anyone arrives", [O(0), S(10, 1), O(30)]),
    Case("10 students queueing for 3 scanners", [S(0, i) for i in range(1, 11)] + [O(1)]),
    Case("12 bags released at once on a belt of 2", [S(0, i) for i in range(1, 13)] + [O(20)]),
    Case("arrivals all through a visit", [S(0, 1), S(0, 2), O(3), S(3, 3), S(4, 4), S(5, 5), S(6, 6), S(7, 7), O(40)]),
    Case("hall reopens between visits", [S(0, 1), S(0, 2), O(5), S(6, 3), O(12), S(13, 4), O(20)]),
    Case("many short visits", [x for v in range(1, 7) for x in (S(12 * v - 6, 10 + v), O(12 * v))]),
    Case("same-tick arrivals in input order", [S(2, 9), S(2, 3), S(2, 7), O(2), S(2, 5), S(2, 1), O(30)]),
    stress("random: 20 students, 3 visits", 1, 20, 3),
    stress("random: 30 students, 5 visits", 2, 30, 5),
    stress("random: 60 students, 4 visits", 3, 60, 4),
    Case("input not sorted by time (Q7)", [S(4, 5), O(9), S(1, 4), S(0, 1), O(3), S(0, 3), S(0, 2)], edge=True),
    Case("large ids (Q7)", [S(0, 2147483647), S(0, 1000000007), S(1, 500000000), O(3), S(4, 7), O(20)], edge=True),
]
