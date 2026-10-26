#!/usr/bin/env python3
"""/settings (phase 7a of tools/platform-plan.md, 2026-10-22): re-enter a setup stage, show its current values, rewrite its file,
append a dated, attributed ruling, and queue what the change owes; never rewrite an existing note.

Who may: the project manager (a members-file role, tools/ledger/members.py) for stages 1 to 8; stage 0 only the administrator.

What a change owes (queued in <project>/owed.md, one row each, never run silently):
    stage 1  the detection re-run over the hold with the new requirements (PIR terms surface entries), the status page's PIR section
    stage 2  a re-scan of the database against the new mapping (rescan, then run --records for new and changed records)
    stage 3  retroactive forthrightness audits for every note under a newly audited subject (listed one row per note); the source balance
             (`ledger analyse balance --write-kinds`) when the circles, quota or compilers change; the era pages when the eras change
    stage 4  the detection re-run when flags, dropped names or ledgered speakers change; a speaker ledger page per new ledgered speaker
    stage 5  the canon controls (witness comparison) for a new or changed canon text; the codebook decoder test
    stage 6  the lens tests (`ledger analyse lens test`) for a new or changed lens
    stage 7  CLAUDE.md regenerated (done at once); the first-utterance tests when the threshold catalyst changes
    every stage: `python3 tools/ledger/briefs.py render --check` over every template

    python3 tools/ledger/settings.py show N [--project P]
    python3 tools/ledger/settings.py set N --answers changes.json [--project P]     exit 0 done, 3 a question needs an answer, 4 refused
    python3 tools/ledger/settings.py owed [--project P]                              the open rows of owed.md
    python3 tools/ledger/settings.py propose N --answers changes.json [--project P] a launcher's proposal: ruling status `proposed`, nothing applied
    python3 tools/ledger/settings.py publish-check viewer|map|docs [--project P]    exit 0 publish, 1 local file only (the reason printed)
    python3 tools/ledger/settings.py published viewer|map|docs [--project P]        record it in pack.toml [display.publish] last_published

Rulings go to rulings.md, one markdown table: # | Date | Author | Stage | Ruling | Effect | Status, the status one of open, pending,
proposed, adopted, withdrawn (tools/build_status.py counts open, pending and proposed). Publishing artifacts (viewer, map, docs) is the
end user's choice, off by default (setup stage 7, pack.toml [display.publish] enabled, targets, last_published); publish-check also
requires a model route with artifacts and claude.ai reachable.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path: sys.path.insert(0, os.path.dirname(HERE))
from ledger import notes as LN
from ledger import members as M
from ledger import setup_stages as SU


def show(project, n):
    """The stage's file (answers, result) and the pack values it set."""
    s = SU.Setup(project, SU.Answers({}))
    if not s.done(n): return {"stage": n, "title": SU.STAGES[n], "done": False}
    st = s.stage(n)
    out = {"stage": n, "title": SU.STAGES[n], "done": True, "completed": st.get("stage", {}).get("completed"), "by": st.get("stage", {}).get("by"),
           "answers": st.get("answers", {}), "result": st.get("result", {})}
    if s.pack_name() and os.path.isfile(s.pack_dir("pack.toml")):
        pk = s.pack(); keys = {1: ["pirs"], 2: ["archives", "metadata"], 3: ["subjects", "audit", "eras", "circles", "source_kinds"],
                               4: ["actors", "speakers", "objects"], 5: ["canon", "codebook"], 6: ["lenses"], 7: ["catalysts"], 8: []}.get(n, [])
        out["pack"] = {k: pk.get(k) for k in keys if k in pk}
        out["ledger"] = {k: s.ledger().get(k) for k in (["models", "database", "acquire"] if n == 0 else ["models", "policy"] if n == 7 else [])}
    return out


