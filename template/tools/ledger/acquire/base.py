"""The base of every acquire adapter (phase 3 of tools/platform-plan.md, 2026-10-22; the schema is tools/hold-schema.md).

An adapter fetches an item, holds it, writes its README and returns a manifest row:

    rows = SomeAdapter(root=...).acquire(<what to fetch>)        # fetch() then hold() for each capture

`fetch()` is the adapter's own (a URL, a video id, a file, a database record) and returns Capture objects: a Record (the hold
schema's fields) and the files to hold. `hold()` is shared and is the only writer of a hold:

- the folder is sources/<kind folder>/<name>/ from `hold_path(kind, ident, title)` (tools/ledger/hold.py), or a folder the adapter gives (set holds: sources/archive/<set>/, sources/db/<source>/);
- a file with role "held" is written byte-for-byte as obtained (bytes in, bytes out, no line-ending change); a "derived" file
  (a text layer, an OCR, a transcript) is UTF-8 with LF and names the held file and the tool it came from;
- nothing held is ever overwritten: a re-capture whose bytes are identical is recorded as a capture row ("unchanged"); one whose
  bytes differ is held beside the first as <stem>.<capture time>.<ext> ("changed", the version rule);
- hold.json (the machine record: the fields, the files with bytes and SHA-256, the captures) is written, and README.md is
  generated from it in the provenance form of the READMEs under books/sources/web/ (never typed by hand);
- every new file's name is checked against the portability rules (ledger.paths.name_problems: reserved characters, device names,
  the stem, basename and path caps) before it is written.
"""
import datetime, hashlib, json, os, re, shutil, sys, time

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2): LF writers, normalising readers
from ledger import paths as LP    # the project root and the portability rules of new holds (tools/ledger/paths.py, phase 2)
from ledger.hold import safe_slug, hold_path          # the names of new holds (tools/ledger/hold.py, phase 2)
HOLD_MODULE = "ledger.hold"
from ledger.acquire import schema as S

VERSION = "1.0"
INNER_NAME_CAP = 64      # a file name inside a hold: the hold folder takes at most 147 of the path cap of 180
RESERVED_NAMES = {"readme.md", "hold.json"}   # written by hold() itself; a captured file of that name is held as held-<name>


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def read_json(path, default=None):
    if not os.path.isfile(path): return default
    with open(path, encoding="utf-8") as f: return json.load(f)


def read_bytes(path):
    with open(path, "rb") as f: return f.read()


def read_raw(path):
    """A text file exactly as written (no line-ending translation), for comparisons with what a writer emitted."""
    with open(path, encoding="utf-8", newline="") as f: return f.read()


def lf(text):
    """Text as a derived file holds it: LF line endings, a byte-order mark dropped."""
    return LN.normalise(text) if hasattr(LN, "normalise") else text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


# ============================================================================================================ the record
class Record:
    """One item in the hold schema (tools/hold-schema.md). Unknown keyword arguments go to the metadata block."""

    def __init__(self, identifier, media_kind, title, date=None, date_raw=None, speaker_or_author=None, text=None,
                 media_link=None, venue=None, provenance=None, capture_time=None, capture_tool=None, metadata=None, **extra):
        self.identifier = str(identifier) if identifier is not None else None
        self.media_kind = media_kind
        self.title = title
        self.date = date
        self.date_raw = date_raw
        if isinstance(speaker_or_author, str): speaker_or_author = [s.strip() for s in re.split(r";|\n", speaker_or_author) if s.strip()]
        self.speaker_or_author = list(speaker_or_author or [])
        self.text = text
        self.media_link = media_link
        self.venue = venue
        self.provenance = provenance
        self.capture_time = capture_time
        self.capture_tool = capture_tool
        self.metadata = dict(metadata or {}); self.metadata.update(extra)

    def as_dict(self):
        d = {k: getattr(self, k) for k in S.FIELD_NAMES}
        d["date_raw"] = self.date_raw
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d); return cls(**{k: d.pop(k, None) for k in S.FIELD_NAMES + ["date_raw"]}, **d)

    def problems(self):
        """The reasons the record cannot be held, as a list ([] when it can)."""
        out = []
        for k in S.REQUIRED:
            if not getattr(self, k): out.append(f"required field {k} is empty")
        if self.media_kind and self.media_kind not in S.MEDIA_KINDS:
            out.append(f"media_kind {self.media_kind!r} is not one of {', '.join(sorted(S.MEDIA_KINDS))}")
        if self.date and not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?\??", str(self.date)):
            out.append(f"date {self.date!r} is not ISO 8601 (YYYY, YYYY-MM or YYYY-MM-DD, optionally ending in ?)")
        return out


