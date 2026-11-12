"""The viva TUI: student list on the left, everything about one student on the right."""

import os
import re
import shutil
import subprocess
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from rich.text import Text
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

import core
import run
from core import parse_dt

MARK = {"pass": ("✓", "green"), "fail": ("✗", "red"), "warn": ("!", "yellow"), "running": ("◌", "yellow"),
        "skip": ("–", "dim"), None: ("·", "dim")}
LEVEL = {"bad": ("✗", "red"), "warn": ("!", "yellow"), "info": ("·", "dim")}
SPARK = " ▁▂▃▄▅▆▇█"


def local(iso, fmt="%a %d %b %H:%M"):
    return parse_dt(iso).astimezone().strftime(fmt) if iso else "—"


def open_file(path):
    if hasattr(os, "startfile"):
        os.startfile(path)  # Windows: default app
    else:
        webbrowser.open(f"file://{path}")


def user_shell():
    if os.name == "nt":  # $SHELL from Git Bash is an msys path native python can't run
        return shutil.which("bash") or os.environ.get("COMSPEC", "cmd.exe")
    return os.environ.get("SHELL", "sh")


def slot_key(s):
    day = re.search(r"\d+", s["date"])
    t = re.search(r"(\d{1,2})[:.](\d{2})\s*([ap]m)?", s["time"], re.I)
    mins = 9999
    if t:
        h = int(t[1]) % 12 + (12 if (t[3] or "").lower() == "pm" or (not t[3] and int(t[1]) < 8) else 0)
        mins = h * 60 + int(t[2])
    return (int(day[0]) if day else 99, mins, s["name"])


COLUMNS = {"commits": ("Pushed", "Committed", "SHA", "+/−", "Message"),
           "code": ("", "+", "−", "File", "Functions touched"),
           "ai": ("File", "Link"), "tests": ("Test", "", "Marks", "Note", "Time", "Run at")}


