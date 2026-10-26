"""Paths of a ledger project (phase 2 of tools/platform-plan.md, 2026-10-22; the plan is wip/platform-phase1/sources-layout.md).

The project root; the alias table that lets a path in the `sources/` layout by media kind (sources/video, sources/text,
sources/web, sources/archive, sources/sets, sources/catalogues) resolve to where the held file stands today (transcripts/,
books/sources/, research/sources/), with no file renamed or moved and no symlink (not portable to Windows without privilege,
and a share may not carry them); and the rules a NEW hold's file name must meet (ASCII, no reserved characters, the slug length
cap and the path cap), checked by one function every acquire tool calls before it writes a new file.

The alias table is `sources/aliases.tsv`: `alias <TAB> target <TAB> date <TAB> reason`, one row per file whose name changes
(the transcripts gain the `yt-` prefix) and one row per folder (a trailing `/`) whose files keep their names. This phase's rows
map the new layout to the current files; the move script of a later phase rewrites the table so the old paths become the aliases
(sources-layout.md section 2). A path with no alias resolves to itself. A folder alias resolves a lower-cased file name to the
file's actual spelling (the layout lower-cases new paths; 12,709 held names carry upper case today).
"""
import os, re, sys, datetime

ALIAS_FILE = os.path.join("sources", "aliases.tsv")
STEM_CAP = 80         # sources-layout.md section 4: the slug's stem
BASENAME_CAP = 96     # the basename with its extension
PATH_CAP = 180        # the path relative to the project root (80 characters of room under the Windows limit of 260)
RESERVED = set('<>:"/\\|?*')
DEVICE_NAMES = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

_ROOT = None


def root():
    """The project folder: $LEDGER_ROOT, else the nearest folder at or above the working directory holding ledger.toml, else the
    folder two levels above this package (tools/ledger/ inside a project)."""
    global _ROOT
    if _ROOT: return _ROOT
    env = os.environ.get("LEDGER_ROOT")
    if env: _ROOT = os.path.abspath(env); return _ROOT
    d = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, "ledger.toml")): _ROOT = d; return _ROOT
        up = os.path.dirname(d)
        if up == d: break
        d = up
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return _ROOT


def set_root(path):
    global _ROOT, _ALIASES
    _ROOT = os.path.abspath(path); _ALIASES = None


def rel(path, base=None):
    """A path relative to the project root, with forward slashes (base: the folder a relative path is relative to; default the root)."""
    p = path if os.path.isabs(path) else os.path.join(base or root(), path)
    return os.path.relpath(os.path.normpath(p), root()).replace(os.sep, "/")


# ============================================================================================================ the alias table
_ALIASES = None


def aliases():
    """{alias: target} from sources/aliases.tsv (root-relative, forward slashes; folder rows end with `/`); {} when absent."""
    global _ALIASES
    if _ALIASES is not None: return _ALIASES
    _ALIASES = {}
    p = os.path.join(root(), ALIAS_FILE)
    if os.path.isfile(p):
        with open(p, encoding="utf-8", newline="") as f:
            for line in f.read().replace("\r\n", "\n").split("\n"):
                if not line.strip() or line.startswith("#"): continue
                c = line.split("\t")
                if len(c) < 2 or c[0] == "alias": continue
                _ALIASES[c[0].strip()] = c[1].strip()
    return _ALIASES


_DIRCASE = {}


def _casefold_lookup(abs_path):
    """The file's actual spelling when only the case differs (one listing per folder, cached), so the answer is the same on a
    case-sensitive file system (Linux) and a case-insensitive one (macOS, Windows); the path unchanged otherwise."""
    d, name = os.path.split(abs_path)
    if not os.path.isdir(d): return abs_path
    if d not in _DIRCASE:
        names = os.listdir(d); m = {}
        for n in names: m.setdefault(n.lower(), n)
        _DIRCASE[d] = (set(names), m)
    exact, low = _DIRCASE[d]
    if name in exact: return abs_path
    hit = low.get(name.lower())
    return os.path.join(d, hit) if hit else abs_path