FILE_ENTRY_KEYS = {"name", "role", "bytes", "sha256", "how", "captured", "derived_from", "tool", "link"}


class HeldFile:
    """A file to hold. role "held": `data` (bytes) or `src` (a path to copy) exactly as obtained. role "derived": `text` (written
    UTF-8 with LF) or `data`, with `derived_from` (a file of the same hold) and `tool`. role "linked": a file held by link (a large
    original kept at its source: `link` the URL, its SHA-256 and size recorded from `data` or `src`, the bytes not stored; the
    hold-by-link of tools/hold-schema.md section 1). `how` says how it was obtained."""

    def __init__(self, name, data=None, src=None, text=None, role="held", how="", derived_from=None, tool=None, link=None, extra=None):
        self.name = name; self.data = data; self.src = src; self.text = text
        self.role = role; self.how = how; self.derived_from = derived_from; self.tool = tool; self.link = link
        self.extra = dict(extra or {})      # further keys of the file's hold.json entry (a normalised copy: normalised, normalised_copy_of)
        if self.extra.keys() & FILE_ENTRY_KEYS: raise ValueError(f"{name}: extra may not replace the file entry's own keys")
        if role not in ("held", "derived", "linked"): raise ValueError(f"role {role!r}: held, derived or linked")
        if role in ("held", "linked") and text is not None: raise ValueError("a held file is bytes as obtained: pass data= or src=, not text=")
        if role == "linked" and not link: raise ValueError(f"{name}: a linked file needs its link (the URL it is kept at)")
        if sum(x is not None for x in (data, src, text)) != 1: raise ValueError(f"{name}: exactly one of data, src, text")

    def bytes(self):
        if self.data is not None: return self.data
        if self.text is not None: return lf(self.text).encode("utf-8")
        with open(self.src, "rb") as f: return f.read()


# ============================================================================================================ text decoding
def decode_text(data, charset=None):
    """(text with LF, encoding, note) of text bytes: the declared charset first (Content-Type), then UTF-8, then cp1252 (the
    Windows encoding a pound sign as 0xA3 betrays), then Latin-1, which decodes anything. A byte-order mark is dropped. The note
    says what was decided and why, for the derived file's tool column."""
    tried = []
    for enc in ([charset] if charset else []) + ["utf-8", "cp1252", "latin-1"]:
        try:
            t = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            tried.append(enc); continue
        crlf = b"\r\n" in data or b"\r" in data
        why = (f"declared charset {charset}" if enc == charset else
               "UTF-8" if enc == "utf-8" else f"{enc} (not valid " + ", ".join(tried) + ")")
        return lf(t), enc, f"decoded as {why}" + ("; line endings made LF" if crlf else "")
    raise ValueError("undecodable")


