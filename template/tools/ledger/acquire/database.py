"""The database adapter (phase 3 of tools/platform-plan.md, 2026-10-22; phase 7: "connection or export read record by record, each
record held byte-for-byte with identifier, table, timestamp and query as provenance; media fields fetched and transcribed locally;
re-read on schedule with new and changed records queued; the setup scan runs over the hold"; setup stage 2, schema mapping).

The recipient keeps sources in a database of their own whose schema the ledger does not know. Five steps, each a command:

    introspect   tables, columns (declared and inferred types), primary and foreign keys (declared, and inferred from names and
                 values where none are declared), row counts, sample values per column, per-column shares (null, date, URL, path,
                 long text), written to a JSON report
    propose      a mapping.toml from the report: the record unit (the table one record of the hold comes from), a column or an
                 expression per hold-schema field with a confidence and the alternatives, the media fields, the date fields with
                 their formats, the unmapped columns kept as metadata, the annotation tables and the register each lands in. The
                 group confirms or corrects it (setup stage 2) before anything is held in the hold proper.
    dry-run      holds five records (the first five by the record order) under wip/db-dry-run/<database>/ with their READMEs, so the
                 group sees what a record will look like before the mapping is saved
    run          every record into sources/db/<database>/<record>/; unchanged records are recognised by the SHA-256 of their rows
                 (the row digest) and skipped; new and changed ones are listed in sources/db/<database>/queue.tsv for intake
    rescan       the saved mapping against the live schema: tables and columns added, removed or retyped, mapped columns that no
                 longer exist (the mapping breaks), new columns not mapped (offered), row-count changes; with --records, the new and
                 changed records since the last run (the scheduled re-read)

A field may name several sources tried in order per record (`alternatives` as a list of tables; phase 6a handoffs H1 and H3): the
text from segment rows (with chapter labels and the channel description), else a body column, else every text attachment; the date
from a full-date column, else month and year read together, else the year, the first that parses setting the precision.

A record's hold: record.json (held: the record row and every related row the mapping reads, serialised as read, keys sorted, BLOBs
replaced by a pointer to the held file), the media files found at their paths (held byte-for-byte), text.md or transcript.md
(derived by the mapping; a segments table renders in tools/fetch_transcript.py's form), annotations.json (derived: the annotation
rows with their register, teller "their database" and reading "the group's reading"), README.md and hold.json. Provenance is the
engine, the source (passwords redacted) and every query with its parameters.

Engines: SQLite and CSV now (a CSV file or a folder of CSV files, loaded into an in-memory SQLite database, one table per file). The
others are an extension point: subclass Engine (tables, columns, foreign_keys, count, select, query) and register it in ENGINES;
ENGINE_TABLE lists what each needs. The adapter only reads: SQLite is opened read-only (mode=ro).

    python3 tools/ledger/acquire/database.py introspect <source> [--out report.json]
    python3 tools/ledger/acquire/database.py propose <source> [--name NAME] [--out mapping.toml]
    python3 tools/ledger/acquire/database.py dry-run <mapping.toml> [--n 5]
    python3 tools/ledger/acquire/database.py run <mapping.toml> [--limit N]
    python3 tools/ledger/acquire/database.py rescan <mapping.toml> [--records] [--out report.json]
<source>: sqlite:///abs/path.db, sqlite:rel/path.db, a .db/.sqlite file, csv:<file or folder>, a .csv file or a folder of CSVs.
"""
import base64, csv, datetime, hashlib, io, json, os, re, sqlite3, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B
from ledger.acquire import schema as S
from ledger.acquire import _toml as T
from ledger.acquire import transcribe as TR

# ============================================================================================================ engines
ENGINE_TABLE = [
    # engine, connection form, Python driver, what the group's machine needs, introspection source, status
    dict(engine="SQLite", form="sqlite:///path/to/file.db (or the file path)", driver="sqlite3 (standard library)",
         needs="nothing", introspection="sqlite_master, PRAGMA table_info and foreign_key_list", status="built"),
    dict(engine="CSV export", form="csv:path (a file, or a folder with one CSV per table)", driver="csv (standard library)",
         needs="nothing; UTF-8 files with a header row", introspection="header row; types inferred from values; keys inferred from names and values",
         status="built"),
    dict(engine="PostgreSQL", form="postgresql://user@host:5432/db", driver="psycopg (3) or psycopg2",
         needs="the driver wheel; network access to the server; a read-only role", introspection="information_schema.columns, table_constraints, key_column_usage; pg_class.reltuples for counts",
         status="extension point"),
    dict(engine="MySQL / MariaDB", form="mysql://user@host:3306/db", driver="PyMySQL or mysql-connector-python",
         needs="the driver wheel; a read-only account", introspection="information_schema.columns, key_column_usage (referenced_table_name)",
         status="extension point"),
    dict(engine="Microsoft SQL Server", form="mssql+pyodbc://user@dsn", driver="pyodbc",
         needs="pyodbc and the Microsoft ODBC Driver 18 for SQL Server; Windows or Kerberos authentication as the site uses",
         introspection="INFORMATION_SCHEMA views, sys.foreign_keys", status="extension point"),
    dict(engine="Oracle", form="oracle://user@host:1521/service", driver="python-oracledb (thin mode, no client install)",
         needs="the driver wheel; a read-only schema user", introspection="ALL_TAB_COLUMNS, ALL_CONSTRAINTS, ALL_CONS_COLUMNS",
         status="extension point"),
    dict(engine="Microsoft Access", form="access:path/to/file.accdb", driver="pyodbc with the Access Database Engine (Windows), or mdbtools export to CSV elsewhere",
         needs="the Access ODBC driver on Windows; on macOS and Linux export with mdb-export and use the CSV engine",
         introspection="ODBC catalog functions (cursor.tables, cursor.columns, cursor.foreignKeys)", status="extension point"),
    dict(engine="DuckDB", form="duckdb:path/to/file.duckdb", driver="duckdb", needs="the duckdb wheel",
         introspection="information_schema; duckdb_constraints()", status="extension point"),
    dict(engine="Excel workbook", form="xlsx:path (one sheet per table)", driver="openpyxl",
         needs="openpyxl (already a dependency of the bulk adapter)", introspection="header row per sheet; types and keys inferred as for CSV",
         status="extension point (or save each sheet as CSV)"),
    dict(engine="MongoDB / document stores", form="mongodb://host/db", driver="pymongo",
         needs="the driver wheel; a decision on the record unit (a collection) and how nested documents flatten",
         introspection="a sample of documents per collection; field paths and types from the sample", status="extension point"),
    dict(engine="FileMaker, Airtable, NocoDB, spreadsheets in a shared drive", form="export to CSV", driver="the CSV engine",
         needs="an export with a header row; attachments exported beside it with their paths in a column",
         introspection="as CSV", status="via export"),
]


def redact(spec):
    return re.sub(r"(//[^:/@]+:)[^@]*@", r"\1***@", spec)


class Engine:
    """The extension point: one per database engine. Every method reads; none writes."""
    name = "engine"

    def tables(self): raise NotImplementedError
    def columns(self, table): raise NotImplementedError          # [{name, type, notnull, pk}]
    def foreign_keys(self, table): raise NotImplementedError     # [{column, ref_table, ref_column}]
    def count(self, table): raise NotImplementedError
    def select(self, table, where=None, params=(), order=None, limit=None): raise NotImplementedError   # (sql, [row dicts])
    def query(self, sql, params=()): raise NotImplementedError   # [row dicts]
    def close(self): pass


