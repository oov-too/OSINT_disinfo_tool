"""The hold schema in machine form (phase 3 of tools/platform-plan.md, 2026-10-22). The document is tools/hold-schema.md; the
two agree field for field (tests/test_base.py checks it). Every adapter fills a Record with these fields; the setup scan and the
database adapter's mapping proposal match a source's column names against the synonyms here.

A field: name, meaning, type, required, synonyms (lower case, matched after the column name is split into words; see
`name_tokens`). `required` is one of "yes" (an adapter refuses to hold without it), "set" (the adapter supplies it, never the
source), "no".
"""
import re

SCHEMA_VERSION = "1.0"

MEDIA_KINDS = {
    # media kind -> the hold folder it lands in under sources/
    "video": "video", "audio": "audio", "text": "text", "document": "document", "image": "image",
    "web-page": "web", "post": "web", "thread": "web", "feed": "web",
    "archive-item": "archive", "canon": "canon", "record": "db",
}

FIELDS = [
    dict(name="identifier", type="string", required="yes",
         meaning="The item's stable identifier in the place it came from: a YouTube id, a URL, a database key, an archive item "
                 "number, a canon text's short name. Unique within its source; never reused for another item.",
         synonyms=["id", "identifier", "key", "uid", "uuid", "guid", "pk", "record id", "rec no", "record no", "record number",
                   "item id", "doc id", "document id", "document number", "accession", "accession number", "catalogue number",
                   "catalog number", "call number", "reference", "ref", "esdn", "serial", "video id", "file id", "entry id",
                   "case number", "case id", "control number", "number", "no"]),
    dict(name="media_kind", type="enum (" + ", ".join(sorted(MEDIA_KINDS)) + ")", required="yes",
         meaning="What the item is as a medium; decides the hold folder (sources/<folder>/) and which preparation applies "
                 "(transcription for video and audio, text layer and OCR for document and image).",
         synonyms=["kind", "type", "media type", "media kind", "medium", "format", "mime", "mime type", "content type",
                   "record type", "item type", "doc type", "document type", "genre", "category", "source type", "kind code"]),
    dict(name="date", type="ISO 8601 date (YYYY-MM-DD, YYYY-MM or YYYY), with date_raw kept", required="no",
         meaning="The date the item belongs to: published, uploaded, recorded, written or created, whichever the source states "
                 "(the metadata block says which as date_basis). The source's own spelling is kept as date_raw; an inferred "
                 "or swapped day and month is marked with a trailing `?`.",
         synonyms=["date", "published", "publication date", "pub date", "uploaded", "upload date", "recorded", "recording date",
                   "created", "creation date", "created at", "date created", "aired", "air date", "broadcast", "dated",
                   "document date", "event date", "timestamp", "time", "issued", "date of", "posted", "posted at", "year"]),
    dict(name="title", type="string", required="yes",
         meaning="The item's title as the source gives it, in full (the slug is cut; the title never is). Where the source has "
                 "none, a description in square brackets, e.g. [untitled letter of 3 May 1950].",
         synonyms=["title", "name", "headline", "heading", "subject", "caption", "label", "document title", "video title",
                   "episode title", "display name", "short title"]),
    dict(name="speaker_or_author", type="list of strings", required="no",
         meaning="Who speaks or wrote: authors, speakers, interviewer and interviewees, signatories, the poster of a post. "
                 "Names as the source spells them; roles, where the source gives them, in the metadata block.",
         synonyms=["author", "authors", "by", "byline", "writer", "creator", "speaker", "speakers", "host", "guest", "guests",
                   "presenter", "interviewer", "interviewee", "participants", "witness", "witnesses", "signatory", "sender",
                   "from", "poster", "username", "user", "handle", "contributor", "respondent", "narrator", "person", "people"]),
    dict(name="text", type="file in the hold (UTF-8, LF), or empty with a status", required="no",
         meaning="The item's text: the transcript of a recording, the text layer or OCR of a document, the body of a page or "
                 "post. A file inside the hold, derived from a held file by a named tool, or held as obtained when the source "
                 "is text. Empty only with a status saying why (transcriber missing, renderer missing, pending).",
         synonyms=["text", "body", "content", "transcript", "transcription", "full text", "fulltext", "ocr", "ocr text",
                   "utterance", "utterances", "words", "contents", "message", "post body", "article", "description", "notes",
                   "summary", "abstract", "narrative", "statement", "testimony"]),
    dict(name="media_link", type="URL or path", required="no",
         meaning="Where the item's media are: the video or audio URL, a file path in the source's store, a scan's URL. Media "
                 "found at a path are held byte-for-byte; a URL is recorded and fetched only where the network permits.",
         synonyms=["url", "link", "href", "uri", "media", "media url", "media link", "file", "file path", "path", "location",
                   "filename", "file name", "attachment", "audio", "video", "recording", "scan", "image", "pdf", "source url",
                   "download", "blob"]),
    dict(name="venue", type="string", required="no",
         meaning="Where the item appeared: channel, programme, outlet, publisher, forum and board, hearing and committee, "
                 "archive and collection, journal.",
         synonyms=["venue", "channel", "outlet", "publisher", "publication", "source", "site", "forum", "board", "subreddit",
                   "programme", "program", "show", "podcast", "series", "network", "station", "journal", "newspaper",
                   "collection", "archive", "repository", "committee", "hearing", "event", "conference", "folder", "box"]),
    dict(name="provenance", type="string (URL, query, path)", required="set",
         meaning="How the item was obtained, exactly enough to obtain it again: the URL fetched, the SQL query with its "
                 "parameters, the archive item URL, the export file and row, the local path a file was copied from.",
         synonyms=["provenance", "source url", "origin", "obtained from", "retrieved from", "query", "accession source",
                   "acquired from", "fetched from", "permalink", "canonical url"]),
    dict(name="capture_time", type="ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)", required="set",
         meaning="When the adapter read the item. Every later capture of the same item adds a capture row; earlier held bytes "
                 "are never overwritten.",
         synonyms=["captured", "capture time", "retrieved", "retrieved at", "accessed", "access date", "fetched", "fetched at",
                   "harvested", "ingested", "imported", "imported at", "updated", "modified", "last modified", "updated at"]),
    dict(name="capture_tool", type="string", required="set",
         meaning="The adapter and version that held the item, and the underlying tool it wrapped with its version or settings "
                 "(e.g. `ledger.acquire.youtube 1.0 via tools/fetch_transcript.py`).",
         synonyms=["tool", "capture tool", "harvester", "scraper", "importer", "software", "agent", "user agent"]),
    dict(name="metadata", type="table of key -> value (strings, numbers, lists)", required="no",
         meaning="Everything else the source states about the item that no field above takes: unmapped columns, the date's "
                 "basis, roles, page counts, captions language, licence. Kept whole; promotable to a pack's keys later.",
         synonyms=["metadata", "meta", "extra", "attributes", "properties", "tags", "keywords", "fields", "info", "misc"]),
]