def normalised_steps(data, enc, charset=None):
    """What a UTF-8 LF copy of held text bytes changed, as a list of plain phrases (the `normalised` key of the copy's file entry):
    the encoding when it was not UTF-8, CRLF or CR line endings, a byte-order mark."""
    out = []
    if enc and enc.lower().replace("-", "") not in ("utf8", "usascii", "ascii"):
        out.append(f"decoded from {enc}" + (" (the declared charset)" if charset and enc == charset else " (not valid UTF-8)") + ", written as UTF-8")
    lone_cr = b"\r" in data.replace(b"\r\n", b"")
    if b"\r\n" in data: out.append("CRLF" + (" and CR" if lone_cr else "") + " line endings made LF")
    elif lone_cr: out.append("CR line endings made LF")
    if data.startswith(b"\xef\xbb\xbf"): out.append("byte-order mark dropped")
    return out or ["none (the bytes were already UTF-8 with LF)"]


def normalised_copy(name, data, held_name, charset=None):
    """The derived UTF-8 LF copy of held text bytes, marked as a copy in its hold.json entry: role derived, derived_from the held
    original, the tool (base.decode_text and its decision), `normalised` (what it changed: normalised_steps) and
    `normalised_copy_of` (the held original), so a reader and a word count know which file is the original and which the copy:
    the two are one text, counted once. Returns (HeldFile, encoding)."""
    t, enc, note = decode_text(data, charset)
    return HeldFile(name, text=t, role="derived", derived_from=held_name, tool=f"ledger.acquire.base.decode_text: {note}",
                    extra=dict(normalised="; ".join(normalised_steps(data, enc, charset)), normalised_copy_of=held_name)), enc


def needs_text_copy(data, charset=None):
    """True when held text bytes are not already the hold's text form (UTF-8 with LF): a derived UTF-8 LF copy is then written."""
    try: t = data.decode("utf-8")
    except UnicodeDecodeError: return True
    declared_other = charset and charset.lower() not in ("utf-8", "utf8", "us-ascii", "ascii") and any(b > 127 for b in data)
    return "\r" in t or t.startswith("﻿") or bool(declared_other)


# ============================================================================================================ configuration
def acquire_config(root):
    """The [acquire] table of the project's ledger.toml (hold_root, state_dir, agent_token, contact, ocr_vision_bin,
    whisper_weights), with [ledger] title and name as `project_title` and `project_name`; {} when absent."""
    p = os.path.join(root, "ledger.toml")
    if not os.path.isfile(p): return {}
    try:
        import tomllib
        with open(p, "rb") as f: d = tomllib.load(f)
    except Exception:
        return {}
    out = dict(d.get("acquire") or {})
    out.setdefault("project_title", (d.get("ledger") or {}).get("title"))
    out.setdefault("project_name", (d.get("ledger") or {}).get("name"))
    return out


SIZE_CLASSES = [(10 * 1024 * 1024, "small"), (100 * 1024 * 1024, "medium")]   # under 10 MB, under 100 MB; else large


def size_class(n):
    for cap, name in SIZE_CLASSES:
        if n < cap: return name
    return "large"


class Capture:
    """What fetch() returns for one item: the record, the files, and optionally the folder (a set hold names its own)."""

    def __init__(self, record, files, folder=None, status_note="", extra=None):
        self.record = record; self.files = list(files); self.folder = folder; self.status_note = status_note
        self.extra = dict(extra or {})     # further top-level keys of hold.json (texts: every file that is the item's text)


# ============================================================================================================ rate gate
class RateGate:
    """At most one request per `gap` seconds to a service, across threads and across processes on this machine: an atomic
    directory create is the lock (portable; tools/platform-plan.md, Portability) and a stamp file holds the time of the last
    request. Sequential by construction: the lock is held from the wait through the request's start."""

    def __init__(self, name, gap, state_dir, clock=time.time, sleep=time.sleep, stale=600):
        self.name = name; self.gap = float(gap); self.dir = state_dir
        self.clock = clock; self.sleep = sleep; self.stale = stale
        self.lock = os.path.join(state_dir, f"{name}.lock"); self.stamp = os.path.join(state_dir, f"{name}.last")
        self.waits = []

    def _acquire(self):
        os.makedirs(self.dir, exist_ok=True)
        while True:
            try: os.mkdir(self.lock); return
            except FileExistsError:
                try:
                    if self.clock() - os.path.getmtime(self.lock) > self.stale: os.rmdir(self.lock); continue
                except OSError: pass
                self.sleep(0.2)

    def _release(self):
        try: os.rmdir(self.lock)
        except OSError: pass

    def last(self):
        try: return float(read_raw(self.stamp).strip() or 0)
        except (OSError, ValueError): return 0.0

    def __enter__(self):
        self._acquire()
        wait = self.last() + self.gap - self.clock()
        if wait > 0: self.sleep(wait)
        self.waits.append(max(0.0, wait))
        return self

    def __exit__(self, *exc):
        LN.write_text(self.stamp, f"{self.clock():.3f}\n")
        self._release()
        return False


