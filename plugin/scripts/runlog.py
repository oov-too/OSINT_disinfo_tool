#!/usr/bin/env python3
"""The run log of a ledger skill (tools/platform-plan.md, phase 7: "reproducible run logs (model, effort, brief and pack versions,
units read)"). Every skill appends a start line and an end line to wip/runs/<run>.log; the status page reads them.

    python3 runlog.py start <run> --skill intake [--briefs wip/<run>/briefs] [--project P]
    python3 runlog.py note <run> "<text>" [--project P]
    python3 runlog.py end <run> [--units N] [--agents N] [--deaths N] [--resumes N] [--cost "<from ledger measure usage>"] [--project P]

A start line records the member and OS user, the machine, the model policy of ledger.toml [models], the pack's name and version, the
SHA-256 of the pack's pack.toml and briefs/slots.toml, and the SHA-256 of every rendered brief under --briefs. One JSON object per line,
UTF-8, LF."""
import datetime, getpass, glob, hashlib, json, os, platform, sys


def root(given=None):
    d = os.path.abspath(given or os.environ.get("LEDGER_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, "ledger.toml")): return d
        up = os.path.dirname(d)
        if up == d: sys.exit("not inside a ledger project (no ledger.toml)")
        d = up


def sha(p):
    try:
        with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return "missing"


def load(p):
    import tomllib
    try:
        with open(p, "rb") as f: return tomllib.load(f)
    except OSError:
        return {}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["start", "note", "end"]); ap.add_argument("run"); ap.add_argument("text", nargs="?")
    ap.add_argument("--skill"); ap.add_argument("--briefs"); ap.add_argument("--project")
    for k in ("units", "agents", "deaths", "resumes"): ap.add_argument(f"--{k}", type=int)
    ap.add_argument("--cost")
    a = ap.parse_args(argv); project = root(a.project)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    led = load(os.path.join(project, "ledger.toml")); pack = led.get("pack", {}).get("path", "")
    user = os.environ.get("LEDGER_USER") or getpass.getuser()
    rec = {"time": now, "event": a.cmd, "run": a.run, "os_user": user}
    if a.cmd == "start":
        pk = load(os.path.join(project, pack, "pack.toml")).get("pack", {}) if pack else {}
        rec.update(skill=a.skill, machine=platform.node(), os=f"{platform.system()} {platform.release()}", models=led.get("models", {}),
                   pack=f"{pk.get('name', '')} {pk.get('version', '')}".strip(), pack_toml=sha(os.path.join(project, pack, "pack.toml")),
                   slots=sha(os.path.join(project, pack, "briefs", "slots.toml")))
        if a.briefs:
            rec["briefs"] = {os.path.relpath(p, os.path.join(project, a.briefs)).replace(os.sep, "/"): sha(p)
                             for p in sorted(glob.glob(os.path.join(project, a.briefs, "**", "*.md"), recursive=True))}
    elif a.cmd == "note":
        rec["note"] = a.text
    else:
        rec.update({k: getattr(a, k) for k in ("units", "agents", "deaths", "resumes", "cost") if getattr(a, k) is not None})
    os.makedirs(os.path.join(project, "wip", "runs"), exist_ok=True)
    with open(os.path.join(project, "wip", "runs", f"{a.run}.log"), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"logged {a.cmd} of {a.run}"); return 0


if __name__ == "__main__":
    sys.exit(main())