def resolve(path, base=None):
    """The absolute path of the file a path names: an alias in the table (an exact row, else the longest folder row that is a
    prefix) gives its target; otherwise the path itself. `base` is the folder a relative path is relative to (a note's folder for a
    link inside the note); default the project root."""
    if path is None: return path
    p = path if os.path.isabs(path) else os.path.join(base or root(), path)
    p = os.path.abspath(p)
    al = aliases()
    if not al: return p
    try: r = os.path.relpath(p, root()).replace(os.sep, "/")
    except ValueError: return p
    if r.startswith("../"): return p
    if r in al: return _casefold_lookup(os.path.join(root(), al[r]))
    best = None
    for a in al:
        if a.endswith("/") and (r + "/").startswith(a) and (best is None or len(a) > len(best)): best = a
    if best is None: return p
    tail = r[len(best):] if len(r) >= len(best) else ""
    return _casefold_lookup(os.path.normpath(os.path.join(root(), al[best] + tail)))


def exists(path, base=None):
    return os.path.exists(resolve(path, base))


def resolve_arg(path, base=None):
    """A path as a tool was given it (a command-line argument, a link) when no alias applies, so what the tool prints and writes is
    unchanged; the resolved absolute path when an alias applies."""
    if path is None: return path
    b = base or os.getcwd()
    r = resolve(path, b)
    plain = os.path.abspath(path if os.path.isabs(path) else os.path.join(b, path))
    return path if r == plain else r


def layout_name(current):
    """The `sources/` layout path of a held file's current root-relative path (the reverse of resolve), or None when the file is
    not under a held folder: transcripts/<YouTube id>.md -> sources/video/yt-<id>.md; transcripts/<slug>.md -> sources/video/<slug>.md;
    a file under an aliased folder -> the folder's alias with the name lower-cased (sources-layout.md section 4)."""
    cur = current.replace(os.sep, "/")
    for a, t in aliases().items():
        if not a.endswith("/") and t == cur: return a
    if cur.startswith("transcripts/") and cur.count("/") == 1:
        stem = cur[len("transcripts/"):-3] if cur.endswith(".md") else None
        if stem and YT_ID_RE.match(stem): return f"sources/video/yt-{stem}.md"
        if stem: return f"sources/video/{stem}.md"
    best = None
    for a, t in aliases().items():
        if a.endswith("/") and t.endswith("/") and cur.startswith(t) and (best is None or len(t) > len(best[1])): best = (a, t)
    if best: return best[0] + cur[len(best[1]):].lower()
    return None


# folder rows of the layout (sources-layout.md section 2), most specific first; the transcripts get a row each. The core holds the
# layout rule's general rows; a project's own folders (named document sets, a bulk archive's mirror) are its pack's rows,
# pack.toml [[layout.folder]] alias, target, why, read through ledger.toml [pack] path and laid before the core rows (phase 7a).
LAYOUT_FOLDERS = [
    ("sources/web/", "books/sources/web/", "held web documents by set, each with its README table"),
    ("sources/catalogues/", "research/sources/", "catalogues are sources, not research pages"),
    ("sources/text/", "books/sources/", "texts: the top-level text layers and scans of books/sources/"),
]


