"""The airport checker decides marks, so check it both ways: correct timelines must pass, and each kind of
broken timeline must fail the constraint it breaks (and only that one, unless the break really hits two).

    python3 -m unittest discover tests
"""

import random
import unittest

import airport

C = set(airport.CONSTRAINTS)

EXAMPLE_IN = "7\n0 Student 1\n0 Student 2\n0 Student 3\n1 Student 4\n3 Immigration officer 1\n4 Student 5\n9 Immigration officer 1\n"
EXAMPLE_OUT = """0 Student 1 enters
0 Student 2 enters
0 Student 3 enters
1 Student 1 scans passport
1 Student 2 scans passport
1 Student 3 scans passport
1 Student 4 enters
3 Student 4 scans passport
3 Immigration officer 1 enters
5 Immigration officer 1 approves
6 Student 1 receives stamp
6 Student 2 receives stamp
6 Student 3 receives stamp
6 Student 4 receives stamp
6 Immigration officer 1 leaves
7 Baggage handler 1 loads bag for Student 1
7 Student 1 leaves hall
7 Baggage handler 2 loads bag for Student 2
7 Student 2 leaves hall
7 Student 3 leaves hall
7 Student 4 leaves hall
7 Student 5 enters
8 Student 1 collects bag
8 Student 2 collects bag
8 Student 5 scans passport
9 Baggage handler 1 loads bag for Student 3
9 Baggage handler 2 loads bag for Student 4
9 Immigration officer 1 enters
10 Student 3 collects bag
10 Student 4 collects bag
10 Immigration officer 1 approves
11 Student 5 receives stamp
11 Immigration officer 1 leaves
12 Baggage handler 1 loads bag for Student 5
12 Student 5 leaves hall
13 Student 5 collects bag
"""


def simulate(text):
    """A correct eager schedule for any legal input: one tick at a time, everything as early as allowed."""
    arrivals = sorted(airport.parse_input(text), key=lambda a: (a.t, a.index))
    students = {a.who: dict(arrive=a.t, entered=None, scanned=None, approved=None, stamped=None, left=None,
                            loaded=None, collected=None) for a in arrivals if a.actor == "Student"}
    visits = [a.t for a in arrivals if a.actor != "Student"]
    handlers = {1: -1, 2: -1}  # busy until
    out, officer, t = [], None, 0

    def inside():
        return officer and officer["e"] < t and (officer["l"] is None or t <= officer["l"])

    while any(s["collected"] is None for s in students.values()) or visits or officer:
        for a in arrivals:  # same-tick arrivals in input order
            if a.actor != "Student" and a.t == t:
                officer = dict(e=t, a=None, l=None, batch=None)
                visits.remove(a.t)
                out.append(f"{t} Immigration officer 1 enters")
            elif a.actor == "Student":
                s = students[a.who]
                if s["entered"] is None and a.t <= t and not inside():
                    s["entered"] = t
                    out.append(f"{t} Student {a.who} enters")
        if officer and officer["batch"] is None and t > officer["e"]:
            officer["batch"] = [i for i, s in students.items() if s["entered"] is not None and s["approved"] is None]
        scanning = sum(1 for s in students.values() if s["scanned"] is not None and s["scanned"] + 2 > t)
        for i, s in students.items():
            if s["entered"] is not None and s["entered"] < t and s["scanned"] is None and scanning < 3:
                s["scanned"] = t
                scanning += 1
                out.append(f"{t} Student {i} scans passport")
        if officer:
            if officer["a"] is None and t > officer["e"] and all(
                    students[i]["scanned"] is not None and students[i]["scanned"] + 2 <= t for i in officer["batch"]):
                officer["a"] = t
                for i in officer["batch"]:
                    students[i]["approved"] = t
                out.append(f"{t} Immigration officer 1 approves")
            elif officer["a"] is not None and officer["l"] is None and t == officer["a"] + 1:
                officer["l"] = t
                out.append(f"{t} Immigration officer 1 leaves")
        for i, s in students.items():
            if s["approved"] is not None and s["stamped"] is None and t > s["approved"]:
                s["stamped"] = t
                out.append(f"{t} Student {i} receives stamp")
        for i, s in students.items():
            if s["stamped"] is not None and s["stamped"] < t and s["left"] is None and not inside():
                s["left"] = t
                out.append(f"{t} Student {i} leaves hall")
        on_belt = sum(1 for s in students.values() if s["loaded"] is not None and (s["collected"] is None or s["collected"] + 1 > t))
        for i, s in students.items():
            if s["stamped"] is not None and s["stamped"] < t and s["loaded"] is None and on_belt < 2:
                h = next((h for h, until in handlers.items() if until <= t), None)
                if h is None:
                    break
                handlers[h] = t + 1
                s["loaded"] = t
                on_belt += 1
                out.append(f"{t} Baggage handler {h} loads bag for Student {i}")
        for i, s in students.items():
            if s["left"] is not None and s["left"] < t and s["loaded"] is not None and s["loaded"] < t and s["collected"] is None:
                s["collected"] = t
                out.append(f"{t} Student {i} collects bag")
        if officer and officer["l"] is not None and t > officer["l"]:
            officer = None
        t += 1
        assert t < 100_000, "simulation did not finish"
    return "\n".join(out) + "\n"


