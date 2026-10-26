#!/usr/bin/env python3
"""Remove byte-identical duplicate text files from existing holds, and mark normalised copies (7b2 item 19, 2026-10-23).

Holds made before the document adapter held the text layer once carry it twice (text.txt = text-layer.txt byte for byte), and
holds made before the normalised copy was marked carry the venue's transcript twice without saying which is the copy
(transcript.txt, the UTF-8 LF copy of a cp1252 CRLF INQ*.txt): a word count over the hold counts the text several times. This
one-off tool, over a sources folder (every folder under it with a hold.json):

1. groups each hold's text files (.txt, .md; not README.md, not linked) by SHA-256, after checking each file's bytes against
   hold.json (a hold whose files do not match is reported and left alone);
2. in each group of identical files keeps one: a held file before any derived one; then the file hold.json's record `text` (or
   `texts`) names; then a file the project references (its hold-relative path, `<hold folder>/<name>`, found in the notes and
   unit files: <root>/videos, <root>/books and every research/tasks/**/units folder, or the folders given with --refs); then a
   file the record's metadata names; then text.txt, transcript.txt, text.md; then the shorter name;
3. removes another member only when it is derived and nothing references it (not the record, not the metadata, not a note or
   unit file); a held file is never removed (tools/hold-schema.md rule 3). Each removal is recorded in hold.json's `removed`
   list (name, role, bytes, sha256, identical_to, derived_from and tool as hold.json had them, the files whose derived_from named
   it, removed, removed_by, why), the size block is recomputed, README.md is regenerated from hold.json (base.readme_text, so
   base.verify_hold passes), and a line goes to the log;
4. marks a normalised copy: a derived text file whose derived_from is a held text file and whose bytes are what
   base.decode_text makes of that file gains `normalised_copy_of` and `normalised` (base.normalised_steps), as the adapters
   now write them (base.normalised_copy).

Dry run by default: prints what it would do and writes nothing (the log only when --log is given). --apply acts. A JSON summary
(per hold: what was removed or marked, the words over the hold's text files before and after, and the words counted once:
the record's text and the other distinct texts, a normalised copy's original not counted) goes to stdout with --json.

    python3 tools/ledger/acquire/dedupe_holds.py <sources folder> [--root PROJECT] [--refs DIR ...] [--log FILE] [--apply] [--json]

--root defaults to the project the sources folder is in (the folder above the first `sources` in its path). Never run on a
project's holds without a dry run first.
"""
import argparse, glob, json, os, re, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B

TOOL = "ledger.acquire.dedupe_holds 1.0"
TEXT_EXT = (".txt", ".md")
NAME_PREFERENCE = ["text.txt", "transcript.txt", "text.md"]
REF_EXT = (".md", ".txt", ".json", ".jsonl", ".tsv", ".toml", ".csv")


def hold_folders(base):
    out = []
    for dp, dns, fs in os.walk(base):
        dns.sort()
        if "hold.json" in fs: out.append(dp); dns[:] = []
    return out


def default_root(sources):
    parts = os.path.abspath(sources).split(os.sep)
    return os.sep.join(parts[:parts.index("sources")]) if "sources" in parts else os.path.dirname(os.path.abspath(sources))


def default_refs(root):
    out = [os.path.join(root, d) for d in ("videos", "books")]
    out += sorted(glob.glob(os.path.join(root, "research", "tasks", "**", "units"), recursive=True))
    return [d for d in out if os.path.isdir(d)]


def ref_files(refs):
    for r in refs:
        if os.path.isfile(r): yield r; continue
        for dp, dns, fs in os.walk(r):
            dns.sort()
            for f in sorted(fs):
                if f.lower().endswith(REF_EXT): yield os.path.join(dp, f)


def find_references(needles, refs):
    """{needle: [file, ...]} for each needle (`<hold folder name>/<file name>`) found in the reference files."""
    hits = {n: [] for n in needles}
    if not needles: return hits
    for p in ref_files(refs):
        try: t = B.LN.read_text(p, errors="replace")
        except OSError: continue
        for n in needles:
            if n in t: hits[n].append(p)
    return hits


def words(path):
    return len(B.LN.read_text(path, errors="replace").split())


def text_entries(h):
    return [f for f in h.get("files", []) if f["role"] != "linked" and f["name"].lower().endswith(TEXT_EXT) and f["name"] != "README.md"]