class SQLiteEngine(Engine):
    name = "sqlite"

    def __init__(self, path, con=None):
        self.path = path
        self.con = con or sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    @staticmethod
    def q(ident): return '"' + str(ident).replace('"', '""') + '"'

    def tables(self):
        return [r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    def columns(self, table):
        return [dict(name=r["name"], type=(r["type"] or "").upper(), notnull=bool(r["notnull"]), pk=int(r["pk"]))
                for r in self.con.execute(f"PRAGMA table_info({self.q(table)})")]

    def foreign_keys(self, table):
        return [dict(column=r["from"], ref_table=r["table"], ref_column=r["to"]) for r in self.con.execute(f"PRAGMA foreign_key_list({self.q(table)})")]

    def count(self, table):
        return self.con.execute(f"SELECT count(*) FROM {self.q(table)}").fetchone()[0]

    def select(self, table, where=None, params=(), order=None, limit=None):
        sql = f"SELECT * FROM {self.q(table)}" + (f" WHERE {where}" if where else "") + (f" ORDER BY {order}" if order else "") + (f" LIMIT {int(limit)}" if limit else "")
        return sql, [dict(r) for r in self.con.execute(sql, params)]

    def query(self, sql, params=()):
        return [dict(r) for r in self.con.execute(sql, params)]

    def close(self): self.con.close()


class CSVEngine(SQLiteEngine):
    """A CSV file or a folder of CSV files, loaded into an in-memory SQLite database (one table per file, named by the file's stem);
    a column's type is INTEGER, REAL or TEXT by its values. CSVs declare no keys: foreign keys are inferred (introspect)."""
    name = "csv"

    def __init__(self, path):
        self.path = path
        files = [path] if os.path.isfile(path) else sorted(os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith((".csv", ".tsv")))
        if not files: raise FileNotFoundError(f"{path}: no CSV files")
        con = sqlite3.connect(":memory:")
        self.files = {}
        for f in files:
            t = re.sub(r"\W+", "_", os.path.splitext(os.path.basename(f))[0]).strip("_") or "table"
            with open(f, encoding="utf-8-sig", newline="") as h:
                rows = list(csv.reader(h, delimiter="\t" if f.lower().endswith(".tsv") else ","))
            if not rows: continue
            hdr = [c.strip() or f"column_{i + 1}" for i, c in enumerate(rows[0])]; body = rows[1:]
            types = []
            for i in range(len(hdr)):
                vals = [r[i] for r in body if i < len(r) and r[i] != ""]
                if vals and all(re.fullmatch(r"-?\d+", v) for v in vals): types.append("INTEGER")
                elif vals and all(re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", v) for v in vals): types.append("REAL")
                else: types.append("TEXT")
            con.execute(f"CREATE TABLE {self.q(t)} (" + ", ".join(f"{self.q(h)} {ty}" for h, ty in zip(hdr, types)) + ")")
            conv = {"INTEGER": int, "REAL": float, "TEXT": str}
            for r in body:
                r = (r + [""] * len(hdr))[:len(hdr)]
                con.execute(f"INSERT INTO {self.q(t)} VALUES (" + ",".join("?" * len(hdr)) + ")",
                            [None if v == "" else conv[ty](v) for v, ty in zip(r, types)])
            self.files[t] = f
        con.commit()
        super().__init__(path, con=con)

    def foreign_keys(self, table): return []


ENGINES = {"sqlite": SQLiteEngine, "csv": CSVEngine}


def connect(spec):
    """An Engine for a source string (module docstring)."""
    s = str(spec)
    m = re.match(r"^([a-z][a-z0-9+]*):(.*)$", s)
    if m and len(m.group(1)) > 1:
        scheme, rest = m.group(1), m.group(2)
        if scheme == "sqlite": return SQLiteEngine(rest[2:] if rest.startswith("//") else rest)
        if scheme == "csv": return CSVEngine(rest)
        row = next((e for e in ENGINE_TABLE if scheme.split("+")[0] in e["form"]), None)
        raise NotImplementedError(f"engine {scheme!r} is an extension point: subclass Engine and register it in ENGINES"
                                  + (f" (needs: {row['driver']}; {row['needs']})" if row else ""))
    if os.path.isdir(s) or s.lower().endswith((".csv", ".tsv")): return CSVEngine(s)
    if s.lower().endswith((".db", ".sqlite", ".sqlite3")) or os.path.isfile(s): return SQLiteEngine(s)
    raise FileNotFoundError(s)


# ============================================================================================================ value shapes
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
                "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d", "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%m/%Y", "%Y-%m", "%Y"]
MONTH_FORMATS = {"%B %Y", "%b %Y", "%m/%Y", "%m %Y", "%Y-%m", "%Y/%m"}          # formats whose precision is the month
SEPARATORS = [" / ", "; ", ";", " | ", "|", " & ", " and ", "\n", ", "]      # how a catalogue joins several names in one cell
LOW_CARDINALITY = 40                                                         # introspect keeps every distinct value of such a column
MONTH_NAMES = {m.lower() for m in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                                   "November", "December", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"]}
URL_RE = re.compile(r"^(https?|ftp|file)://\S+$", re.I)
PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\.{0,2}[\\/])?(?:[^\\/\n]+[\\/])*[^\\/\n]+\.[A-Za-z0-9]{2,5}$")
MEDIA_EXTS = {"mp3", "wav", "m4a", "flac", "ogg", "opus", "mp4", "mov", "mkv", "avi", "webm", "m4v", "pdf", "png", "jpg", "jpeg",
              "tif", "tiff", "webp", "txt", "md", "html", "htm", "doc", "docx"}


def parses(v, fmt):
    try:
        datetime.datetime.strptime(str(v).strip(), fmt); return True
    except ValueError:
        return False


def date_format(values):
    """(format, share of values it parses, ambiguous) for a column's sample: the format that parses the most values; day-first and
    month-first are told apart by any value whose first or second part exceeds 12; when none does, ambiguous=True."""
    vals = [str(v).strip() for v in values if v not in (None, "")]
    if not vals: return None, 0.0, False
    best = None
    for f in DATE_FORMATS:
        n = sum(parses(v, f) for v in vals)
        if n and (best is None or n > best[1]): best = (f, n)
    if not best: return None, 0.0, False
    fmt, n = best; amb = False
    if fmt in ("%d/%m/%Y", "%m/%d/%Y"):
        dmy = sum(parses(v, "%d/%m/%Y") for v in vals); mdy = sum(parses(v, "%m/%d/%Y") for v in vals)
        if dmy > mdy: fmt = "%d/%m/%Y"
        elif mdy > dmy: fmt = "%m/%d/%Y"
        else: fmt = "%d/%m/%Y"; amb = any(re.match(r"(\d+)/(\d+)/", v) and re.match(r"(\d+)/(\d+)/", v).group(1) != re.match(r"(\d+)/(\d+)/", v).group(2) for v in vals)
        n = max(dmy, mdy)
    return fmt, round(n / len(vals), 3), amb


def to_iso(raw, fmt, ambiguous=False):
    """The ISO date of a raw value under a format (YYYY, YYYY-MM or YYYY-MM-DD by the format's precision); a trailing `?` when
    the column's day and month order could not be told and this value's day and month differ; None when it does not parse."""
    if raw in (None, ""): return None
    if isinstance(raw, (int, float)) and fmt in (None, "%Y") and 1000 <= raw <= 2999: return str(int(raw))
    try: d = datetime.datetime.strptime(str(raw).strip(), fmt)
    except (ValueError, TypeError): return None
    iso = d.strftime("%Y") if fmt in ("%Y",) else d.strftime("%Y-%m") if fmt in MONTH_FORMATS else d.date().isoformat()
    if ambiguous and fmt in ("%d/%m/%Y", "%m/%d/%Y") and d.day <= 12 and d.day != d.month: iso += "?"
    return iso


def shape(values):
    """Shares of a column's sample that look like dates, URLs, file paths, media files; the mean text length; numeric share."""
    vals = [v for v in values if v not in (None, "")]
    if not vals: return dict(date=0.0, url=0.0, path=0.0, media=0.0, mean_length=0, numeric=0.0, month_names=0.0, separators={})
    sv = [str(v) for v in vals]
    fmt, dshare, amb = date_format(sv)
    if all(isinstance(v, (int, float)) for v in vals): dshare = 0.0 if not all(1000 <= v <= 2999 for v in vals if isinstance(v, (int, float))) else dshare
    url = sum(bool(URL_RE.match(s)) for s in sv) / len(sv)
    path = sum(bool(PATH_RE.match(s)) and not URL_RE.match(s) for s in sv) / len(sv)
    media = sum(s.rsplit(".", 1)[-1].lower() in MEDIA_EXTS for s in sv if "." in s and (PATH_RE.match(s) or URL_RE.match(s))) / len(sv)
    numeric = sum(isinstance(v, (int, float)) or bool(re.fullmatch(r"-?\d+(\.\d+)?", str(v))) for v in vals) / len(vals)
    month = sum(s.strip().lower().rstrip(".") in MONTH_NAMES for s in sv) / len(sv)
    seps = {sep: sum(sep in s for s in sv) for sep in SEPARATORS}
    return dict(date=dshare, date_format=fmt, date_ambiguous=amb, url=round(url, 3), path=round(path, 3), media=round(media, 3),
                mean_length=round(sum(len(s) for s in sv) / len(sv)), numeric=round(numeric, 3), month_names=round(month, 3),
                separators={k: v for k, v in seps.items() if v})


def _jsonable(v):
    if isinstance(v, bytes): return {"$blob": True, "bytes": len(v), "sha256": B.sha256(v)}
    return v


# ============================================================================================================ introspect
def introspect(engine, spec="", sample=5, scan=2000):
    """The schema report: per table its row count, columns (declared type, inferred shape over up to `scan` values, null share,
    distinct count, `sample` distinct example values cut to 120 characters), foreign keys (declared, else inferred: a column named
    like another table's key whose sampled values all occur there), and the tables that reference it."""
    rep = dict(source=redact(spec), engine=engine.name, introspected=B.utc_now(), tables=[])
    tabs = engine.tables(); info = {}
    for t in tabs:
        cols = engine.columns(t); n = engine.count(t)
        _, rows = engine.select(t, limit=scan)
        tcols = []
        for c in cols:
            vals = [r.get(c["name"]) for r in rows]
            nn = [v for v in vals if v is not None and v != ""]
            distinct = []
            for v in nn:
                key = v if not isinstance(v, bytes) else B.sha256(v)
                if key not in distinct: distinct.append(key)
            ex = []
            for v in nn:
                s = f"<blob {len(v)} bytes>" if isinstance(v, bytes) else (str(v) if len(str(v)) <= 120 else str(v)[:117] + "...")
                if s not in ex: ex.append(s)
                if len(ex) >= sample: break
            col = dict(name=c["name"], declared_type=c["type"], pk=c["pk"], notnull=c["notnull"],
                       null_share=round(1 - len(nn) / len(vals), 3) if vals else None, distinct=len(distinct),
                       distinct_share=round(len(distinct) / len(nn), 3) if nn else None, samples=ex,
                       shape=shape([v for v in nn if not isinstance(v, bytes)]), blob=any(isinstance(v, bytes) for v in nn))
            if nn and len(distinct) <= LOW_CARDINALITY and not col["blob"]:
                counts = {}
                for v in nn: counts[v] = counts.get(v, 0) + 1
                # every distinct value with its count (a code column's full value set, not five samples: handoff H6 of phase 6a)
                col["values"] = [[v if isinstance(v, (int, float)) else (str(v) if len(str(v)) <= 120 else str(v)[:117] + "..."), n]
                                 for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))]
            tcols.append(col)
        info[t] = dict(name=t, rows=n, columns=tcols, foreign_keys=[dict(fk, declared=True) for fk in engine.foreign_keys(t)], referenced_by=[], _rows=rows)
    # inferred foreign keys where a table declares none
    pks = {t: [c["name"] for c in i["columns"] if c["pk"]] or [c["name"] for c in i["columns"][:1]] for t, i in info.items()}
    for t, i in info.items():
        declared = {fk["column"] for fk in i["foreign_keys"]}
        for c in i["columns"]:
            if c["name"] in declared or c["pk"]: continue
            toks = S.name_tokens(c["name"])
            for t2, keys in pks.items():
                if t2 == t: continue
                for k in keys:
                    named = (c["name"].lower() == k.lower() or toks[:-1] and "_".join(toks[:-1]) in (t2.lower(), t2.lower().rstrip("s"))
                             and toks[-1] in ("id", "no", "key", "ref", "num"))
                    if not named: continue
                    have = {r.get(k) for r in info[t2]["_rows"]}
                    vals = [r.get(c["name"]) for r in i["_rows"] if r.get(c["name"]) is not None]
                    if vals and all(v in have for v in vals):
                        i["foreign_keys"].append(dict(column=c["name"], ref_table=t2, ref_column=k, declared=False))
    for t, i in info.items():
        for fk in i["foreign_keys"]:
            if fk["ref_table"] in info: info[fk["ref_table"]]["referenced_by"].append(dict(table=t, column=fk["column"], ref_column=fk["ref_column"]))
    for t in tabs:
        info[t].pop("_rows"); rep["tables"].append(info[t])
    rep["fingerprint"] = fingerprint(rep)
    return rep


