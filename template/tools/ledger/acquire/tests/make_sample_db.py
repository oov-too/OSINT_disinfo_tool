#!/usr/bin/env python3
"""Generate the sample SQLite database of the acquire tests (phase 3 of tools/platform-plan.md, 2026-10-22) from three notes'
metadata, under a deliberately different schema, as phase 6a's round-trip test will do at scale:

    records(rec_no PK, headline, aired DD/MM/YYYY, outlet, presenter, participants "; "-joined, src_link, kind_code VID|RPT,
            blurb, keywords, entered YYYY-MM-DD, run_time)
    attachments(att_id PK, rec_no -> records, mime, location relative to the corpus root, byte_size, label)
    transcript_rows(row_id PK, rec_no -> records, seq, t_offset seconds, spk, utterance)   one row per timestamped paragraph
    annotations(ann_id PK, rec_no -> records, coder, code, body, attributed_to, created)   the first claims rows of each note

The three notes and their held sources are the synthetic casebook corpus (tools/ledger/tests/casebook_corpus.py), written beside the
database (in <out folder>/corpus/, or the root given) before the database is built; nothing is read from a project's own notes
(phase 7a: the tests ship and name nothing real).

    python3 tools/ledger/acquire/tests/make_sample_db.py <out.db> [--claims 8]
"""
import os, re, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, TOOLS); sys.path.insert(0, os.path.join(TOOLS, "ledger", "tests"))
from ledger import notes as LN
import casebook_corpus as CC

ROOT = None   # the corpus root, set by build()


def corpus_root(out):
    return os.path.join(os.path.dirname(os.path.abspath(out)), "corpus")
NOTES = ["videos/harrowmere-day-12.md", "videos/harbour-talks-vanecek-2020.md", "books/lisle-memo-2015.md"]
PARA_RE = re.compile(r"^\*\*\[(\d\d):(\d\d):(\d\d)\]\*\* (.*)$")
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def note_meta(path):
    lines = LN.read_lines(os.path.join(ROOT, path))
    meta = {k: v for k, v, _ in LN.meta_rows(lines)}
    title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else path
    claims = []
    b = LN.section_bounds(lines, "## Claims ledger")
    if b:
        for t in LN.tables(lines, b[0], b[1]):
            hdr = [h.lower() for h in t.header] if hasattr(t, "header") else [h.lower() for h in t[1]]
            rows = t.rows if hasattr(t, "rows") else t[2]
            if "claim" in hdr:
                ci = hdr.index("claim"); si = hdr.index("speaker") if "speaker" in hdr else None; ti = hdr.index("topic") if "topic" in hdr else None
                for _, cs in rows:
                    if len(cs) > ci: claims.append(dict(claim=cs[ci], speaker=cs[si] if si is not None and len(cs) > si else None, topic=cs[ti] if ti is not None and len(cs) > ti else None))
                break
    return title, meta, claims


def held_paths(path, meta):
    """The note's Transcript links as root-relative paths that exist."""
    out = []
    for link in LINK_RE.findall(meta.get("Transcript", "")):
        for cand in (os.path.normpath(os.path.join(os.path.dirname(path), link)), os.path.normpath(os.path.join("books", link)), link):
            if os.path.isfile(os.path.join(ROOT, cand)): out.append(cand.replace(os.sep, "/")); break
    return out


def dmy(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else None


def build(out, n_claims=8, root=None):
    """Write the synthetic corpus (at `root`, default <out folder>/corpus) and the database built from its three notes; returns out.
    The attachments' locations are relative to the corpus root, which `corpus_root(out)` gives the tests as the mapping's base_dir."""
    global ROOT
    ROOT = os.path.abspath(root or corpus_root(out))
    CC.build(ROOT)
    if os.path.exists(out): os.remove(out)
    con = sqlite3.connect(out)
    con.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE records (rec_no INTEGER PRIMARY KEY, headline TEXT NOT NULL, aired TEXT, outlet TEXT, presenter TEXT, participants TEXT,
                              src_link TEXT, kind_code TEXT, blurb TEXT, keywords TEXT, entered TEXT, run_time TEXT);
        CREATE TABLE attachments (att_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), mime TEXT, location TEXT,
                                  byte_size INTEGER, label TEXT);
        CREATE TABLE transcript_rows (row_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), seq INTEGER, t_offset INTEGER,
                                      spk TEXT, utterance TEXT);
        CREATE TABLE annotations (ann_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), coder TEXT, code TEXT, body TEXT,
                                  attributed_to TEXT, created TEXT);
    """)
    for rec_no, path in enumerate(NOTES, 1):
        title, meta, claims = note_meta(path)
        video = path.startswith("videos/")
        url = (meta.get("URL") or "").split(" ")[0]
        presenter = meta.get("Host") if video else re.sub(r" \(.*", "", meta.get("Authors", "")).split(";")[0].split(",")[0].strip() or None
        participants = meta.get("Speakers") if video else None
        if participants: participants = "; ".join(p.strip() for p in re.split(r",(?![^()]*\))", participants) if p.strip())
        con.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rec_no, title, dmy(meta.get("Uploaded")), re.sub(r" \(.*", "", meta.get("Channel", "")).strip(), presenter, participants,
                     url, "VID" if video else "RPT", meta.get("Description"), meta.get("Tags"), meta.get("Added to notes"), meta.get("Length")))
        for p in held_paths(path, meta):
            ext = os.path.splitext(p)[1].lower()
            mime = {".md": "text/markdown", ".txt": "text/plain", ".pdf": "application/pdf"}.get(ext, "application/octet-stream")
            con.execute("INSERT INTO attachments (rec_no, mime, location, byte_size, label) VALUES (?,?,?,?,?)",
                        (rec_no, mime, p, os.path.getsize(os.path.join(ROOT, p)), "transcript" if video else ("scan" if ext == ".pdf" else "provenance" if os.path.basename(p) == "README.md" else "text layer")))
            if video and ext == ".md":
                seq = 0
                for line in LN.read_lines(os.path.join(ROOT, p)):
                    m = PARA_RE.match(line)
                    if m:
                        seq += 1
                        con.execute("INSERT INTO transcript_rows (rec_no, seq, t_offset, spk, utterance) VALUES (?,?,?,?,?)",
                                    (rec_no, seq, int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), None, m.group(4).strip()))
        for c in claims[:n_claims]:
            con.execute("INSERT INTO annotations (rec_no, coder, code, body, attributed_to, created) VALUES (?,?,?,?,?,?)",
                        (rec_no, "seed (claims ledger)", "claim" + (":" + c["topic"] if c.get("topic") else ""), c["claim"], c.get("speaker"), meta.get("Added to notes")))
    con.commit(); con.close()
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--claims") + 1]) if "--claims" in a else 8
    print(build(a[0], n))
