#!/usr/bin/env python3
"""Builds mp3-viva.html, the MP3 viva sheet, from the content below.

Edit the content, then `python3 sheet/build.py` and commit both files.
TAs open it with `./viva.py sheet` or `?` in the TUI."""

import html
import re
from pathlib import Path

# ---------------------------------------------------------------- tiny markup
# `code`, **bold**, ```c blocks```, blank line = paragraph break


def md(s):
    s = s.strip("\n")
    out, parts = [], re.split(r"```(\w*)\n(.*?)```", s, flags=re.S)
    for i in range(0, len(parts), 3):
        text = html.escape(parts[i].strip("\n"))
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        for para in filter(None, (p.strip() for p in text.split("\n\n"))):
            out.append("<p>" + para.replace("\n", "<br>") + "</p>")
        if i + 2 < len(parts):
            out.append(f'<pre><code>{html.escape(parts[i + 2].rstrip())}</code></pre>')
    return "".join(out)


def inline(s):
    return md(s).removeprefix("<p>").removesuffix("</p>")


# ---------------------------------------------------------------- content
# q: (question, answer, tag)  tag in {"", "easy", "medium", "hard"}

SECTIONS = [
    {
        "id": "airport", "group": "Concurrency", "title": "Airport troubles", "code": 80,
        "run_note": "Press `x` and read the Tests tab: C1 to C8 are worth 10 each, and Enter on a row shows the "
                    "violating runs with input and output. Press `c` for a shell with their built program (it prints "
                    "the path; `./airport` below stands for it). `./viva.py airport in out` checks any output.",
        "run": [
            ("printf '2\\n0 Student 1\\n0 Immigration officer 1\\n' | ./airport",
             "Both enter at 0 (Q23). She waits for the scan: approves at 3, leaves at 4"),
            ("printf '1\\n5 Immigration officer 1\\n' | ./airport", "Empty batch: enters at 5, approves at 6, leaves at 7"),
            ("./airport < in > out; ./viva.py airport in out", "Your own input. Lists each constraint and what broke it"),
        ],
        "checks": [
            "C1: while she is in the hall nobody enters and no student leaves",
            "C2: she waits for every student in the hall to scan, then approves them as one batch",
            "C3: stamps only after approval; she leaves right after approving, even for an empty batch",
            "C4: no leaving the hall before the stamp",
            "C5: a bag is loaded only after its owner's stamp; the belt holds 2",
            "C6: a student collects after leaving the hall, once their bag is on the belt",
            "C7: every stamped student's bag is loaded and collected exactly once, and no other bag is loaded",
            "C8: every action takes 1 tick, except scanning which takes 2. Also checks 3 scanners and 2 handlers",
            "Every person is a thread. Each constraint is 10 marks",
        ],
        "look": [
            "A row failing in 1 of 69 runs is a race, not a logic error: ask them to find it",
            "`airport extras` has no marks attached: output format, same-tick order, not-sorted input, huge ids, clean exit",
            "Flags on the Overview tab: `usleep`-style delays (may be penalised), `pthread_barrier`, atomics. Barriers and "
            "atomics are not allowed (Q11, Q17, Q22); semaphores are (Q10)",
            "The doubts doc is linked on the assignment page: Q8, Q9, Q12 and Q23 settle the timing questions",
        ],
        "q": [
            ("Walk me through one student thread from arrival to exit. Where can it block?",
             "Entering (officer inside), waiting for a scanner, waiting for approval, leaving the hall (officer inside), "
             "and waiting for its bag. Use it to choose what to dig into.", "easy"),
            ("How does your logical clock work? How do you know nothing else can happen at this tick before moving on?",
             "Either tick by tick or jumping to the next event (Q6, Q14). The hard part is the same: every thread must "
             "have finished or blocked for the current tick before the clock moves, usually tracked with a count of "
             "runnable threads under a lock.", ""),
            ("How does the officer know everyone in the hall has scanned, including those waiting for a scanner?",
             "A count of students inside who have not finished scanning, updated under a lock. She waits on a condition "
             "variable until it reaches zero. Students who are queued for a scanner are in the count too.", ""),
            ("A student and the officer arrive on the same tick. What happens, and why?",
             "Both can start entering (Q23). She only closes the hall once her `enters` has finished, one tick later, so "
             "that student is in the hall and she has to wait for their scan. The lines are printed in input order (Q12).",
             "medium"),
            ("Why `while` around `pthread_cond_wait` and not `if`?",
             "Wakeups can be spurious, and another woken thread may have changed the state first. The condition has to be "
             "checked again after waking.", "easy"),
            ("When she leaves, several students are waiting to enter or leave. `signal` or `broadcast`?",
             "`broadcast`: all of them can go now. `signal` wakes one, and the rest would sleep until something else "
             "happens to wake them.", ""),
            ("How do you enforce 3 scanners and 2 belt slots? Why does a semaphore fit?",
             "A counting semaphore starts at the number of free units: `sem_wait` takes one and blocks at zero, `sem_post` "
             "returns one. A counter and a condition variable under a mutex also work. When is the unit released? When the "
             "action ends: the scanner at start + 2, the belt slot at collect + 1 (Q8).", ""),
            ("Can students, handlers and the belt deadlock?",
             "No cycle exists. A bag on the belt belongs to a stamped student who can always collect it eventually. A "
             "student held in the hall by a visit is only waiting for her to leave, and her leaving depends on nothing on "
             "the belt side.", "hard"),
            ("How do your threads finish? How does a handler know there are no more bags?",
             "They need an explicit end condition, such as a count of expected bags, and a wakeup for handlers still "
             "waiting when the last bag is done. Otherwise the program prints everything and then hangs.", "medium"),
            ("What is the difference between a mutex and a binary semaphore?",
             "A mutex has an owner: the thread that locked it must unlock it. A semaphore is a counter that any thread may "
             "post, which is why it suits signalling between threads.", "easy"),
            ("Why is simulating time with `usleep` a poor idea here?",
             "The times are symbolic. Sleeping hides ordering bugs behind timing instead of fixing them, and it makes the "
             "program slow. The assignment warns it may be penalised.", "easy"),
            ("The input is not sorted by time (Q7). What do you do, and how do you keep same-tick lines in order?",
             "A stable sort on time keeps input order among equal times, which is what Q12 needs.", ""),
        ],
    },
    {
        "id": "symlink", "group": "xv6 symlinks", "title": "symlink and open", "code": 40,
        "run_note": "`symlinktest` and `usertests -q` in the Tests tab cover both syscalls (20 + 20): the 40 marks need both "
                    "to pass. They run with the template's copies, so editing those shows up as a flag. Press `v` to boot "
                    "their xv6 and try things yourself.",
        "run": [
            ("symlinktest", "`test symlinks: ok`, `test O_CREATE on existing symlink: ok`, `test concurrent symlinks: ok`"),
            ("usertests -q", "`ALL TESTS PASSED`: symlinks must not have broken anything else"),
        ],
        "checks": [
            "`int symlink(char *target, char *path)`: returns 0, or -1 on failure. The target need not exist",
            "`open` follows links, through chains, up to a depth of 10",
            "`O_NOFOLLOW` opens the link itself",
        ],
        "look": [
            "`T_SYMLINK` in `kernel/stat.h`; the target stored in the inode's data blocks",
            "`begin_op`/`end_op` around `symlink`, and every error path in `open` releasing what it holds",
            "If the kernel panics the note shows the panic line",
        ],
        "q": [
            ("Where do you store the target path? How long can it be?",
             "In the link's data blocks, with `writei`, and read back with `readi`. Its length is limited by `MAXPATH`, "
             "because `argstr` copies it into a buffer of that size.", "easy"),
            ("Walk me through `open` on a symlink.",
             "`namei` and `ilock` get the inode. While it is a `T_SYMLINK` and `O_NOFOLLOW` is not set: `readi` the target, "
             "`iunlockput` the link, `namei` the target, `ilock` it, and count the depth. Then carry on as for a normal "
             "file.", ""),
            ("Why release the link's lock before looking up its target?",
             "`namei` takes inode locks along the path. In a cycle (a to b to a), still holding a's lock would mean "
             "sleeping forever on a lock you own. Holding one inode while locking another can also deadlock against "
             "another process.", "hard"),
            ("Why the depth limit? What happens when it is exceeded?",
             "Links can form cycles, and `a -> b -> a` would loop forever. `open` gives up and returns -1.", "easy"),
            ("`echo hi >> link` opens with `O_CREATE`. What would the unmodified `create()` do with an existing symlink?",
             "Return 0, so the `open` fails: it only accepts an existing inode when it is `T_FILE` or `T_DEVICE`. It has "
             "to let links through and `open` then follows them, and `symlinktest` checks the link stays a link.", "medium"),
            ("Why `begin_op`/`end_op` around `symlink`?",
             "It writes the new inode, a directory entry and a data block. They have to commit as one log transaction, so a "
             "crash cannot leave half a link.", ""),
            ("`rm` on a symlink: what gets removed?",
             "The link. `unlink` works on the directory entry and never follows, because `open` is the only syscall that "
             "does.", "easy"),
            ("Hard link vs symlink: what happens to each after `rm` of the original?",
             "A hard link is another directory entry for the same inode, so `nlink` stays above zero and the data remains. "
             "A symlink only holds a path, so it dangles.", "easy"),
            ("Why can a symlink point at nothing, when a hard link can't?",
             "`symlink` only stores a string. `link` needs an existing inode to bump `nlink` on.", "easy"),
            ("A relative target: relative to what, in your code?",
             "If they just call `namei(target)`, the process's current directory. Linux resolves it against the directory "
             "holding the link. Worth seeing whether they know the difference.", "medium"),
        ],
    },
    {
        "id": "userprogs", "group": "xv6 symlinks", "title": "ln and readlink", "code": 20,
        "run_note": "The Tests tab runs a short series of shell commands in a fresh boot: `ln -s` and `readlink` are worth 10 "
                    "each, and Enter shows each command with the console. Press `v` to try it by hand.",
        "run": [
            ("echo hello > f1; ln -s f1 f2; cat f2", "`hello` through the link"),
            ("echo world >> f2; cat f1", "`hello`, `world`: the write went through the link"),
            ("readlink f2", "`f1`"),
            ("readlink f1", "An error message: it is not a symlink"),
            ("ln f1 f3; rm f1; cat f2; cat f3", "`cat f2` fails (dangling); `cat f3` still prints the file"),
            ("readlink f2", "Still `f1`: a dangling link has a target"),
        ],
        "checks": [
            "`ln -s target path` makes a symlink; plain `ln` still makes a hard link. `-s` only ever comes as the second argument",
            "`readlink` prints the path the link points to, one level only",
            "On something that is not a symlink, `readlink` prints an error and exits non-zero",
        ],
        "look": [
            "The non-zero exit cannot be seen from the xv6 shell, which ignores exit codes: read `user/readlink.c`",
            "`_readlink` has to be in `UPROGS`. If not, the row shows `exec readlink failed`",
        ],
        "q": [
            ("How does `readlink` get the path out?",
             "`open` with `O_RDONLY | O_NOFOLLOW`, `fstat` to check it is `T_SYMLINK`, then a plain `read`. The link's data "
             "is the path.", "easy"),
            ("Why did `readlink` not need its own syscall?",
             "With `O_NOFOLLOW`, `open` returns the link's own inode, and reading it gives the target.", ""),
            ("`readlink` on a dangling link: what happens, and why?",
             "It prints the target. `O_NOFOLLOW` never looks at the target, so it does not matter that it is missing.", ""),
            ("How does `ln` tell which kind of link to make?",
             "`argc == 4` and `argv[1]` is `-s` call `symlink(argv[2], argv[3])`. Otherwise `link(argv[1], argv[2])` as before.",
             "easy"),
        ],
    },
    {
        "id": "bellman", "group": "Birthday boy", "title": "Bellman-Ford", "code": 10,
        "run_note": "The Tests tab compares their output with BFS on 14 connected graphs, including a 2000-vertex path and "
                    "more threads than vertices. Graphs with several threads run 3 times. Press `c` to try it by hand.",
        "run": [
            ("printf '6 7 0 4\\n0 1\\n0 2\\n1 3\\n2 3\\n3 4\\n1 2\\n4 5\\n' | ./bellman", "`0 1 1 2 3 4`"),
        ],
        "checks": [
            "`V E N T` then `E` lines of `S D`: zero-indexed, bidirectional, every edge counts 1",
            "Prints `V` space-separated distances, newline-terminated (Q18)",
            "Uses threads; only locks, condition variables and semaphores (Q22). A hand-written barrier is fine, `pthread_barrier_t` is not (Q17)",
            "Only C (Q4)",
        ],
        "look": [
            "The banned-API flags on the Overview tab. Several students used atomics or `pthread_barrier_t`",
        ],
        "q": [
            ("What is shared between your threads, and how is it protected?",
             "The distance array and whatever tracks whether a round changed anything. A lock per vertex, or one lock, "
             "around each read-compare-write.", "easy"),
            ("Two threads relax the same vertex at once. What goes wrong without a lock?",
             "Check-then-set is not atomic, so a smaller distance can be overwritten by a larger one. It is also a data race, "
             "which is undefined behaviour in C.", "medium"),
            ("Why at most V-1 rounds? When can you stop early?",
             "A shortest path has at most V-1 edges, and each round extends correct distances by at least one edge. Stop "
             "after a whole round with no change.", "easy"),
            ("Does it matter if a thread sees another thread's update within the same round?",
             "No. Distances only ever decrease and are always the length of some real path, so seeing a fresher value can "
             "only reach the answer sooner.", "hard"),
            ("How do you synchronise the end of a round?",
             "A barrier built from a mutex and condition variable, or joining and respawning the threads each round. "
             "Whichever they did, the next round must not start until all threads have finished this one.", ""),
            ("The graph is unweighted. What is the better algorithm, and why?",
             "BFS, O(V+E), against O(VE) for Bellman-Ford. It visits each edge a constant number of times instead of once "
             "per round.", "easy"),
        ],
    },
    {
        "id": "report", "group": "Birthday boy", "title": "Performance report", "code": 20,
        "run_note": "Marked by hand from the root `README.md`. Press `o` to see it rendered on Forgejo.",
        "run": [
            ("(read the README on Forgejo)", "Two plots and the observations"),
        ],
        "checks": [
            "Runtime against V at a fixed core count, averaged over several graphs with the same V and E",
            "The expected complexity on the same plot (such as kVE) with the fitted k stated",
            "Runtime against T with V and E fixed, averaged over different edge sets",
            "Observations explaining the runtime-against-T plot",
            "Every plot watermarked with their IIIT username (placement may vary, Q20)",
        ],
        "look": [
            "AI may write the plotting scripts (Q3). The results and the explanation must be their own",
        ],
        "q": [
            ("What does k in your fit represent? What are its units?",
             "Roughly the time for one edge relaxation in seconds, including locking overhead, if the curve is kVE.", ""),
            ("Why average over several edge sets?",
             "The number of rounds depends on the graph's shape and the order of its edges, so a single graph can be far "
             "from typical.", "easy"),
            ("With early stopping, does your program really take time proportional to VE?",
             "Usually not. Rounds track the graph's diameter, which is small for random graphs, so measurements often fall "
             "well below kVE. A long path comes close to it.", "medium"),
            ("Why does adding threads stop helping?",
             "The sequential part (Amdahl), contention on locks, cache lines bouncing between cores, and more threads than "
             "cores causing context switches.", ""),
            ("Could 2 threads be slower than 1? Why?",
             "Yes. For a small graph the locking and coherence traffic can cost more than the parallel work saves.", "medium"),
        ],
    },
]