def _diff(old, new, prefix=""):
    """[(key, old, new)] for every changed leaf."""
    out = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if isinstance(a, dict) and isinstance(b, dict): out += _diff(a, b, f"{prefix}{k}.")
        elif a != b: out.append((f"{prefix}{k}", a, b))
    return out


def _notes_under(project, subjects):
    """Notes whose Subjects metadata row names one of `subjects` (by slug or a link to subjects/<slug>.md)."""
    led = SU.load_toml(os.path.join(project, "ledger.toml"))
    dirs = led.get("sources", {}).get("notes", ["videos", "books"])
    hits = []
    for d in dirs:
        base = os.path.join(project, d)
        if not os.path.isdir(base): continue
        for f in sorted(os.listdir(base)):
            if not f.endswith(".md"): continue
            p = os.path.join(base, f)
            meta = {k: v for k, v, _ in LN.meta_rows(LN.read_lines(p, errors="replace"))}
            subj = meta.get("Subjects", "")
            for s in subjects:
                if re.search(r"(?<![a-z0-9-])" + re.escape(s) + r"(?![a-z0-9-])", subj): hits.append((f"{d}/{f}", s)); break
    return hits


def owed_for(project, n, old_stage, new_stage, old_pack, new_pack):
    """[(what, command)] the change owes."""
    o, nw = old_stage.get("result", {}), new_stage.get("result", {})
    out = []
    if n == 1 and (old_pack.get("pirs") != new_pack.get("pirs") or o.get("referent") != nw.get("referent")):
        out.append(("the detection re-run over the hold with the new requirements (PIR terms surface entries; nothing placed)",
                    "python3 tools/ledger/setup_stages.py stage 2 --project . --answers <answers with 2.hold_now true>  (re-scans; or: re-run stage 4)"))
        out.append(("the status page's PIR section", "/status"))
    if n == 2:
        out.append(("a re-scan of their database against the new mapping", "python3 tools/ledger/acquire/database.py rescan setup/mapping.toml"))
        out.append(("new and changed records queued for intake", "python3 tools/ledger/acquire/database.py rescan setup/mapping.toml --records"))
    if n == 3:
        added = sorted(set(new_pack.get("subjects", {}).get("audited", [])) - set(old_pack.get("subjects", {}).get("audited", [])))
        for note, s in _notes_under(project, added):
            out.append((f"a retroactive {SU.audit_name(new_pack)} of {note} (newly audited subject {s}); listed, never run silently", f"/intake --audit-only {note}"))
        if added and not _notes_under(project, added):
            out.append((f"retroactive {SU.audit_name(new_pack)}s for the newly audited subject(s) {', '.join(added)}: no note is under them yet", "none"))
        if old_pack.get("circles") != new_pack.get("circles") or old_pack.get("source_kinds", {}).get("compilers") != new_pack.get("source_kinds", {}).get("compilers"):
            out.append(("the source balance and the quota ledger with the new circles, quota or compilers", "ledger analyse balance --write-kinds"))
        if old_pack.get("eras") != new_pack.get("eras"):
            out.append(("the consolidated era pages and the timeline with the new era boundaries", "ledger build timeline"))
    if n == 4:
        oa, na = old_pack.get("actors", {}), new_pack.get("actors", {})
        if oa.get("flagged") != na.get("flagged") or o.get("dropped") != nw.get("dropped"):
            out.append(("the detection re-run (flags and dropped names changed)", "python3 tools/ledger/setup_stages.py stage 4 --project . (re-reads setup/scan.json)"))
        osp = {x["name"] for x in old_pack.get("speakers", {}).get("ledgered", [])}; nsp = {x["name"] for x in new_pack.get("speakers", {}).get("ledgered", [])}
        for sp in sorted(nsp - osp):
            out.append((f"a speaker ledger page for {sp} built from the notes already held", f"/report --speaker-ledger \"{sp}\""))
    if n == 5:
        if old_pack.get("canon") != new_pack.get("canon"):
            out.append(("the canon controls: hold the new or changed texts in units and run the witness comparison", "ledger acquire canon; ledger analyse canon-control"))
        if old_pack.get("codebook") != new_pack.get("codebook"):
            out.append(("the codebook decoder test over the held transcripts (each decode a lead naming its code)", "ledger analyse codebook --test"))
    if n == 6 and old_pack.get("lenses") != new_pack.get("lenses"):
        for inst in new_pack.get("lenses", {}).get("instance", []):
            out.append((f"the lens tests for {inst['id']} (the database tests T1 to T6 with counterexamples)", f"ledger analyse lens test {inst['id']}"))
    if n == 7 and old_pack.get("catalysts", {}).get("threshold_date") != new_pack.get("catalysts", {}).get("threshold_date"):
        out.append(("the first-utterance tests against the new threshold catalyst", "ledger analyse first-utterance --apply"))
    out.append(("the brief templates rendered against the changed pack (no slot may be missing)", "python3 tools/ledger/briefs.py render --check --project ."))
    return out


