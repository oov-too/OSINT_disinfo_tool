#!/usr/bin/env python3
"""Render the brief templates with a project's pack slots (phase 7a of tools/platform-plan.md, 2026-10-22): the renderer the
plugin's skills call at run time, the module form of `ledger brief render`.

The prototype is wip/platform-phase4/render_briefs.py. It is a top-level script (it parses arguments and changes directory when
loaded), so it cannot be imported as a module; this module imports its slot grammar instead (the TOKEN pattern, read from the
prototype's source by `ast` without running it, when the prototype is present) and applies the same three rules:

  1. every {{pack.<key>}} is filled from the pack's briefs/slots.toml, falling back on the templates' slots-default.toml;
     every {{run.<key>}} from a run's TOML ([run] table); {{ledger.root}} is the project folder and {{ledger.title}} its
     ledger.toml [ledger] title;
  2. a line that starts with "| `{{" (a slot table row at the head of a template) is left as written;
  3. a slot with no value is an error: the render reports it and the command exits 1.

tools/ledger/tests/test_setup.py renders this project's pack with both and compares the outputs byte for byte.

Templates are looked for in this order: --templates; $LEDGER_TEMPLATES; $CLAUDE_PLUGIN_ROOT/templates/briefs (the shipped plugin); the same
under $LEDGER_PLUGIN_ROOT and under the plugin path setup stage 0 recorded (setup/stage-0.toml; phase 7b);
<project>/plugin/templates/briefs (the canonical source); <project>/wip/platform-phase4/briefs (the old place, now a pointer); the same two beside this
module's project.

    python3 tools/ledger/briefs.py render --project <folder> [--pack packs/<name>] [--run <run.toml>] [--only operations.md intake- staged/]
                                         [--out <folder>] [--templates <folder>] [--defaults-only] [--check]
    python3 tools/ledger/briefs.py slots --project <folder> [--pack packs/<name>]     every slot with its value and where it came from
--check renders into memory only and reports the missing slots (exit 1 on any)."""
import ast, json, os, re, sys

try:
    import tomllib
except ImportError:  # Python 3.9 and 3.10
    import tomli as tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
THIS_PROJECT = os.path.dirname(TOOLS)
PROTOTYPE = os.path.join(THIS_PROJECT, "wip", "platform-phase4", "render_briefs.py")
DEFAULT_TOKEN = r"\{\{(pack|run|ledger)\.([a-z_.]+)\}\}"


def _prototype_token(path=PROTOTYPE):
    """The prototype's TOKEN pattern, read from its source without executing it; None when the prototype is absent."""
    if not os.path.isfile(path): return None
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOKEN" for t in node.targets):
            call = node.value
            if isinstance(call, ast.Call) and call.args and isinstance(call.args[0], ast.Constant): return call.args[0].value
    return None


TOKEN_SOURCE = "wip/platform-phase4/render_briefs.py" if _prototype_token() else "briefs.py (the prototype's pattern, copied)"
TOKEN = re.compile(_prototype_token() or DEFAULT_TOKEN)
TABLE_ROW = "| `{{"


def _load(path):
    with open(path, "rb") as f: return tomllib.load(f)


def templates_dir(project=None, given=None):
    """The brief templates folder (module docstring for the order)."""
    cands = [given, os.environ.get("LEDGER_TEMPLATES")]
    for var in ("CLAUDE_PLUGIN_ROOT", "LEDGER_PLUGIN_ROOT"):   # inside a Claude Code session; setup's stand-in outside one (phase 7b)
        if os.environ.get(var): cands.append(os.path.join(os.environ[var], "templates", "briefs"))
    st0 = os.path.join(project, "setup", "stage-0.toml") if project else None   # the plugin setup stage 0 found on this machine
    if st0 and os.path.isfile(st0):
        plug = _load(st0).get("result", {}).get("plugin")
        if plug: cands.append(os.path.join(plug, "templates", "briefs"))
    for base in ([project] if project else []) + [THIS_PROJECT]:
        cands += [os.path.join(base, "plugin", "templates", "briefs"), os.path.join(base, "wip", "platform-phase4", "briefs")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "slots-default.toml")): return os.path.abspath(c)
    raise FileNotFoundError("no brief templates found (set $LEDGER_TEMPLATES or pass --templates); looked in: " + ", ".join(c for c in cands if c))


def ledger_values(project):
    p = os.path.join(project, "ledger.toml")
    title = _load(p).get("ledger", {}).get("title", "") if os.path.isfile(p) else ""
    return {"root": project, "title": title}


