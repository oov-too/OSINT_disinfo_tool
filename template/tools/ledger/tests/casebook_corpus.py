#!/usr/bin/env python3
"""A small synthetic corpus written from the invented cases of tools/example-casebook.md, for the tests of the parser library and the
acquire adapters (phase 7a: the tests run on fixtures that name nothing real, so they ship and run on any machine).

build(root) writes, under root, in this project's own layout:
    ledger.toml, packs/casebook/pack.toml       a project and a pack (the object watch: core sample C-14, its criteria column)
    transcripts/<id>.md                          two recordings in tools/fetch_transcript.py's form (one id starting with '-')
    videos/harrowmere-day-12.md, videos/harbour-talks-vanecek-2020.md, books/lisle-memo-2015.md
                                                 notes in the house form (metadata table, claims ledger, dated timeline, open
                                                 questions, cross-checks, object watch), each linking its held source
    books/sources/web/harrowmere-2018/           the held text of the Authority's review, its README (a set's provenance file)
    books/sources/web/harrowmere-2018/*.pdf+.txt PDFs with text layers and the per-page text beside each (both joins)
    books/sources/charter-1888.txt               a canon text in the verse form (book chapter:verse, TAB, text) and its witnesses
    books/sources/garbled-front-matter.txt       an OCR'd front matter that reads as noise
    books/sources/web/blog/                      blog posts held twice: the first-posted state and the completed copy
Every sentence is invented; any resemblance to a real person, body, place or document is accidental (the casebook's rule).
"""
import os, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)

VID_DAY12, VID_HARBOUR = "Hx12Day12Aa", "-HbrTalks20"   # synthetic recording ids (the second starts with '-', as some do)

SENTENCES = [
    "The left wall of the spillway was poured at night in August 2009 after the weather held the work back.",
    "Counsel to the inquiry asked whether the foundation levels were raised at the site meeting.",
    "The site diary for that week records the pour, the delay and the names of the workers on shift.",
    "Core sample C-14 was taken from the left wall in 2011, labelled, dated and signed out to the laboratory.",
    "Nobody in the room could say where the chain sheet for the sample went after the laboratory move.",
    "The inspector's memorandum of 2 June 2015 reported cracking wider than at the inspection of 2013.",
    "The chief executive told the press that no warning had ever been put in writing.",
    "The engineer said she could speak only to what she saw herself on the site that summer.",
    "The design certificate DC-0917 was signed by the contractor in 2009 and reviewed by nobody after.",
    "The Authority's review of 2018 does not mention the core sample at all.",
    "A podcast series retold the case in 2022 and followed the sample from the test to its loss.",
    "A sceptical blog argued that the failure was an ordinary design-margin problem and not concealment.",
]


def _para(i, n=12):
    return " ".join(SENTENCES[(i + k) % len(SENTENCES)] for k in range(n))


def transcript(title, channel, url, uploaded, n=240, chapters=False):
    from ledger.acquire import transcribe as TR
    segs = []
    for i in range(n):
        seg = (i * 45, 44, _para(i, 2))
        segs.append(seg + ((f"Part {1 + i // 80}",) if chapters else ()))
    return TR.format_transcript(title, channel, url, uploaded, "synthetic captions (the casebook fixtures)", segs)


NOTE = """# {title}

| | |
|---|---|
| **Channel** | {channel} |
| **Host** | {host} |
| **Speakers** | {speakers} |
| **URL** | {url} |
| **Uploaded** | {uploaded} |
| **Length** | {length} |
| **Description** | {description} |
| **Subjects** | [Infrastructure safety](../subjects/infrastructure-safety.md), [Public accountability](../subjects/public-accountability.md) |
| **Tags** | spillway, inspection, core sample |
| **Added to notes** | 2026-10-20 |
| **Transcript** | {transcript} |

## Summary

{summary}

## Claims ledger

| # | Time | Speaker | Topic | Claim | Source class | Move | Note |
|---|---|---|---|---|---|---|---|
{claims}

## Dated timeline

| # | Date (as stated) | Sortable | Event | Speaker, basis (time) | Chain | Database link | Agreement |
|---|---|---|---|---|---|---|---|
| 1 | August 2009 | 2009-08 | the left wall poured at night | {first} (0:01:00) | 1: {first} (firsthand) | new | new |
| 2 | 2 June 2015 | 2015-06-02 | the inspector's memorandum on cracking | {first} (0:03:00) | 2: {first} <- the memo | new | new |
| 2.1 | 14 March 2017 | 2017-03-14 | the spillway fails in a storm | {first} (0:04:00) | 1: {first} (public record) | new | new |

## Open questions

| # | Kind | Question | Bears on | What would settle it | Status | Answer | Answered by | Answered on |
|---|---|---|---|---|---|---|---|---|
| 1 | question | Where did the chain sheet of core sample C-14 go? | inspection-and-warnings; 0:02:00 | the laboratory's move records | open | | | |

## Cross-checks

| # | Kind | This note (time, row, claim) | Elsewhere (note, row) | Verdict | Note |
|---|---|---|---|---|---|
| 1 | corroborates | 0:01:00, claims 1 | [lisle-memo-2015](../books/lisle-memo-2015.md) claims 1 | partial | point: the cracking |

## Object watch

| Time | Object | Witness | Custody | Core sample criteria met | Strength | Register |
|---|---|---|---|---|---|---|
| 0:02:00 | core sample C-14 | {first} | contractor | core, labelled, dated | strong | 1 |
"""