FLOW = [
    "Run `./viva.py test` beforehand (or `x` on the student) and read the Tests tab. Enter on a row shows its log.",
    "Check their push history and AI chat links (Commits and AI usage tabs), and the flags on the Overview tab.",
    "Try their programs yourself: `c` for the concurrency parts, `v` to boot their xv6.",
    "Ask for a high-level overview of the whole implementation: they should convince you they did it themselves. "
    "The Code tab shows what they changed, so you can pick what to quiz on.",
]

# ---------------------------------------------------------------- render

TAG = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


def questions(qs, start=1):
    items = []
    for i, (q, a, tag) in enumerate(qs, start):
        badge = f'<span class="tag {tag}">{TAG[tag]}</span>' if tag else ""
        items.append(f'<li><details><summary><span class="qn">{i}</span><span class="qt">{inline(q)}</span>'
                     f'{badge}</summary><div class="ans">{md(a)}</div></details></li>')
    return f'<ol class="qs">{"".join(items)}</ol>'


def section(s):
    out = [f'<section id="{s["id"]}">',
           f'<header class="sh"><p class="eyebrow">{s["group"]}</p><h2>{s["title"]}</h2>'
           f'<p class="marks"><span>Marks <b>{s["code"]}</b></span></p></header>',
           '<div class="grid">',
           f'<div class="card run"><h3>Run</h3><p class="note">{inline(s["run_note"])}</p><div class="tw"><table>'
           + "".join(f'<tr><td><code>{html.escape(c)}</code></td><td>{inline(e)}</td></tr>' for c, e in s["run"])
           + "</table></div></div>",
           '<div class="card"><h3>Code marks</h3><ul class="checks">'
           + "".join(f"<li>{inline(c)}</li>" for c in s["checks"]) + "</ul>"
           + ('<h3 class="sub">Look for</h3><ul class="look">'
              + "".join(f"<li>{inline(c)}</li>" for c in s["look"]) + "</ul>" if s["look"] else "")
           + "</div></div>",
           f'<h3 class="qh">Questions</h3>{questions(s["q"])}',
           "</section>"]
    return "".join(out)


