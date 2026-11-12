"""BFS decides the Bellman-Ford marks, so check it against an independent Bellman-Ford here."""

import unittest

import birthday


def bellman_ford(case):
    dist = [float("inf")] * case.v
    dist[case.source] = 0
    for _ in range(case.v):
        changed = False
        for a, b in case.edges:
            for x, y in ((a, b), (b, a)):
                if dist[x] + 1 < dist[y]:
                    dist[y] = dist[x] + 1
                    changed = True
        if not changed:
            break
    return dist


class Cases(unittest.TestCase):
    def test_answers_match_an_independent_bellman_ford(self):
        for case in birthday.CASES:
            with self.subTest(case.name):
                self.assertEqual(case.expected(), bellman_ford(case))

    def test_graphs_are_legal(self):
        for case in birthday.CASES:
            with self.subTest(case.name):
                self.assertNotIn(-1, case.expected())  # connected (Q5)
                self.assertTrue(all(a != b for a, b in case.edges))

    def test_input_is_in_the_assignment_format(self):  # `S D` per edge, no weights
        for case in birthday.CASES:
            with self.subTest(case.name):
                lines = case.text.splitlines()
                self.assertEqual(len(lines[0].split()), 4)
                self.assertTrue(all(len(line.split()) == 2 for line in lines[1:]))

    def test_assignment_example(self):
        self.assertEqual(birthday.CASES[0].expected(), [0, 1, 1, 2, 3, 4])


class Judging(unittest.TestCase):
    case = birthday.CASES[0]

    def test_right_answer(self):
        self.assertIsNone(birthday.judge(self.case, "0 1 1 2 3 4\n"))

    def test_whitespace_is_not_judged(self):
        self.assertIsNone(birthday.judge(self.case, "0 1 1 2 3 4 \n\n"))

    def test_wrong_answers(self):
        self.assertIn("vertex 5", birthday.judge(self.case, "0 1 1 2 3 5\n"))
        self.assertEqual(birthday.judge(self.case, ""), "printed nothing")
        self.assertIn("6 vertices", birthday.judge(self.case, "0 1 1"))
        self.assertIn("integers", birthday.judge(self.case, "dist: 0 1 1 2 3 4"))


if __name__ == "__main__":
    unittest.main()