# ============================================================================================================ the README form
def _cell(v):
    if v is None or v == "" or v == []: return ""
    if isinstance(v, (list, tuple)): v = "; ".join(str(x) for x in v)
    elif isinstance(v, dict): v = json.dumps(v, ensure_ascii=False, sort_keys=True)
    return str(v).replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "\n").replace("\n", " <br> ")


FIELD_LABELS = [("identifier", "Identifier"), ("media_kind", "Media kind"), ("date", "Date"), ("title", "Title"),
                ("speaker_or_author", "Speaker or author"), ("text", "Text"), ("media_link", "Media link"), ("venue", "Venue"),
                ("provenance", "Provenance"), ("capture_time", "Capture time"), ("capture_tool", "Capture tool")]


def readme_text(h):
    """README.md of a hold from its hold.json dict: the provenance form (tools/hold-schema.md section 3)."""
    r = h["record"]; caps = h["captures"]; first = caps[0]; last = caps[-1]
    held = [f for f in h["files"] if f["role"] == "held"]; derived = [f for f in h["files"] if f["role"] == "derived"]
    linked = [f for f in h["files"] if f["role"] == "linked"]
    out = [f"# {r.get('title') or r.get('identifier')}", ""]
    para = (f"Held {first['time'][:10]} by {first['tool']} from {r.get('provenance') or 'the source named below'}. "
            f"{len(held)} file{'s' if len(held) != 1 else ''} held byte-for-byte as obtained"
            + (f" and {len(derived)} derived from {'them' if len(held) != 1 else 'it'} by the tools named in the files table" if derived else "")
            + ". The SHA-256 of every file is in the table; a later capture never overwrites a held file (identical bytes are "
              "recorded as a capture, different bytes are held beside the first with the capture time in the name).")
    if linked: para += (f" {len(linked)} file{'s' if len(linked) != 1 else ''} held by link: the URL, size and SHA-256 recorded, the bytes "
                        "kept at the source, not here (fetch and check against the SHA-256 when needed).")
    if h.get("size"): para += f" Size {h['size']['bytes']:,} bytes stored ({h['size']['size_class']})."
    if len(caps) > 1: para += f" Captured {len(caps)} times; the last on {last['time'][:10]} ({last['status']})."
    if h.get("status_note"): para += " " + h["status_note"]
    out += [para, "", "This file is generated from hold.json by ledger.acquire; it is not typed and not edited by hand.", "",
            "| Field | Value |", "|---|---|"]
    for k, label in FIELD_LABELS:
        v = r.get(k)
        if k == "date" and r.get("date_raw") and r.get("date_raw") != v: v = f"{v or 'unknown'} (as the source gives it: {r['date_raw']})"
        out.append(f"| {label} | {_cell(v)} |")
        if k == "text" and len(h.get("texts") or []) > 1: out.append(f"| Texts | {_cell(h['texts'])} |")
    md = r.get("metadata") or {}
    if md:
        out += ["", "## Metadata", "", "| Key | Value |", "|---|---|"]
        for k in sorted(md): out.append(f"| {_cell(k)} | {_cell(md[k])} |")
    out += ["", "## Files", "", "| File | Role | Bytes | SHA-256 | How obtained |", "|---|---|---|---|---|"]
    for f in h["files"]:
        how = f.get("how") or ""
        if f["role"] == "derived":
            how = (how + " " if how else "") + f"(from {f.get('derived_from') or 'the held files'} by {f.get('tool') or 'an unnamed tool'})"
        if f.get("normalised_copy_of"):
            how += f" A normalised copy of {f['normalised_copy_of']} (the same text, counted once): {f.get('normalised') or 'normalised'}."
        if f["role"] == "linked": how = (how + " " if how else "") + f"(kept at {f.get('link')})"
        out.append(f"| {_cell(f['name'])} | {f['role']} | {f['bytes']:,} | {f['sha256']} | {_cell(how)} |")
    if h.get("removed"):
        out += ["", "## Removed", "", "Files once in this hold and removed as byte-identical copies of a file kept here (the record of each is "
                "hold.json's `removed`; the kept file has the same bytes and SHA-256).", "",
                "| File | Bytes | SHA-256 | Identical to | Removed | By | Why |", "|---|---|---|---|---|---|---|"]
        for x in h["removed"]:
            out.append(f"| {_cell(x.get('name'))} | {x.get('bytes', 0):,} | {x.get('sha256', '')} | {_cell(x.get('identical_to'))} | "
                       f"{_cell(x.get('removed'))} | {_cell(x.get('removed_by'))} | {_cell(x.get('why'))} |")
    out += ["", "## Captures", "", "| Captured | Tool | Status | Note |", "|---|---|---|---|"]
    for c in caps: out.append(f"| {c['time']} | {_cell(c['tool'])} | {c['status']} | {_cell(c.get('note', ''))} |")
    return "\n".join(out) + "\n"