def failing(text, output):
    return {c for c, msgs in airport.check(text, output).violations.items() if msgs}


def edit(old, new, source=EXAMPLE_OUT):
    assert old in source, old
    return source.replace(old, new, 1)


class CorrectTimelines(unittest.TestCase):
    def test_assignment_example(self):
        r = airport.check(EXAMPLE_IN, EXAMPLE_OUT)
        self.assertEqual(r.violations, {c: [] for c in C})
        self.assertEqual(r.other, [])

    def test_simulator_reproduces_the_example(self):
        self.assertEqual(sorted(simulate(EXAMPLE_IN).splitlines()), sorted(EXAMPLE_OUT.splitlines()))

    def test_every_grading_input_has_a_correct_answer_that_passes(self):
        for case in airport.CASES:
            with self.subTest(case.name):
                r = airport.check(case.text, simulate(case.text))
                self.assertEqual({c: m for c, m in r.violations.items() if m}, {})
                self.assertEqual(r.other, [])

    def test_random_inputs(self):
        for seed in range(150):
            rnd = random.Random(seed)
            case = airport.stress("fuzz", seed, rnd.randint(1, 40), rnd.randint(1, 6))
            r = airport.check(case.text, simulate(case.text))
            self.assertEqual(({c: m for c, m in r.violations.items() if m}, r.other), ({}, []), case.text)

    def test_visits_in_grading_inputs_do_not_overlap(self):  # Q9: the input guarantees this
        for case in airport.CASES:
            with self.subTest(case.name):
                events, _ = airport.parse_output(simulate(case.text))
                officer = [e for e in sorted(events, key=lambda e: e.t) if e.actor == "Immigration officer"]
                for a, b in zip(officer, officer[1:]):
                    self.assertGreaterEqual(b.t, a.end)

    def test_officer_listed_first_may_either_admit_or_block_the_student(self):
        text = "3\n0 Immigration officer 1\n0 Student 1\n30 Immigration officer 1\n"
        admitted = ("0 Immigration officer 1 enters\n0 Student 1 enters\n1 Student 1 scans passport\n"
                    "3 Immigration officer 1 approves\n4 Student 1 receives stamp\n4 Immigration officer 1 leaves\n"
                    "5 Student 1 leaves hall\n5 Baggage handler 1 loads bag for Student 1\n6 Student 1 collects bag\n"
                    "30 Immigration officer 1 enters\n31 Immigration officer 1 approves\n32 Immigration officer 1 leaves\n")
        blocked = ("0 Immigration officer 1 enters\n1 Immigration officer 1 approves\n2 Immigration officer 1 leaves\n"
                   "3 Student 1 enters\n4 Student 1 scans passport\n30 Immigration officer 1 enters\n"
                   "31 Immigration officer 1 approves\n32 Immigration officer 1 leaves\n32 Student 1 receives stamp\n"
                   "33 Student 1 leaves hall\n33 Baggage handler 1 loads bag for Student 1\n34 Student 1 collects bag\n")
        for name, out in (("admitted", admitted), ("blocked", blocked)):
            with self.subTest(name):
                r = airport.check(text, out)
                self.assertEqual({c: m for c, m in r.violations.items() if m}, {})
                self.assertEqual(r.other, [])

    def test_same_tick_as_officer_entering_may_still_leave(self):  # Q23's boundary, for leaving
        text = "3\n0 Student 1\n5 Immigration officer 1\n8 Immigration officer 1\n"
        out = ("0 Student 1 enters\n1 Student 1 scans passport\n5 Immigration officer 1 enters\n"
               "6 Immigration officer 1 approves\n7 Immigration officer 1 leaves\n7 Student 1 receives stamp\n"
               "8 Immigration officer 1 enters\n8 Student 1 leaves hall\n8 Baggage handler 1 loads bag for Student 1\n"
               "9 Immigration officer 1 approves\n9 Student 1 collects bag\n10 Immigration officer 1 leaves\n")
        self.assertEqual(failing(text, out), set())

    def test_scanner_and_belt_are_free_the_tick_the_action_ends(self):  # Q8
        self.assertEqual(failing(EXAMPLE_IN, EXAMPLE_OUT), set())  # the example reuses both at exactly end time