def pack_layout_folders():
    """The pack's own folder rows ([[layout.folder]] in pack.toml), in the pack's order; [] when the project has no pack or none."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return []
    lt = os.path.join(root(), "ledger.toml")
    try:
        with open(lt, "rb") as f: pack = (tomllib.load(f).get("pack") or {}).get("path")
        if not pack: return []
        with open(os.path.join(root(), pack, "pack.toml"), "rb") as f: rows = (tomllib.load(f).get("layout") or {}).get("folder", [])
    except (OSError, ValueError):
        return []
    return [(r["alias"], r["target"], r.get("why", "")) for r in rows if r.get("alias") and r.get("target")]


def layout_folders():
    """Every folder row: the pack's, then the core's (most specific first)."""
    return pack_layout_folders() + LAYOUT_FOLDERS


def build_alias_rows(today=None):
    """The rows of this phase's table from the folders as they stand: one per transcript, one per folder row (layout_folders()) present."""
    today = today or datetime.date.today().isoformat()
    rows = []
    tdir = os.path.join(root(), "transcripts")
    for fn in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
        if not fn.endswith(".md"): continue
        stem = fn[:-3]
        new = f"sources/video/yt-{stem}.md" if YT_ID_RE.match(stem) else f"sources/video/{stem}.md"
        rows.append((new, f"transcripts/{fn}", today, "phase 2 layout alias (YouTube id under yt-; file not moved)" if YT_ID_RE.match(stem) else "phase 2 layout alias (film or pasted transcript; file not moved)"))
    for a, t, why in layout_folders():
        if os.path.isdir(os.path.join(root(), t)): rows.append((a, t, today, f"phase 2 layout alias, folder ({why}); nothing moved"))
    return rows


def write_alias_table(rows=None, path=None):
    """Write sources/aliases.tsv (LF, UTF-8); the only writer of the table. Returns the path and the row count."""
    global _ALIASES
    rows = rows if rows is not None else build_alias_rows()
    p = path or os.path.join(root(), ALIAS_FILE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    head = ["# The alias table of the sources/ layout (wip/platform-phase1/sources-layout.md; tools/ledger/paths.py).",
            "# Phase 2 (2026-10-22): the layout's paths resolve to where each held file stands today; nothing is moved or renamed.",
            "# A row ending in / is a folder: every file under it keeps its name (a lower-cased name resolves to the file's spelling).",
            "alias\ttarget\tdate\treason"]
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + ["\t".join(r) for r in rows]) + "\n")
    _ALIASES = None
    return p, len(rows)


def check_aliases():
    """Every alias target exists, no two aliases share a target file, and no folder holds two names that differ only by case
    (which the lower-cased layout could not tell apart). Returns a list of problems."""
    probs = []; seen = {}
    for a, t in aliases().items():
        tp = os.path.join(root(), t)
        if not os.path.exists(tp): probs.append(f"alias {a}: target {t} does not exist")
        if not a.endswith("/"):
            if t in seen: probs.append(f"aliases {seen[t]} and {a} share the target {t}")
            seen[t] = a
    for a, t in aliases().items():
        if not a.endswith("/"): continue
        for dp, dns, fns in os.walk(os.path.join(root(), t)):
            low = {}
            for n in dns + fns:
                if n.lower() in low: probs.append(f"{os.path.relpath(dp, root())}: {low[n.lower()]} and {n} differ only by case")
                low[n.lower()] = n
    return probs


# ============================================================================================================ names of new holds
def name_problems(relpath, kind="file"):
    """The reasons a hold's root-relative path breaks the portability rules (sources-layout.md section 4), as a list; [] when it is
    fine. Enforced: reserved characters and control characters, a name ending in a space or a dot, a Windows device name as the
    stem, a name starting with `-` or `.`, the stem cap (80), the basename cap (96), the path cap (180). kind="youtube": the name is a
    YouTube id (`<id>.md`), checked as the layout writes it (`yt-<id>.md`, so a leading `-` is allowed) for the id's characters."""
    r = relpath.replace("\\", "/")
    base = r.rsplit("/", 1)[-1]
    stem, ext = os.path.splitext(base)
    out = []
    if kind == "youtube":
        if not YT_ID_RE.match(stem): out.append(f"not a YouTube id: {stem!r}")
        lay = f"sources/video/yt-{stem}{ext}"
        if len(lay) > PATH_CAP: out.append(f"layout path over {PATH_CAP} characters")
        return out
    bad = sorted({ch for ch in base if ch in RESERVED or ord(ch) < 32})
    if bad: out.append("reserved or control characters: " + " ".join(repr(c) for c in bad))
    if base != base.rstrip(" ."): out.append("ends in a space or a dot")
    if stem.lower().split(".")[0] in DEVICE_NAMES: out.append(f"a Windows device name as the stem: {stem}")
    if base.startswith(("-", ".")): out.append("starts with '-' or '.'")
    if len(stem) > STEM_CAP: out.append(f"stem of {len(stem)} characters (cap {STEM_CAP})")
    if len(base) > BASENAME_CAP: out.append(f"basename of {len(base)} characters (cap {BASENAME_CAP})")
    if len(r) > PATH_CAP: out.append(f"path of {len(r)} characters (cap {PATH_CAP})")
    return out


