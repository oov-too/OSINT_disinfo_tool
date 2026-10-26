#!/usr/bin/env python3
"""The members file of a ledger project (phase 7a of tools/platform-plan.md, 2026-10-22; "Research group": rulings binding only from
members the pack names; member identity from a members file and the OS user; the launcher recorded in note metadata).

The file is <project>/members.toml:

    [members]
    version = 1
    updated = "2026-10-22"

    [[member]]
    name = "A. Researcher"           # as the person wants to be named in rulings and run logs
    os_user = "aresearcher"          # the operating-system login on the group's machines (one per machine allowed: a list)
    roles = ["administrator", "project-manager", "launcher"]
    added = "2026-10-22"
    added_by = "A. Researcher"

Roles:
    administrator     installs and configures (setup stage 0); the only role that may re-enter stage 0 through /settings
    project-manager   makes rulings: re-enters stages 1 to 8 through /settings; answers setup's stages 1 to 8
    launcher          launches intakes, narrative runs, attacks and reports
A member may hold several roles. An administrator may also rule and launch; a project manager may also launch.

Who is acting is the OS user (getpass.getuser(), or $LEDGER_USER where a shared service account runs Claude Code) matched against
`os_user`. A skill calls `check` before a ruling or a launch; an unknown OS user, or a known one without the role, is refused with
the reason, and the skill stops.

    python3 tools/ledger/members.py whoami [--project P]
    python3 tools/ledger/members.py check --action rule|launch|administer [--stage N] [--project P]   exit 0 allowed, 1 refused
    python3 tools/ledger/members.py add --name NAME --os-user USER --roles r1,r2 [--project P]          (an administrator or project manager)
    python3 tools/ledger/members.py list [--project P]
    python3 tools/ledger/members.py stamp <note.md> --run LABEL [--project P]                         the launcher row in the note's metadata
"""
import datetime, getpass, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path: sys.path.insert(0, os.path.dirname(HERE))
from ledger.acquire import _toml as T
from ledger import notes as LN

FILE = "members.toml"
ROLES = ("administrator", "project-manager", "launcher")
ACTIONS = {
    "administer": {"administrator"},
    "rule": {"administrator", "project-manager"},
    "launch": {"administrator", "project-manager", "launcher"},
}
LAUNCHER_KEY = "Launched by"


class Refused(Exception):
    """A member check that failed; str() is the reason the skill shows."""


def today(): return datetime.date.today().isoformat()


def os_user():
    return os.environ.get("LEDGER_USER") or getpass.getuser()


def path(project): return os.path.join(project, FILE)


def load(project):
    """{"members": {...}, "member": [...]}; an empty file form when the file is absent."""
    p = path(project)
    if not os.path.isfile(p): return {"members": {"version": 1, "updated": ""}, "member": []}
    d = T.loads(LN.read_text(p))
    d.setdefault("members", {"version": 1}); d.setdefault("member", [])
    for m in d["member"]:
        if isinstance(m.get("os_user"), str): m["os_user"] = [m["os_user"]]
    return d


def save(project, d):
    d = {"__comment__": "members.toml: who may rule, launch and administer in this ledger project (tools/ledger/members.py).\n"
                        "Written by /setup stage 0 and 7 and by `members.py add`; read before every ruling and launch.",
         "members": dict(d["members"], updated=today()),
         "member": [{k: v for k, v in m.items() if v not in (None, "")} for m in d["member"]]}
    LN.write_text(path(project), T.dumps(d))
    return path(project)


def validate(member):
    probs = []
    if not str(member.get("name", "")).strip(): probs.append("a member needs a name")
    users = member.get("os_user") or []
    if isinstance(users, str): users = [users]
    if not users or not all(re.fullmatch(r"[A-Za-z0-9._\\@-]+", u) for u in users): probs.append(f"{member.get('name')}: os_user must be one or more login names")
    bad = [r for r in member.get("roles", []) if r not in ROLES]
    if bad or not member.get("roles"): probs.append(f"{member.get('name')}: roles must be among {', '.join(ROLES)} (got {member.get('roles')})")
    return probs


def find(project, user=None):
    """The member whose os_user includes `user` (default: this OS user), or None."""
    user = (user or os_user()).lower()
    for m in load(project)["member"]:
        if user in [u.lower() for u in m.get("os_user", [])]: return m
    return None


def whoami(project):
    m = find(project)
    return {"os_user": os_user(), "member": m["name"] if m else None, "roles": m.get("roles", []) if m else []}


def check(project, action, stage=None, user=None):
    """The member allowed to take `action` (administer, rule, launch), or Refused. A ruling on stage 0 needs the administrator."""
    if action not in ACTIONS: raise ValueError(f"unknown action {action}; actions: {', '.join(ACTIONS)}")
    need = ACTIONS["administer"] if (action == "rule" and stage is not None and int(stage) == 0) else ACTIONS[action]
    if not os.path.isfile(path(project)):
        raise Refused(f"no members file at {path(project)}: run /setup (stage 0 records the administrator, stage 7 the members)")
    m = find(project, user)
    who = user or os_user()
    if not m: raise Refused(f"the OS user {who!r} is not in {FILE}: rulings and launches are binding only from named members; ask the administrator to add you")
    if not set(m.get("roles", [])) & need:
        raise Refused(f"{m['name']} ({who}) holds {', '.join(m.get('roles', [])) or 'no role'}; {action}" + (f" on stage {stage}" if stage is not None else "")
                      + f" needs {' or '.join(sorted(need))}")
    return m