class BrokenTimelines(unittest.TestCase):
    def assertFails(self, output, *expected, text=EXAMPLE_IN):
        self.assertEqual(failing(text, output), set(expected))

    def test_empty_output_fails_everything(self):
        self.assertFails("", *C)

    def test_no_student_lines_fails_everything(self):
        officer_only = "".join(ln + "\n" for ln in EXAMPLE_OUT.splitlines() if "officer" in ln)
        self.assertEqual(failing(EXAMPLE_IN, officer_only), C)

    def test_c1_student_enters_during_visit(self):
        self.assertFails(edit("7 Student 5 enters", "5 Student 5 enters"), "C1")

    def test_c1_student_enters_while_officer_is_leaving(self):
        self.assertFails(edit("7 Student 5 enters", "6 Student 5 enters"), "C1")

    def test_c1_student_leaves_while_officer_is_leaving(self):  # she is inside until her `leaves` ends
        out = edit("7 Student 3 leaves hall", "11 Student 3 leaves hall")
        self.assertFails(edit("10 Student 3 collects bag", "12 Student 3 collects bag", out), "C1")

    def test_c1_student_leaves_during_visit(self):
        # student 3's stamp and load are early enough; only the leave lands inside the second visit
        out = edit("7 Student 3 leaves hall", "10 Student 3 leaves hall")
        out = edit("10 Student 3 collects bag", "11 Student 3 collects bag", out)
        self.assertFails(out, "C1")

    def test_c2_approves_before_last_scan_ends(self):
        self.assertFails(edit("5 Immigration officer 1 approves", "4 Immigration officer 1 approves"), "C2", "C3")

    def test_c2_two_approvals_in_one_visit(self):
        self.assertFails(edit("6 Immigration officer 1 leaves", "5 Immigration officer 1 approves\n6 Immigration officer 1 leaves"), "C2")

    def test_c2_student_left_out_of_batch(self):
        text = "3\n0 Student 1\n5 Immigration officer 1\n20 Immigration officer 1\n"
        out = ("0 Student 1 enters\n1 Student 1 scans passport\n5 Immigration officer 1 enters\n"
               "6 Immigration officer 1 approves\n7 Immigration officer 1 leaves\n20 Immigration officer 1 enters\n"
               "21 Immigration officer 1 approves\n22 Immigration officer 1 leaves\n22 Student 1 receives stamp\n"
               "23 Student 1 leaves hall\n23 Baggage handler 1 loads bag for Student 1\n24 Student 1 collects bag\n")
        self.assertFails(out, "C2", text=text)

    def test_c3_stamp_before_approval_finishes(self):
        self.assertFails(edit("6 Student 1 receives stamp", "5 Student 1 receives stamp"), "C3")

    def test_c3_officer_waits_before_leaving(self):
        # also keeps her inside when students 1-4 leave and student 5 enters at t=7
        self.assertFails(edit("6 Immigration officer 1 leaves", "7 Immigration officer 1 leaves"), "C1", "C3")

    def test_c3_skipping_a_later_visit_costs_only_c3(self):  # the empty-batch rule, and nothing else
        out = "".join(ln + "\n" for ln in simulate("3\n0 Student 1\n5 Immigration officer 1\n30 Immigration officer 1\n").splitlines()
                      if not ln.startswith(("30 ", "31 ", "32 ")))
        self.assertEqual(failing("3\n0 Student 1\n5 Immigration officer 1\n30 Immigration officer 1\n", out), {"C3"})

    def test_c3_officer_alone_printing_nothing_costs_only_c3(self):
        self.assertEqual(failing("1\n5 Immigration officer 1\n", ""), {"C3"})

    def test_students_but_no_officer_lines_cannot_pass_c1_c2_c8(self):
        no_officer = "".join(ln + "\n" for ln in EXAMPLE_OUT.splitlines() if "officer" not in ln)
        self.assertLessEqual({"C1", "C2", "C3", "C8"}, failing(EXAMPLE_IN, no_officer))

    def test_c3_visit_without_leaving(self):
        out = EXAMPLE_OUT.replace("11 Immigration officer 1 leaves\n", "")
        self.assertIn("C3", failing(EXAMPLE_IN, out))

    def test_c4_leaves_during_own_stamp(self):
        self.assertFails(edit("6 Student 3 receives stamp", "7 Student 3 receives stamp"), "C4")

    def test_c5_load_during_stamp(self):
        self.assertFails(edit("7 Baggage handler 1 loads bag for Student 1", "6 Baggage handler 1 loads bag for Student 1"), "C5")

    def test_c5_third_bag_on_belt(self):
        out = edit("9 Baggage handler 1 loads bag for Student 3", "8 Baggage handler 1 loads bag for Student 3")
        self.assertFails(out, "C5")

    def test_c5_slot_reused_on_the_collect_tick(self):  # the slot only frees at collect + 1 (Q8)
        out = edit("9 Baggage handler 2 loads bag for Student 4", "8 Baggage handler 2 loads bag for Student 4")
        self.assertFails(out, "C5")

    def test_c6_collects_before_leaving_finishes(self):
        self.assertFails(edit("8 Student 1 collects bag", "7 Student 1 collects bag"), "C6")

    def test_c6_collects_before_load_finishes(self):
        self.assertFails(edit("10 Student 3 collects bag", "9 Student 3 collects bag"), "C6")

    def test_c7_loaded_twice(self):
        self.assertFails(edit("12 Baggage handler 1 loads bag for Student 5", "12 Baggage handler 1 loads bag for Student 5\n13 Baggage handler 1 loads bag for Student 5"), "C7")

    def test_c7_collected_twice(self):
        self.assertFails(edit("13 Student 5 collects bag", "13 Student 5 collects bag\n14 Student 5 collects bag"), "C7")

    def test_c7_never_loaded(self):
        out = EXAMPLE_OUT.replace("12 Baggage handler 1 loads bag for Student 5\n", "")
        self.assertEqual(failing(EXAMPLE_IN, out), {"C5", "C6", "C7", "C8"})

    def test_c7_bag_of_someone_not_in_the_input(self):
        self.assertFails(edit("13 Student 5 collects bag", "13 Student 5 collects bag\n13 Baggage handler 2 loads bag for Student 99"), "C7")

    def test_c8_scan_during_entry(self):
        self.assertFails(edit("1 Student 1 scans passport", "0 Student 1 scans passport"), "C8")

    def test_c8_fourth_scanner(self):
        self.assertFails(edit("3 Student 4 scans passport", "2 Student 4 scans passport"), "C8")

    def test_c8_scanner_needs_two_ticks(self):
        text = "5\n0 Student 1\n0 Student 2\n0 Student 3\n0 Student 4\n20 Immigration officer 1\n"
        out = simulate(text).replace("3 Student 4 scans passport", "2 Student 4 scans passport")
        self.assertEqual(failing(text, out), {"C8"})

    def test_c8_handler_does_two_loads_at_once(self):
        self.assertFails(edit("9 Baggage handler 2 loads bag for Student 4", "9 Baggage handler 1 loads bag for Student 4"), "C8")

    def test_c8_third_handler(self):
        self.assertFails(EXAMPLE_OUT.replace("Baggage handler 2", "Baggage handler 3"), "C8")

    def test_c8_approve_during_officer_entry(self):
        text = "2\n0 Immigration officer 1\n9 Immigration officer 1\n"
        out = ("0 Immigration officer 1 enters\n0 Immigration officer 1 approves\n1 Immigration officer 1 leaves\n"
               "9 Immigration officer 1 enters\n10 Immigration officer 1 approves\n11 Immigration officer 1 leaves\n")
        self.assertFails(out, "C8", text=text)

    def test_c8_visits_overlap(self):
        # back inside at t=6 before finishing the first visit, which also closes the hall at t=7
        self.assertFails(edit("9 Immigration officer 1 enters", "6 Immigration officer 1 enters"), "C1", "C8")