def name_warnings(relpath):
    """Rules of section 4 not enforced on holds in this phase (reported only): ASCII, lower case, the slug's character set."""
    base = relpath.replace("\\", "/").rsplit("/", 1)[-1]
    out = []
    if any(ord(ch) > 127 for ch in base): out.append("non-ASCII characters")
    if base != base.lower(): out.append("upper case (the layout lower-cases new paths)")
    if re.search(r"[^A-Za-z0-9._-]", base): out.append("characters outside a-z 0-9 - _ .")
    return out


def slug(title, cap=STEM_CAP):
    """A slug from a title: ASCII, lower case, `[a-z0-9]+(-[a-z0-9]+)*`, cut at a word boundary to `cap` characters (the full title
    stays in the note's metadata and the set's README table)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > cap:
        cut = t[:cap + 1]
        t = cut[:cut.rfind("-")] if "-" in cut[:cap + 1] else t[:cap]
        t = t.strip("-") or title[:cap]
    if t.split("-")[0] in DEVICE_NAMES and len(t.split("-")) == 1: t += "-file"
    return t


def hold_name(name, cap=STEM_CAP):
    """A compliant file name for a new hold from a proposed one: reserved and control characters to `-`, a leading `-` or `.` and a
    trailing space or dot dropped, a device-name stem suffixed, the stem cut at a word boundary to the cap and the basename to its
    cap; the extension kept. Case is kept (the layout lower-cases through the alias table)."""
    stem, ext = os.path.splitext(name)
    if len(ext) > 10 or not re.fullmatch(r"\.[A-Za-z0-9]+", ext or ".x"): stem, ext = name, ""
    s = "".join("-" if (ch in RESERVED or ord(ch) < 32) else ch for ch in stem)
    if s != stem: s = re.sub(r"-{2,}", "-", s).rstrip("-")
    s = s.strip(" .").lstrip("-.")
    if s.lower().split(".")[0] in DEVICE_NAMES: s += "-file"
    cap = min(cap, BASENAME_CAP - len(ext))
    if len(s) > cap:
        cut = s[:cap + 1]; k = max(cut.rfind("-"), cut.rfind("_"), cut.rfind(" "))
        s = (cut[:k] if k > cap // 2 else s[:cap]).rstrip(" .-_")
    return (s or "hold") + ext


def new_hold(path, kind="file", fix=True):
    """The one function every acquire tool calls before it writes a held file. An existing file is never renamed (the rules bind
    new holds only): its path comes back unchanged. For a new file the name is checked by name_problems(); with fix=True a name
    that breaks a rule is replaced by hold_name()'s compliant form (reported on stderr), else SystemExit names the problems.
    Returns the path to write (absolute when given absolute)."""
    ap = path if os.path.isabs(path) else os.path.join(root(), path)
    if os.path.exists(ap): return path
    r = rel(ap)
    probs = name_problems(r, kind)
    if not probs: return path
    if kind == "youtube" or not fix:
        raise SystemExit(f"hold name refused ({r}): " + "; ".join(probs))
    d, base = os.path.split(path)
    new = os.path.join(d, hold_name(base))
    left = name_problems(rel(new if os.path.isabs(new) else os.path.join(root(), new)), kind)
    if left: raise SystemExit(f"hold name refused ({r}): " + "; ".join(left))
    print(f"hold name changed for portability: {base} -> {os.path.basename(new)} ({'; '.join(probs)})", file=sys.stderr)
    return new
