"""Sheet, Forgejo, git analysis and red flags. No UI in here."""

import csv
import io
import json
import math
import os
import re
import subprocess
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:  # use the OS trust store (uv-managed pythons ship without one)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

AI_PATHS = re.compile(
    r"(^|/)(\.claude|CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.cursor|\.cursorrules|\.aider[^/]*"
    r"|\.windsurf\w*|\.codex|\.github/copilot[^/]*|\.continue|\.cline\w*|\.roo\w*)(/|$)", re.I)
AI_TEXT = re.compile(r"co-authored-by|generated (with|by)|\bclaude\b|copilot|chatgpt|\bgpt-?\d|cursor|gemini"
                     r"|anthropic", re.I)
VAGUE = re.compile(r"^(\W*|update\w*|fix\w*|changes?|commit|wip|done|final|test\w*|misc|stuff|minor"
                   r"|[a-z]{1,3})\W*$", re.I)
URL = re.compile(r"https?://[^\s<>()\[\]\"'`]+")


class Fatal(Exception):
    pass


# ---------------------------------------------------------------- config

def load_cfg(path=None):
    path = Path(path or ROOT / "config.toml")
    cfg = tomllib.loads(path.read_text())
    cfg["deadline_dt"] = datetime.fromisoformat(cfg["deadline"])
    cfg["late_ends"] = sorted(datetime.fromisoformat(d) for d in cfg.get("late_days", []))
    cfg["work"] = ROOT / "work" / cfg["name"]
    cfg["work"].mkdir(parents=True, exist_ok=True)
    return cfg


def token():
    if t := os.environ.get("FORGEJO_TOKEN"):
        return t
    for env in (Path.cwd() / ".env", ROOT / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                k, _, v = line.partition("=")
                if k.strip() == "FORGEJO_TOKEN" and v.strip():
                    return v.strip().strip("'\"")
    raise Fatal("no FORGEJO_TOKEN: put it in viva/.env (see .env.example) or export it")


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def late_days(cfg, t):
    """Late days used by a push at t: index of the first late-day window that contains it."""
    if t <= cfg["deadline_dt"]:
        return 0
    ends = cfg["late_ends"]
    for i, end in enumerate(ends, 1):
        if t <= end:
            return i
    last = ends[-1] if ends else cfg["deadline_dt"]
    return len(ends) + math.ceil((t - last) / timedelta(days=1))


def ago(dt, ref):
    s = (ref - dt).total_seconds()
    d, h = int(abs(s) // 86400), int(abs(s) % 86400 // 3600)
    txt = f"{d}d {h}h" if d else f"{h}h {int(abs(s) % 3600 // 60)}m"
    return txt + (" late" if s < 0 else " early")


# ---------------------------------------------------------------- sheet

def read_sheet(cfg):
    with urllib.request.urlopen(cfg["sheet"], timeout=30) as r:
        rows = list(csv.reader(io.StringIO(r.read().decode())))
    tas, cur = {}, None
    for row in rows[1:]:
        row += [""] * 7
        first = row[0].strip()
        if not first:
            continue
        if not first[:1].isdigit():
            cur = tas.setdefault(first.split()[0], [])
        elif cur is not None:
            cur.append({"roll": first, "name": f"{row[1]} {row[2]}".strip(), "email": row[3].strip(),
                        "date": row[4].strip(), "time": row[5].strip(), "status": row[6].strip()})
    return tas


def find_ta(tas, query):
    hits = [t for t in tas if t.lower().startswith(query.lower())]
    if len(hits) != 1:
        raise Fatal(f"TA '{query}' matches {hits or 'nobody'}; TAs: {', '.join(tas)}")
    return hits[0]


# ---------------------------------------------------------------- forgejo

class Forge:
    def __init__(self, cfg):
        self.cfg, self.tok = cfg, token()

    def get(self, path, **params):
        url = f"{self.cfg['host']}/api/v1{path}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"token {self.tok}"})
        time.sleep(0.15)  # the server runs fail2ban; don't hammer it
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # stop at once: repeated auth failures get the IP banned
                raise Fatal(f"Forgejo said {e.code} for {path}: check FORGEJO_TOKEN (needs read:repository)") from None
            if e.code == 404:
                return None
            raise

    def paged(self, path):
        page = 1
        while batch := self.get(path, limit=50, page=page):
            yield from batch
            page += 1

    def git(self, *args, cwd=None):
        hdr = f"http.extraHeader=Authorization: token {self.tok}"
        return git("-c", hdr, *args, cwd=cwd)

    def url(self, repo):
        return f"{self.cfg['host']}/{repo}.git"


def git(*args, cwd=None, check=True, binary=False):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=not binary,
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a for a in args if 'token' not in a)}: {r.stderr.strip()[-300:]}")
    return r.stdout


