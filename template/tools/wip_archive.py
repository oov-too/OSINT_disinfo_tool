#!/usr/bin/env python3
"""Keep an agent's tool-feedback artefacts before its wip folder is deleted (tools/narratives.md section 8b, 2026-10-09: the pilot's lane
reassignment lists were lost with the wip folders). Usage: python3 tools/wip_archive.py <wip/task-folder> [<more folders>] [--run <run label>]
Copies the folder's deliverables (every file except current-unit.md, prompt.md, q.sh, derived database caches *.db / *.sqlite /
*.db-journal, and files over 50 MB, which are listed in ARCHIVE-MANIFEST.md beside the kept copy; --keep-all keeps everything) into
research/tasks/tool-feedback/<run>/<task>/ (run defaults to today's date) and repoints citations of wip/<task>/ on the
research/narrative-*.md pages to the kept copy (owner ruling 2026-10-09, proposal 26). With --trash (the standing hand-back form from
2026-10-22, owner ruling: completed work leaves wip/), the folder is then moved to ~/.Trash under a dated name; nothing is ever deleted
outright by this tool."""
import sys, os, shutil, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
args = sys.argv[1:]; run = datetime.date.today().isoformat()
if "--run" in args: i = args.index("--run"); run = args[i + 1]; del args[i:i + 2]
keep_all = "--keep-all" in args; args = [a for a in args if a != "--keep-all"]
do_trash = "--trash" in args; args = [a for a in args if a != "--trash"]
SKIP_EXT = (".db", ".sqlite", ".db-journal", ".pyc"); CAP = 50 * 1024 * 1024
for folder in args:
    task = os.path.basename(folder.rstrip("/")); dest = os.path.join("research", "tasks", "tool-feedback", run, task); n = 0; skipped = []
    # Owner ruling 2026-10-09 (proposal 26): every file is kept, with its sub-path, so that whatever a score card cites survives.
    for dp, _, fs in os.walk(folder):
        for fn in fs:
            if fn in ("current-unit.md", "prompt.md", "q.sh") or fn.startswith("."): continue
            src = os.path.join(dp, fn); rel = os.path.relpath(src, folder); out = os.path.join(dest, rel)
            if not keep_all and (fn.endswith(SKIP_EXT) or os.path.getsize(src) > CAP): skipped.append(f"{rel} ({os.path.getsize(src) // 1024} KB)"); continue
            os.makedirs(os.path.dirname(out), exist_ok=True); shutil.copy2(src, out); n += 1
    print(f"{task}: {n} files kept under {dest}" if n else f"{task}: nothing to keep")
    if skipped:
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "ARCHIVE-MANIFEST.md"), "w", encoding="utf-8") as w:
            w.write(f"# Archived {run} from {folder}\n\nKept {n} files; skipped {len(skipped)} (derived caches and files over 50 MB):\n" + "".join(f"- {x}\n" for x in skipped))
    # repoint page citations from wip/<task>/... to the kept copy (narrative, synchrony, rival and register pages)
    old = f"{folder.rstrip('/')}/"; new = dest + "/"; hits = 0
    for page in glob.glob("research/narrative-*.md"):
        t = LN.read_text(page)
        if old in t: LN.write_text(page, t.replace(old, new)); hits += t.count(old)
    if hits: print(f"{task}: {hits} page citations repointed to {dest}")
    if do_trash and os.path.isdir(folder):
        trash = os.path.expanduser("~/.Trash"); dst = os.path.join(trash, f"{os.path.basename(os.path.abspath(ROOT))}-wip-{datetime.date.today().isoformat()}-{task}"); k = 1
        while os.path.exists(dst): k += 1; dst = f"{dst}-{k}"
        shutil.move(folder, dst); print(f"{task}: folder moved to the Trash as {os.path.basename(dst)}")