NOTES = {
    "videos/harrowmere-day-12.md": dict(
        title="Harrowmere Inquiry, hearing Day 12: evidence of the site engineer", channel="Harrowmere Inquiry (public hearings)", host="Ms Adair",
        speakers="Ms Adair, Petra Vanecek, Judge Imelda Corrin", url=f"https://video.example.org/watch?v={VID_DAY12}", uploaded="2019-11-05",
        length="0:45:00", description="Day 12 of the public hearings: the site engineer's evidence on the 2009 pour.",
        transcript=f"[{VID_DAY12}.md](../transcripts/{VID_DAY12}.md)", first="Petra Vanecek",
        summary="Counsel examines the site engineer on the 2009 pour, the site diary and core sample C-14."),
    "videos/harbour-talks-vanecek-2020.md": dict(
        title="Harbour Talks: Petra Vanecek on building the Harrowmere spillway", channel="Harbour Talks (podcast)", host="Nell Ambrose",
        speakers="Nell Ambrose, Petra Vanecek", url=f"https://video.example.org/watch?v={VID_HARBOUR}", uploaded="2020-03-18",
        length="0:45:00", description="An interview with the former site engineer.",
        transcript=f"[{VID_HARBOUR}.md](../transcripts/{VID_HARBOUR}.md)", first="Petra Vanecek",
        summary="The former site engineer talks about the pour, the sample and her evidence."),
    "books/lisle-memo-2015.md": dict(
        title="Report on the Harrowmere Event (Vale Water Authority, 2018) and the Lisle memo", channel="Vale Water Authority", host="",
        speakers="Gareth Lisle, Desmond Harlowe", url="https://records.example.org/harrowmere-2018", uploaded="2018-05-14",
        length="4 pages", description="The Authority's review and the memorandum it does not cite.",
        transcript=("[report-on-the-harrowmere-event.txt](sources/web/harrowmere-2018/report-on-the-harrowmere-event.txt); "
                    "[README.md](sources/web/harrowmere-2018/README.md)"), first="Gareth Lisle",
        summary="The review says no warning was received; the memo of 2 June 2015 says otherwise."),
}

CLAIM_TOPICS = ["design-and-construction", "inspection-and-warnings", "decision-makers", "money-and-contracts", "other"]


def claims_rows(first, n=10):
    out = []
    for i in range(1, n + 1):
        out.append(f"| {i} | 0:{i:02d}:00 | {first if i % 2 else 'Ms Adair'} | {CLAIM_TOPICS[i % len(CLAIM_TOPICS)]} | {SENTENCES[i % len(SENTENCES)]} | "
                   f"firsthand | open | attribution: {'firsthand' if i % 2 else 'told'}; chain: 1: {first} (firsthand). |")
    return "\n".join(out)


REPORT_PAGES = [
    "REPORT ON THE HARROWMERE EVENT\nVale Water Authority, 2018",
    "1. The spillway failed in a storm on the night of 14 March 2017.\n2. No warning of cracking was received before 2017.",
    "3. The design certificate DC-0917 was in order.\n4. The left wall met its design margin at construction.",
    "5. The Authority accepts the findings of this review.",
]