# ---------------------------------------------------------------- sync

def sdir(cfg, roll):
    return cfg["work"] / roll


def load_students(cfg):
    f = cfg["work"] / "students.json"
    if not f.exists():
        raise Fatal("nothing synced yet: run `viva.py sync <your TA name>` first")
    return json.loads(f.read_text())


def edited(repo):
    """True if the TA has changed the clone in work/. Tests run on what is there, edits included."""
    return bool(git("status", "--porcelain", cwd=repo).strip())


def _clone_or_fetch(forge, repo, dest, branch):
    """Fetch and move to the latest push. False if the clone has your edits: those are kept and it stays put."""
    if (dest / ".git").exists():
        forge.git("fetch", "-q", "--prune", "--force", "origin", cwd=dest)
        if edited(dest):
            return False
    else:
        forge.git("clone", "-q", forge.url(repo), str(dest))
        # better function names in diff hunk headers
        (dest / ".git/info").mkdir(exist_ok=True)
        (dest / ".git/info/attributes").write_text("*.c diff=cpp\n*.h diff=cpp\n")
    git("checkout", "-q", "-f", "-B", branch, f"origin/{branch}", cwd=dest)
    return True


def sync(cfg, ta_query=None, log=print):
    forge = Forge(cfg)
    # always re-read the sheet: slots and allocations change
    tas = read_sheet(cfg)
    ta = find_ta(tas, ta_query or load_students(cfg)["ta"])
    students = tas[ta]
    if forge.get(f"/repos/{cfg['template']}") is None:
        raise Fatal(f"template {cfg['template']} not visible with this token")
    log(f"{ta}: {len(students)} students")
    _clone_or_fetch(forge, cfg["template"], cfg["work"] / "_template", "main")
    (cfg["work"] / "students.json").write_text(json.dumps(
        {"ta": ta, "synced": datetime.now().astimezone().isoformat(), "students": students}, indent=1))

    with ThreadPoolExecutor(4) as ex:
        for line in ex.map(lambda s: sync_one(cfg, s, forge), students):
            log(line)


def sync_one(cfg, s, forge=None):
    """Clone/fetch one student, read their push feed, analyze. Returns a status line."""
    forge = forge or Forge(cfg)
    repo = f"{cfg['org']}/{cfg['prefix']}{s['roll']}"
    d = sdir(cfg, s["roll"])
    d.mkdir(exist_ok=True)
    try:
        info = forge.get(f"/repos/{repo}")
        if not info or info.get("empty"):
            (d / "analysis.json").write_text(json.dumps({"missing": True}))
            return f"  {s['roll']} {s['name']}: {'no repo' if not info else 'empty repo'}"
        updated = _clone_or_fetch(forge, repo, d / "repo", info["default_branch"])
        git("fetch", "-q", "--force", str(cfg["work"] / "_template"), "main:refs/viva/template", cwd=d / "repo")
        pushes = []
        for a in forge.paged(f"/repos/{repo}/activities/feeds"):
            if a.get("op_type") != "commit_repo":
                continue
            c = json.loads(a.get("content") or "{}")
            pushes.append({"at": a["created"], "ref": a.get("ref_name"),
                           "by": (a.get("act_user") or {}).get("login"),
                           "head": (c.get("HeadCommit") or {}).get("Sha1"),
                           "shas": [x["Sha1"] for x in c.get("Commits") or []]})
        (d / "pushes.json").write_text(json.dumps(
            {"branch": info["default_branch"], "url": info["html_url"], "pushes": pushes}, indent=1))
        a = analyze(cfg, s)
        (d / "analysis.json").write_text(json.dumps(a, indent=1))
        kept = "" if updated else " (your edits kept: not moved to the latest push)"
        return f"  {s['roll']} {s['name']}: {len(a['commits'])} commits, {len(a['flags'])} flags{kept}"
    except Fatal:
        raise
    except Exception as e:  # one broken repo must not stop the rest
        return f"  {s['roll']} {s['name']}: ERROR {e}"


# ---------------------------------------------------------------- analysis