def queue_owed(project, n, items, author):
    p = os.path.join(project, "owed.md")
    if not os.path.isfile(p):
        SU.write(p, "# Owed\n\nWhat a /settings change owes: each row is run by the group or a skill and its status changed to done there; "
                    "nothing here runs silently and no existing note is rewritten by /settings.\n\n"
                    "| # | Date | Raised by | Stage | Owed | Command | Status |\n|---|---|---|---|---|---|---|\n")
    last = max([int(m.group(1)) for m in re.finditer(r"^\| (\d+) \|", LN.read_text(p), re.M)] or [0])
    rows = [f"| {last + i} | {SU.today()} | {SU.md_cell(author)} | {n} | {SU.md_cell(what)} | `{SU.md_cell(cmd)}` | open |" for i, (what, cmd) in enumerate(items, 1)]
    if rows: LN.append_text(p, "\n".join(rows) + "\n")
    return len(rows)


def open_owed(project):
    p = os.path.join(project, "owed.md")
    if not os.path.isfile(p): return []
    return [l for l in LN.read_lines(p) if re.match(r"^\| \d+ \|", l) and l.rstrip().endswith("| open |")]


def reenter(project, n, changes, user=None, launcher=None, interactive=False):
    """Re-enter stage n with `changes` (answers keyed as setup asks them). Returns {diff, rulings, owed}. Raises M.Refused, SU.NeedAnswer."""
    project = os.path.abspath(project)
    member = M.check(project, "rule", stage=n, user=user)
    s = SU.Setup(project, SU.Answers(dict(changes), interactive=interactive, use_defaults=True), launcher=launcher)
    if not s.done(n): raise SU.Refusal(f"stage {n} has not been run yet: run /setup first (next stage: {s.next_stage()})")
    old_stage = s.stage(n)
    old_pack = s.pack() if s.pack_name() and os.path.isfile(s.pack_dir("pack.toml")) else {}
    notes_before = _note_hashes(project)
    # the ruling's author is the member now acting, so the stage is re-run as that member
    saved = os.environ.get("LEDGER_USER")
    if user: os.environ["LEDGER_USER"] = user
    try:
        s.rerun(n)
    finally:
        if user:
            if saved is None: os.environ.pop("LEDGER_USER", None)
            else: os.environ["LEDGER_USER"] = saved
    new_stage = s.stage(n)
    new_pack = s.pack() if s.pack_name() and os.path.isfile(s.pack_dir("pack.toml")) else {}
    diff = _diff({"answers": old_stage.get("answers", {}), "result": old_stage.get("result", {})},
                 {"answers": new_stage.get("answers", {}), "result": new_stage.get("result", {})})
    # the stage's own rulings were appended by the re-run; add one summary ruling naming what changed and what it supersedes
    supersedes = f"stage {n} of {old_stage.get('stage', {}).get('completed')} by {old_stage.get('stage', {}).get('by')}"
    lines = [f"/settings: stage {n} re-entered by {member['name']}; changed " + ("; ".join(f"{k}: {json.dumps(a, ensure_ascii=False)} -> {json.dumps(b, ensure_ascii=False)}"
                                                                                       for k, a, b in diff if k.startswith("answers.")) or "nothing")]
    owed = owed_for(project, n, old_stage, new_stage, old_pack, new_pack)
    q = queue_owed(project, n, owed, M.author(project, user))
    s.record_rulings(n, lines, effect=f"supersedes {supersedes}; setup/stage-{n}.toml rewritten; {q} item(s) owed (owed.md); no note rewritten",
                     status="adopted")
    s.write_claude_md()
    after = _note_hashes(project)
    if after != notes_before: raise RuntimeError("a note changed during /settings: this must never happen (report it)")
    return {"stage": n, "member": member["name"], "diff": diff, "owed": owed, "owed_rows": q}