CHARTER_VERSES = [
    ("Charter", 1, 1, "The Commissioners shall hold the reservoir at Harrowmere and its works in trust for the inhabitants of Ostley Vale."),
    ("Charter", 1, 2, "The Commissioners shall cause the dam, the spillway and every channel to be inspected once in each year."),
    ("Charter", 1, 3, "Every inspection shall be reported in writing and entered in the book of the works."),
    ("Charter", 2, 1, "No report of a defect shall be withdrawn from the book; a later report may answer it but shall not replace it."),
    ("Charter", 2, 2, "Any inhabitant may read the book of the works at the office of the Commissioners."),
    ("Minutes", 1, 1, "The commissioners met on the first day and resolved to draft a charter for the works."),
    ("Minutes", 1, 2, "The clerk was told to keep a book of the works and to enter every report in it."),
]

GARBLED = "\n".join(["~;l, ;1 ' .:!ii' l1| ,,. ':;i !l 1 |' ;", "r~ ll ;.,' i:| 1l ',. ;; l! i ~ .", "tl1 ,; :' !| l ii .,;' ~r 1 l",
                     "' ;1 l| ,. !i ~:; 1' l, .i |l ;", "ll ;i ', !1 .| ~l ;: i' ,l 1 !"] * 6)

BLOG_FULL = ("The post sets out the spillway story from the first warning to the inquiry, step by step, with the documents the author "
             "has read and the people he has spoken to, and it ends with the questions the inquiry has not yet answered. ") * 6
BLOG_HEADER = "# A blog post on the spillway\n\nProvenance: the casebook fixtures, a blog post held twice\n"


def text_pdf(path, pages, scanned=False, producer=None):
    """A PDF with one text page per entry (lines in Helvetica 12), no dependency; the text layer pypdf reads back is the lines joined by
    newlines. scanned=True makes each page a scan with someone else's OCR under it, as a paper-capture file is: a page-sized image
    drawn first and the text in invisible render mode over it. `producer` sets the document's /Producer."""
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids = []
    n = 5 if scanned else 4
    if scanned:   # one 8 x 8 greyscale image, shared by every page
        px = zlib.compress(bytes([200, 210, 220, 230, 240, 230, 220, 210] * 8))
        objs[4] = (b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length "
                   + str(len(px)).encode() + b" >>\nstream\n" + px + b"\nendstream")
    for text in pages:
        ops = (["q", "612 0 0 792 0 0 cm", "/Im1 Do", "Q"] if scanned else []) + ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"] + (["3 Tr"] if scanned else [])
        for k, line in enumerate(text.split("\n")):
            esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({esc}) Tj" if k == 0 else f"T* ({esc}) Tj")
        ops.append("ET")
        stream = zlib.compress("\n".join(ops).encode("latin-1"))
        objs[n] = b"<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream"
        res = "/Font << /F1 3 0 R >>" + (" /XObject << /Im1 4 0 R >>" if scanned else "")
        objs[n + 1] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {n} 0 R /Resources << {res} >> >>").encode()
        kids.append(n + 1); n += 2
    objs[2] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>").encode()
    info = None
    if producer:
        info = max(objs) + 1
        objs[info] = ("<< /Producer (" + producer.replace("(", "\\(").replace(")", "\\)") + ") >>").encode("latin-1")
    out = bytearray(b"%PDF-1.4\n"); offs = {}
    for i in sorted(objs):
        offs[i] = len(out); out += f"{i} 0 obj\n".encode() + objs[i] + b"\nendobj\n"
    x = len(out); size = max(objs) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode() + b"".join(f"{offs[i]:010d} 00000 n \n".encode() for i in range(1, size))
    out += (f"trailer\n<< /Size {size} /Root 1 0 R" + (f" /Info {info} 0 R" if info else "") + f" >>\nstartxref\n{x}\n%%EOF\n").encode()
    with open(path, "wb") as f: f.write(bytes(out))
    return path


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)
    return path