def author(project, user=None):
    """The ruling author line: '<name> (<os user>)' for a member, else 'not a member (<os user>)'."""
    m = find(project, user); u = user or os_user()
    return f"{m['name']} ({u})" if m else f"not a member ({u})"


def add(project, name, os_users, roles, added_by=None):
    d = load(project)
    if isinstance(os_users, str): os_users = [u.strip() for u in os_users.split(",") if u.strip()]
    if isinstance(roles, str): roles = [r.strip() for r in roles.split(",") if r.strip()]
    member = {"name": name.strip(), "os_user": os_users, "roles": roles, "added": today(), "added_by": added_by or author(project)}
    probs = validate(member)
    if probs: raise ValueError("; ".join(probs))
    for m in d["member"]:
        if m["name"].lower() == member["name"].lower():
            m["os_user"] = sorted(set(m.get("os_user", [])) | set(os_users)); m["roles"] = [r for r in ROLES if r in set(m.get("roles", [])) | set(roles)]
            save(project, d); return m
        clash = set(u.lower() for u in m.get("os_user", [])) & set(u.lower() for u in os_users)
        if clash: raise ValueError(f"OS user {', '.join(sorted(clash))} already belongs to {m['name']}")
    d["member"].append(member); save(project, d)
    return member


def set_members(project, members, added_by=None):
    """Replace the member list (setup stage 7); every entry validated; at least one administrator and one project manager kept."""
    probs = []
    clean = []
    for m in members:
        m = dict(m)
        if isinstance(m.get("os_user"), str): m["os_user"] = [m["os_user"]]
        if isinstance(m.get("roles"), str): m["roles"] = [r.strip() for r in m["roles"].split(",") if r.strip()]
        m.setdefault("added", today()); m.setdefault("added_by", added_by or author(project))
        probs += validate(m); clean.append(m)
    roles = {r for m in clean for r in m.get("roles", [])}
    if "administrator" not in roles: probs.append("the members file needs an administrator")
    if "project-manager" not in roles: probs.append("the members file needs a project manager (who rules)")
    if probs: raise ValueError("; ".join(probs))
    d = load(project); d["member"] = clean
    return save(project, d)


def launcher_row(member, run, date=None):
    """The metadata row an intake writes into its note: who launched it, the run and the date."""
    return f"| **{LAUNCHER_KEY}** | {member['name']}, run {run}, {date or today()} |"


def stamp(note, member, run, date=None):
    """Write the launcher row into a note's metadata table (after its last metadata row), once; returns True when it was added.
    The intake's finisher calls this (or the orchestrator, at hand-back); it never changes another row."""
    lines = LN.read_lines(note)
    if any(l.startswith(f"| **{LAUNCHER_KEY}** |") for l in lines): return False
    last = None
    for i, l in enumerate(lines[:120]):
        if LN.META_TEXT_RE.match(l): last = i
        elif last is not None and not l.startswith("|"): break
    if last is None: raise ValueError(f"{note}: no metadata table (| **Key** | value | rows) to stamp")
    lines.insert(last + 1, launcher_row(member, run, date))
    LN.write_lines(note, lines)
    return True


def _project(a):
    return os.path.abspath(a.project or os.environ.get("LEDGER_ROOT") or os.getcwd())


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="The members file of a ledger project")
    ap.add_argument("cmd", choices=["whoami", "check", "add", "list", "stamp"]); ap.add_argument("note", nargs="?")
    ap.add_argument("--project"); ap.add_argument("--action"); ap.add_argument("--stage", type=int)
    ap.add_argument("--name"); ap.add_argument("--os-user"); ap.add_argument("--roles"); ap.add_argument("--run")
    a = ap.parse_args(argv); project = _project(a)
    if a.cmd == "whoami":
        w = whoami(project); print(f"{w['os_user']}: {w['member'] or 'not a member'}" + (f" ({', '.join(w['roles'])})" if w["roles"] else "")); return 0
    if a.cmd == "list":
        for m in load(project)["member"]: print(f"{m['name']}\t{','.join(m.get('os_user', []))}\t{','.join(m.get('roles', []))}\t{m.get('added', '')}")
        return 0
    if a.cmd == "check":
        try:
            m = check(project, a.action, a.stage); print(f"allowed: {m['name']} may {a.action}" + (f" (stage {a.stage})" if a.stage is not None else "")); return 0
        except Refused as e:
            print(f"refused: {e}"); return 1
    if a.cmd == "add":
        if os.path.isfile(path(project)):
            try: check(project, "rule")
            except Refused as e: print(f"refused: {e}"); return 1
        print(add(project, a.name, a.os_user, a.roles)); return 0
    if a.cmd == "stamp":
        try: m = check(project, "launch")
        except Refused as e: print(f"refused: {e}"); return 1
        print("stamped" if stamp(a.note, m, a.run) else "already stamped"); return 0


if __name__ == "__main__":
    sys.exit(main())