def _note_hashes(project):
    import hashlib
    led = SU.load_toml(os.path.join(project, "ledger.toml"))
    out = {}
    for d in led.get("sources", {}).get("notes", ["videos", "books"]):
        base = os.path.join(project, d)
        if os.path.isdir(base):
            for f in sorted(os.listdir(base)):
                if f.endswith(".md"):
                    with open(os.path.join(base, f), "rb") as fh: out[f"{d}/{f}"] = hashlib.sha256(fh.read()).hexdigest()
    return out


def propose(project, n, changes, user=None):
    """A member without the right to rule (a launcher) proposes a change: the changes are saved under setup/proposals/, a ruling with
    status `proposed` is appended (not binding; the status page lists it as open), and nothing else changes. A project manager adopts
    it with `set N --answers <the saved file>`."""
    project = os.path.abspath(project)
    member = M.check(project, "launch", user=user)
    s = SU.Setup(project, SU.Answers({}))
    if not s.done(n): raise SU.Refusal(f"stage {n} has not been run yet: nothing to change")
    d = os.path.join(project, "setup", "proposals"); os.makedirs(d, exist_ok=True)
    k = len([f for f in os.listdir(d) if f.endswith(".json")]) + 1
    path = os.path.join(d, f"{SU.today()}-stage-{n}-{k:03d}.json")
    SU.write_json(path, {"answers": changes, "proposed_by": M.author(project, user), "stage": n, "date": SU.today()})
    rel = os.path.relpath(path, project).replace(os.sep, "/")
    saved = os.environ.get("LEDGER_USER")
    if user: os.environ["LEDGER_USER"] = user
    try:
        s.record_rulings(n, [f"proposal by {member['name']}: " + "; ".join(f"{q}: {json.dumps(v, ensure_ascii=False)}" for q, v in changes.items())],
                         effect=f"none until adopted: a project manager runs `settings.py set {n} --answers {rel}`", status="proposed")
    finally:
        if user:
            if saved is None: os.environ.pop("LEDGER_USER", None)
            else: os.environ["LEDGER_USER"] = saved
    s.write_claude_md()
    return {"stage": n, "proposal": rel, "status": "proposed"}


# ---- publishing artifacts (owner ruling, 2026-10-22): the end user's choice, off by default; local files always
def publish_settings(project):
    s = SU.Setup(project, SU.Answers({}))
    pk = s.pack() if s.pack_name() and os.path.isfile(s.pack_dir("pack.toml")) else {}
    return s, pk, (pk.get("display", {}).get("publish") or {"enabled": False, "targets": [], "last_published": ""})


def claude_ai_reachable(timeout=3):
    import socket
    try:
        socket.create_connection(("claude.ai", 443), timeout=timeout).close(); return True
    except OSError:
        return False


