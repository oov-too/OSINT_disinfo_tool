"""Names of new holds (phase 2 of tools/platform-plan.md, 2026-10-22; the rules are wip/platform-phase1/sources-layout.md section 4).
The two functions the acquire layer (tools/ledger/acquire/, phase 3) imports; the caps, the reserved characters and the device
names are ledger.paths', so a name made here passes ledger.paths.name_problems() and ledger.paths.new_hold().

    safe_slug(text, max_len=80) -> str        an ASCII slug [a-z0-9]+(-[a-z0-9]+)*, cut at a word boundary
    hold_path(kind, ident, title) -> str      the root-relative folder of a new hold: sources/<kind>/<name>

The hold's name: a YouTube id under kind "video" is `yt-<id>` with its case kept (the layout's rule, so no name starts with `-`);
otherwise the slug of the identifier, then the slug of the title when there is one and room under the stem cap. The folder leaves
room for a 32-character file name inside it under the 180-character path cap. Nothing here touches the file system.
"""
import re, unicodedata
from . import paths as _P

STEM_CAP = _P.STEM_CAP
BASENAME_CAP = _P.BASENAME_CAP
PATH_CAP = _P.PATH_CAP
DEVICE_NAMES = _P.DEVICE_NAMES
YT_ID_RE = _P.YT_ID_RE
FILE_ROOM = 32          # characters kept for a file name inside the hold's folder
KINDS = ("video", "audio", "text", "document", "image", "web", "archive", "canon", "db", "sets", "catalogues")


def safe_slug(text, max_len=STEM_CAP):
    """An ASCII slug of `text`: NFKD-folded to ASCII, lower case, runs of anything else to one `-`, cut at a word boundary to
    `max_len`; a bare Windows device name gains `-file`; an empty result is `untitled`."""
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > max_len:
        cut = t[:max_len + 1]
        k = cut.rfind("-")
        t = (cut[:k] if k > max_len // 2 else t[:max_len]).strip("-")
    if not t: t = "untitled"
    if t in DEVICE_NAMES: t += "-file"
    return t


def hold_path(kind, ident, title):
    """The root-relative folder (forward slashes, no trailing slash) of the hold of one item: sources/<kind>/<name>. `kind` is a
    media kind folder (KINDS); a set's kind may carry sub-folders (`web/<set>`, `archive/<set>`), each part slugged. ValueError for
    an unknown kind, a missing kind, or a folder that leaves no room for a file name under the path cap."""
    parts = [safe_slug(p, 40) for p in str(kind or "").replace("\\", "/").split("/") if p]
    if not parts: raise ValueError("hold_path: a kind is required")
    if parts[0] not in KINDS: raise ValueError(f"hold_path: unknown media kind {kind!r} (one of {', '.join(KINDS)})")
    ident = str(ident or "").strip()
    if parts[0] == "video" and YT_ID_RE.match(ident) and len(parts) == 1:
        name = f"yt-{ident}"
    elif ident.startswith("yt-") and YT_ID_RE.match(ident[3:]):
        name = ident
    else:
        name = safe_slug(ident, STEM_CAP) if ident else ""
        if title:
            room = STEM_CAP - len(name) - (1 if name else 0)
            if room >= 12: name = (name + "-" if name else "") + safe_slug(title, room)
        name = name or safe_slug(title, STEM_CAP)
    path = "/".join(["sources"] + parts + [name])
    if len(path) > PATH_CAP - 1 - FILE_ROOM:
        raise ValueError(f"hold_path: {path} leaves no room under the path cap of {PATH_CAP}")
    probs = [p for p in _P.name_problems(path) if not p.startswith("path of")]
    if probs: raise ValueError(f"hold_path: {path}: " + "; ".join(probs))   # cannot happen for a slug; kept as the rules' check
    return path