FIELD_NAMES = [f["name"] for f in FIELDS]
BY_NAME = {f["name"]: f for f in FIELDS}
REQUIRED = [f["name"] for f in FIELDS if f["required"] == "yes"]
SET_BY_ADAPTER = [f["name"] for f in FIELDS if f["required"] == "set"]


def name_tokens(name):
    """A column name as lower-case words: camelCase, snake_case, kebab-case, dotted and spaced names all split the same way
    (`recNo` -> ['rec', 'no']; `upload_date` -> ['upload', 'date'])."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [w for w in re.split(r"[^A-Za-z0-9]+", s.lower()) if w]


def synonym_score(column, field):
    """How well a column name matches a field's synonyms: 1.0 an exact synonym; 0.85 a synonym that is the column's last words
    (`aired_on` no; `upload_date` yes for "date"); 0.7 a synonym's words all inside the column's words; 0.5 a near spelling
    (difflib ratio >= 0.85); else 0."""
    import difflib
    toks = name_tokens(column); joined = " ".join(toks)
    best = 0.0
    for syn in BY_NAME[field]["synonyms"]:
        sw = syn.split()
        if joined == syn: return 1.0
        if len(toks) >= len(sw) and toks[-len(sw):] == sw: best = max(best, 0.85)
        elif all(w in toks for w in sw): best = max(best, 0.7)
        elif difflib.SequenceMatcher(None, joined, syn).ratio() >= 0.85: best = max(best, 0.5)
    return best