class NotPartOfTheEight(unittest.TestCase):
    def other(self, output, text=EXAMPLE_IN):
        return airport.check(text, output).other

    def test_wrong_case_still_counts_but_is_reported(self):
        r = airport.check(EXAMPLE_IN, EXAMPLE_OUT.replace("Immigration officer", "Immigration Officer"))
        self.assertTrue(r.ok)
        self.assertTrue(r.other)

    def test_junk_lines_are_reported(self):
        self.assertTrue(any("cannot parse" in p for p in self.other("Simulation start\n" + EXAMPLE_OUT)))

    def test_output_out_of_time_order(self):
        lines = EXAMPLE_OUT.splitlines()
        lines[3], lines[10] = lines[10], lines[3]
        self.assertTrue(any("time order" in p for p in self.other("\n".join(lines))))

    def test_same_tick_enters_must_follow_input_order(self):
        out = edit("0 Student 1 enters\n0 Student 2 enters", "0 Student 2 enters\n0 Student 1 enters")
        self.assertTrue(any("input order" in p for p in self.other(out)))

    def test_entering_before_arrival(self):
        out = EXAMPLE_OUT.replace("1 Student 4 enters", "0 Student 4 enters")
        self.assertTrue(any("arrives" in p for p in self.other(out)))

    def test_entering_late_with_the_hall_open(self):
        out = EXAMPLE_OUT.replace("7 Student 5 enters", "8 Student 5 enters").replace("8 Student 5 scans passport", "9 Student 5 scans passport")
        self.assertTrue(any("could enter" in p for p in self.other(out)))

    def test_wrong_officer_id(self):
        self.assertTrue(any("officer id" in p for p in self.other(EXAMPLE_OUT.replace("Immigration officer 1 approves", "Immigration officer 2 approves"))))


if __name__ == "__main__":
    unittest.main()
