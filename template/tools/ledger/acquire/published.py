"""A recording whose venue publishes its own transcript (phase 3 follow-up 2, 2026-10-22; finding 6 of
wip/platform-phase6b/adapter-findings.md): an inquiry's hearing day, a parliament's sitting, a court's hearing. The venue's page,
its transcript files and its links to the recordings are held together as one video item in <hold root>/video/<date>-<id>-<title>/:

- the page (held `page.html`, derived `page.md`), fetched through the web adapter (its robots policy, user agent and gate);
- each transcript file (held as obtained); the text is the first text transcript, copied to `transcript.txt` in UTF-8 with LF
  when it is not already (the venue's TXT may be cp1252 with CRLF: base.decode_text), else the text layer of a PDF transcript;
  the copy is marked in hold.json as the held original's normalised copy (base.normalised_copy: role derived, derived_from and
  `normalised_copy_of` the held file, the tool, and `normalised`, what it changed), so a word count takes one of the two. The
  record's `text` names the copy, not the original: the copy is the hold's text form (UTF-8, LF: tools/hold-schema.md rule 4),
  the form line citations and the verbatim gate read, and it has the original's lines one for one;
  a PDF transcript beside a text one is kept, and its text layer derived as `transcript-pdf-layer.txt`, a second witness;
- the recordings are linked, not fetched: `media_link` is the first, the metadata's `media_links` lists every one with its label,
  `media_status` says they are not downloaded, and `transcription` that a local transcription (transcribe.py) can be checked
  against the published transcript as its control when they are.

Files may be URLs or local paths (a local path is held with `how` naming it).

    python3 tools/ledger/acquire/published.py <page url> --transcript URL [--transcript URL ...] [--media "label|url" ...]
        [--id ID] [--title T] [--date YYYY-MM-DD] [--venue V] [--root DIR] [--hold-root DIR]
"""
import json, os, sys, tempfile, urllib.parse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B
from ledger.acquire import web as W


class PublishedTranscriptAdapter(W.WebAdapter):
    name = "published"

    def _get(self, src):
        """(bytes, name, how, content type, charset) of a URL (through the web adapter) or a local path."""
        if "://" in src:
            g = self.get_full(src)
            nm = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(g["final_url"]).path)) or "file"
            return g["data"], nm, f"HTTP {g['status']} response body of {g['final_url']}, {g['content_type']}", g["content_type"], g["charset"]
        ap = self.abs(src)
        nm = os.path.basename(ap)
        ctype = "application/pdf" if nm.lower().endswith(".pdf") else "text/plain" if nm.lower().endswith(".txt") else "application/octet-stream"
        return B.read_bytes(ap), nm, f"copied byte-for-byte from {self.rel(ap) if ap.startswith(self.root + os.sep) else ap}", ctype, None

    def capture_published(self, page_url, transcripts, media_links=(), identifier=None, title=None, date=None, date_basis=None,
                          venue=None, speakers=None, metadata=None, folder=None):
        g = self.get_full(page_url)
        raw = g["data"].decode(g["charset"] or "utf-8", "replace"); f = W.page_fields(raw, g["final_url"])
        files = [B.HeldFile("page.html", data=g["data"], how=f"HTTP {g['status']} response body of {g['final_url']}, {g['content_type']}"),
                 B.HeldFile("page.md", text=W.html_to_text(raw) + "\n", role="derived", derived_from="page.html", tool="ledger.acquire.web.html_to_text")]
        text_name = None; notes = []; pdfs = []
        for src in transcripts:
            data, nm, how, ctype, cs = self._get(src)
            nm = nm if len(nm) <= B.INNER_NAME_CAP and not B.LP.name_problems(nm) else B.LP.hold_name(nm)
            files.append(B.HeldFile(nm, data=data, how=how))
            if data[:5] == b"%PDF-": pdfs.append((nm, data)); continue
            if text_name is None:
                if B.needs_text_copy(data, cs):
                    copy, enc = B.normalised_copy("transcript.txt", data, nm, cs)   # marked as the held original's normalised copy
                    files.append(copy)
                    text_name = "transcript.txt"
                else:
                    text_name = nm
        if pdfs:
            from ledger.acquire import document as D
            import pypdf
            nm, data = pdfs[0]
            with tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, nm)
                with open(p, "wb") as fh: fh.write(data)
                layer = D.per_page_form(D.text_layer(p))
            out = "transcript-pdf-layer.txt" if text_name else "transcript.txt"
            files.append(B.HeldFile(out, text=layer, role="derived", derived_from=nm, tool=f"pypdf {pypdf.__version__} (the PDF transcript's text layer)"
                                    + ("; a second witness to the text transcript" if text_name else "")))
            text_name = text_name or out
        if date: basis = date_basis or "given by the caller"
        else: date = f["date"]; basis = f["date_basis"]
        links = [{"label": l, "url": u} for l, u in media_links]
        md = dict(media_links=[f"{l['label']}: {l['url']}" if l["label"] else l["url"] for l in links] or None,
                  media_status="linked, not downloaded" if links else "no recording linked",
                  transcription=("queued: a local transcription (tools/ledger/acquire/transcribe.py) of the recordings, when they are fetched, "
                                 "can be checked against the published transcript as its control") if links else None,
                  transcript_source="the venue's own transcript", page_url=page_url, date_basis=basis, robots=W.R.summary(g["robots"]))
        md.update(metadata or {})
        ident = identifier or page_url
        t = title or f["title"] or ident
        rec = B.Record(ident, "video", t, date=date, speaker_or_author=speakers, text=text_name, venue=venue or f.get("site"),
                       media_link=links[0]["url"] if links else None, provenance=page_url, metadata={k: v for k, v in md.items() if v is not None})
        name = (date + " " if date else "undated ") + (B.safe_slug(identifier, 40) if identifier else "")
        return B.Capture(rec, files, folder=folder or self.hold_path("video", name.strip(), t), status_note="; ".join(notes))

    def published(self, page_url, transcripts, **kw):
        try: cap = self.capture_published(page_url, transcripts, **kw)
        except (W.RobotsRefusal, W.FetchFailure) as e: return self._failed(page_url, "video", kw.get("title"), e)
        return self.hold(cap)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page"); ap.add_argument("--transcript", action="append", default=[]); ap.add_argument("--media", action="append", default=[])
    ap.add_argument("--id"); ap.add_argument("--title"); ap.add_argument("--date"); ap.add_argument("--venue"); ap.add_argument("--gap", type=float, default=10.0)
    ap.add_argument("--root"); ap.add_argument("--hold-root")
    a = ap.parse_args(argv)
    p = PublishedTranscriptAdapter(root=a.root, gap=a.gap, hold_root=a.hold_root)
    media = [tuple(m.split("|", 1)) if "|" in m else ("", m) for m in a.media]
    print(json.dumps(p.published(a.page, a.transcript, media_links=media, identifier=a.id, title=a.title, date=a.date, venue=a.venue), ensure_ascii=False))


if __name__ == "__main__":
    main()