def pack_path(project, pack=None):
    """The pack folder: --pack, else ledger.toml [pack] path; absolute."""
    if not pack:
        p = os.path.join(project, "ledger.toml")
        pack = _load(p).get("pack", {}).get("path") if os.path.isfile(p) else None
    if not pack: raise FileNotFoundError(f"no pack: pass --pack or set [pack] path in {project}/ledger.toml")
    return pack if os.path.isabs(pack) else os.path.join(project, pack)


def slot_values(project, pack=None, templates=None, defaults_only=False):
    """{key: (value, origin)} for every pack slot the defaults or the pack define."""
    tdir = templates_dir(project, templates)
    out = {k: (v, "core default") for k, v in _load(os.path.join(tdir, "slots-default.toml"))["slots"].items()}
    if not defaults_only:
        sp = os.path.join(pack_path(project, pack), "briefs", "slots.toml")
        if os.path.isfile(sp):
            for k, v in _load(sp).get("slots", {}).items(): out[k] = (v, "pack")
        # the pack's [intake] sample_threshold (packload.intake(), the value the workflow acts on) wins over a slots.toml copy (2026-10-25)
        pt = os.path.join(pack_path(project, pack), "pack.toml")
        if os.path.isfile(pt) and "sample_threshold" in _load(pt).get("intake", {}): out["sample_threshold"] = (_load(pt)["intake"]["sample_threshold"], "pack")
    return out


def render(project, pack=None, run=None, only=None, out=None, templates=None, defaults_only=False, check=False):
    """Render the templates. Returns {n, out, used, from_pack, from_defaults, unused, missing, files}; writes UTF-8 with LF unless
    check is set (then nothing is written)."""
    project = os.path.abspath(project)
    tdir = templates_dir(project, templates)
    slots = slot_values(project, pack, tdir, defaults_only)
    pack_slots = {k for k, (_, o) in slots.items() if o == "pack"}
    values = {"pack": {k: v for k, (v, _) in slots.items()}, "run": _load(run).get("run", {}) if run else {}, "ledger": ledger_values(project)}
    missing, used = set(), {"pack": set(), "run": set(), "ledger": set()}

    def value(m):
        ns, key = m.group(1), m.group(2); used[ns].add(key)
        if key in values[ns]: return str(values[ns][key])
        missing.add(f"{ns}.{key}"); return m.group(0)

    files = {}
    for dp, dns, fs in os.walk(tdir):
        dns.sort()
        for f in sorted(fs):
            if not f.endswith(".md"): continue
            src = os.path.join(dp, f); rel = os.path.relpath(src, tdir).replace(os.sep, "/")
            if only and not any(rel.startswith(o) for o in only): continue
            with open(src, encoding="utf-8") as fh: lines = fh.read().split("\n")
            files[rel] = "\n".join(l if l.startswith(TABLE_ROW) else TOKEN.sub(value, l) for l in lines)
    if out and not check:
        for rel, text in files.items():
            dst = os.path.join(out, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as fh: fh.write(text)
    return dict(n=len(files), out=out, templates=tdir, used=sorted(used["pack"]), from_pack=sorted(used["pack"] & pack_slots),
                from_defaults=sorted(used["pack"] - pack_slots), unused=sorted(pack_slots - used["pack"]), missing=sorted(missing),
                files=sorted(files), token_source=TOKEN_SOURCE)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Render the brief templates with a project's pack slots")
    ap.add_argument("cmd", choices=["render", "slots"])
    ap.add_argument("--project", default=os.environ.get("LEDGER_ROOT") or os.getcwd()); ap.add_argument("--pack"); ap.add_argument("--run")
    ap.add_argument("--only", nargs="*"); ap.add_argument("--out"); ap.add_argument("--templates"); ap.add_argument("--defaults-only", action="store_true")
    ap.add_argument("--check", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "slots":
        for k, (v, o) in sorted(slot_values(os.path.abspath(a.project), a.pack, a.templates, a.defaults_only).items()):
            print(f"{k}\t{o}\t{str(v)[:160]}")
        return 0
    out = a.out
    if not out and not a.check:
        run_name = os.path.splitext(os.path.basename(a.run))[0] if a.run else "templates"
        out = os.path.join(os.path.abspath(a.project), "wip", "briefs", run_name)
    r = render(a.project, a.pack, a.run, a.only, out, a.templates, a.defaults_only, a.check)
    if a.json: print(json.dumps(r, indent=1))
    else:
        print(f"rendered {r['n']} briefs" + (f" to {r['out']}" if r['out'] and not a.check else " (check only)") +
              f"; pack slots used {len(r['used'])}, from the pack {len(r['from_pack'])}, from the core defaults {len(r['from_defaults'])}")
        if r["unused"]: print("pack values no template uses (kept for the skills): " + ", ".join(r["unused"]))
        if r["missing"]: print("MISSING: " + ", ".join(r["missing"]))
    return 1 if r["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
