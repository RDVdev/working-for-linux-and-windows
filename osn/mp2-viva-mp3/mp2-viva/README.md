# viva

Everything a TA needs for an MP3 viva in one terminal: your students (from the
allocation sheet) with their push history, late days, red flags, code changes
vs the template, AI-usage links, and an autograder for all three parts of the
assignment.

## Setup (once)

You need `git`, `docker` and [`uv`](https://docs.astral.sh/uv/). On Windows, run
it from Git Bash with Docker Desktop running (the MP2 setup, not re-tested for MP3).

1. On code.iiit.ac.in go to **Settings → Applications → Generate token**,
   with scope `read:repository`.
2. Run `cp .env.example .env` and paste the token into `.env`.
3. Connect to the VPN if you are off campus: code.iiit.ac.in is internal.
4. Run `./viva.py sync <your name as on the sheet>`, e.g. `./viva.py sync Advait`.

The sync clones your students into `work/`, reads their push history, and
analyses every repo. It takes seconds. Re-run `./viva.py sync` any time (it
remembers your name) to pick up new pushes and slot changes on the sheet.

Student code only ever runs in the `viva-env` docker image: builds, programs and
qemu. If you built that image for MP2, viva reuses it. Otherwise the first test
run builds it, which takes a few minutes once. Containers have no network, a
1 GB memory limit and a 512 process limit, and every command has a time limit.
The TUI, git and the checks on what programs printed run on your machine.

## Before the vivas

```
./viva.py test        # autograde everyone (about a minute each, mostly usertests -q)
./viva.py report      # every student's marks and flags as plain text
```

`./viva.py test <roll> ...` grades a few students, and `--only birthday`,
`--only airport` or `--only xv6` runs one part.

## The autograder

Marks are from the assignment. The performance report (20) is marked by hand,
so the autograder covers 150 of the 170.

| Part | Rows | Marks | What it does |
|---|---|---|---|
| Birthday boy | `bellman-ford` | 10 | Compares the output with BFS on 14 connected graphs in the assignment's `S D` format, in 1 to 16 threads. Graphs with more than one thread run 3 times |
| Airport troubles | `C1` to `C8` | 10 each | Runs 15 inputs, 3 or 5 times each (69 runs), parses the printed timeline and checks it against the 8 constraints. A constraint passes only if it holds in every run |
| | `airport extras` | none | Output format, same-tick order, sorted input (Q7), huge ids (Q7), clean exit |
| Symlinks | `symlinktest` | 40 | Boots xv6 and runs the template's copy of `symlinktest`. The 40 also need `usertests -q` to pass, because the assignment calls the kernel correct only if it passes both |
| | `ln -s`, `readlink` | 10 each | Boots a clean disk and types a short series of commands at the xv6 shell |
| | `usertests -q` | see above | Boots a clean disk and runs the template's copy. It takes about a minute, so it runs last |

Each part is built with its Makefile, in the part's folder or in
`concurrency/`. viva runs the program named under `[tests.programs]` in
`config.toml`; with no name there, it picks the executable that looks like the
part's and says which in the build row. A failed build skips that part's rows.

### Trying a fix

Tests run on the clone in `work/mp3/<roll>/repo` as it is on disk, so you can
edit it (`!` opens a shell there) and press `x` to re-run. Rows run on edited
code say "(your edits)", and the Overview tab says so too. `s` won't overwrite an
edited clone. `git checkout . && git clean -fd` in the clone drops your edits,
and the next `s` brings it to the latest push.

The airport checker lives in `airport.py`, one function per constraint. It
applies the timing from the doubts doc: timestamps are when an action starts,
and the next dependent action can start when it ends (Q8). The officer is in
the hall from the end of her `enters` to the end of her `leaves` (Q23). Each
"A must finish before B starts" rule belongs to one constraint, so one
off-by-one costs one constraint. Its own tests are in `tests/`:
`python3 -m unittest discover tests`.

`readlink`'s non-zero exit status can't be seen from the xv6 shell, so read
`user/readlink.c` for that.

## The viva sheet

`./viva.py sheet` (or `?` in the TUI) opens `sheet/mp3-viva.html` in your
browser. For every part it lists what to run, what earns the marks, and the viva
questions with hidden answers. To add questions, edit `sheet/build.py`, run
`python3 sheet/build.py`, and commit both files.

## During a viva

Run `./viva.py` to open the TUI. Pick a student on the left. Tabs `1`–`5`:

| Tab | What it shows |
|---|---|
| Overview | slot, last push, late days, autograder marks, flags, lines added per day around the deadline |
| Commits | server push time next to the commit's own date; Enter shows the commit |
| Code | every file changed vs the template, plus the functions touched (pick quiz targets here); Enter shows the diff |
| AI usage | links from `ai-usage.md`/`.pdf`; Enter opens the link |
| Tests | autograder rows and marks; Enter opens the row's log: what broke, on which input, with the full output |

| Key | Action |
|---|---|
| `c` | shell with their built concurrency programs |
| `v` | boot their xv6 here (Ctrl-A then X to quit) |
| `x` / `X` | run the autograder for this student / everyone |
| `s` | re-fetch this student |
| `!` | shell in their repo |
| `o` | open the repo on Forgejo |
| `?` | open the viva sheet |

To check a timeline from a hand-run, for example with your own input:

```
./airport < in > out                 # in the `c` shell
./viva.py airport in out             # from this repo: lists each constraint and what broke it
```

## Reading the flags

- **Push times come from the server**, so they can be trusted. Commit dates are
  whatever the student's clock said. Commits dated *after* the server received
  them mean a wrong clock or forged dates.
- **Late days** use the last push to the default branch and the deadline in
  `config.toml` (Nov 10, 23:59). HEAD is what's graded. "since deadline" lists
  what changed after the deadline.
- **Unmerged branches** are not graded. Students who forgot to merge show up here.
- **AI tool files** (`.claude/`, `CLAUDE.md`, `.cursor`, ...) are searched across
  the whole history, including files that were later deleted.
  `Co-authored-by` trailers and `.gitignore` entries that hide them are flagged too.
- **Banned API?** flags `usleep`-style delays, `pthread_barrier`, and atomics in
  `concurrency/` (doubts Q11, Q17, Q22). C++ files are flagged too (Q4).
- **xv6 tests run with the template's copies** of `symlinktest.c` and
  `usertests.c`. Editing them shows up as a flag, not as a pass.

## Other assignments

Copy `config.toml` (prefix, template, deadline, tests) and pass `-c other.toml`.
The push, flag, code and AI views work for any repo. The autograder rows are
specific to MP3.