def counts(folder, h):
    """(words over every text file in the hold, words counted once: distinct SHA-256, a normalised copy's original left out)."""
    ents = [f for f in text_entries(h) if os.path.isfile(os.path.join(folder, f["name"]))]
    total = sum(words(os.path.join(folder, f["name"])) for f in ents)
    originals = {f.get("normalised_copy_of") for f in ents if f.get("normalised_copy_of")}
    seen = set(); once = 0
    for f in sorted(ents, key=lambda f: f["name"] != (h.get("record") or {}).get("text")):
        if f["name"] in originals or f["sha256"] in seen: continue
        seen.add(f["sha256"]); once += words(os.path.join(folder, f["name"]))
    return total, once


def metadata_names(h, name):
    md = json.dumps((h.get("record") or {}).get("metadata") or {}, ensure_ascii=False)
    return bool(re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])", md))


def plan_hold(folder, h, refs_hits, rel):
    """(removals, marks, kept notes, problems) for one hold; refs_hits maps `<folder name>/<file>` to the files referencing it."""
    probs = []; ents = text_entries(h)
    for f in ents:
        p = os.path.join(folder, f["name"])
        if not os.path.isfile(p): probs.append(f"{f['name']}: listed in hold.json, missing on disk")
        elif os.path.getsize(p) != f["bytes"] or B.file_sha256(p) != f["sha256"]: probs.append(f"{f['name']}: bytes differ from hold.json")
    if probs: return [], [], [], probs
    rec = h.get("record") or {}
    named = {rec.get("text")} | set(h.get("texts") or [])
    fname = os.path.basename(folder)

    def external(n): return refs_hits.get(f"{fname}/{n}", [])

    groups = {}
    for f in ents: groups.setdefault(f["sha256"], []).append(f)
    removals = []; kept = []
    for sha, g in groups.items():
        if len(g) < 2: continue
        rank = lambda f: (f["role"] != "held", f["name"] not in named, not external(f["name"]), not metadata_names(h, f["name"]),
                          NAME_PREFERENCE.index(f["name"]) if f["name"] in NAME_PREFERENCE else len(NAME_PREFERENCE), len(f["name"]), f["name"])
        g = sorted(g, key=rank); keep = g[0]
        for f in g[1:]:
            why_not = []
            if f["role"] != "derived": why_not.append("a held file (never removed)")
            if f["name"] in named: why_not.append("named by the record's text")
            if external(f["name"]): why_not.append("referenced by " + ", ".join(os.path.relpath(x, rel) for x in external(f["name"])[:5]))
            if metadata_names(h, f["name"]): why_not.append("named in the record's metadata")
            if why_not: kept.append(dict(name=f["name"], identical_to=keep["name"], kept_because="; ".join(why_not))); continue
            named_by = [x["name"] for x in h["files"] if x is not f and f["name"] in (x.get("derived_from") or "")]
            removals.append(dict(name=f["name"], role=f["role"], bytes=f["bytes"], sha256=f["sha256"], identical_to=keep["name"],
                                 derived_from=f.get("derived_from"), tool=f.get("tool"), named_by=named_by or None,
                                 why=f"byte-identical to {keep['name']}, which is kept"
                                     + (" (the record's text)" if keep["name"] in named else "")
                                     + "; nothing references this file (not the record, its metadata, the notes or the unit files)"))
    marks = []
    held = {f["name"]: f for f in h.get("files", []) if f["role"] == "held"}
    gone = {r["name"] for r in removals}
    for f in ents:
        if f["role"] != "derived" or f.get("normalised_copy_of") or f["name"] in gone: continue
        src = held.get(f.get("derived_from") or "")
        if not src or not src["name"].lower().endswith(TEXT_EXT): continue
        sp = os.path.join(folder, src["name"])
        if not os.path.isfile(sp): continue
        data = B.read_bytes(sp)
        try: t, enc, _ = B.decode_text(data)
        except ValueError: continue
        if B.lf(t).encode("utf-8") == B.read_bytes(os.path.join(folder, f["name"])):
            marks.append(dict(name=f["name"], normalised_copy_of=src["name"], normalised="; ".join(B.normalised_steps(data, enc))))
    return removals, marks, kept, []


def apply_hold(folder, h, removals, marks, stamp):
    for m in marks:
        e = next(f for f in h["files"] if f["name"] == m["name"])
        e["normalised"] = m["normalised"]; e["normalised_copy_of"] = m["normalised_copy_of"]
    names = {r["name"] for r in removals}
    h["files"] = [f for f in h["files"] if f["name"] not in names]
    h.setdefault("removed", [])
    for r in removals:
        h["removed"].append({k: v for k, v in dict(r, removed=stamp, removed_by=TOOL).items() if v is not None})
    if not h["removed"]: h.pop("removed")
    stored = sum(f["bytes"] for f in h["files"] if f["role"] != "linked")
    if "size" in h:
        h["size"] = dict(bytes=stored, size_class=B.size_class(stored), linked_bytes=sum(f["bytes"] for f in h["files"] if f["role"] == "linked"))
    with B.LN.open_write(os.path.join(folder, "hold.json")) as f: json.dump(h, f, indent=1, ensure_ascii=False, sort_keys=False); f.write("\n")
    B.LN.write_text(os.path.join(folder, "README.md"), B.readme_text(h))
    for r in removals: os.remove(os.path.join(folder, r["name"]))


