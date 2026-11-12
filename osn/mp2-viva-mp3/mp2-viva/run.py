"""Everything that executes student code: builds and the three autograders.

All of it runs inside the viva-env docker image, so TAs need docker and no toolchain. Containers get no network,
memory and process caps, and no capabilities. Only the programs run there: judging what they printed (airport.py,
birthday.py) happens on the host.
"""

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import airport
import birthday
from core import ROOT, Fatal, edited, git, sdir

AIRPORT_ROWS = {c: f"{c} {label}" for c, label in airport.CONSTRAINTS.items()}
AIRPORT_OTHER = "airport extras"
MARKS = {"bellman-ford": 10, **dict.fromkeys(AIRPORT_ROWS.values(), 10), "symlinktest": 40, "ln -s": 10, "readlink": 10}
NEEDS_ALSO = {"symlinktest": ("usertests -q",)}  # rows that must pass too before this row's marks count

AIRPORT_LIMIT = 20  # seconds per run; there is no real-time waiting in a correct solution
AIRPORT_AFTER_HANG = 3  # one run hung, so stop giving the others the full limit
BIRTHDAY_LIMIT = 30
BUILD_LIMIT = 180
XV6_BUILD_LIMIT = 600
BOOT_LIMIT = 60
SHELL_LIMIT = 30

IMAGE = "viva-env"
MEMORY = "1g"  # enforced by the kernel on real usage, so a leak can't take the host down with it
PIDS = 512  # threads count too; the largest airport input needs about 70
# One command in a container: no core files, 64 MB of output, stopped at the time limit in $1.
STEP = 'ulimit -c 0; ulimit -f 131072; t=$1; shift; exec timeout -k 1 "$t" "$@" </w/.viva/in >/w/.viva/out 2>/w/.viva/err'
TIMED_OUT = 124  # what timeout(1) exits with
OUTPUT_CAP = 32_000_000

_image_lock = threading.Lock()


def ensure_image(log=print):
    if not shutil.which("docker"):
        raise Fatal("docker is not installed")
    with _image_lock:
        r = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, text=True)
        if r.returncode == 0:
            return
        if "No such" not in r.stderr:
            raise Fatal(f"docker is not usable: {r.stderr.strip()[-300:]}")
        log("building docker image viva-env (once, a few minutes)...")
        subprocess.run(["docker", "build", "-q", "-t", IMAGE, str(ROOT / "docker")], check=True)


def as_host_user():
    """Run containers as the TA so files they write into work/ stay the TA's.
    Linux/macOS only: Windows has no uids, and Docker Desktop maps ownership itself."""
    return ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []


def container_name():
    return f"viva-{os.getpid()}-{time.monotonic_ns()}"