def page():
    nav, last = [], None
    for s in SECTIONS:
        if s["group"] != last:
            nav.append(f'<p class="ng">{s["group"]}</p>')
            last = s["group"]
        nav.append(f'<a href="#{s["id"]}">{s["title"]}<span>{s["code"]}</span></a>')
    rows = "".join(f'<tr><td><a href="#{s["id"]}">{s["title"]}</a></td><td>{s["code"]}</td></tr>' for s in SECTIONS)
    total = sum(s["code"] for s in SECTIONS)
    css = Path(__file__).with_name("style.css").read_text()
    return f"""<title>MP3 Viva Sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{css}</style>
<div class="wrap">
<nav aria-label="Sections"><p class="brand">MP3 viva</p><a href="#start">Running a viva</a>{"".join(nav)}</nav>
<main>
<header class="top" id="start">
<h1>MP3 viva sheet</h1>
<p class="lede">What to run, what earns the marks, and what to ask, for each part of MP3.
Answers stay hidden until you open a question.</p>
<div class="bar"><button type="button" id="toggle" aria-pressed="false">Show all answers</button></div>
</header>
<div class="intro">
<div class="card"><h3>Running a viva</h3><ol class="flow">{"".join(f"<li>{inline(f)}</li>" for f in FLOW)}</ol></div>
<div class="card"><h3>Marks</h3><div class="tw"><table class="marks-t"><thead><tr><th>Part</th><th>Marks</th></tr></thead>
<tbody>{rows}</tbody><tfoot><tr><td>Total</td><td>{total}</td></tr></tfoot></table></div>
<p class="note">viva's autograder covers everything except the performance report, 150 of the 170 marks. It reports
what the programs did; the viva and any penalties are yours to apply.</p></div>
</div>
{"".join(section(s) for s in SECTIONS)}
</main>
</div>
<script>
const btn = document.getElementById('toggle');
btn.addEventListener('click', () => {{
  const open = btn.getAttribute('aria-pressed') !== 'true';
  document.querySelectorAll('.qs details').forEach(d => d.open = open);
  btn.setAttribute('aria-pressed', open);
  btn.textContent = open ? 'Hide all answers' : 'Show all answers';
}});
</script>
"""


if __name__ == "__main__":
    out = Path(__file__).with_name("mp3-viva.html")
    out.write_text(page())
    print(out, len(out.read_text()), "bytes")
