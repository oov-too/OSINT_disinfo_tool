#!/usr/bin/env python3
"""The one-writer lock of a ledger run (tools/platform-plan.md, phase 7: "one writer per note set enforced by a lock file per run";
Portability: "the one-writer lock is an atomic directory create"). A skill takes the lock before it writes notes or pages and
releases it at hand-back; a second run on the same set is refused and told who holds it.

    python3 lock.py acquire <set> --run LABEL [--wip wip/<task>] [--project P]   exit 0 taken, 1 held by another run (printed)
    python3 lock.py release <set> --run LABEL [--project P]                      exit 0 released, 1 not held by this run
    python3 lock.py list [--project P]

<set> names what the run writes: a note set (`notes`), a page (`page-<slug>`), the pack (`pack`). The lock is the directory
wip/.locks/<set>/ (os.mkdir is atomic on local disks and on SMB and NFS shares) with lock.json inside: run, member, OS user, machine,
time, wip. The database hook builds into the wip's check.db while a lock names it."""
import datetime, getpass, json, os, platform, re, sys


def root(given=None):
    d = os.path.abspath(given or os.environ.get("LEDGER_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, "ledger.toml")): return d
        up = os.path.dirname(d)
        if up == d: sys.exit("not inside a ledger project (no ledger.toml)")
        d = up


def member(project):
    user = os.environ.get("LEDGER_USER") or getpass.getuser()
    try:
        import tomllib
        with open(os.path.join(project, "members.toml"), "rb") as f: ms = tomllib.load(f).get("member", [])
        for m in ms:
            users = m.get("os_user", []); users = [users] if isinstance(users, str) else users
            if user.lower() in [u.lower() for u in users]: return m["name"], user
    except Exception:
        pass
    return None, user


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["acquire", "release", "list"]); ap.add_argument("set", nargs="?")
    ap.add_argument("--run"); ap.add_argument("--wip"); ap.add_argument("--project")
    a = ap.parse_args(argv); project = root(a.project); base = os.path.join(project, "wip", ".locks")
    os.makedirs(base, exist_ok=True)
    if a.cmd == "list":
        for d in sorted(os.listdir(base)):
            try:
                with open(os.path.join(base, d, "lock.json"), encoding="utf-8") as f: print(d, json.dumps(json.load(f), ensure_ascii=False))
            except Exception:
                print(d, "(no lock.json)")
        return 0
    if not a.set or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.set): sys.exit("a set name is lower case letters, digits and hyphens")
    d = os.path.join(base, a.set)
    if a.cmd == "acquire":
        try:
            os.mkdir(d)
        except FileExistsError:
            try:
                with open(os.path.join(d, "lock.json"), encoding="utf-8") as f: held = json.load(f)
            except Exception:
                held = {"run": "unknown (no lock.json yet)"}
            print(json.dumps({"refused": f"{a.set} is locked by run {held.get('run')} ({held.get('member') or held.get('os_user')}, since {held.get('time')})", "holder": held}))
            return 1
        name, user = member(project)
        info = {"set": a.set, "run": a.run, "member": name, "os_user": user, "machine": platform.node(),
                "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "wip": a.wip}
        with open(os.path.join(d, "lock.json"), "w", encoding="utf-8", newline="\n") as f: json.dump(info, f, indent=1)
        print(json.dumps({"locked": a.set, "run": a.run})); return 0
    try:
        with open(os.path.join(d, "lock.json"), encoding="utf-8") as f: held = json.load(f)
    except Exception:
        print(json.dumps({"refused": f"{a.set} is not locked"})); return 1
    if held.get("run") != a.run:
        print(json.dumps({"refused": f"{a.set} is held by run {held.get('run')}, not {a.run}"})); return 1
    os.remove(os.path.join(d, "lock.json")); os.rmdir(d)
    print(json.dumps({"released": a.set, "run": a.run})); return 0


if __name__ == "__main__":
    sys.exit(main())