def build(root):
    """Write the corpus under root; returns a dict of the paths the tests use."""
    from ledger.acquire import document as D
    root = os.path.abspath(root); P = lambda *p: os.path.join(root, *p)
    write(P("ledger.toml"), '[ledger]\nname = "casebook-fixtures"\ntitle = "Casebook fixtures"\n\n[pack]\npath = "packs/casebook"\n')
    write(P("packs", "casebook", "pack.toml"), '[pack]\nname = "casebook"\n\n[objects]\nwatch_heading = "## Object watch"\n'
          'criteria_column = "Core sample criteria met"\n\n[[layout.folder]]\nalias = "sources/sets/harrowmere-2018/"\n'
          'target = "books/sources/web/harrowmere-2018/"\nwhy = "a document set of one intake run"\n')
    write(P("transcripts", f"{VID_DAY12}.md"), transcript(NOTES["videos/harrowmere-day-12.md"]["title"], "Harrowmere Inquiry (public hearings)",
                                                        NOTES["videos/harrowmere-day-12.md"]["url"], "2019-11-05", chapters=True))
    write(P("transcripts", f"{VID_HARBOUR}.md"), transcript(NOTES["videos/harbour-talks-vanecek-2020.md"]["title"], "Harbour Talks (podcast)",
                                                          NOTES["videos/harbour-talks-vanecek-2020.md"]["url"], "2020-03-18"))
    for rel, v in NOTES.items():
        write(P(rel), NOTE.format(claims=claims_rows(v["first"]), **v))
    set_dir = P("books", "sources", "web", "harrowmere-2018")
    write(os.path.join(set_dir, "report-on-the-harrowmere-event.txt"), D.per_page_form(REPORT_PAGES))
    write(os.path.join(set_dir, "README.md"), "# Harrowmere 2018\n\n| File | Held from | Captured |\n|---|---|---|\n"
          "| report-on-the-harrowmere-event.txt | the Authority's records portal | 2026-10-20 |\n")
    pdfs = {}
    for name, sep in (("review-2018", "\n\n"), ("review-2018-annex", "\n")):
        pdf = text_pdf(os.path.join(set_dir, f"{name}.pdf"), REPORT_PAGES)
        write(os.path.join(set_dir, f"{name}.txt"), D.per_page_form(REPORT_PAGES, sep))
        pdfs[name] = pdf
    # the review as a scan with someone else's OCR under its page images (a paper-capture file), and that OCR's per-page text
    pdfs["scan"] = text_pdf(os.path.join(set_dir, "review-2018-scan.pdf"), REPORT_PAGES, scanned=True, producer="Synthetic Paper Capture Plug-in")
    write(os.path.join(set_dir, "review-2018-scan.txt"), D.per_page_form(REPORT_PAGES))
    write(P("books", "sources", "charter-1888.txt"), "\n".join(f"{b} {c}:{v}\t{t}" for b, c, v, t in CHARTER_VERSES) + "\n")
    write(P("books", "sources", "charter-witnesses.txt"), "\n".join(f"{w} {b} {c}:{v}\t{t}" for w in ("Ed1888", "Ed1932") for b, c, v, t in CHARTER_VERSES[:5]) + "\n")
    write(P("books", "sources", "garbled-front-matter.txt"), "Front matter\n\n\n" + GARBLED + "\n")
    blog = P("books", "sources", "web", "blog")
    write(os.path.join(blog, "W01-spillway.md"), BLOG_HEADER + "\n---\n\n" + BLOG_FULL.strip() + "\n")
    write(os.path.join(blog, "W01-spillway.first-posted-state.md"), BLOG_HEADER + "\n---\n\n" + BLOG_FULL[:len(BLOG_FULL) * 3 // 5].rsplit(" ", 1)[0] + "\n")
    write(os.path.join(blog, "W02-other.md"), BLOG_HEADER.replace("Provenance:", "Provenance (verified by the orchestrator by reading):") + "\n---\n\n"
          + ("A different post about the laboratory move and the chain sheet, written later and on another subject entirely. " * 8).strip() + "\n")
    write(os.path.join(blog, "W02-other.first-posted-state.md"), BLOG_HEADER + "\n---\n\n" + BLOG_FULL[:300].rsplit(" ", 1)[0] + "\n")
    return {"root": root, "notes": sorted(NOTES), "transcripts": [f"transcripts/{VID_DAY12}.md", f"transcripts/{VID_HARBOUR}.md"],
            "set": os.path.relpath(set_dir, root), "pdfs": pdfs, "report_txt": os.path.join(set_dir, "report-on-the-harrowmere-event.txt"),
            "verses": P("books", "sources", "charter-1888.txt"), "witnesses": P("books", "sources", "charter-witnesses.txt"),
            "garbled": P("books", "sources", "garbled-front-matter.txt"), "blog": blog,
            "image": os.path.join(HERE, "fixtures", "casebook-page.png")}


if __name__ == "__main__":
    import json
    print(json.dumps(build(sys.argv[1]), indent=1))