def fingerprint(rep):
    """SHA-256 over the tables, columns and declared types (not counts or samples): a schema change changes it."""
    s = json.dumps([[t["name"], [[c["name"], c["declared_type"]] for c in t["columns"]]] for t in sorted(rep["tables"], key=lambda t: t["name"])])
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ============================================================================================================ propose
RECORD_TABLE_WORDS = {"records", "record", "items", "item", "documents", "document", "docs", "sources", "source", "entries", "entry",
                      "videos", "video", "interviews", "interview", "recordings", "recording", "files", "cases", "case", "reports",
                      "articles", "posts", "testimonies", "testimony", "accessions", "objects", "materials", "sightings", "events"}
ANNOTATION_WORDS = {"annotations", "annotation", "codes", "coding", "codings", "tags", "tag", "labels", "label", "claims", "claim",
                    "notes", "comments", "comment", "remarks", "assessments", "assessment", "highlights", "excerpts", "quotes",
                    "relations", "links", "mentions", "speakers", "people", "persons", "events", "timeline"}
SEGMENT_WORDS = {"transcript", "transcripts", "segments", "segment", "utterances", "utterance", "lines", "rows", "turns", "captions",
                 "subtitles", "pages", "paragraphs", "chunks", "passages"}
MEDIA_WORDS = {"attachments", "attachment", "media", "files", "file", "assets", "asset", "blobs", "scans", "scan", "images", "audio",
               "recordings", "documents", "exhibits", "exhibit"}
KIND_CODES = {  # a whole value or one of its words -> the hold's media kind (catalogue codes as groups write them)
    "vid": "video", "video": "video", "vod": "video", "film": "video", "movie": "video", "tv": "video", "youtube": "video",
    "aud": "audio", "audio": "audio", "pod": "audio", "podcast": "audio", "radio": "audio", "tape": "audio", "mp3": "audio",
    "doc": "document", "document": "document", "pdf": "document", "scn": "document", "scan": "document", "rpt": "document",
    "report": "document", "memo": "document", "ltr": "document", "letter": "document", "book": "document", "paper": "document",
    "web": "web-page", "www": "web-page", "htm": "web-page", "html": "web-page", "url": "web-page", "page": "web-page",
    "blg": "web-page", "blog": "web-page", "article": "web-page",
    "pst": "post", "post": "post", "twt": "post", "tweet": "post", "reddit": "post", "comment": "post",
    "thr": "thread", "thd": "thread", "thread": "thread", "forum": "thread", "discussion": "thread",
    "can": "canon", "canon": "canon", "scripture": "canon", "bible": "canon", "treatise": "canon", "classic": "canon",
    "arc": "archive-item", "arch": "archive-item", "archive": "archive-item", "release": "archive-item",
    "img": "image", "image": "image", "photo": "image", "jpg": "image", "png": "image", "pic": "image",
    "txt": "text", "text": "text", "transcript": "text", "rss": "feed", "feed": "feed", "rec": "record", "record": "record"}
REGISTERS = [("claims", {"claim", "claims", "statement", "statements", "assertion", "quote", "quotes", "excerpt", "coding", "coded"}),
             ("people", {"person", "people", "persons", "speaker", "speakers", "name", "names", "witness", "role", "participant", "author"}),
             ("relations", {"relation", "relations", "relationship", "knows", "link", "links", "source", "target"}),
             ("timeline", {"event", "events", "timeline", "occurred", "happened"}),
             ("subjects", {"tag", "tags", "label", "labels", "subject", "subjects", "topic", "topics", "keyword", "keywords", "category"})]
CODER_WORDS = {"coder", "annotator", "analyst", "reviewer", "rater", "coded", "by"}
RAW_WORDS = {"written", "raw", "original", "verbatim", "spelled", "spelling", "literal", "seen"}          # the source's own spelling
NORMAL_WORDS = {"normal", "normalised", "normalized", "canonical", "standard", "std", "clean", "cleaned", "norm"}   # the catalogue's reading
HEADING_WORDS = {"section", "chapter", "heading", "header", "label", "part", "title", "topic", "segment"}
BODY_WORDS = {"body", "text", "content", "contents", "fulltext", "full", "transcript", "article", "html", "markdown"}
DESCRIPTION_WORDS = {"description", "desc", "blurb", "summary", "abstract", "synopsis"}
ENTRY_TIME_WORDS = {"entered", "created", "modified", "updated", "imported", "ingested", "captured", "loaded", "inserted", "catalogued", "cataloged"}
REFERENCE_WORDS = {"ref", "reference", "accession", "acc", "catalogue", "catalog", "call", "shelfmark", "signature", "esdn", "control",
                   "case", "number", "no", "doc", "document"}
SURROGATE_WORDS = {"uuid", "guid", "uid", "pk", "rowid", "oid"}


def _tok(name): return set(S.name_tokens(name))


def _col(rep_t, name): return next(c for c in rep_t["columns"] if c["name"] == name)


def _coverage(c):
    return 1 - (c.get("null_share") or 0)


def _field_candidates(t, field, used=()):
    """[(score, column, why)] for one field over a table's columns: the name's synonym score and a value check per field. For the
    date the score is weighed by the column's coverage (the share of rows with a value): a column that parses perfectly but is empty
    in most rows (a year kept only where the full date is unknown) ranks below the column that holds most rows' dates."""
    out = []
    for c in t["columns"]:
        if c["name"] in used: continue
        name = S.synonym_score(c["name"], field); sh = c["shape"]; val = 0.0; why = []
        if name: why.append(f"name {name}")
        if field == "identifier":
            val = 1.0 if c["pk"] else (0.6 if c["distinct_share"] == 1.0 and c["null_share"] == 0 else 0.0)
            if c["pk"]: why.append("primary key")
        elif field == "date":
            val = sh.get("date", 0.0)
            if val: why.append(f"{val:.0%} parse as {sh.get('date_format')}, {_coverage(c):.0%} of rows have a value")
        elif field == "title":
            ml = sh.get("mean_length", 0); val = 0.6 if 8 <= ml <= 250 and (c["distinct_share"] or 0) > 0.8 and sh.get("date", 0) < 0.5 and sh.get("url", 0) < 0.5 else 0.0
        elif field == "media_link":
            val = max(sh.get("url", 0), sh.get("path", 0))
            if val: why.append(f"{val:.0%} URLs or paths")
        elif field == "text":
            ml = sh.get("mean_length", 0); val = 0.9 if ml >= 400 else 0.5 if ml >= 120 else 0.0
            if val: why.append(f"mean length {ml}")
        elif field == "media_kind":
            val = 0.5 if c["distinct"] and c["distinct"] <= 12 and (c["distinct_share"] or 1) < 0.9 else 0.0
        elif field == "speaker_or_author":
            val = 0.3 if sh.get("mean_length", 0) and sh.get("mean_length", 0) < 200 and sh.get("date", 0) < 0.5 and sh.get("url", 0) < 0.5 and sh.get("numeric", 0) < 0.5 else 0.0
        elif field == "venue":
            val = 0.3 if c["distinct_share"] is not None and c["distinct_share"] < 1.0 and sh.get("mean_length", 0) < 150 and sh.get("numeric", 0) < 0.5 else 0.0
        if field in ("date",) and not name and val < 0.8: continue
        if field not in ("identifier", "date") and not name: val *= 0.5
        score = round(0.6 * name + 0.4 * val, 3) if name else round(0.5 * val, 3)
        if field == "identifier" and c["pk"]: score = max(score, 0.95)
        if field == "date" and name and val >= 0.8: score = max(score, 0.9)
        if field == "date": score = round(score * (0.5 + 0.5 * _coverage(c)), 3)
        if score >= 0.2: out.append((score, c["name"], ", ".join(why) or "values"))
    return sorted(out, key=lambda x: (-x[0], x[1]))


