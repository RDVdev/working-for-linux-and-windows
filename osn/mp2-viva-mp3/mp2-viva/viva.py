#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["textual>=3", "pypdf>=5", "truststore>=0.10"]
# ///
"""viva: evaluation helper for OSN TAs.

  ./viva.py sync <TA>        clone/fetch your students' repos + push history
  ./viva.py                  the TUI
  ./viva.py test [roll ...]  autograde birthday boy, airport troubles, symlinks (all your students by default)
  ./viva.py report           flags and autograder marks for every student, as text
  ./viva.py sheet            open the viva sheet (what to run, check and ask per part)
  ./viva.py shell <roll>     shell with their built concurrency programs
  ./viva.py qemu <roll>      boot their xv6 in this terminal
  ./viva.py airport <input> [output]
                             check one output (a file, or stdin) against the 8 constraints
"""

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import airport
import core
import run


def open_sheet(cfg):
    import webbrowser
    page = core.ROOT / cfg["viva_sheet"]
    print(page)
    webbrowser.open(page.as_uri())


def check_airport(input_file, output_file):
    """Print the verdict for one output. Exit status 1 if a constraint is broken."""
    text = Path(input_file).read_text()
    report = airport.check(text, Path(output_file).read_text() if output_file else sys.stdin.read())
    for c, label in airport.CONSTRAINTS.items():
        print(f"{'✗' if report.violations[c] else '✓'} {c} {label}")
        for message in report.violations[c][:20]:
            print(f"    {message}")
    if report.other:
        print("\nAlso worth a look (no marks attached):")
        for message in report.other[:30]:
            print(f"    {message}")
    return 0 if report.ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--config", help="assignment config (default: config.toml)")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("sync", help="fetch the sheet, clone/fetch repos, read push history")
    s.add_argument("ta", nargs="?", help="your name as on the sheet (remembered after the first sync)")
    t = sub.add_parser("test", help="build and autograde submissions")
    t.add_argument("rolls", nargs="*")
    t.add_argument("-j", "--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 4))
    t.add_argument("--only", choices=["birthday", "airport", "xv6"])
    sub.add_parser("report", help="print every student's flags and marks")
    sub.add_parser("sheet", help="open the viva sheet in the browser")
    n = sub.add_parser("shell", help="shell with the student's built concurrency programs")
    n.add_argument("roll")
    m = sub.add_parser("qemu", help="boot the student's xv6 in this terminal")
    m.add_argument("roll")
    a = sub.add_parser("airport", help="check one airport output against the 8 constraints")
    a.add_argument("input")
    a.add_argument("output", nargs="?", help="default: read from stdin")
    sub.add_parser("tui", help="the TUI (default)")
    args = p.parse_args()
    if args.cmd == "airport":
        sys.exit(check_airport(args.input, args.output))
    cfg = core.load_cfg(args.config)

    if args.cmd == "sheet":
        open_sheet(cfg)
    elif args.cmd == "sync":
        core.sync(cfg, args.ta)
    elif args.cmd == "test":
        rolls = args.rolls or [s["roll"] for s in core.load_students(cfg)["students"]]
        run.ensure_image()
        which = (args.only,) if args.only else ("birthday", "airport", "xv6")

        def one(roll):
            if core.load_analysis(cfg, roll).get("missing"):
                return f"{roll}: no repo"
            run.run_tests(cfg, roll, which=which)
            res = run.load_results(cfg, roll)
            got, total = run.marks(cfg, res)
            bad = [f"{v['status']}: {k}" for k, v in res.items() if v["status"] in ("fail", "warn")]
            return f"{roll}: {got}/{total}" + ("  (" + "; ".join(bad) + ")" if bad else "")
        print(f"testing {len(rolls)} students, {args.jobs} at a time")
        with ThreadPoolExecutor(args.jobs) as ex:
            for line in ex.map(one, rolls):
                print(line, flush=True)
    elif args.cmd == "report":
        for s in core.load_students(cfg)["students"]:
            a = core.load_analysis(cfg, s["roll"])
            print(f"\n{s['roll']}  {s['name']}  ({s['date']} {s['time']})")
            if res := run.load_results(cfg, s["roll"]):
                print("  autograder {}/{}".format(*run.marks(cfg, res)))
            for lvl, txt in a.get("flags", [["bad", "no repo"]]):
                print(f"  {'✗!·'[['bad', 'warn', 'info'].index(lvl)]} {txt}")
    elif args.cmd == "shell":
        run.ensure_image()
        subprocess.run(run.concurrency_shell(cfg, args.roll))
    elif args.cmd == "qemu":
        run.ensure_image()
        subprocess.run(run.qemu(cfg, args.roll))
    else:
        from tui import Viva
        Viva(cfg).run()


if __name__ == "__main__":
    try:
        main()
    except core.Fatal as e:
        sys.exit(f"viva: {e}")
    except KeyboardInterrupt:
        sys.exit(130)