def container_options(mount, name):
    """What every container gets: the student's files at /w, no network, capped resources, your uid."""
    return ["--init", "--name", name, "--network", "none", "--memory", MEMORY, "--memory-swap", MEMORY,
            "--pids-limit", str(PIDS), "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            *as_host_user(), "-e", "HOME=/tmp", "-v", f"{mount}:/w"]


# ---------------------------------------------------------------- running things

@dataclass
class Exec:
    rc: int | None  # None: stopped at the time limit; negative: killed by that signal
    out: str
    err: str


class Box:
    """A container with one student's files at /w; commands run in it with `docker exec`, far faster than a
    `docker run` each. It ends itself after an hour, in case viva dies without cleaning up."""

    def __init__(self, mount):
        self.mount, self.name = Path(mount), container_name()
        self.io = self.mount / ".viva"
        self.io.mkdir(exist_ok=True)
        r = subprocess.run(["docker", "run", "-d", "--rm", *container_options(self.mount, self.name), IMAGE, "sleep", "3600"],
                           capture_output=True, text=True)
        if r.returncode:
            raise Fatal(f"could not start a container: {r.stderr.strip()[-300:]}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        subprocess.run(["docker", "kill", self.name], capture_output=True)

    def path(self, host_path):
        return "/w/" + Path(host_path).relative_to(self.mount).as_posix()

    def run(self, argv, cwd, limit, stdin=""):
        (self.io / "in").write_text(stdin)
        for name in ("out", "err"):
            (self.io / name).unlink(missing_ok=True)
        command = ["docker", "exec", "-w", self.path(cwd), self.name, "sh", "-c", STEP, "sh", str(limit), *argv]
        try:
            rc = subprocess.run(command, capture_output=True, timeout=limit + 30).returncode
        except subprocess.TimeoutExpired:
            rc = TIMED_OUT
        code = None if rc == TIMED_OUT else 128 - rc if rc > 128 else rc  # timeout(1) reports a signal as 128 + n
        return Exec(code, self._read("out"), self._read("err"))

    def _read(self, name):
        path = self.io / name
        if not path.exists():
            return ""
        with path.open("rb") as f:
            return f.read(OUTPUT_CAP).decode(errors="replace")


def run_program(box, binary, stdin, limit):
    return box.run(["stdbuf", "-oL", box.path(binary)], binary.parent, limit, stdin=stdin)


def how_it_ended(r, limit):
    """What went wrong with the process itself, if anything."""
    if r.rc is None:
        return f"killed after {limit}s (hang or too slow)"
    if r.rc == -signal.SIGKILL:
        return f"killed: SIGKILL (over its {MEMORY} memory limit, or ignored the time limit)"
    if r.rc < 0:
        try:
            return f"crashed: {signal.Signals(-r.rc).name}"
        except ValueError:
            return f"crashed: signal {-r.rc}"
    return f"exit status {r.rc}" if r.rc else None


def export(cfg, roll, dest, protect=()):
    """Fresh copy of the student's clone at dest, as it is on disk: edits you made in work/<roll>/repo are tested
    too. Files git ignores are left out. Protected files come from the template."""
    repo = sdir(cfg, roll) / "repo"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    inside = dest.resolve()
    for rel in filter(None, git("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=repo).split("\0")):
        src, dst = repo / rel, dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            target = os.readlink(src)
            if not os.path.isabs(target) and (dst.parent / target).resolve().is_relative_to(inside):
                os.symlink(target, dst)  # links out of the copy are dropped: viva writes into it
        elif src.is_file():
            shutil.copy2(src, dst)
    for path in protect:
        (dest / path).parent.mkdir(parents=True, exist_ok=True)
        (dest / path).write_bytes(git("show", f"refs/viva/template:{path}", cwd=repo, binary=True))


# ---------------------------------------------------------------- results

def load_results(cfg, roll):
    f = sdir(cfg, roll) / "results.json"
    return json.loads(f.read_text()) if f.exists() else {}


def test_names(cfg):
    t, names = cfg["tests"], []
    if t.get("birthday"):
        names += ["birthday build", "bellman-ford"]
    if t.get("airport"):
        names += ["airport build", *AIRPORT_ROWS.values(), AIRPORT_OTHER]
    if t.get("xv6"):
        names += ["xv6 build", *t["xv6"]]
        if t.get("xv6_shell"):
            names += ["ln -s", "readlink"]
        names += t.get("xv6_last", [])
    return names


def earned(cfg, results, name):
    """Marks one row has earned. The assignment calls the kernel correct only if it passes both tests."""
    passed = lambda n: (results.get(n) or {}).get("status") == "pass"
    configured = test_names(cfg)
    if name in MARKS and passed(name) and all(passed(n) for n in NEEDS_ALSO.get(name, ()) if n in configured):
        return MARKS[name]
    return 0


def marks(cfg, results):
    """(earned, available) from the autograder alone. The report and the viva are marked by hand."""
    rows = [n for n in test_names(cfg) if n in MARKS]
    return sum(earned(cfg, results, n) for n in rows), sum(MARKS[n] for n in rows)


class Recorder:
    def __init__(self, cfg, roll, on_update):
        self.d, self.on_update = sdir(cfg, roll), on_update
        names = set(test_names(cfg))
        self.results = {k: v for k, v in load_results(cfg, roll).items() if k in names}
        self.head = git("rev-parse", "HEAD", cwd=self.d / "repo").strip()
        self.edited = edited(self.d / "repo")
        (self.d / "logs").mkdir(exist_ok=True)

    def set(self, name, status, log=None, secs=None, note=""):
        r = {"status": status, "note": note, "head": self.head, "edited": self.edited,
             "at": datetime.now().astimezone().isoformat(timespec="seconds"), "secs": secs}
        if log is not None:
            path = self.d / "logs" / (re.sub(r"\W+", "_", name).strip("_") + ".log")
            path.write_text(log)
            r["log"] = str(path)
        self.results[name] = r
        (self.d / "results.json").write_text(json.dumps(self.results, indent=1))
        self.on_update()

    def run(self, name, fn):
        self.set(name, "running")
        t = time.monotonic()
        status, log, note = fn()
        self.set(name, status, log, round(time.monotonic() - t), note)
        return status == "pass"

    def skip(self, names, why):
        for name in names:
            self.set(name, "skip", note=why)


# ---------------------------------------------------------------- building the concurrency parts

PARTS = {"birthday": ("birthday-boy", r"birthday|bellman|bf|main|a\.out"), "airport": ("airport-troubles", r"airport|main|a\.out")}
NOT_SUBMISSION = re.compile(r"(^|/)(tests?|bench\w*|tools?|scripts?|plots?)(/|$)", re.I)


@dataclass
class Build:
    binary: Path | None
    note: str
    log: str


def is_program(p):
    if not (p.is_file() and not p.is_symlink() and os.access(p, os.X_OK) and p.suffix not in (".so", ".o", ".a")):
        return False
    with p.open("rb") as f:
        return f.read(4) == b"\x7fELF"


def executables(root):
    return [p for p in root.rglob("*") if is_program(p)]


def pick_binary(bins, hint, part_dir):
    """Usually there is only one. Otherwise: the named-like-it-should-be one, not a test helper, closest to the top."""
    rel = lambda p: p.relative_to(part_dir).as_posix()
    return min(bins, key=lambda p: (not re.search(hint, p.name, re.I), bool(NOT_SUBMISSION.search(rel(p))), rel(p).count("/")),
               default=None)


def build_part(box, root, part, program=None):
    """Run the part's Makefile, in its own folder or in concurrency/, and find what it built: `program` if
    config.toml names it, otherwise the executable that looks like this part's."""
    name, hint = PARTS[part]
    part_dir = root / "concurrency" / name
    makedir = next((d for d in (part_dir, part_dir.parent) if (d / "Makefile").exists() or (d / "makefile").exists()), None)
    if makedir is None:
        return Build(None, "no Makefile", f"no Makefile in concurrency/{name} or concurrency/\n")
    # a committed binary must not stand in for a build
    for stale in [*executables(part_dir), *filter(is_program, part_dir.parent.iterdir())]:
        stale.unlink()
    r = box.run(["make", "-B"], makedir, BUILD_LIMIT)
    log = f"$ make -B   (in {makedir.relative_to(root)})\n{r.out}{r.err}\n"
    if r.rc:
        return Build(None, f"make failed ({how_it_ended(r, BUILD_LIMIT)})", log)
    if program:
        binary = next(filter(is_program, (part_dir / program, part_dir.parent / program)), None)
        where = f"concurrency/{name}/{program} or concurrency/{program}"
        return Build(binary, f"make: {binary.relative_to(root / 'concurrency')}" if binary else f"make built no {where}", log)
    binary = pick_binary(executables(part_dir), hint, part_dir)
    return Build(binary, f"make: {binary.relative_to(part_dir)}" if binary else "make built no program", log)


def program_for(cfg, part):
    return cfg["tests"].get("programs", {}).get(part)


def run_build(rec, row, box, root, part, program):
    result = {}

    def build():
        result["build"] = b = build_part(box, root, part, program)
        return ("pass" if b.binary else "fail"), b.log, b.note
    rec.run(row, build)
    return result["build"]


# ---------------------------------------------------------------- birthday boy

def run_birthday(box, root, rec, program):
    build = run_build(rec, "birthday build", box, root, "birthday", program)
    if not build.binary:
        rec.skip(["bellman-ford"], "not built")
        return

    def grade():
        log, failed = [], []
        for case in birthday.CASES:
            problem = None
            for i in range(1, case.runs + 1):
                r = run_program(box, build.binary, case.text, BIRTHDAY_LIMIT)
                ended = how_it_ended(r, BIRTHDAY_LIMIT)
                problem = birthday.judge(case, r.out) if r.rc is not None else ended
                if ended and r.rc is not None and not problem:
                    log.append(f"     note: {ended}")
                if problem:
                    log.append(f"FAIL {case.name}, run {i}: {problem}")
                    break
            if problem:
                failed.append((case.name, problem))
            else:
                log.append(f"ok   {case.name} (V={case.v}, E={len(case.edges)}, T={case.threads})")
        total = len(birthday.CASES)
        note = f"{total - len(failed)}/{total} graphs" + (f"; {failed[0][0]}: {failed[0][1]}" if failed else "")
        return ("fail" if failed else "pass"), "\n".join(log) + "\n", note[:90]
    rec.run("bellman-ford", grade)


# ---------------------------------------------------------------- airport troubles

def grade_airport(box, binary):
    fails, other, runs, limit = {c: [] for c in airport.CONSTRAINTS}, [], 0, AIRPORT_LIMIT
    for case in airport.CASES:
        for i in range(1, case.runs + 1):
            r = run_program(box, binary, case.text, limit)
            report = airport.check(case.text, r.out)
            tag = f"{case.name}, run {i}"
            if ended := how_it_ended(r, limit):
                other.append(f"{tag}: {ended}")
            other += [f"{tag}: {p}" for p in report.other]
            if case.edge:
                if broken := [c for c, msgs in report.violations.items() if msgs]:
                    other.append(f"{tag}: violates {', '.join(broken)}")
            else:
                runs += 1
                for c, msgs in report.violations.items():
                    if msgs:
                        fails[c].append((tag, case.text, msgs, r.out))
            if r.rc is None:  # a hang will hang again; don't spend the full limit on every run
                limit = AIRPORT_AFTER_HANG
                break
    return fails, other, runs


def airport_log(c, fails, runs):
    rule = f"{c}: {airport.CHECKS[c].__doc__}\n\n"
    if not fails:
        return rule + f"Satisfied in all {runs} runs.\n"
    parts = [rule + f"Violated in {len(fails)} of {runs} runs. The first few, in full:\n"]
    for tag, text, msgs, output in fails[:5]:
        numbered = "\n".join(f"{n:4}  {ln}" for n, ln in enumerate(output.splitlines()[:600], 1))
        parts.append(f"\n===== {tag} =====\n" + "\n".join(f"  * {m}" for m in msgs[:15]) +
                     (f"\n  ... and {len(msgs) - 15} more" if len(msgs) > 15 else "") +
                     f"\n\n----- input -----\n{text}\n----- output -----\n{numbered}\n")
    return "".join(parts)


def run_airport(box, root, rec, program):
    build = run_build(rec, "airport build", box, root, "airport", program)
    rows = [*AIRPORT_ROWS.values(), AIRPORT_OTHER]
    if not build.binary:
        rec.skip(rows, "not built")
        return
    for row in rows:
        rec.set(row, "running")
    start = time.monotonic()
    fails, other, runs = grade_airport(box, build.binary)
    secs = round(time.monotonic() - start)
    for c, row in AIRPORT_ROWS.items():
        note = f"{len(fails[c])}/{runs} runs: {fails[c][0][2][0]}"[:90] if fails[c] else f"all {runs} runs"
        rec.set(row, "fail" if fails[c] else "pass", airport_log(c, fails[c], runs), secs, note)
    log = "Not worth marks by themselves: output format, following the input, clean exit, edge-case inputs.\n\n" + \
          "\n".join(other[:300]) + ("\n..." if len(other) > 300 else "") + "\n"
    rec.set(AIRPORT_OTHER, "warn" if other else "pass", log, secs, f"{len(other)}: {other[0]}"[:90] if other else "")


# ---------------------------------------------------------------- xv6

XV6_TESTS = {  # row -> (command, seconds, lines that must all appear)
    "symlinktest": ("symlinktest", 180, ["test symlinks: ok", "test O_CREATE on existing symlink: ok",
                                         "test concurrent symlinks: ok"]),
    "usertests -q": ("usertests -q", 900, ["ALL TESTS PASSED"]),
}


class Console:
    """A booted xv6, in its own container: type at its shell, read what it prints."""

    def __init__(self, mount):
        self.buf = bytearray()
        self.name = container_name()
        self.p = subprocess.Popen(["docker", "run", "-i", "--rm", *container_options(mount, self.name), "-w", "/w/xv6",
                                   IMAGE, "make", "qemu"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        threading.Thread(target=self._pump, daemon=True).start()
        self.ready = self._prompt(0, BOOT_LIMIT) is not None

    def _pump(self):
        while chunk := os.read(self.p.stdout.fileno(), 65536):
            self.buf += chunk

    def _prompt(self, since, limit):
        """What it printed since offset `since`, once it is back at the prompt. None: panic, exit or timeout."""
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            text = bytes(self.buf[since:]).replace(b"\r", b"")
            if text.endswith(b"$ "):
                return text.decode(errors="replace")
            if b"panic: " in text or self.p.poll() is not None:
                return None
            time.sleep(0.02)
        return None

    def run(self, command, limit=SHELL_LIMIT):
        """Type a command; its output without the echoed command and the prompt, or None if xv6 didn't come back."""
        since = len(self.buf)
        self.p.stdin.write(command.encode() + b"\n")
        text = self._prompt(since, limit)
        if text is None:
            return None
        return text.partition("\n")[2].removesuffix("$ ").strip()

    def transcript(self):
        return self.buf.decode(errors="replace").replace("\r", "")

    def close(self):
        subprocess.run(["docker", "kill", self.name], capture_output=True)
        self.p.wait()


def boot(tree):
    shutil.copy(tree / "fs.img.pristine", tree / "fs.img")  # every test starts from a clean disk
    return Console(tree.parent)


def build_xv6(cfg, roll):
    """Export and build; (tree, exit status, log). Students' gcc may differ from the image's, so -Werror alone
    doesn't fail a build here."""
    root = sdir(cfg, roll) / "build/xv6"
    export(cfg, roll, root, cfg["tests"].get("xv6_protected", []))
    tree = root / "xv6"
    with Box(root) as box:
        r = box.run(["make", "kernel/kernel", "fs.img"], tree, XV6_BUILD_LIMIT)
        log = r.out + r.err
        if r.rc and "-Werror=" in log:
            makefile = tree / "Makefile"  # this is the throwaway export, not their repo
            makefile.write_text(makefile.read_text().replace("-Werror", "-Wno-error"))
            retry = box.run(["make", "kernel/kernel", "fs.img"], tree, XV6_BUILD_LIMIT)
            if retry.rc == 0:
                (tree / "RELAXED").write_text(log)
                log = (f"[viva] fails as written with this gcc; built with -Wno-error.\n----- as written -----\n{log}\n"
                       f"----- with -Wno-error -----\n{retry.out}{retry.err}")
                r = retry
    if r.rc == 0:
        shutil.copy(tree / "fs.img", tree / "fs.img.pristine")
    return tree, r.rc, log


def console_test(tree, command, limit, must_print):
    c = boot(tree)
    try:
        if not c.ready:
            return "fail", c.transcript(), "did not boot to a shell"
        out = c.run(command, limit)
        log = c.transcript()
    finally:
        c.close()
    if out is None:
        return "fail", log, panic_note(log) or f"no prompt within {limit}s"
    bad = next((ln.strip() for ln in out.splitlines() if "FAIL" in ln), "")
    done = sum(m in out for m in must_print)
    if bad or done < len(must_print):
        return "fail", log, (f"{done}/{len(must_print)} ok; {bad}" if bad else f"{done}/{len(must_print)} ok")[:90]
    return "pass", log, ""


def panic_note(log):
    return next((ln.strip()[:90] for ln in log.splitlines() if "panic: " in ln), "")


def prints(want):
    return lambda got: None if got == want else f"printed {got!r}, expected {want!r}"


def complains(not_this):
    """It must say something, and that something must not be the file's contents."""
    def judge(got):
        if not got:
            return "printed nothing, expected an error"
        return f"printed {got!r}, expected an error" if not_this in got else None
    return judge


LINES = "hello\nworld"
SHELL = [  # (row, command, how to judge its output)
    (None, "echo hello > f1", None),
    ("ln -s", "ln -s f1 f2", None),
    ("ln -s", "cat f2", prints("hello")),
    (None, "echo world >> f2", None),
    ("ln -s", "cat f1", prints(LINES)),  # the write went through the link, as in the assignment's example
    ("readlink", "readlink f2", prints("f1")),
    ("readlink", "readlink f1", complains("hello")),  # a regular file
    ("ln -s", "ln f1 f3", None),  # without -s it is still a hard link
    ("ln -s", "cat f3", prints(LINES)),
    ("readlink", "readlink f3", complains("hello")),
    ("ln -s", "ln -s f2 f4", None),  # a link to a link
    ("ln -s", "cat f4", prints(LINES)),
    ("readlink", "readlink f4", prints("f2")),  # one level, not the final target
    (None, "rm f1", None),
    ("ln -s", "cat f2", complains("hello")),  # now dangling
    ("readlink", "readlink f2", prints("f1")),  # dangling, but it still has a target to read
    ("ln -s", "cat f3", prints(LINES)),  # the hard link keeps the data
    ("ln -s", "ln -s nowhere f5", None),  # a target that never existed is fine
    ("readlink", "readlink f5", prints("nowhere")),
]


def shell_checks(tree):
    """Run SHELL in a fresh boot; {row: (status, log, note)}."""
    results = {"ln -s": [], "readlink": []}
    c = boot(tree)
    try:
        alive = c.ready
        for row, command, judge in SHELL:
            got = c.run(command) if alive else None
            if got is None and alive:
                alive = False
            if judge:
                if got is None:
                    results[row].append((command, "xv6 did not answer"))
                else:
                    results[row].append((command, judge(got)))
        console = c.transcript()
    finally:
        c.close()
    out = {}
    for row, checks in results.items():
        bad = [(cmd, why) for cmd, why in checks if why]
        lines = "".join(f"{'FAIL' if why else 'ok  '} {cmd}" + (f": {why}" if why else "") + "\n" for cmd, why in checks)
        note = f"{len(checks) - len(bad)}/{len(checks)}" + (f"; `{bad[0][0]}` {bad[0][1]}" if bad else "")
        out[row] = ("fail" if bad else "pass"), f"{lines}\n----- console -----\n{console}", note[:90]
    return out


def run_xv6(cfg, roll, rec):
    t = cfg["tests"]
    rows = [*t["xv6"], *(["ln -s", "readlink"] if t.get("xv6_shell") else []), *t.get("xv6_last", [])]
    built = {}

    def build():
        built["tree"], rc, log = build_xv6(cfg, roll)
        note = "build failed" if rc else "built only with -Wno-error" if (built["tree"] / "RELAXED").exists() else ""
        return ("fail" if rc else "pass"), log, note
    if not rec.run("xv6 build", build):
        rec.skip(rows, "build failed")
        return
    tree = built["tree"]

    def at_console(tests):
        for test in tests:
            command, limit, must_print = XV6_TESTS[test]
            rec.run(test, lambda: console_test(tree, command, limit, must_print))
    at_console(t["xv6"])
    if t.get("xv6_shell"):
        for row in ("ln -s", "readlink"):
            rec.set(row, "running")
        start = time.monotonic()
        for row, (status, log, note) in shell_checks(tree).items():
            rec.set(row, status, log, round(time.monotonic() - start), note)
    at_console(t.get("xv6_last", []))


def run_tests(cfg, roll, on_update=lambda: None, which=("birthday", "airport", "xv6")):
    rec, t = Recorder(cfg, roll, on_update), cfg["tests"]
    if ("birthday" in which and t.get("birthday")) or ("airport" in which and t.get("airport")):
        root = sdir(cfg, roll) / "build/concurrency"
        export(cfg, roll, root)
        with Box(root) as box:
            if "birthday" in which and t.get("birthday"):
                run_birthday(box, root, rec, program_for(cfg, "birthday"))
            if "airport" in which and t.get("airport"):
                run_airport(box, root, rec, program_for(cfg, "airport"))
    if "xv6" in which and t.get("xv6"):
        run_xv6(cfg, roll, rec)


# ---------------------------------------------------------------- trying things by hand

def concurrency_shell(cfg, roll):
    """Build both concurrency parts; argv for a shell in a container where the TA can run them."""
    root = sdir(cfg, roll) / "build/concurrency"
    export(cfg, roll, root)
    with Box(root) as box:
        bins = [build_part(box, root, part, program_for(cfg, part)).binary for part in PARTS]
    cwd = root / "concurrency"
    found = "  ".join(f"./{b.relative_to(cwd).as_posix()}" for b in bins if b) or "nothing built"
    hint = f"built: {found}   (exit to return)"
    return ["docker", "run", "--rm", "-it", *container_options(root, container_name()), "-w", "/w/concurrency",
            "-e", "PS1=[viva] \\w $ ", IMAGE, "sh", "-c", f"echo {shlex.quote(hint)}; exec bash --norc"]


def qemu(cfg, roll):
    """Build their xv6; argv to boot it in this terminal, in a container."""
    tree, rc, log = build_xv6(cfg, roll)
    if rc:
        raise Fatal(f"xv6 build failed:\n{log[-1500:]}")
    return ["docker", "run", "--rm", "-it", *container_options(tree.parent, container_name()), "-w", "/w/xv6",
            IMAGE, "sh", "-c", "echo 'xv6: Ctrl-A then X to quit'; exec make qemu"]