def _reference_column(t, key):
    """A citable reference that should be the identifier instead of a surrogate integer key: unique, never empty, not numeric, named
    like a reference (acc_ref, accession_no, call_number, esdn), not a surrogate (uuid, guid). None when there is none."""
    best = None
    for c in t["columns"]:
        if c["name"] == key or c["pk"] or c["blob"]: continue
        toks = _tok(c["name"])
        if toks & SURROGATE_WORDS or not toks & REFERENCE_WORDS: continue
        if c.get("null_share") != 0 or c.get("distinct_share") != 1.0 or c["shape"].get("numeric", 1) >= 1.0: continue
        s = S.synonym_score(c["name"], "identifier")
        if s >= 0.7 and (best is None or s > best[0]): best = (s, c["name"])
    return best[1] if best else None


def _separator(cols):
    """The separator a catalogue joins names with, from the columns' value counts (shape separators): the most frequent of
    SEPARATORS; ", " only when nothing else joins names and most comma-holding values hold two or more commas (a lone comma is
    `Surname, Given`)."""
    counts = {}
    for c in cols:
        for sep, n in (c["shape"].get("separators") or {}).items(): counts[sep] = counts.get(sep, 0) + n
    other = {k: v for k, v in counts.items() if k != ", "}
    if other:
        sep = max(other, key=lambda k: (other[k], len(k)))
        return {"; ": ";", " | ": "|"}.get(sep, sep)
    multi = sum(1 for c in cols for s in (c.get("values") and [v for v, _ in c["values"]] or c["samples"]) if str(s).count(",") >= 2)
    single = sum(1 for c in cols for s in (c.get("values") and [v for v, _ in c["values"]] or c["samples"]) if str(s).count(",") == 1)
    return ", " if counts.get(", ") and multi > single else ";"


def _kind_values(c):
    """Every distinct value of a kind column: introspection's full value list (low-cardinality columns), else the samples."""
    return [str(v) for v, _ in c["values"]] if c.get("values") else [str(v) for v in c["samples"]]


def _guess_kind(v):
    low = str(v).strip().lower()
    if low in KIND_CODES: return KIND_CODES[low]
    for w in S.name_tokens(low):
        if w in KIND_CODES: return KIND_CODES[w]
    return "record"


def _text_column(cols):
    """The column holding an annotation or segment table's text: the text synonyms first, the source's own spelling over the
    catalogue's normal form (people.written_as over people.normal_form), then the longest values."""
    def key(c):
        toks = _tok(c["name"])
        return (S.synonym_score(c["name"], "text") + (0.3 if toks & RAW_WORDS else 0) - (0.5 if toks & NORMAL_WORDS else 0),
                c["shape"].get("mean_length", 0))
    cands = [c for c in cols if c["shape"].get("numeric", 0) < 1.0 and c["shape"].get("date", 0) < 0.8]
    return max(cands, key=key, default=None)


def _guess_register(t, textcol=None):
    """The register a table of the group's coding lands in: the text column's name weighs three, the table's name two, the other
    columns' names one; a coder column beside a text column is coded claims. Sample values are read only when the names say
    nothing."""
    tname = _tok(t["name"]); txt = _tok(textcol["name"]) if textcol is not None else set()
    others = set()
    for c in t["columns"]:
        if textcol is None or c["name"] != textcol["name"]: others |= _tok(c["name"])
    score = {}
    for reg, words in REGISTERS:
        score[reg] = 3 * len(txt & words) + 2 * len(tname & words) + len(others & words)
    if textcol is not None and others & CODER_WORDS and not (tname & {"people", "persons", "speakers", "names"}): score["claims"] += 2
    if not any(score.values()):
        samp = set()
        for c in t["columns"]:
            for s in c["samples"][:5]: samp |= set(S.name_tokens(s)[:3])
        for reg, words in REGISTERS: score[reg] = len(samp & words)
    best = max(REGISTERS, key=lambda r: score[r[0]])[0]
    return best if score[best] else "claims"


def _date_chain(rt, primary, fmt_of):
    """The date's sources in order when the best column leaves rows empty: other day-precision date columns named as dates, then a
    month column and a year column read together, then the year column alone (a catalogue that splits a date by what it knows).
    Columns named like the catalogue's own entry times (entered_at, created) are never the item's date."""
    chain = [dict(column=primary, format=fmt_of(primary))]
    if (_col(rt, primary).get("null_share") or 0) == 0: return chain
    named = lambda c: S.synonym_score(c["name"], "date") > 0 and not (_tok(c["name"]) & ENTRY_TIME_WORDS)
    for c in sorted(rt["columns"], key=lambda c: -_coverage(c)):
        f = c["shape"].get("date_format")
        if c["name"] != primary and named(c) and c["shape"].get("date", 0) >= 0.8 and f and "%d" in f:
            chain.append(dict(column=c["name"], format=f))
    month = next((c for c in rt["columns"] if c["shape"].get("month_names", 0) >= 0.8 or
                  (_tok(c["name"]) & {"month", "mon", "mo"} and c["shape"].get("numeric", 0) == 1.0)), None)
    year = next((c for c in rt["columns"] if _tok(c["name"]) & {"year", "yr", "yyyy"} and c["shape"].get("date_format") == "%Y"), None)
    if month and year:
        vals = [str(v) for v, _ in (month.get("values") or [])] or month["samples"]
        mf = "%m %Y" if month["shape"].get("numeric", 0) == 1.0 else ("%b %Y" if all(len(v.strip(".")) <= 3 for v in vals) else "%B %Y")
        chain.append(dict(template="{" + month["name"] + "} {" + year["name"] + "}", format=mf))
    if year and year["name"] != primary:
        chain.append(dict(column=year["name"], format="%Y"))
    return chain


