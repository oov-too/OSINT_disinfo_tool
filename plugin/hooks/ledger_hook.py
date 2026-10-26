#!/usr/bin/env python3
"""The ledger plugin's hooks (hooks/hooks.json): three checks, each run by Python, each reported as advice or as a request to fix,
never as a failed write (tools/platform-plan.md, phase 7: "a failing check never reads as a failed write").

    ledger_hook.py verbatim   PostToolUse on Write|Edit: a note part (wip/<task>/parts/...) or a note (the ledger.toml [sources] notes
                              folders) is checked by tools/verbatim_check.py as its own call; a copied span is reported to the agent as
                              additional context; the write stands
    ledger_hook.py dbbuild    PostToolUse on Write|Edit of a note: tools/build_db.py --report into a check copy (the running task's
                              wip/<task>/check.db when a run lock names one, else .ledger/hook-check.db), never the shared database;
                              a failure is reported as additional context; the write stands
    ledger_hook.py report     SubagentStop of a ledger reading or writing agent: when the agent's last message names its report
                              (a line `report: wip/<task>/report.json` and `form: <form>`), tools/report_check.py runs on it; a failing
                              report keeps the agent running with the check's lines as its next instruction (it fixes the report in
                              place: resumed, never re-run), at most three times, then the agent stops and the person is told

Every mode reads the hook's JSON on stdin, does nothing outside a ledger project (no ledger.toml), and exits 0 unless the script
itself crashes (which Claude Code reports as a non-blocking hook error; the write still stands)."""
import json, os, re, subprocess, sys

MAX_BLOCKS = 3


def project_root(payload):
    for c in (os.environ.get("LEDGER_ROOT"), os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd"), os.getcwd()):
        d = os.path.abspath(c) if c else None
        while d:
            if os.path.isfile(os.path.join(d, "ledger.toml")): return d
            up = os.path.dirname(d)
            if up == d: break
            d = up
    return None


def ledger_toml(root):
    try:
        import tomllib
        with open(os.path.join(root, "ledger.toml"), "rb") as f: return tomllib.load(f)
    except Exception:
        return {}


def rel(root, path):
    p = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    r = os.path.relpath(p, root).replace(os.sep, "/")
    return None if r.startswith("../") else r


def is_part(r): return bool(re.match(r"^wip/[^/]+/parts/.+\.md$", r))


def is_note(root, r):
    dirs = ledger_toml(root).get("sources", {}).get("notes", ["videos", "books"])
    return r.endswith(".md") and any(r.startswith(d.rstrip("/") + "/") and r.count("/") == d.rstrip("/").count("/") + 1 for d in dirs)


def say(event, text):
    """Advice the agent sees beside the tool result; exit 0 (never a hook error, never a failed write)."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text[:9000]}}))
    return 0


def run(root, args, timeout):
    try:
        r = subprocess.run([sys.executable] + args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout} s"


def verbatim(payload, root):
    path = (payload.get("tool_input") or {}).get("file_path")
    r = rel(root, path) if path else None
    if not r or not (is_part(r) or is_note(root, r)): return 0
    tool = os.path.join(root, "tools", "verbatim_check.py")
    if not os.path.isfile(tool): return 0
    rc, out = run(root, [tool, r], 110)
    if rc == 0: return 0
    lines = "\n".join(out.strip().splitlines()[-30:])
    return say("PostToolUse", f"Verbatim check (advisory; the write of {r} stands): tools/verbatim_check.py "
                              f"{'did not finish: ' + out if rc is None else 'found copied spans'}.\n{lines}\n"
                              "Rewrite the named spans in your own words or mark them as quotations, then write the part again.")


def check_db(root):
    """The running task's check.db (a run lock's task file names its wip), else .ledger/hook-check.db; never the shared database."""
    locks = os.path.join(root, "wip", ".locks")
    if os.path.isdir(locks):
        for d in sorted(os.listdir(locks)):
            info = os.path.join(locks, d, "lock.json")
            try:
                with open(info, encoding="utf-8") as f: wip = json.load(f).get("wip")
                if wip: return f"{wip.rstrip('/')}/check.db"
            except Exception:
                continue
    os.makedirs(os.path.join(root, ".ledger"), exist_ok=True)
    return ".ledger/hook-check.db"


def dbbuild(payload, root):
    path = (payload.get("tool_input") or {}).get("file_path")
    r = rel(root, path) if path else None
    if not r or not is_note(root, r): return 0
    tool = os.path.join(root, "tools", "build_db.py")
    if not os.path.isfile(tool): return 0
    db = check_db(root)
    shared = ledger_toml(root).get("database", {}).get("path", "notes.db")
    if os.path.abspath(os.path.join(root, db)) == os.path.abspath(os.path.join(root, shared)): return 0
    rc, out = run(root, [tool, "--report", "--db", db], 580)
    if rc == 0: return 0
    lines = "\n".join(out.strip().splitlines()[-30:])
    return say("PostToolUse", f"Database build into the check copy {db} (advisory; the write of {r} stands) "
                              f"{'did not finish: ' + out if rc is None else 'reported problems'}:\n{lines}")


REPORT_RE = re.compile(r"(?im)^\s*[-*]?\s*report(?:\.json)?\s*:\s*`?([^\s`]+\.json)`?")
FORM_RE = re.compile(r"(?im)^\s*[-*]?\s*form\s*:\s*`?([a-z-]+)`?")


def report(payload, root):
    msg = payload.get("last_assistant_message") or ""
    m = REPORT_RE.search(msg)
    if not m: return 0
    path = m.group(1); form = (FORM_RE.search(msg) or [None, None])[1]
    tool = os.path.join(root, "tools", "report_check.py")
    if not os.path.isfile(tool): return 0
    args = [tool, path] + (["--form", form] if form else []) + ["--pre-sample"]   # an agent's stop comes before the sample phase (2026-10-25)
    rc, out = run(root, args, 110)
    if rc == 0: return 0
    state_dir = os.path.join(root, ".ledger", "hook-state"); os.makedirs(state_dir, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9_-]", "_", str(payload.get("agent_id") or payload.get("session_id") or "agent"))
    sp = os.path.join(state_dir, f"report-{key}.json")
    try:
        with open(sp, encoding="utf-8") as f: n = json.load(f).get("blocks", 0)
    except Exception:
        n = 0
    lines = "\n".join(out.strip().splitlines()[-40:])
    if n < MAX_BLOCKS:
        with open(sp, "w", encoding="utf-8", newline="\n") as f: json.dump({"blocks": n + 1, "report": path}, f)
        print(json.dumps({"decision": "block", "reason": f"The report check failed on {path} (form {form or 'default'}); fix the report in place and reply again "
                                                          f"with the same report and form lines. This is check {n + 1} of {MAX_BLOCKS}.\n{lines}"}))
        return 0
    print(json.dumps({"systemMessage": f"ledger: the report {path} still fails tools/report_check.py after {MAX_BLOCKS} fixes; the orchestrator "
                                       f"receives it with these lines:\n{lines}"}))
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    root = project_root(payload)
    if not root: return 0
    return {"verbatim": verbatim, "dbbuild": dbbuild, "report": report}.get(mode, lambda p, r: 0)(payload, root)


if __name__ == "__main__":
    sys.exit(main())