def set_readme_text(title, intro, columns, rows, generated_by):
    """README.md of a set hold (sources/archive/<set>/, sources/db/<source>/): a paragraph and one table row per item, the form of
    books/sources/web/<set>/README.md."""
    out = [f"# {title}", "", intro.strip(), "", f"This file is generated by {generated_by}; it is not typed and not edited by hand.", "",
           "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for r in rows: out.append("| " + " | ".join(_cell(r.get(c, "")) for c in columns) + " |")
    return "\n".join(out) + "\n"


# ============================================================================================================ the adapter
class Adapter:
    """Subclasses set `name` (the module, e.g. "web") and implement fetch(*args, **kw) -> [Capture]."""
    name = "base"
    version = VERSION

    def __init__(self, root=None, dry=False, log=None, hold_root=None, state_dir=None):
        """hold_root: the folder holds go under, relative to the project root (default `sources`, or ledger.toml [acquire]
        hold_root): a pilot pack holding under sources/pilot/ keeps the same names and caps. state_dir: where the rate gates keep
        their lock and stamp files (default <project>/.ledger/acquire, or [acquire] state_dir); the default is shared by every
        session on the machine, which is the point of a gate: two sessions fetching one host wait for each other."""
        self.root = os.path.abspath(root) if root else LP.root()
        self.dry = dry
        self.log = log or (lambda msg: print(msg, file=sys.stderr))
        self.config = acquire_config(self.root)
        self.hold_root = str(hold_root or self.config.get("hold_root") or "sources").replace("\\", "/").strip("/")
        sd = state_dir or self.config.get("state_dir")
        self.state_dir = (sd if os.path.isabs(sd) else os.path.join(self.root, sd)) if sd else os.path.join(self.root, ".ledger", "acquire")

    def hold_path(self, kind, ident, title):
        """ledger.hold.hold_path under this adapter's hold root (sources/<kind>/<name> becomes <hold_root>/<kind>/<name>)."""
        p = str(hold_path(kind, ident, title)).replace("\\", "/").rstrip("/")
        return p if self.hold_root == "sources" else self.hold_root + p[len("sources"):]

    @property
    def tool(self):
        return f"ledger.acquire.{self.name} {self.version}"

    # ---------------------------------------------------------------------------------------------------- to override
    def fetch(self, *args, **kw):
        raise NotImplementedError

    # ---------------------------------------------------------------------------------------------------- shared
    def acquire(self, *args, **kw):
        """fetch() then hold() each capture; returns the manifest rows."""
        return [self.hold(c) for c in self.fetch(*args, **kw)]

    def abs(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)

    def rel(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def folder_for(self, record):
        kind = S.MEDIA_KINDS.get(record.media_kind, record.media_kind)
        return self.hold_path(kind, record.identifier, record.title)

    def check_name(self, relpath):
        """The portability rules of a new hold's file name (ledger.paths.name_problems), plus the inner-name cap."""
        probs = list(LP.name_problems(relpath)) if hasattr(LP, "name_problems") else []
        base = relpath.rsplit("/", 1)[-1]
        if len(base) > INNER_NAME_CAP and not base.startswith(("README", "hold.json")): probs.append(f"file name of {len(base)} characters inside a hold (cap {INNER_NAME_CAP})")
        return probs

    def hold(self, cap):
        """Hold one capture; returns its manifest row (tools/hold-schema.md section 5)."""
        rec = cap.record
        rec.capture_time = rec.capture_time or utc_now()
        rec.capture_tool = rec.capture_tool or self.tool
        probs = rec.problems()
        if not cap.files: probs.append("nothing to hold")
        if probs: return self._row(rec, None, "failed", "; ".join(probs + ([cap.status_note] if cap.status_note else [])), [])
        folder = (cap.folder or self.folder_for(rec)).replace("\\", "/").rstrip("/")
        afolder = self.abs(folder)
        hj = os.path.join(afolder, "hold.json")
        old = read_json(hj)
        if old and old["record"].get("identifier") != rec.identifier:
            folder = folder + "-" + hashlib.sha1(rec.identifier.encode("utf-8")).hexdigest()[:8]
            afolder = self.abs(folder); hj = os.path.join(afolder, "hold.json")
            old = read_json(hj)
        files = {f["name"]: f for f in (old or {}).get("files", [])}
        status = "new" if not old else "unchanged"; notes = []; written = []
        stamp = rec.capture_time.replace("-", "").replace(":", "")
        for hf in cap.files:
            data = hf.bytes(); digest = sha256(data)
            name = hf.name
            if name.lower() in RESERVED_NAMES: name = "held-" + name     # the hold's own README.md and hold.json are generated
            hf.name = name
            prev = files.get(name)
            if prev and prev["sha256"] == digest: continue
            if prev:
                stem, ext = os.path.splitext(name)
                name = f"{stem}.{stamp}{ext}"; status = "changed"
                notes.append(f"{hf.name} differs from the held copy; held as {name}")
            elif old: status = "changed"; notes.append(f"{name} new in this capture")
            relp = f"{folder}/{name}"
            np = self.check_name(relp)
            if np: return self._row(rec, folder, "failed", f"{name}: " + "; ".join(np), [])
            entry = dict(name=name, role=hf.role, bytes=len(data), sha256=digest, how=hf.how, captured=rec.capture_time)
            if hf.role == "derived": entry.update(derived_from=hf.derived_from, tool=hf.tool)
            if hf.role == "linked": entry.update(link=hf.link)               # held by link: recorded, the bytes not stored
            entry.update(hf.extra)                                            # a normalised copy's marks (normalised_copy)
            files[name] = entry
            if hf.role != "linked": written.append((name, data))
        h = dict(schema=S.SCHEMA_VERSION, adapter=self.tool, hold_module=HOLD_MODULE, record=rec.as_dict(),
                 files=sorted(files.values(), key=lambda f: (f["role"] != "held", f["name"])),
                 captures=(old or {}).get("captures", []) + [dict(time=rec.capture_time, tool=rec.capture_tool, status=status,
                                                                  provenance=rec.provenance, note="; ".join(notes) or cap.status_note)],
                 status_note=cap.status_note)
        stored = sum(f["bytes"] for f in h["files"] if f["role"] != "linked")
        h["size"] = dict(bytes=stored, size_class=size_class(stored), linked_bytes=sum(f["bytes"] for f in h["files"] if f["role"] == "linked"))
        if (old or {}).get("removed"): h["removed"] = old["removed"]       # the record of removed duplicates outlives a re-capture
        for k, v in cap.extra.items():
            if k in h: raise ValueError(f"Capture.extra may not replace hold.json's own key {k!r}")
            h[k] = v
        if old and status == "unchanged":
            h["record"] = dict(old["record"]); h["record"]["capture_time"] = old["record"].get("capture_time")
        if self.dry: return self._row(rec, folder, status, "dry run: nothing written", [n for n, _ in written], h)
        os.makedirs(afolder, exist_ok=True)
        for name, data in written:
            p = os.path.join(afolder, name)
            if os.path.exists(p): raise RuntimeError(f"refusing to overwrite a held file: {self.rel(p)}")
            with open(p, "wb") as f: f.write(data)
        with LN.open_write(hj) as f: json.dump(h, f, indent=1, ensure_ascii=False, sort_keys=False); f.write("\n")
        LN.write_text(os.path.join(afolder, "README.md"), readme_text(h))
        return self._row(rec, folder, status, "; ".join(notes) or cap.status_note, [n for n, _ in written], h)

    def _row(self, rec, folder, status, note, written, h=None):
        files = (h or {}).get("files", [])
        stored = sum(f["bytes"] for f in files if f["role"] != "linked")
        return dict(identifier=rec.identifier, media_kind=rec.media_kind, title=rec.title, date=rec.date, hold=folder,
                    status=status, files=len(files), bytes=stored, size_class=size_class(stored) if files else "", written=written,
                    captured=rec.capture_time, adapter=self.tool, note=note)


MANIFEST_COLUMNS = ["identifier", "media_kind", "title", "date", "hold", "status", "files", "bytes", "size_class", "captured", "adapter", "note"]


def write_manifest(rows, path):
    """Append manifest rows to a TSV (header written when the file is new); LF; tabs and newlines in cells become spaces. A file
    begun with an earlier header keeps its own columns, so rows appended later line up with the rows already there."""
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    cols = MANIFEST_COLUMNS if new else (LN.first_line(path) if hasattr(LN, "first_line") else read_raw(path).split("\n", 1)[0]).rstrip("\n").split("\t")
    with LN.open_append(path) as f:
        if new: f.write("\t".join(cols) + "\n")
        for r in rows: f.write("\t".join(re.sub(r"[\t\r\n]+", " ", str(r.get(c, "") if r.get(c) is not None else "")) for c in cols) + "\n")
    return path


def load_hold(folder):
    """hold.json of a hold folder as a dict, or None."""
    p = os.path.join(folder, "hold.json")
    return read_json(p)


def verify_hold(folder):
    """Every file hold.json lists exists with its bytes and SHA-256; README.md is what readme_text() makes of hold.json. Returns a
    list of problems ([] when the hold is intact)."""
    h = load_hold(folder); out = []
    if not h: return [f"{folder}: no hold.json"]
    for f in h["files"]:
        if f["role"] == "linked": continue                              # held by link: the bytes are at f["link"], not here
        p = os.path.join(folder, f["name"])
        if not os.path.isfile(p): out.append(f"{f['name']}: missing"); continue
        if os.path.getsize(p) != f["bytes"]: out.append(f"{f['name']}: {os.path.getsize(p)} bytes, hold.json says {f['bytes']}")
        if file_sha256(p) != f["sha256"]: out.append(f"{f['name']}: SHA-256 differs from hold.json")
    rp = os.path.join(folder, "README.md")
    if not os.path.isfile(rp) or read_raw(rp) != readme_text(h): out.append("README.md is not the generated form of hold.json")
    return out