def _description_column(engine, rt, key, seg, cands):
    """A record-table column that, for the records with segment rows, is short beside their transcript (under a quarter of its
    length in the median, present in at least half of them): the channel's description, rendered as the transcript's closing
    block. Read from the rows when an engine is at hand; otherwise by name (description, blurb, summary, abstract)."""
    for c in cands:
        if engine is not None:
            try:
                q = engine.q
                rows = engine.query(f"SELECT r.{q(c)} AS d, (SELECT SUM(LENGTH(s.{q(seg['text'])})) FROM {q(seg['table'])} s WHERE s.{q(seg['key'])} = r.{q(key)}) AS n "
                                    f"FROM {q(rt['name'])} r WHERE EXISTS (SELECT 1 FROM {q(seg['table'])} s WHERE s.{q(seg['key'])} = r.{q(key)})")
            except Exception:
                rows = None
            if rows:
                have = [r for r in rows if r["d"] not in (None, "") and r["n"]]
                if len(have) >= 0.5 * len(rows):
                    ratios = sorted(len(str(r["d"])) / r["n"] for r in have)
                    if ratios and ratios[len(ratios) // 2] < 0.25: return c, f"for the {len(have)} records with segment rows, {c} is under a quarter of the transcript's length (median {ratios[len(ratios) // 2]:.2f}): their description"
                continue
        if _tok(c) & DESCRIPTION_WORDS: return c, f"named as a description ({c})"
    return None, None


def propose(rep, name=None, source=None, base_dir=None, engine=None):
    """A mapping (a dict in mapping.toml's form) from an introspection report. `engine` (or a local `source`, opened read-only)
    lets the proposer read rows where the report's shapes cannot decide (which column is a video's description)."""
    tabs = {t["name"]: t for t in rep["tables"]}
    own_engine = None
    if engine is None and source:
        try: engine = own_engine = connect(source)
        except Exception: engine = None

    def table_score(t):
        toks = _tok(t["name"]); s = 0.0
        if toks & RECORD_TABLE_WORDS: s += 2
        if toks & ANNOTATION_WORDS or toks & SEGMENT_WORDS: s -= 2
        s += 1.5 * len({r["table"] for r in t["referenced_by"]})
        if t["foreign_keys"] and not t["referenced_by"]: s -= 1.5
        if _field_candidates(t, "title"): s += 1
        if _field_candidates(t, "date"): s += 0.5
        return round(s, 2)

    ranked = sorted(tabs.values(), key=lambda t: (-table_score(t), t["name"]))
    rt = ranked[0]
    key = next((c["name"] for c in rt["columns"] if c["pk"]), rt["columns"][0]["name"])
    conf_rt = min(0.99, 0.5 + 0.1 * table_score(rt)) if table_score(rt) > 0 else 0.3
    m = {"__comment__": "mapping.toml: the schema mapping of setup stage 2 (tools/hold-schema.md section 6), proposed by "
                        "ledger.acquire.database; confirm or correct each section, set [mapping] confirmed and confirmed_by, then run.\n"
                        "Confidence is the proposer's (0 to 1); alternatives are the next candidates (a list of names), or, for the text and "
                        "the date, the sources tried in order per record (a list of tables). Nothing here is applied before the dry run.",
         "mapping": dict(version=1, database=B.safe_slug(name or os.path.splitext(os.path.basename(str(source or "database")))[0], 40),
                         source=redact(str(source or rep.get("source", ""))), engine=rep["engine"], proposed=B.utc_now(),
                         proposer="ledger.acquire.database " + B.VERSION, confirmed="", confirmed_by=""),
         "record": dict(table=rt["name"], key=key, order=key, where="", confidence=round(conf_rt, 2),
                        alternatives=[t["name"] for t in ranked[1:4]],
                        why=f"score {table_score(rt)}: referenced by {len(rt['referenced_by'])} table(s), name and columns"),
         "fields": {}}
    F = m["fields"]
    ref = _reference_column(rt, key)
    if ref:
        F["identifier"] = dict(column=ref, prefix="", confidence=0.85, alternatives=[key],
                               why=f"{ref} is unique, never empty and named as a reference: the catalogue's citable identifier ({key} is its internal key)")
    else:
        F["identifier"] = dict(column=key, prefix=rt["name"] + "/", confidence=0.95, why="the record table's primary key")
    used = {F["identifier"]["column"]}
    for field in ("title", "date", "venue", "media_link"):
        c = _field_candidates(rt, field, used | ({key} if field != "date" else set()))
        if not c: continue
        F[field] = dict(column=c[0][1], confidence=c[0][0], why=c[0][2], alternatives=[x[1] for x in c[1:4]])
        used.add(c[0][1])
        if field == "date":
            fmt_of = lambda col: _col(rt, col)["shape"].get("date_format") or "%Y-%m-%d"
            F["date"]["format"] = fmt_of(c[0][1])
            if _ambiguous_column(rt, c[0][1]): F["date"]["ambiguous"] = True
            chain = _date_chain(rt, c[0][1], fmt_of)
            if len(chain) > 1:
                for s in chain:
                    if s.get("column") and _ambiguous_column(rt, s["column"]): s["ambiguous"] = True
                F["date"]["candidates"] = F["date"].pop("alternatives")
                F["date"]["alternatives"] = [T.Inline(s) for s in chain]
                F["date"]["why"] += (f"; {_col(rt, c[0][1])['null_share']:.0%} of rows have no {c[0][1]}, so the date is read from the sources in "
                                     "order, the first that parses setting the precision")
                for s in chain: used |= spec_columns(s)
    # speakers: every column that names people, joined into the list field, split by the separator the values use
    sp = [x for x in _field_candidates(rt, "speaker_or_author", used) if x[0] >= 0.5]
    if sp:
        cols = [_col(rt, x[1]) for x in sp]
        F["speaker_or_author"] = dict(columns=[x[1] for x in sp], split=_separator(cols), confidence=sp[0][0],
                                      why=", ".join(f"{x[1]} ({x[2]})" for x in sp) + f"; names joined by {_separator(cols)!r} in the values")
        used.update(x[1] for x in sp)
    # media kind: a code column with a value map over every distinct value, else "record"
    kc = [x for x in _field_candidates(rt, "media_kind", used) if x[0] >= 0.4]
    if kc:
        col = kc[0][1]; vals = _kind_values(_col(rt, col))
        vm = T.Inline({v: _guess_kind(v) for v in vals})
        F["media_kind"] = dict(column=col, value_map=vm, default="record", confidence=kc[0][0],
                               why=kc[0][2] + f"; {len(vals)} distinct values" + (" (all)" if _col(rt, col).get("values") else " (sampled)"))
        used.add(col)
    else:
        F["media_kind"] = dict(value="record", confidence=0.5, why="no kind column; every record is a database record")
    # children: segments (text), media, annotations
    media = []; annotations = []; ignored = []; seg_spec = None; seg_why = ""
    for ref_t in rt["referenced_by"]:
        ct = tabs[ref_t["table"]]; toks = _tok(ct["name"]); fk = ref_t["column"]
        cols = [c for c in ct["columns"] if c["name"] != fk and not c["pk"]]
        textcol = _text_column(cols)
        pathcol = max(cols, key=lambda c: (max(c["shape"].get("path", 0), c["shape"].get("url", 0)), S.synonym_score(c["name"], "media_link")), default=None)
        if toks & SEGMENT_WORDS and textcol is not None and seg_spec is None:
            numeric = [c for c in cols if c["shape"].get("numeric", 0) == 1.0]
            order = next((c["name"] for c in numeric if _tok(c["name"]) & {"seq", "sequence", "order", "idx", "index", "n", "line", "position", "ordinal"}), None)
            start = next((c["name"] for c in numeric if _tok(c["name"]) & {"offset", "start", "begin", "time", "sec", "secs", "seconds", "ts", "t", "started"}), None)
            dur = next((c["name"] for c in numeric if _tok(c["name"]) & {"duration", "dur", "length", "len"}), None)
            spk = next((c["name"] for c in cols if S.synonym_score(c["name"], "speaker_or_author") >= 0.85 or _tok(c["name"]) & {"spk", "spkr"}), None)
            heading = next((c["name"] for c in cols if c["name"] != textcol["name"] and _tok(c["name"]) & HEADING_WORDS
                            and c["shape"].get("numeric", 0) < 1.0 and (c["distinct_share"] or 1) < 0.5), None)
            seg_spec = {k: v for k, v in dict(table=ct["name"], key=fk, order=order or start, start=start, duration=dur, text=textcol["name"],
                                              speaker=spk, heading=heading).items() if v}
            seg_why = (f"{ct['name']} references the record and holds its text in order ({textcol['name']}" + (f", times in {start}" if start else "")
                       + (f", chapter labels in {heading}" if heading else "") + "); rendered in tools/fetch_transcript.py's form")
        elif pathcol is not None and max(pathcol["shape"].get("path", 0), pathcol["shape"].get("url", 0)) >= 0.5:
            mime = next((c["name"] for c in cols if _tok(c["name"]) & {"mime", "type", "format", "kind", "content", "ext", "extension"}), None)
            isurl = pathcol["shape"].get("url", 0) > pathcol["shape"].get("path", 0)
            media.append(dict(table=ct["name"], key=fk, path=None if isurl else pathcol["name"], url=pathcol["name"] if isurl else None,
                              mime=mime, base_dir=base_dir or ".", transcribe=True, confidence=0.8,
                              why=f"{ct['name']} references the record; {pathcol['name']} holds {'URLs' if isurl else 'paths'}"))
        elif toks & ANNOTATION_WORDS or textcol is not None:
            reg = _guess_register(ct, textcol)
            ann = dict(table=ct["name"], key=fk, register=reg, text=textcol["name"] if textcol is not None else None,
                       author=next((c["name"] for c in cols if _tok(c["name"]) & (CODER_WORDS | {"author", "user"})), None),
                       kind=next((c["name"] for c in cols if _tok(c["name"]) & {"code", "kind", "type", "category", "label", "tag"}), None),
                       date=next((c["name"] for c in cols if c["shape"].get("date", 0) >= 0.8), None),
                       attributed_to=next((c["name"] for c in cols if S.synonym_score(c["name"], "speaker_or_author") >= 0.7 and c["name"] != (textcol or {}).get("name")), None),
                       teller=f"their database ({m['mapping']['database']}), table {ct['name']}", reading="the group's reading",
                       confidence=0.7, why=f"{ct['name']} references the record and carries the group's coding"
                                           + (f"; text {textcol['name']} -> the {reg} register" if textcol is not None else ""))
            annotations.append({k: v for k, v in ann.items() if v is not None})
        else:
            ignored.append(dict(table=ct["name"], reason="references the record but holds no text, media or coding the proposer recognised"))
    # the text: every place it can live, tried in order per record (handoff H1): segment rows, a body column, the text attachments
    sources = []; whys = []
    body = next((x for x in _field_candidates(rt, "text", used) if x[0] >= 0.5 and
                 (_tok(x[1]) & BODY_WORDS or _col(rt, x[1])["shape"].get("mean_length", 0) >= 400)), None)
    if seg_spec:
        cands = [c["name"] for c in rt["columns"] if c["name"] not in used and c["shape"].get("numeric", 0) < 1.0 and c["shape"].get("mean_length", 0) >= 40
                 and _tok(c["name"]) & (DESCRIPTION_WORDS | BODY_WORDS)]
        dcol, dwhy = _description_column(engine, rt, key, seg_spec, ([body[1]] if body else []) + [c for c in cands if not body or c != body[1]])
        if dcol: seg_spec["description"] = dcol; seg_why += f"; {dwhy}, closing the transcript as its description block"
        sources.append({"segments": T.Inline(seg_spec)}); whys.append(seg_why)
        if dcol: used.add(dcol)
    if body:
        sources.append({"column": body[1]}); whys.append(f"{body[1]} ({body[2]}) for records with no segment rows"); used.add(body[1])
    if media:
        sources.append({"fallback": "media_text", "all": True})
        whys.append("else every held text attachment (provenance READMEs only when nothing else), named in hold.json as texts; else the transcription of an audio or video attachment")
    if len(sources) > 1:
        F["text"] = dict(alternatives=sources, confidence=0.85 if seg_spec else 0.75, why="; ".join(whys))
    elif sources:
        s = sources[0]
        F["text"] = dict(**({"segments": s["segments"]} if "segments" in s else {"column": s["column"]} if "column" in s else {"fallback": "media_text", "all": True}),
                         confidence=0.85 if seg_spec and seg_spec.get("start") else 0.7 if seg_spec else 0.6 if body else 0.5, why=whys[0])
    # media fields in the record table itself
    for c in rt["columns"]:
        if c["name"] in used: continue
        if c["shape"].get("media", 0) >= 0.5 or c["blob"]:
            media.append(dict(table=rt["name"], key=key, path=c["name"] if not c["blob"] else None, blob=c["name"] if c["blob"] else None,
                              base_dir=base_dir or ".", transcribe=True, confidence=0.6, why=f"{c['name']} holds media in the record row"))
            used.add(c["name"])
    if media: m["media"] = [{k: v for k, v in x.items() if v is not None} for x in media]
    # dates: the mapped one, and every other date-shaped column into the metadata with its ISO form
    dates = []; in_date = spec_columns(F.get("date") or {})
    for c in rt["columns"]:
        sh = c["shape"]
        if c["name"] in in_date and c["name"] != F.get("date", {}).get("column"): continue
        if sh.get("date", 0) >= 0.8 and sh.get("numeric", 0) < 1.0:
            d = dict(column=c["name"], format=sh.get("date_format"), target="date" if F.get("date", {}).get("column") == c["name"] else "metadata")
            if _ambiguous_column(rt, c["name"]): d["ambiguous"] = True
            dates.append(d)
    if dates: m["dates"] = dates
    left = [c["name"] for c in rt["columns"] if c["name"] not in used]
    m["metadata"] = dict(keep_unmapped=True, columns=left, why="the record table's columns no field takes; kept whole in each record's metadata block, promotable to pack keys")
    if annotations: m["annotations"] = annotations
    for t in tabs.values():
        if t["name"] != rt["name"] and t["name"] not in {r["table"] for r in rt["referenced_by"]}:
            ignored.append(dict(table=t["name"], reason="not linked to the record table by a key"))
    if ignored: m["ignored"] = ignored
    m["schema"] = dict(fingerprint=rep["fingerprint"], introspected=rep["introspected"],
                       tables={t["name"]: dict(rows=t["rows"], columns=[f"{c['name']} {c['declared_type']}".strip() for c in t["columns"]]) for t in rep["tables"]})
    if own_engine is not None: own_engine.close()
    return m


def _ambiguous_column(t, col):
    """True when no scanned value of a day-month-year column tells day-first from month-first (shape's date_ambiguous)."""
    return bool(_col(t, col)["shape"].get("date_ambiguous"))


def save_mapping(m, path):
    B.LN.write_text(path, T.dumps(m)); return path


def load_mapping(path):
    return T.loads(B.LN.read_text(path))


# ============================================================================================================ field specs
SOURCE_KEYS = ("segments", "column", "columns", "template", "sql", "join", "value")
TEMPLATE_FIELD_RE = re.compile(r"\{([^{}!:]+)[^{}]*\}")
NOT_THE_TEXT = re.compile(r"^(held-)?(readme|index|manifest)(\.[a-z0-9]+)?$", re.I)   # a set's provenance file, not the item's text


def spec_sources(spec):
    """The ordered sources of a field spec (handoffs H1 and H3 of phase 6a). `alternatives` as a list of tables is the order the
    adapter tries, per record, the first that yields a value winning. A spec without it is one source, and a legacy text spec
    {segments or column, fallback} is the two sources [{segments or column}, {fallback}]. An `alternatives` list of strings is the
    proposer's other candidates (shown to the group, never read)."""
    if not spec: return []
    alts = spec.get("alternatives")
    if isinstance(alts, list) and alts and all(isinstance(a, dict) for a in alts): return [dict(a) for a in alts]
    base = {k: v for k, v in spec.items() if k not in ("fallback", "all", "alternatives", "candidates", "confidence", "why")}
    out = [base] if any(k in base for k in SOURCE_KEYS) else []
    if spec.get("fallback"): out.append({"fallback": spec["fallback"], "all": bool(spec.get("all", False))})
    return out


def spec_columns(spec):
    """The record-table columns a spec reads (its sources, template placeholders, a segments description column)."""
    out = set()
    for s in spec_sources(spec) if isinstance(spec, dict) else []:
        if s.get("column"): out.add(s["column"])
        out.update(s.get("columns", []))
        if s.get("template"): out.update(TEMPLATE_FIELD_RE.findall(s["template"]))
        seg = s.get("segments") or {}
        if seg.get("description"): out.add(seg["description"])
        if s.get("description"): out.add(s["description"])
    return out


def spec_label(s, table):
    if s.get("column"): return f"{table}.{s['column']}"
    if s.get("columns"): return f"{table}.{' + '.join(s['columns'])}"
    if s.get("template"): return f"template {s['template']!r} of {table}"
    if s.get("segments"): return f"segments of {s['segments']['table']}"
    if s.get("fallback"): return f"{s['fallback']}" + (" (all)" if s.get("all") else "")
    return next((k for k in SOURCE_KEYS if k in s), "source")


# ============================================================================================================ records
class DatabaseAdapter(B.Adapter):
    name = "database"

    def __init__(self, mapping, root=None, engine=None, hold_root=None, dry_root=None, **kw):
        """dry_root: an absolute folder the holds go into instead of the project (a dry run), media still resolved in the project.
        hold_root: as for every adapter, the hold folder under the project (default `sources`); an absolute hold_root keeps its first
        meaning (the dry_root; tools/roundtrip/synthetic.py passes it so)."""
        if hold_root and os.path.isabs(str(hold_root)): dry_root, hold_root = dry_root or hold_root, None
        super().__init__(root=root, hold_root=hold_root, **kw)
        hold_root = dry_root
        self.m = load_mapping(mapping) if isinstance(mapping, str) else mapping
        self.mapping_path = mapping if isinstance(mapping, str) else None
        mp = self.m["mapping"]
        self.engine = engine or connect(mp["source"])
        self.db = mp["database"]
        self.set_folder = f"{self.hold_root}/db/{self.db}"
        self.project_root = self.root       # relative media base_dirs resolve here; the hold may be elsewhere (a dry run)
        if hold_root: self.root = os.path.abspath(hold_root)
        self.transcriber = TR.TranscribeAdapter(root=self.project_root)

    # ---------------------------------------------------------------------------------------------------- reading
    def record_keys(self, limit=None):
        r = self.m["record"]
        sql = f"SELECT {self.engine.q(r['key'])} FROM {self.engine.q(r['table'])}" + (f" WHERE {r['where']}" if r.get("where") else "") \
              + f" ORDER BY {self.engine.q(r.get('order') or r['key'])}" + (f" LIMIT {int(limit)}" if limit else "")
        return [row[r["key"]] for row in self.engine.query(sql)]

    def read_record(self, keyval):
        """The record row and every related row the mapping reads: (record dict, related {table: rows}, queries [(sql, params)])."""
        r = self.m["record"]; q = self.engine.q; queries = []
        sql, rows = self.engine.select(r["table"], where=f"{q(r['key'])} = ?", params=(keyval,)); queries.append((sql, [keyval]))
        if not rows: raise KeyError(f"{r['table']}.{r['key']} = {keyval!r}: no row")
        related = {}
        segs = [s["segments"] for s in spec_sources(self.m["fields"].get("text")) if s.get("segments")]
        specs = [dict(table=seg["table"], key=seg["key"], order=seg.get("order")) for seg in segs] \
                + [dict(table=x["table"], key=x["key"]) for x in self.m.get("media", []) if x["table"] != r["table"]] \
                + [dict(table=x["table"], key=x["key"], order=x.get("order")) for x in self.m.get("annotations", [])]
        for s in specs:
            if s["table"] in related: continue
            sql, rr = self.engine.select(s["table"], where=f"{q(s['key'])} = ?", params=(keyval,), order=q(s["order"]) if s.get("order") else None)
            queries.append((sql, [keyval])); related[s["table"]] = rr
        return rows[0], related, queries

    # ---------------------------------------------------------------------------------------------------- fields
    def _value(self, spec, row, related):
        if not spec: return None
        if "value" in spec: return spec["value"]
        if "column" in spec:
            v = row.get(spec["column"])
            if "value_map" in spec: return spec["value_map"].get(str(v), spec.get("default")) if v is not None else spec.get("default")
            return v
        if "columns" in spec:
            out = []
            for c in spec["columns"]:
                v = row.get(c)
                if v in (None, ""): continue
                for x in ([x.strip() for x in str(v).split(spec["split"])] if spec.get("split") else [str(v)]):
                    if x and x not in out: out.append(x)
            return out
        if "template" in spec:
            # a template with an empty placeholder yields nothing (so a date chain moves on to its next source), unless partial = true
            if not spec.get("partial") and any(row.get(n) in (None, "") for n in TEMPLATE_FIELD_RE.findall(spec["template"])): return None
            v = spec["template"].format(**{k: ("" if v is None else v) for k, v in row.items()}).strip()
            return v or None
        if "sql" in spec:
            rows = self.engine.query(spec["sql"], {"key": row.get(self.m["record"]["key"])})
            return spec.get("sep", "\n\n").join(str(next(iter(r.values()))) for r in rows if r) if rows else None
        if "join" in spec:
            j = spec["join"]; rows = related.get(j["table"], [])
            return j.get("sep", "\n\n").join(str(x.get(j["column"])) for x in rows if x.get(j["column"]) not in (None, ""))
        return None

    def _segments(self, seg, rows):
        out = []
        for x in rows:
            t = x.get(seg["text"])
            if t in (None, ""): continue
            if seg.get("speaker") and x.get(seg["speaker"]): t = f"{x[seg['speaker']]}: {t}"
            st = x.get(seg["start"]) if seg.get("start") else None
            item = (float(st) if st is not None else 0.0, float(x.get(seg["duration"]) or 0) if seg.get("duration") else 0.0, str(t))
            if seg.get("heading"): item += (x.get(seg["heading"]),)       # the chapter label in force (handoff H2)
            out.append(item)
        return out

    # ---------------------------------------------------------------------------------------------------- the date (H3)
    def _date(self, spec, row, related):
        """(ISO date or None, the raw value, the basis): the sources tried in order, each with its format or formats; the first
        value that parses sets the date and its precision (day, month or year by the format). date_raw keeps the source's spelling;
        the basis names the source and format taken, or, when none parsed, what was empty and what did not parse."""
        if not spec: return None, None, None
        table = self.m["record"]["table"]; tried = []; first_raw = None
        for s in spec_sources(spec):
            raw = self._value(s, row, related); label = spec_label(s, table)
            if raw in (None, ""): tried.append(f"{label} empty"); continue
            if first_raw is None: first_raw = raw
            fmts = s.get("formats") or ([s["format"]] if s.get("format") else (spec.get("formats") or ([spec["format"]] if spec.get("format") else DATE_FORMATS)))
            amb = s.get("ambiguous", spec.get("ambiguous", False))
            for f in fmts:
                iso = to_iso(raw, f, amb)
                if iso:
                    return iso, raw, f"{label} ({f})" + (" (day and month order not determinable from the column; ? marks)" if amb else "")
            tried.append(f"{label} = {str(raw)!r} did not parse as {', '.join(fmts)}")
        return None, first_raw, "no date: " + "; ".join(tried)

    # ---------------------------------------------------------------------------------------------------- the text (H1, H2, H8)
    def _text(self, spec, row, related, ctx, media_files, files, md, notes):
        """The record's text from the first source that yields one (segments, a column or expression, the text attachments, the
        transcription of an audio or video attachment). Returns (the text file's name or None, the texts list or None, the basis)."""
        title, ident, venue, mlink, date = ctx
        for s in spec_sources(spec):
            if s.get("segments"):
                seg = s["segments"]; segs = self._segments(seg, related.get(seg["table"], []))
                if not segs: continue
                dcol = seg.get("description") or s.get("description")
                desc = row.get(dcol) if dcol else None
                cap = (f"from their database ({self.db}.{seg['table']}, {len(segs)} rows" + (", times in seconds" if seg.get("start") else ", no times")
                       + (f", chapters from {seg['heading']}" if seg.get("heading") else "") + ")")
                files.append(B.HeldFile("transcript.md", text=TR.format_transcript(title or ident, venue or "unknown", mlink or ident, date or "unknown", cap, segs,
                                                                                   description=desc),
                                        role="derived", derived_from="record.json",
                                        tool="ledger.acquire.database segments, in tools/fetch_transcript.py's form" + (f"; description from {dcol}" if desc else "")))
                return "transcript.md", None, spec_label(s, self.m["record"]["table"])
            if any(k in s for k in ("column", "template", "sql", "join")):
                v = self._value(s, row, related)
                if v in (None, "") or not str(v).strip(): continue
                files.append(B.HeldFile("text.md", text=str(v).rstrip("\n") + "\n", role="derived", derived_from="record.json",
                                        tool=f"ledger.acquire.database field text ({spec_label(s, self.m['record']['table'])})"))
                return "text.md", None, spec_label(s, self.m["record"]["table"])
            if s.get("fallback") == "media_text" and media_files:
                texts = [nm for nm, mime, ap in media_files if ap and (os.path.splitext(nm)[1].lower() in (".txt", ".md") or (mime or "").startswith("text/"))]
                own = [t for t in texts if not NOT_THE_TEXT.match(t)] or texts      # a provenance README is the text only when nothing else is
                if own:
                    return own[0], (own if s.get("all") else None), "attachments (media_text" + (", all" if s.get("all") else ", first") + ")"
                av = [(nm, mime, ap) for nm, mime, ap in media_files if ap and (os.path.splitext(nm)[1].lower() in TR.MEDIA_EXT or (mime or "").startswith(("audio/", "video/")))]
                if av and any(ms.get("transcribe", True) for ms in self.m.get("media", [])):
                    nm, mime, ap = av[0]
                    try:
                        segs, st = self.transcriber.transcribe(ap)
                        files.append(B.HeldFile("transcript.md", text=TR.format_transcript(title or ident, venue or "unknown", mlink or nm, date or "unknown",
                                                                                           f"{st['language']} (local transcription: {st['engine']} {st['model']}, {st['device']})", segs),
                                                role="derived", derived_from=nm, tool=f"{st['engine']} {st['engine_version']} model {st['model']} on {st['device']}"))
                        md["transcription"] = st
                        return "transcript.md", None, f"transcription of {nm}"
                    except RuntimeError as e:
                        md["transcription"] = str(e).split(" (")[0]; notes.append(f"{nm} not transcribed: {e}; queued")
        return None, None, None

    # ---------------------------------------------------------------------------------------------------- one record
    def capture(self, keyval):
        row, related, queries = self.read_record(keyval)
        F = self.m["fields"]; r = self.m["record"]
        ident = f"{F.get('identifier', {}).get('prefix', r['table'] + '/')}{row.get(F.get('identifier', {}).get('column', r['key']))}"
        title = self._value(F.get("title"), row, related)
        kind = self._value(F.get("media_kind"), row, related) or "record"
        if kind not in S.MEDIA_KINDS: kind = "record"
        date, date_raw, date_basis = self._date(F.get("date"), row, related)
        speakers = self._value(F.get("speaker_or_author"), row, related) or []
        venue = self._value(F.get("venue"), row, related)
        mlink = self._value(F.get("media_link"), row, related)
        md = {"database": self.db, "table": r["table"], "key": f"{r['key']} = {keyval}"}
        used = set()
        for f in F.values(): used |= spec_columns(f)
        if self.m.get("metadata", {}).get("keep_unmapped", True):
            for c in self.m.get("metadata", {}).get("columns", [k for k in row if k not in used]):
                if c in row and c not in used and row[c] not in (None, ""): md[c] = row[c] if not isinstance(row[c], bytes) else f"<blob {len(row[c])} bytes>"
        for d in self.m.get("dates", []):
            if d.get("target") == "metadata" and row.get(d["column"]) not in (None, ""):
                md[d["column"]] = row[d["column"]]; md[d["column"] + "_iso"] = to_iso(row[d["column"]], d.get("format"), d.get("ambiguous", False))
        if date_basis: md["date_basis"] = date_basis
        files = []; notes = []
        held_record = dict(source=redact(self.m["mapping"]["source"]), engine=self.engine.name, table=r["table"], key=r["key"], key_value=keyval,
                           row={k: _jsonable(v) for k, v in row.items()},
                           related={t: [{k: _jsonable(v) for k, v in x.items()} for x in rows] for t, rows in related.items()})
        # the change digest of the scheduled re-read: the rows only (not the source string, which moves with an export's path)
        digest = B.sha256(json.dumps([held_record["row"], held_record["related"]], ensure_ascii=False, sort_keys=True).encode("utf-8"))
        files.append(B.HeldFile("record.json", data=(json.dumps(held_record, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"),
                                how="the record row and its related rows as the queries returned them (the provenance field lists the queries), "
                                    "serialised as JSON with sorted keys; BLOB values are held as their own files"))
        # media
        media_files = []
        for mi, ms in enumerate(self.m.get("media", []), 1):
            rows = [row] if ms["table"] == r["table"] else related.get(ms["table"], [])
            for ri, x in enumerate(rows, 1):
                mime = x.get(ms["mime"]) if ms.get("mime") else None
                if ms.get("blob") and isinstance(x.get(ms["blob"]), bytes):
                    nm = f"media-{mi}-{ri}.bin"; files.append(B.HeldFile(nm, data=x[ms["blob"]], how=f"BLOB {ms['table']}.{ms['blob']}"))
                    media_files.append((nm, mime, None)); continue
                p = x.get(ms["path"]) if ms.get("path") else None
                u = x.get(ms["url"]) if ms.get("url") else None
                if p:
                    bd = ms.get("base_dir") or "."
                    bd = bd if os.path.isabs(bd) else (os.path.dirname(os.path.abspath(self.engine.path)) if bd == "." else os.path.join(self.project_root, bd))
                    ap = p if os.path.isabs(p) else os.path.join(bd, p)
                    if os.path.isfile(ap):
                        base = os.path.basename(ap)
                        nm = base if len(base) <= B.INNER_NAME_CAP and not B.LP.name_problems(base) else f"media-{mi}-{ri}{os.path.splitext(base)[1].lower()}"
                        if nm.lower() in B.RESERVED_NAMES: nm = "held-" + nm
                        files.append(B.HeldFile(nm, src=ap, how=f"{ms['table']}.{ms['path']} = {p}, copied byte-for-byte"))
                        media_files.append((nm, mime, ap))
                    else:
                        notes.append(f"media not found at {p} ({ms['table']}.{ms['path']})")
                        md.setdefault("media_missing", []).append(p)
                elif u:
                    md.setdefault("media_urls", []).append(u)
                    notes.append(f"media URL recorded, not fetched: {u}")
        # text: the first source that yields one (segments, a column or expression, the text attachments, a transcription)
        text_name, texts, text_basis = self._text(F.get("text"), row, related, (title, ident, venue, mlink, date or date_raw),
                                                  media_files, files, md, notes)
        if text_basis: md["text_basis"] = text_basis
        # annotations
        anns = []
        for a in self.m.get("annotations", []):
            for x in related.get(a["table"], []):
                anns.append({k: v for k, v in dict(register=a["register"], teller=a["teller"], reading=a.get("reading", "the group's reading"),
                                                    table=a["table"], text=x.get(a.get("text")) if a.get("text") else None,
                                                    author=x.get(a.get("author")) if a.get("author") else None,
                                                    kind=x.get(a.get("kind")) if a.get("kind") else None,
                                                    date=x.get(a.get("date")) if a.get("date") else None,
                                                    attributed_to=x.get(a.get("attributed_to")) if a.get("attributed_to") else None,
                                                    row=x).items() if v is not None})
        if anns:
            files.append(B.HeldFile("annotations.json", text=json.dumps(anns, indent=1, ensure_ascii=False, sort_keys=True) + "\n", role="derived",
                                    derived_from="record.json", tool="ledger.acquire.database annotations (offered for import at setup; their database as the teller)"))
            md["annotations"] = {k: sum(1 for x in anns if x["register"] == k) for k in sorted({x["register"] for x in anns})}
        prov = f"{self.engine.name} {redact(self.m['mapping']['source'])}: " + "; ".join(sql.replace("?", repr(p[0])) for sql, p in queries)
        rec = B.Record(ident, kind, title or f"[{ident}]", date=date, date_raw=str(date_raw) if date_raw not in (None, "") else None,
                       speaker_or_author=speakers, text=text_name, media_link=mlink, venue=venue, provenance=prov, metadata=md)
        rec.capture_tool = f"{self.tool} (mapping {os.path.basename(self.mapping_path) if self.mapping_path else 'in memory'}, {self.m['mapping'].get('confirmed') and 'confirmed ' + self.m['mapping']['confirmed'] or 'unconfirmed'})"
        folder = f"{self.set_folder}/" + B.safe_slug(f"{r['table']} {keyval}", 40) + (("-" + B.safe_slug(title, 40)) if title else "")
        cap = B.Capture(rec, files, folder=folder, status_note=("; ".join(notes) + ".") if notes else "",
                        extra={"texts": texts} if texts else None)       # every text attachment, for the pre-pass (handoff H8)
        cap.digest = digest
        return cap

    # ---------------------------------------------------------------------------------------------------- runs
    def run(self, limit=None, keys=None):
        """Hold records (all, the first `limit`, or the given keys); write the set README, state.json and queue.tsv. Returns rows."""
        rows = []
        state_p = self.abs(f"{self.set_folder}/state.json")
        state = B.read_json(state_p, {})
        for k in (keys if keys is not None else self.record_keys(limit)):
            cap = self.capture(k)
            digest = cap.digest
            if state.get(cap.record.identifier, {}).get("sha256") == digest and os.path.isdir(self.abs(state[cap.record.identifier]["hold"])):
                rows.append(dict(identifier=cap.record.identifier, media_kind=cap.record.media_kind, title=cap.record.title, date=cap.record.date,
                                 hold=state[cap.record.identifier]["hold"], status="unchanged", adapter=self.tool, note="rows identical to the last run (row digest); not re-held"))
                continue
            row = self.hold(cap); rows.append(row)
            if row["status"] != "failed": state[cap.record.identifier] = dict(sha256=digest, hold=row["hold"], captured=row["captured"])
        os.makedirs(self.abs(self.set_folder), exist_ok=True)
        with B.LN.open_write(state_p) as f: json.dump(state, f, indent=1, sort_keys=True); f.write("\n")
        q = [r for r in rows if r["status"] in ("new", "changed")]
        qp = self.abs(f"{self.set_folder}/queue.tsv")
        B.write_manifest(q, qp) if q else None
        self.write_set_readme(state)
        if self.mapping_path: B.LN.write_text(self.abs(f"{self.set_folder}/mapping.toml"), B.LN.read_text(self.mapping_path))
        return rows

    def write_set_readme(self, state):
        recs = []
        for ident, s in sorted(state.items()):
            h = B.load_hold(self.abs(s["hold"])) or {}
            r = h.get("record", {})
            recs.append({"Identifier": ident, "Title": r.get("title"), "Date": r.get("date"), "Kind": r.get("media_kind"),
                         "Hold": s["hold"].split("/")[-1] + "/", "Captured": s["captured"], "Row digest": s["sha256"]})
        mp = self.m["mapping"]
        intro = (f"Records of their database {self.db} ({self.engine.name}, {redact(mp['source'])}), held by {self.tool} under the mapping in "
                 f"mapping.toml ({'confirmed ' + mp['confirmed'] + ' by ' + mp.get('confirmed_by', '') if mp.get('confirmed') else 'not yet confirmed'}). "
                 f"Record unit: table {self.m['record']['table']}, key {self.m['record']['key']}. Each record's folder holds record.json (the rows as "
                 f"read), its media byte-for-byte, the derived text and annotations, and its own README with the queries. state.json holds "
                 f"each record's row digest (SHA-256 of its rows, not of the source string) for the scheduled re-read; queue.tsv lists new and changed records for intake.")
        B.LN.write_text(self.abs(f"{self.set_folder}/README.md"),
                        B.set_readme_text(f"Database: {self.db}", intro, ["Identifier", "Title", "Date", "Kind", "Hold", "Captured", "Row digest"], recs, self.tool))

    def dry_run(self, n=5, out_root=None):
        """Hold the first n records under wip/db-dry-run/<database>/ (a separate root: the hold proper is untouched)."""
        out = out_root or os.path.join(self.project_root, "wip", "db-dry-run", self.db)
        dr = DatabaseAdapter(self.m, root=self.project_root, engine=self.engine, dry_root=out, hold_root=self.hold_root, log=self.log)
        dr.mapping_path = self.mapping_path
        rows = dr.run(limit=n)
        for r in rows: r["dry_run_root"] = out
        return rows


# ============================================================================================================ rescan
def rescan(mapping, engine=None, records=False, root=None):
    """The saved mapping against the live schema; with records=True also the records new or changed since the last run."""
    m = load_mapping(mapping) if isinstance(mapping, str) else mapping
    eng = engine or connect(m["mapping"]["source"])
    live = introspect(eng, m["mapping"]["source"])
    saved = m.get("schema", {}).get("tables", {})
    lt = {t["name"]: t for t in live["tables"]}
    rep = dict(mapping=m["mapping"].get("database"), rescanned=B.utc_now(), fingerprint_saved=m.get("schema", {}).get("fingerprint"),
               fingerprint_live=live["fingerprint"], tables_added=sorted(set(lt) - set(saved)), tables_removed=sorted(set(saved) - set(lt)),
               columns_added={}, columns_removed={}, columns_retyped={}, row_counts={}, mapping_breaks=[], unmapped_new_columns=[])
    rep["unchanged"] = rep["fingerprint_saved"] == rep["fingerprint_live"]
    for t, s in saved.items():
        if t not in lt: continue
        old = dict(c.split(" ", 1) if " " in c else (c, "") for c in s["columns"])
        new = {c["name"]: c["declared_type"] for c in lt[t]["columns"]}
        add = sorted(set(new) - set(old)); rem = sorted(set(old) - set(new)); ret = sorted(c for c in set(old) & set(new) if old[c] != new[c])
        if add: rep["columns_added"][t] = add
        if rem: rep["columns_removed"][t] = rem
        if ret: rep["columns_retyped"][t] = {c: [old[c], new[c]] for c in ret}
        if s.get("rows") != lt[t]["rows"]: rep["row_counts"][t] = [s.get("rows"), lt[t]["rows"]]
    refs = []
    rt = m["record"]["table"]
    refs += [(rt, m["record"]["key"])]
    for f, spec in m.get("fields", {}).items():
        if not isinstance(spec, dict): continue
        refs += [(rt, c) for c in spec_columns(spec)]
        for s in spec_sources(spec):
            seg = s.get("segments")
            if seg: refs += [(seg["table"], seg[k]) for k in ("key", "order", "start", "duration", "text", "speaker", "heading") if seg.get(k)]
    for x in m.get("media", []): refs += [(x["table"], x[k]) for k in ("key", "path", "url", "mime", "blob") if x.get(k)]
    for x in m.get("annotations", []): refs += [(x["table"], x[k]) for k in ("key", "text", "author", "kind", "date", "attributed_to") if x.get(k)]
    for x in m.get("dates", []): refs.append((rt, x["column"]))
    for t, c in sorted(set(refs)):
        if t not in lt: rep["mapping_breaks"].append(f"table {t} is gone (mapped)")
        elif c not in {x["name"] for x in lt[t]["columns"]}: rep["mapping_breaks"].append(f"column {t}.{c} is gone (mapped)")
    mapped_tables = {t for t, _ in refs}
    for t, cols in rep["columns_added"].items():
        if t in mapped_tables: rep["unmapped_new_columns"] += [f"{t}.{c}" for c in cols]
    if records:
        ad = DatabaseAdapter(m, root=root, engine=eng)
        state_p = ad.abs(f"{ad.set_folder}/state.json")
        state = B.read_json(state_p, {})
        new, changed = [], []
        for k in ad.record_keys():
            cap = ad.capture(k); d = cap.digest
            if cap.record.identifier not in state: new.append(cap.record.identifier)
            elif state[cap.record.identifier]["sha256"] != d: changed.append(cap.record.identifier)
        rep.update(records_new=new, records_changed=changed)
    return rep


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["introspect", "propose", "dry-run", "run", "rescan", "engines"]); ap.add_argument("target", nargs="?")
    ap.add_argument("--out"); ap.add_argument("--name"); ap.add_argument("--n", type=int, default=5); ap.add_argument("--limit", type=int)
    ap.add_argument("--records", action="store_true"); ap.add_argument("--root"); ap.add_argument("--base-dir")
    a = ap.parse_args(argv)
    if a.cmd == "engines":
        for e in ENGINE_TABLE: print(f"{e['engine']}\t{e['status']}\t{e['form']}\t{e['driver']}\t{e['needs']}")
        return
    if a.cmd in ("introspect", "propose"):
        eng = connect(a.target); rep = introspect(eng, a.target)
        if a.cmd == "introspect":
            out = a.out or "introspection.json"
            with B.LN.open_write(out) as f: json.dump(rep, f, indent=1, ensure_ascii=False); f.write("\n")
            print(f"{out}: {len(rep['tables'])} tables, fingerprint {rep['fingerprint'][:12]}")
        else:
            m = propose(rep, name=a.name, source=a.target, base_dir=a.base_dir, engine=eng)
            out = a.out or "mapping.toml"; save_mapping(m, out)
            print(f"{out}: record unit {m['record']['table']} ({m['record']['confidence']}), fields {', '.join(m['fields'])}")
        return
    if a.cmd == "rescan":
        rep = rescan(a.target, records=a.records, root=a.root)
        s = json.dumps(rep, indent=1, ensure_ascii=False)
        if a.out: B.LN.write_text(a.out, s + "\n")
        print(s); return
    ad = DatabaseAdapter(a.target, root=a.root)
    rows = ad.dry_run(n=a.n) if a.cmd == "dry-run" else ad.run(limit=a.limit)
    for r in rows: print(json.dumps({k: r.get(k) for k in ("identifier", "status", "hold", "note")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
