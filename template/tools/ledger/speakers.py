"""The speaker ledgers' integrate step (pilot defect 7, 7b2 2026-10-23): an intake report's sections for the pack's ledgered speakers
appended to each speaker's ledger page.

The pack names its ledgered speakers in pack.toml [[speakers.ledgered]] (name, page, report_keys). For every entry and every one of its
report keys the report carries:
  - a markdown section (a string whose first line is a heading, the form the first pack's single-agent briefs return) is inserted
    before the page's anchor heading ([tools.post_intake] ledger_anchor, when that table names this page; else at the end), unless
    its first line already stands on the page;
  - anything else (a string, a list of strings or objects, an object: the forms the staged writers return) is appended under the
    page's `## Entries from the intakes` heading as `### <note>, <report key>, appended <date>` and one bullet per entry (an object
    as `key: value; ...`), unless that heading line already stands on the page;
  - a value that only says the speaker is absent (`does not speak`, `n/a`, `none`, with nothing but a parenthesis after it) adds
    nothing.
A page that does not exist is started with a title and that heading. The entries are the raw material of the ledger's grid (topics
down, one column per appearance), which its builder sets by hand; nothing here rewrites the grid."""
import datetime, os, re

from . import notes

ENTRIES_HEADING = "## Entries from the intakes"
ABSENT_RE = re.compile(r"^\s*(?:does not speak|n/?a|none)\.?\s*(?:\([^()]*\))?\s*\.?\s*$", re.I)


def _entries(value):
    """The bullet lines for one report value, or [] when it only says the speaker is absent."""
    items = value if isinstance(value, list) else [value]
    out = []
    for it in items:
        if it is None: continue
        if isinstance(it, dict):
            s = "; ".join(f"{k}: {v}" for k, v in it.items() if v not in (None, ""))
        else:
            s = str(it)
        s = " ".join(s.split())
        if not s or ABSENT_RE.match(s): continue
        out.append(f"- {s}")
    return out


def _is_section(value):
    return isinstance(value, str) and value.strip().startswith("#")


def append(rep, stem, ledgered, root, anchors=None, today=None):
    """Append one report's speaker-ledger values. ledgered: [{name, page, report_keys}]; anchors: {page: anchor text}. Returns
    [(page, report key, 'section' | n entries | 'held' | 'absent')] for every key the report carries."""
    today = today or datetime.date.today().isoformat(); anchors = anchors or {}
    done = []
    for sp in ledgered:
        page = sp.get("page"); keys = sp.get("report_keys") or []
        if not page: continue
        for key in keys:
            if key not in rep: continue
            v = rep[key]; path = os.path.join(root, page)
            text = notes.read_text(path) if os.path.exists(path) else f"# Speaker ledger: {sp.get('name', '')}\n"
            if _is_section(v):
                sec = v.strip(); first = sec.splitlines()[0]
                if first in text: done.append((page, key, "held")); continue
                anchor = anchors.get(page)
                text = text.replace(anchor, "\n" + sec + "\n" + anchor, 1) if anchor and anchor in text else text.rstrip("\n") + "\n\n" + sec + "\n"
                notes.write_text(path, text); done.append((page, key, "section")); continue
            lines = _entries(v)
            if not lines: done.append((page, key, "absent")); continue
            head = f"### {stem}, {key}, appended {today}"
            if f"### {stem}, {key}," in text: done.append((page, key, "held")); continue
            if ENTRIES_HEADING not in text:
                text = text.rstrip("\n") + f"\n\n{ENTRIES_HEADING}\n\nAppended by `ledger integrate` from each intake report's speaker-ledger keys (pack.toml [[speakers.ledgered]] report_keys), as the writers returned them; the grid above is set from them by hand.\n"
            i = text.index(ENTRIES_HEADING); j = text.find("\n## ", i + len(ENTRIES_HEADING))   # the end of the entries section
            block = "\n\n" + head + "\n\n" + "\n".join(lines) + "\n"
            text = text.rstrip("\n") + block if j < 0 else text[:j].rstrip("\n") + block + text[j:]
            notes.write_text(path, text); done.append((page, key, len(lines)))
    return done