def _commits(repo):
    fmt = "%x1e%H%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%cI%x1f%s%x1f%b%x1f"
    out = {}
    for rec in git("log", "--remotes=origin", f"--format={fmt}", "--numstat", cwd=repo).split("\x1e")[1:]:
        h, parents, an, ae, ad, cd, subj, body, stat = rec.split("\x1f")
        add = dele = 0
        binaries = []
        for line in stat.strip().splitlines():
            a, d, path = line.split("\t", 2)
            if a == "-":
                binaries.append(path)
            else:
                add, dele = add + int(a), dele + int(d)
        out[h] = {"sha": h, "parents": parents.split(), "author": an, "email": ae, "authored": ad,
                  "committed": cd, "subject": subj, "body": body.strip(), "add": add, "del": dele,
                  "binaries": binaries, "files": []}
    for rec in git("log", "--remotes=origin", "--format=%x1e%H", "--name-status", cwd=repo).split("\x1e")[1:]:
        h, *lines = rec.strip().splitlines()
        out[h]["files"] = [ln.split("\t") for ln in lines if ln]
    return out


def _functions(repo):
    """Files changed in HEAD vs the template, with +/- and the functions each hunk touches."""
    files = {}
    for line in git("diff", "--numstat", "refs/viva/template", "HEAD", cwd=repo).splitlines():
        a, d, path = line.split("\t", 2)
        files[path] = {"path": path, "add": a, "del": d, "funcs": [], "new": False}
    cur = None
    for line in git("diff", "-U0", "--no-color", "refs/viva/template", "HEAD", cwd=repo).splitlines():
        if line.startswith("diff --git"):
            cur = None
        elif line.startswith(("--- a/", "+++ b/")):
            cur = files.get(line[6:]) or cur
        elif line.startswith("@@") and cur:
            m = re.search(r"@@[^@]*@@.*?(\w+)\s*\(", line)
            if m and m.group(1) not in cur["funcs"]:
                cur["funcs"].append(m.group(1))
    for line in git("diff", "--name-status", "refs/viva/template", "HEAD", cwd=repo).splitlines():
        st, path = line.split("\t")[0], line.split("\t")[-1]
        if path in files:
            files[path]["new"] = st == "A"
            files[path]["status"] = st[0]
    return sorted(files.values(), key=lambda f: f["path"])


def ai_links(repo):
    """(ai-usage files in HEAD, [(file, url)] found in them). PDFs: text and link annotations."""
    found, files = [], []
    for path in git("ls-tree", "-r", "--name-only", "HEAD", cwd=repo).splitlines():
        if not re.search(r"ai[-_ ]?usage", path, re.I):
            continue
        files.append(path)
        raw = git("show", f"HEAD:{path}", cwd=repo, binary=True)
        urls = []
        if path.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                pdf = PdfReader(io.BytesIO(raw))
                for page in pdf.pages:
                    urls += URL.findall(page.extract_text() or "")
                    for annot in page.get("/Annots") or []:
                        uri = (annot.get_object().get("/A") or {}).get("/URI")
                        if uri:
                            urls.append(str(uri))
            except Exception as e:
                urls.append(f"(could not read pdf: {e})")
        else:
            urls = URL.findall(raw.decode(errors="replace"))
        for u in dict.fromkeys(u.rstrip(".,;:*_") for u in urls):
            found.append((path, u))
    return files, found