class Viva(App):
    TITLE = "viva"
    CSS = """
    #top { height: 1; padding: 0 1; background: $panel; }
    #students { width: 62; border-right: solid $panel; }
    #right { width: 1fr; }
    #overview { padding: 0 1; }
    #commit-files { height: 9; border-top: solid $panel; padding: 0 1; }
    DataTable { height: 1fr; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("x", "test", "Run tests"), Binding("X", "test_all", "Test all", show=False),
        Binding("c", "concurrency", "Concurrency shell"),
        Binding("v", "qemu", "Boot xv6"),
        Binding("s", "sync", "Fetch"), Binding("o", "open_repo", "Web", show=False),
        Binding("exclamation_mark", "shell", "Shell"),
        Binding("question_mark", "sheet", "Viva sheet"),
        Binding("escape", "students", "Students", show=False),
        *[Binding(str(i), f"tab('{t}')", show=False) for i, t in enumerate(
            ["overview", "commits", "code", "ai", "tests"], 1)],
    ]

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        meta = core.load_students(cfg)
        self.ta, self.students = meta["ta"], sorted(meta["students"], key=slot_key)
        self.by_roll = {s["roll"]: s for s in self.students}
        self.an = {s["roll"]: core.load_analysis(cfg, s["roll"]) for s in self.students}
        self.roll = self.students[0]["roll"] if self.students else None

    def compose(self):
        yield Static(id="top")
        with Horizontal():
            yield DataTable(id="students", cursor_type="row", zebra_stripes=True)
            with Vertical(id="right"), TabbedContent(id="tabs"):
                with TabPane("Overview", id="overview-tab"):
                    yield Static(id="overview")
                with TabPane("Commits", id="commits-tab"):
                    yield DataTable(id="commits", cursor_type="row")
                    yield Static(id="commit-files")
                with TabPane("Code", id="code-tab"):
                    yield DataTable(id="code", cursor_type="row")
                with TabPane("AI usage", id="ai-tab"):
                    yield DataTable(id="ai", cursor_type="row")
                with TabPane("Tests", id="tests-tab"):
                    yield DataTable(id="tests", cursor_type="row")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#students", DataTable)
        t.add_columns("Slot", "Name", "Late", "Tests", "Flags")
        for s in self.students:
            t.add_row(*self.student_row(s), key=s["roll"])
        self.draw_top()
        t.focus()

    # ------------------------------------------------------------ drawing

    def student_row(self, s):
        a, res = self.an[s["roll"]], run.load_results(self.cfg, s["roll"])
        slot = " ".join(filter(None, [re.sub(r"(st|nd|rd|th|-th)\b", "", s["date"]).split(" ")[0],
                                      (re.search(r"\d{1,2}[:.]\d{2}\s*[APap]?[Mm]?", s["time"]) or [""])[0]]))
        late = Text(f"{a['late_days']}d", "yellow") if a.get("late_days") else Text("—", "dim")
        tests = self.tests_cell(res)
        flags = Text()
        if a.get("missing"):
            flags.append("no repo", "red")
        for lvl in ("bad", "warn"):
            n = sum(f[0] == lvl for f in a.get("flags", []))
            if n:
                flags.append(f"{LEVEL[lvl][0]}{n} ", LEVEL[lvl][1])
        return Text(slot or "—", "dim" if s["status"] == "Completed" else ""), s["name"][:20], late, tests, flags

    def tests_cell(self, res):
        """Autograder marks, then how many rows failed or need a look."""
        statuses = [(res.get(name) or {}).get("status") for name in run.test_names(self.cfg)]
        if not any(statuses):
            return Text("·", "dim")
        if "running" in statuses:
            return Text("◌ running", "yellow")
        cell = Text(f"{run.marks(self.cfg, res)[0]:>3}", "bold")
        for status in ("fail", "warn"):
            if n := statuses.count(status):
                cell.append(f" {MARK[status][0]}{n}", MARK[status][1])
        return cell

    def draw_top(self):
        self.query_one("#top").update(
            Text.assemble(("viva", "bold"), f" · {self.cfg['name']} · {self.ta} · {len(self.students)} students"))

    def on_data_table_row_highlighted(self, ev):
        if ev.data_table.id == "students" and ev.row_key.value:
            self.roll = ev.row_key.value
            self.show()
        elif ev.data_table.id == "commits" and ev.row_key.value:
            self.show_commit_files(ev.row_key.value)

    def show(self):
        a = self.an[self.roll]
        self.draw_overview(a)
        for tid in ("commits", "code", "ai"):
            self.reset_table(tid)
        self.query_one("#commit-files").update("")
        if not a.get("missing"):
            self.draw_commits(a)
            self.draw_code(a)
            self.draw_ai(a)
        self.draw_tests()

    def reset_table(self, tid):
        t = self.query_one(f"#{tid}", DataTable)
        t.clear(columns=True)
        t.add_columns(*COLUMNS[tid])
        return t

    def draw_overview(self, a):
        s = self.by_roll[self.roll]
        o = Text()
        o.append(f"{s['name']}", "bold")
        o.append(f"  {s['roll']}  {s['email']}\n", "dim")
        o.append(f"slot {s['date'] or '—'} {s['time']}  [{s['status'] or '—'}]\n\n")
        if a.get("missing"):
            self.query_one("#overview").update(o + Text("No repo / empty repo on Forgejo.", "red"))
            return
        o.append(f"{a['url']}\n", "underline")
        if core.edited(core.sdir(self.cfg, self.roll) / "repo"):
            o.append("You have edited this clone: tests run on your edits, and `s` won't overwrite them\n", "yellow")
        o.append(f"HEAD {a['head'][:8]} on {a['branch']} · {a['n_commits']} commits · {a['n_pushes']} pushes · "
                 f"{', '.join(a['emails'])}\n")
        o.append(f"last push {local(a['last_push'])} · ")
        o.append(f"{a['late_days']} late day(s)" if a["late_days"] else "on time",
                 "yellow" if a["late_days"] else "green")
        o.append(f" · final 24h: {a['frac_committed']:.0%} of lines committed, {a['frac_pushed']:.0%} pushed\n")
        res = run.load_results(self.cfg, self.roll)
        if res:
            got, total = run.marks(self.cfg, res)
            o.append(f"autograder {got}/{total}", "bold")
            o.append(" (the report and the viva are marked by hand)", "dim")
        o.append("\n\n")
        o.append("Flags\n", "bold")
        for lvl, txt in a["flags"] or [["info", "none"]]:
            mark, style = LEVEL[lvl]
            o.append(f" {mark} ", style)
            o.append(txt + "\n", style if lvl != "info" else "")
        o.append("\nLines added per day (by commit date, ")
        o.append("│", "red")
        o.append(" = deadline)\n")
        o.append_text(self.spark(a))
        self.query_one("#overview").update(o)

    def spark(self, a):
        mine = [c for c in a["commits"] if not c["initial"] and c["on_head"]]
        if not mine:
            return Text("—", "dim")
        deadline = self.cfg["deadline_dt"].astimezone().date()
        days = [parse_dt(c["committed"]).astimezone().date() for c in mine]
        start, end = min(days + [deadline]), max(days + [deadline])
        n = (end - start).days + 1
        per = [0] * n
        for c, d in zip(mine, days):
            per[(d - start).days] += c["add"]
        top = max(per) or 1
        t = Text(f"{start:%d %b} ")
        for i, v in enumerate(per):
            day = start + timedelta(days=i)
            ch = SPARK[min(8, (v * 8 + top - 1) // top)] if v else "│" if day == deadline else "·"
            t.append(ch, "red" if day == deadline else
                     "yellow" if day > deadline else "cyan")
        t.append(f" {end:%d %b}  (peak {top} lines/day)", "dim")
        return t

    def draw_commits(self, a):
        t = self.query_one("#commits", DataTable)
        for c in sorted(a["commits"], key=lambda c: c["pushed"] or c["committed"], reverse=True):
            pushed = parse_dt(c["pushed"]) if c["pushed"] else None
            committed = parse_dt(c["committed"])
            cstyle = ""
            if pushed and pushed - committed > timedelta(days=2):
                cstyle = "yellow"
            if pushed and committed - pushed > timedelta(hours=1):
                cstyle = "red"
            late = pushed and pushed > self.cfg["deadline_dt"]
            subj = Text(c["subject"][:70], "dim" if c["initial"] else "")
            if not c["on_head"]:
                subj = Text("⎇ ", "magenta") + subj
            if core.AI_TEXT.search(c["subject"] + c["body"]):
                subj.stylize("red")
            t.add_row(Text("template", "dim") if c["initial"] else Text(local(c["pushed"]), "yellow" if late else ""),
                      Text(local(c["committed"]), cstyle or "dim"), c["sha"][:8],
                      Text.assemble((f"+{c['add']}", "green"), " ", (f"−{c['del']}", "red")),
                      subj, key=c["sha"])

    def show_commit_files(self, sha):
        c = next(c for c in self.an[self.roll]["commits"] if c["sha"] == sha)
        o = Text()
        o.append(f"{c['author']} <{c['email']}>  authored {local(c['authored'])}", "dim")
        if c["body"]:
            o.append("\n" + c["body"][:300], "italic")
        for st, *paths in c["files"]:
            style = {"A": "green", "D": "red", "M": "", "R": "cyan"}.get(st[0], "")
            if any(core.AI_PATHS.search(p) for p in paths):
                style = "bold red"
            elif any(p in c["binaries"] for p in paths):
                style = "yellow"
            o.append(f"\n{st[0]} {' → '.join(paths)}", style)
        self.query_one("#commit-files").update(o)

    def draw_code(self, a):
        t = self.query_one("#code", DataTable)
        protected = set(self.cfg["tests"].get("xv6_protected", []))
        for f in a["changed"]:
            style = "bold red" if f["path"] in protected or core.AI_PATHS.search(f["path"]) else ""
            t.add_row(Text(f.get("status", "M"), {"A": "green", "D": "red"}.get(f.get("status"), "")),
                      Text(str(f["add"]), "green"), Text(str(f["del"]), "red"), Text(f["path"], style),
                      "(new file)" if f["new"] else ", ".join(f["funcs"])[:80], key=f["path"])

    def draw_ai(self, a):
        t = self.query_one("#ai", DataTable)
        for i, (f, url) in enumerate(a["links"]):
            t.add_row(f, url, key=str(i))
        if not a["links"]:
            t.add_row(Text("no links", "dim"), ", ".join(a["ai_files"]) or "no ai-usage file")

    def draw_tests(self):
        t = self.reset_table("tests")
        res = run.load_results(self.cfg, self.roll)
        head = self.an[self.roll].get("head")
        for name in run.test_names(self.cfg):
            r = res.get(name) or {}
            mark, style = MARK.get(r.get("status"), MARK[None])
            stale = r.get("head") and r["head"] != head
            when = (r.get("at") or "")[5:16].replace("T", " ") + (" (old HEAD)" if stale else "") + \
                (" (your edits)" if r.get("edited") else "")
            worth, got = run.MARKS.get(name), run.earned(self.cfg, res, name)
            earned = "" if worth is None or r.get("status") in (None, "running") else f"{got}/{worth}"
            # a passing row can still earn nothing: symlinktest's marks also need usertests -q
            t.add_row(name, Text(mark, style), Text(earned, style if got or r.get("status") != "pass" else "yellow"),
                      Text(r.get("note", ""), style),
                      f"{r['secs']}s" if r.get("secs") is not None else "",
                      Text(when, "yellow" if stale or r.get("edited") else "dim"), key=name)

    def refresh_student(self, roll):
        t = self.query_one("#students", DataTable)
        for col, val in zip(t.columns, self.student_row(self.by_roll[roll])):
            t.update_cell(roll, col, val)
        if roll == self.roll:
            self.draw_tests()
            self.draw_overview(self.an[roll])

    # ------------------------------------------------------------ actions

    def on_data_table_row_selected(self, ev):
        key = ev.row_key.value
        repo = core.sdir(self.cfg, self.roll) / "repo"
        tid = ev.data_table.id
        if tid == "commits":
            self.foreground(["git", "-C", str(repo), "show", "--stat", "-p", key])
        elif tid == "code":
            self.foreground(["git", "-C", str(repo), "diff", "refs/viva/template", "HEAD", "--", key])
        elif tid == "ai" and key and key.isdigit():
            webbrowser.open(self.an[self.roll]["links"][int(key)][1])
        elif tid == "tests":
            log = (run.load_results(self.cfg, self.roll).get(key) or {}).get("log")
            if log:
                self.foreground(["less", "-R", "+G", log]) if shutil.which("less") else open_file(log)

    def foreground(self, argv, **kw):
        # LESS without F: git's default (FRX) quits on short output, so a
        # small diff would flash and vanish before the TUI redraws
        env = {**os.environ, "LESS": "-R"}
        with self.suspend():
            subprocess.run(argv, env=env, **kw)

    def action_tab(self, name):
        self.query_one("#tabs", TabbedContent).active = f"{name}-tab"
        tables = self.query_one(f"#{name}-tab").query(DataTable)
        (tables.first() if tables else self.query_one("#students")).focus()

    def action_students(self):
        self.query_one("#students").focus()

    def action_sheet(self):
        webbrowser.open((core.ROOT / self.cfg["viva_sheet"]).as_uri())

    def action_open_repo(self):
        if url := self.an[self.roll].get("url"):
            webbrowser.open(url)

    def action_shell(self):
        repo = core.sdir(self.cfg, self.roll) / "repo"
        if repo.exists():
            self.foreground([user_shell()], cwd=repo)

    @work(thread=True, group="tests")
    def action_test(self):
        roll = self.roll
        self.call_from_thread(self.notify, f"testing {self.by_roll[roll]['name']}…")
        self.run_tests(roll)
        self.call_from_thread(self.notify, f"tests done: {self.by_roll[roll]['name']}")

    @work(thread=True, group="tests")
    def action_test_all(self):
        jobs = max(1, (os.cpu_count() or 4) // 4)
        self.call_from_thread(self.notify, f"testing {len(self.students)} students, {jobs} at a time…")
        with ThreadPoolExecutor(jobs) as ex:
            list(ex.map(self.run_tests, [s["roll"] for s in self.students]))
        self.call_from_thread(self.notify, "all tests done")

    def run_tests(self, roll):
        if self.an[roll].get("missing"):
            return
        try:
            run.ensure_image(lambda m: self.call_from_thread(self.notify, m))
            run.run_tests(self.cfg, roll, lambda: self.call_from_thread(self.refresh_student, roll))
        except Exception as e:
            self.call_from_thread(self.notify, f"{roll}: {e}", severity="error")

    @work(thread=True, exclusive=True, group="sync")
    def action_sync(self):
        s = self.by_roll[self.roll]
        self.call_from_thread(self.notify, f"fetching {s['name']}…")
        try:
            line = core.sync_one(self.cfg, s)
        except Exception as e:
            line = f"ERROR {e}"
        if "ERROR" in line:
            self.call_from_thread(self.notify, line.strip(), severity="error")
            return
        self.an[s["roll"]] = core.load_analysis(self.cfg, s["roll"])
        self.call_from_thread(self.refresh_student, s["roll"])
        self.call_from_thread(self.show)
        self.call_from_thread(self.notify, f"{s['name']}: up to date")

    @work(thread=True, exclusive=True, group="shell")
    def action_concurrency(self):
        roll = self.roll
        self.call_from_thread(self.notify, f"building {self.by_roll[roll]['name']}'s concurrency parts…")
        try:
            run.ensure_image(lambda m: self.call_from_thread(self.notify, m))
            argv = run.concurrency_shell(self.cfg, roll)
        except Exception as e:
            self.call_from_thread(self.notify, str(e)[:300], severity="error")
            return
        self.call_from_thread(self.foreground, argv)

    @work(thread=True, exclusive=True, group="shell")
    def action_qemu(self):
        roll = self.roll
        self.call_from_thread(self.notify, f"building {self.by_roll[roll]['name']}'s xv6…")
        try:
            run.ensure_image(lambda m: self.call_from_thread(self.notify, m))
            argv = run.qemu(self.cfg, roll)
        except Exception as e:
            self.call_from_thread(self.notify, str(e)[-500:], severity="error", timeout=15)
            return
        self.call_from_thread(self.foreground, argv)