def run(sources, root=None, refs=None, apply=False, log=None, out=print):
    sources = os.path.abspath(sources); root = os.path.abspath(root) if root else default_root(sources)
    refs = [os.path.abspath(r) for r in refs] if refs else default_refs(root)
    folders = hold_folders(sources)
    holds = [(d, B.load_hold(d)) for d in folders]
    needles = []
    for d, h in holds:
        for f in text_entries(h): needles.append(f"{os.path.basename(d)}/{f['name']}")
    hits = find_references(needles, refs)
    stamp = B.utc_now(); summary = []; logrows = []
    for d, h in holds:
        rel = os.path.relpath(d, root).replace(os.sep, "/")
        verify_before = B.verify_hold(d)
        before = counts(d, h)
        removals, marks, kept, probs = plan_hold(d, h, hits, root)
        row = dict(hold=rel, problems=probs or None, remove=[dict(name=r["name"], bytes=r["bytes"], sha256=r["sha256"], identical_to=r["identical_to"]) for r in removals],
                   mark=marks, kept_duplicates=kept or None, words_before=before[0], words_once_before=before[1], verify_before=verify_before or "intact")
        if apply and (removals or marks) and not probs:
            apply_hold(d, h, removals, marks, stamp)
            h2 = B.load_hold(d); after = counts(d, h2)
            row.update(words_after=after[0], words_once_after=after[1], verify_after=B.verify_hold(d) or "intact", applied=True)
        else:
            # what the counts would be: the removed files left out, the marks made
            sim = json.loads(json.dumps(h)); gone = {r["name"] for r in removals}
            sim["files"] = [f for f in sim["files"] if f["name"] not in gone]
            for m in marks: next(f for f in sim["files"] if f["name"] == m["name"]).update(normalised_copy_of=m["normalised_copy_of"])
            after = counts(d, sim)
            row.update(words_after=after[0], words_once_after=after[1], applied=False)
        summary.append(row)
        for r in removals:
            logrows.append(dict(time=stamp, mode="apply" if apply else "dry-run", action="remove", hold=rel, name=r["name"], bytes=r["bytes"],
                                sha256=r["sha256"], identical_to=r["identical_to"], why=r["why"]))
        for m in marks:
            logrows.append(dict(time=stamp, mode="apply" if apply else "dry-run", action="mark-normalised-copy", hold=rel, name=m["name"],
                                normalised_copy_of=m["normalised_copy_of"], normalised=m["normalised"]))
        verb = "removed" if apply else "would remove"
        for r in removals: out(f"{rel}: {verb} {r['name']} ({r['bytes']:,} bytes, sha256 {r['sha256'][:12]}..., identical to {r['identical_to']})")
        for m in marks: out(f"{rel}: {'marked' if apply else 'would mark'} {m['name']} as the normalised copy of {m['normalised_copy_of']} ({m['normalised']})")
        for k in kept: out(f"{rel}: keeps {k['name']} (identical to {k['identical_to']}): {k['kept_because']}")
        for p in probs: out(f"{rel}: PROBLEM {p}; hold left alone")
    if log and logrows:
        os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
        with B.LN.open_append(log) as f:
            for r in logrows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_rm = sum(len(s["remove"]) for s in summary); n_mk = sum(len(s["mark"]) for s in summary)
    out(f"{len(summary)} holds; {n_rm} duplicate file{'s' if n_rm != 1 else ''} {'removed' if apply else 'to remove'} "
        f"({sum(r['bytes'] for s in summary for r in s['remove']):,} bytes); {n_mk} normalised cop{'ies' if n_mk != 1 else 'y'} "
        f"{'marked' if apply else 'to mark'}; {'applied' if apply else 'dry run: nothing written'}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sources"); ap.add_argument("--root"); ap.add_argument("--refs", nargs="+")
    ap.add_argument("--log"); ap.add_argument("--apply", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root) if a.root else default_root(a.sources)
    log = a.log or (os.path.join(root, ".ledger", "acquire", "dedupe-holds.jsonl") if a.apply else None)
    msgs = []
    s = run(a.sources, root=root, refs=a.refs, apply=a.apply, log=log, out=(msgs.append if a.json else print))
    if a.json: print(json.dumps(dict(messages=msgs, holds=s, log=log), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