def publish_check(project, target):
    """Whether a skill may publish `target` (viewer, map, docs) as an artifact: the setting must allow it, the model route must be one with
    artifacts (Claude for Enterprise or the Anthropic API; provider and gateway routes have none), and claude.ai must be reachable.
    Otherwise the skill writes the local file only and says why."""
    project = os.path.abspath(project)
    _, pk, pub = publish_settings(project)
    route = SU.load_toml(os.path.join(project, "ledger.toml")).get("models", {}).get("route", "")
    why = None
    if target not in SU.PUBLISH_TARGETS: why = f"unknown target {target!r} (targets: {', '.join(SU.PUBLISH_TARGETS)})"
    elif not pub.get("enabled"): why = "publishing artifacts is off for this project (setup stage 7, /settings 7)"
    elif target not in pub.get("targets", []): why = f"{target} is not among the publish targets {pub.get('targets', [])}"
    elif route not in ("anthropic", "enterprise"): why = f"the model route ({route or 'unknown'}) has no artifacts; provider and gateway routes publish nothing"
    elif not claude_ai_reachable(): why = "claude.ai is not reachable from this machine"
    return {"target": target, "publish": why is None, "reason": why or "allowed", "last_published": pub.get("last_published", "")}


def published(project, target):
    """Record a publish in pack.toml [display.publish] last_published (date and target)."""
    s, pk, pub = publish_settings(os.path.abspath(project))
    if not pk: raise SU.Refusal("no setup pack in this folder (setup stage 1 writes it): nothing to record")
    pk.setdefault("display", {})["publish"] = dict(pub, last_published=f"{SU.today()} {target}")
    s.write_pack(pk, None)
    return pk["display"]["publish"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="/settings: re-enter a setup stage")
    ap.add_argument("cmd", choices=["show", "set", "propose", "owed", "publish-check", "published"]); ap.add_argument("n", nargs="?")
    ap.add_argument("--project", default=os.environ.get("LEDGER_ROOT") or os.getcwd()); ap.add_argument("--answers")
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args(argv); project = os.path.abspath(a.project)
    if a.cmd in ("publish-check", "published"):
        if not a.n: ap.error(f"{a.cmd} needs a target: {', '.join(SU.PUBLISH_TARGETS)}")
        try:
            r = publish_check(project, a.n) if a.cmd == "publish-check" else published(project, a.n)
        except SU.Refusal as e:
            print(json.dumps({"refused": str(e)}, ensure_ascii=False)); return 4
        print(json.dumps(r, ensure_ascii=False)); return 0 if a.cmd == "published" or r["publish"] else 1
    a.n = int(a.n) if a.n is not None else None
    if a.cmd == "propose":
        if a.n is None or not a.answers: ap.error("propose needs a stage number and --answers")
        with open(a.answers, encoding="utf-8") as f: d = json.load(f)
        try:
            print(json.dumps(propose(project, a.n, d.get("answers", d)), ensure_ascii=False)); return 0
        except (M.Refused, SU.Refusal) as e:
            print(json.dumps({"refused": str(e)}, ensure_ascii=False)); return 4
    if a.cmd == "show":
        if a.n is None: ap.error("show needs a stage number")
        print(json.dumps(show(project, a.n), indent=1, ensure_ascii=False, default=str)); return 0
    if a.cmd == "owed":
        for l in open_owed(project): print(l)
        return 0
    if a.n is None: ap.error("set needs a stage number")
    changes = {}
    if a.answers:
        with open(a.answers, encoding="utf-8") as f: d = json.load(f)
        changes = d.get("answers", d)
    try:
        r = reenter(project, a.n, changes, interactive=a.interactive)
        print(json.dumps(r, indent=1, ensure_ascii=False, default=str)); return 0
    except SU.NeedAnswer as e:
        print(json.dumps(dict(e.q, stage=a.n), indent=1, ensure_ascii=False, default=str)); return 3
    except (M.Refused, SU.Refusal) as e:
        print(json.dumps({"refused": str(e)}, ensure_ascii=False)); return 4


if __name__ == "__main__":
    sys.exit(main())