def analyze(cfg, s):
    d = sdir(cfg, s["roll"])
    repo = d / "repo"
    meta = json.loads((d / "pushes.json").read_text())
    branch, deadline = meta["branch"], cfg["deadline_dt"]
    commits = _commits(repo)
    on_head = set(git("rev-list", "HEAD", cwd=repo).split())

    # Server push time per commit. The feed only lists a few commits per push,
    # so everything reachable from a push's head that no earlier push brought
    # is attributed to it too.
    pushed = {}
    for p in sorted(meta["pushes"], key=lambda p: p["at"]):
        reach = []
        if p["head"]:
            reach = git("rev-list", p["head"], cwd=repo, check=False).split()
        for sha in reach + p["shas"]:
            pushed.setdefault(sha, p["at"])

    tpl_files = set(git("ls-tree", "-r", "--name-only", "refs/viva/template", cwd=repo).splitlines())
    rows = []
    for c in commits.values():
        c["pushed"] = pushed.get(c["sha"])
        c["on_head"] = c["sha"] in on_head
        # the commit Forgejo made from the template is not the student's work
        c["initial"] = not c["parents"] and not git(
            "diff", "--name-only", "refs/viva/template", c["sha"], cwd=repo).strip()
        rows.append(c)
    rows.sort(key=lambda c: c["pushed"] or c["committed"])
    mine = [c for c in rows if not c["initial"]]
    head_mine = [c for c in mine if c["on_head"]]

    flags = []
    def flag(level, text):
        flags.append([level, text])

    main_pushes = [p["at"] for p in meta["pushes"] if p["ref"] == f"refs/heads/{branch}"]
    last = parse_dt(max(main_pushes)) if main_pushes else None
    late = late_days(cfg, last) if last else 0
    if not head_mine:
        flag("bad", "no student commits on " + branch)
    if late:
        # what changed after the deadline: HEAD vs the newest commit on it pushed in time
        base = next((c for c in sorted(head_mine, key=lambda c: c["pushed"] or "", reverse=True)
                     if c["pushed"] and parse_dt(c["pushed"]) <= deadline), None)
        if base:
            post = git("diff", "--shortstat", base["sha"], "HEAD", cwd=repo).strip()
            names = git("diff", "--name-only", base["sha"], "HEAD", cwd=repo).split()
            post += ": " + ", ".join(names[:6]) + (" ..." if len(names) > 6 else "")
        else:
            post = "everything (nothing on time)"
        flag("warn", f"{late} late day{'s' * (late > 1)}: last push to {branch} "
                     f"{last.astimezone():%a %d %b %H:%M} ({ago(last, deadline)})")
        flag("info", f"since deadline: {post}")
    any_last = max((p["at"] for p in meta["pushes"]), default=None)
    if any_last and last and parse_dt(any_last) > max(last, deadline):
        flag("info", f"pushed to another branch after the last {branch} push "
                     f"({parse_dt(any_last).astimezone():%d %b %H:%M})")

    for ref in git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", cwd=repo).split():
        if ref in ("origin", "origin/HEAD", f"origin/{branch}"):
            continue
        n = int(git("rev-list", "--count", ref, "^HEAD", cwd=repo).strip() or 0)
        if n:
            flag("warn", f"branch {ref[7:]}: {n} commit{'s' * (n > 1)} not merged into {branch} (not graded)")

    gap = {c["sha"]: parse_dt(c["pushed"]) - parse_dt(c["committed"]) for c in mine if c["pushed"]}
    backdated = [c for c in mine if gap.get(c["sha"], timedelta()) > timedelta(days=2)]
    future = [c for c in mine if gap.get(c["sha"], timedelta()) < -timedelta(hours=1)]
    if backdated:
        flag("warn", f"{len(backdated)} commit(s) pushed >2 days after their commit date")
    if future:
        skew = sorted(-gap[c["sha"]] for c in future)[len(future) // 2]
        flag("bad", f"{len(future)} commit(s) dated after the server received them "
                    f"(median +{skew.total_seconds() / 3600:.1f}h): wrong clock or forged dates")

    total = sum(c["add"] for c in head_mine) or 1
    end = max(deadline, last) if last else deadline
    def frac(key):
        return sum(c["add"] for c in head_mine if c[key] and parse_dt(c[key]) > end - timedelta(hours=24)) / total
    fc, fp = frac("committed"), frac("pushed")
    if fc >= 0.5:
        flag("warn", f"{fc:.0%} of added lines committed in the final 24h")
    elif fp >= 0.7:
        flag("info", f"{fp:.0%} of added lines pushed in the final 24h (committed earlier)")
    if head_mine:
        big = max(head_mine, key=lambda c: c["add"])
        if big["add"] >= 400:
            flag("warn", f"largest commit +{big['add']} lines: {big['sha'][:8]} {big['subject'][:50]}")
    if 0 < len(head_mine) < 8:
        flag("warn", f"only {len(head_mine)} commits")
    vague = [c for c in head_mine if VAGUE.match(c["subject"])]
    if len(vague) >= 3 and len(vague) >= 0.3 * len(head_mine):
        flag("warn", f"{len(vague)}/{len(head_mine)} vague commit messages")

    ai_hits = {}
    for c in mine:
        for st, *paths in c["files"]:
            for p in paths:
                if AI_PATHS.search(p):
                    ai_hits.setdefault(p, []).append(f"{st[0]} {c['sha'][:8]}")
        if m := AI_TEXT.search(c["subject"] + "\n" + c["body"]):
            line = next(ln for ln in (c["subject"] + "\n" + c["body"]).splitlines() if m.group(0) in ln)
            flag("bad", f"commit {c['sha'][:8]} mentions AI: {line.strip()[:70]}")
    for p, ev in ai_hits.items():
        flag("bad", f"AI tool file in history: {p} ({', '.join(ev[:4])})")
    gi = git("show", "HEAD:.gitignore", cwd=repo, check=False)
    hidden = [ln for ln in gi.splitlines() if AI_PATHS.search(ln.strip().lstrip("/!*"))]
    if hidden:
        flag("bad", f".gitignore hides AI files: {', '.join(hidden)}")

    bins = sorted({b for c in mine for b in c["binaries"]})
    junk = sorted({p for c in mine for st, *ps in c["files"] for p in ps
                   if re.search(r"\.(o|d|asm|sym|img)$|(^|/)(kernel/kernel|_\w+)$", p)})
    if bins or junk:
        flag("info", f"build artifacts/binaries committed: {', '.join((bins + junk)[:6])}")

    changed = _functions(repo)
    touched = [f["path"] for f in changed if f["path"] in cfg["tests"].get("xv6_protected", [])]
    if touched:
        flag("bad", f"modified test file(s): {', '.join(touched)} (tests run with the template's copies)")
    # The frozen tests must only appear in the initial commit. Suffix match so a
    # copy under a nested folder (later moved to the root) is caught too.
    for f in cfg["tests"].get("xv6_frozen", []):
        tpl_blob = git("rev-parse", f"refs/viva/template:{f}", cwd=repo, check=False).strip()
        hits, edited = [], False
        for c in mine:
            for st, *paths in c["files"]:
                if not any(p == f or p.endswith("/" + f) for p in paths):
                    continue
                hits.append(f"{st[0]} {c['sha'][:8]}")
                # D leaves no blob; A/M/R/C: the version this commit left behind
                blob = "" if st[0] == "D" else git(
                    "rev-parse", f"{c['sha']}:{paths[-1]}", cwd=repo, check=False).strip()
                edited |= blob != tpl_blob
        if hits:
            what = "content changed" if edited else "content always identical to the template"
            flag("bad" if edited else "warn",
                 f"{f.rsplit('/', 1)[-1]} in {len(hits)} commit(s) after the initial one "
                 f"({', '.join(hits[:4])}{' ...' if len(hits) > 4 else ''}): {what}")
    rules = cfg.get("flags", {})
    if rules.get("banned"):
        banned = git("grep", "-nIE", rules["banned"], "HEAD", "--", *rules.get("banned_paths", []), cwd=repo, check=False)
        hits = [ln.split(":", 1)[1] for ln in banned.splitlines()
                if not ln.split(":", 3)[-1].lstrip().startswith(("//", "/*", "*"))]
        for line in hits[:5]:
            flag("bad", "banned API? " + line[:90])
        if len(hits) > 5:
            flag("bad", f"banned API? ... and {len(hits) - 5} more")
    in_head = git("ls-tree", "-r", "--name-only", "HEAD", cwd=repo).splitlines()
    if rules.get("banned_files"):
        for path in [p for p in in_head if re.search(rules["banned_files"], p)][:3]:
            flag("bad", f"only C is allowed: {path}")
    for name in rules.get("required", []):
        if name not in in_head:
            flag("warn", f"no {name} at the repo root")

    emails = sorted({c["email"] for c in mine})
    if len(emails) > 2:
        flag("info", f"{len(emails)} author emails: {', '.join(emails)}")

    ai_files, links = ai_links(repo)
    if not ai_files:
        flag("warn", "no AI-usage file")
    elif not links and not any(f not in tpl_files or f in {c["path"] for c in changed} for f in ai_files):
        flag("warn", "AI-usage file untouched from template")
    elif not links:
        flag("info", "AI-usage file has no links")

    return {"head": git("rev-parse", "HEAD", cwd=repo).strip(), "branch": branch, "url": meta["url"],
            "last_push": last.isoformat() if last else None, "late_days": late,
            "n_pushes": len(meta["pushes"]), "n_commits": len(head_mine), "emails": emails,
            "frac_committed": fc, "frac_pushed": fp, "commits": rows, "changed": changed,
            "ai_files": ai_files, "links": links,
            "flags": sorted(flags, key=lambda f: ["bad", "warn", "info"].index(f[0]))}


def load_analysis(cfg, roll):
    f = sdir(cfg, roll) / "analysis.json"
    return json.loads(f.read_text()) if f.exists() else {"missing": True}


