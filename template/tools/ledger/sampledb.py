#!/usr/bin/env python3
"""The shipped sample database (phase 7a of tools/platform-plan.md, 2026-10-22): a small SQLite database written from the invented
cases of tools/example-casebook.md, under the same deliberately different schema as the acquire tests' private sample
(tools/ledger/acquire/tests/make_sample_db.py, which is built from held notes and never ships):

    records(rec_no PK, headline, aired DD/MM/YYYY, outlet, presenter, participants "; "-joined, src_link, kind_code VID|AUD|RPT,
            blurb, keywords, entered YYYY-MM-DD, run_time)
    attachments(att_id PK, rec_no -> records, mime, location relative to the database's folder, byte_size, label)
    transcript_rows(row_id PK, rec_no -> records, seq, t_offset seconds, spk, utterance)   one row per timestamped paragraph
    annotations(ann_id PK, rec_no -> records, coder, code, body, attributed_to, created)   the group's coding

Every name, place, event, document and sentence below is invented (the casebook's rule); none is a quotation of anything real.
The attachments are small text files written beside the database under media/. The setup test (tools/ledger/tests/test_setup.py)
and the release bundle (tools/build_bundle.py) use this database; a recipient runs /setup against it before their own.

    python3 tools/ledger/sampledb.py <out.db>
"""
import os, sqlite3, sys

RECORDS = [
    # rec_no, headline, aired, outlet, presenter, participants, src_link, kind_code, blurb, keywords, entered, run_time
    (1, "Harrowmere Inquiry, hearing Day 12: evidence of the site engineer", "05/11/2019", "Harrowmere Inquiry", "Ms Adair",
     "Petra Vanecek; Ms Adair; Judge Imelda Corrin", "file:media/harrowmere-day-12.txt", "VID",
     "Counsel to the inquiry examines Calloway Ashdown Civil's site engineer on the 2009 concrete pour and the site diary (exhibit HI-114).",
     "infrastructure-safety; design-and-construction", "2026-10-20", "02:10:00"),
    (2, "Memorandum on cracking in the spillway's left wall", "02/06/2015", "Vale Water Authority", "Gareth Lisle", "Gareth Lisle",
     "file:media/lisle-memo-2015.txt", "RPT",
     "The inspector's memorandum to the chief executive reporting cracking in the left wall of the Harrowmere spillway.",
     "infrastructure-safety; inspection-and-warnings", "2026-10-20", "2 pages"),
    (3, "The memo nobody read: a warning about Harrowmere two years before the flood", "09/10/2017", "Ostley Gazette", "Owen Thale",
     "Owen Thale", "file:media/thale-ostley-gazette-2017.txt", "RPT",
     "The newspaper story that first published the Lisle memo, from an anonymous source inside the Authority.",
     "public-accountability; inspection-and-warnings", "2026-10-20", "1,100 words"),
    (4, "Harbour Talks: Petra Vanecek on building the Harrowmere spillway", "18/03/2020", "Harbour Talks", "Nell Ambrose",
     "Nell Ambrose; Petra Vanecek", "file:media/harbour-talks-vanecek-2020.txt", "AUD",
     "An interview podcast episode in which the former site engineer talks about the 2009 pour, core sample C-14 and her evidence.",
     "infrastructure-safety; design-and-construction", "2026-10-21", "00:58:00"),
    (5, "The Long Table, episode 4: the core sample", "02/06/2022", "The Long Table", "Rhea Castellan",
     "Rhea Castellan; Petra Vanecek", "file:media/long-table-episode-4.txt", "AUD",
     "A narrative podcast retelling the case; the fourth episode follows core sample C-14 from the 2011 test to its loss.",
     "public-accountability; design-and-construction", "2026-10-21", "00:47:00"),
    (6, "Margin Notes: what the Harrowmere failure does and does not show", "14/04/2021", "Margin Notes", "Ivo Strand", "Ivo Strand",
     "file:media/margin-notes-strand-2021.txt", "RPT",
     "An engineering blog series arguing that the failure was an ordinary design-margin problem, sceptical of the cover-up reading.",
     "infrastructure-safety; public-accountability", "2026-10-21", "2,400 words"),
    (7, "Corvane Holdings board minutes, 3 April 2014", "03/04/2014", "Corvane Holdings", "Anton Vesk", "Anton Vesk; Mara Quillon",
     "file:media/corvane-board-minutes-2014.txt", "RPT",
     "Minutes of the board meeting at which Project Larkspur was approved.", "money-and-contracts", "2026-10-21", "4 pages"),
    (8, "The Dorr cables: reporting from the Joint Trade Panel", "21/09/2015", "Dorr cables", "Anselm Dorr", "Anselm Dorr",
     "file:media/dorr-cables-2015.txt", "RPT",
     "Leaked diplomatic cables from Kestria's envoy on the timber levy dispute before the Joint Trade Panel.",
     "decision-makers; money-and-contracts", "2026-10-21", "6 cables"),
]

TEXTS = {
    1: [("Ms Adair", "Ms Vanecek, you were the site engineer for Calloway Ashdown Civil on the Harrowmere spillway from 2008 to 2012. Is that right?"),
        ("Petra Vanecek", "Yes. I joined CAC in 2008 and I was on site for the whole of the 2009 pour."),
        ("Ms Adair", "Please look at exhibit HI-114, the site diary. The entry for the pour of the left wall is dated 12 August 2009. Did you write it?"),
        ("Petra Vanecek", "I wrote most of the entries that summer. The left wall entry is mine. The weather that week was poor and the pour ran late into the night."),
        ("Ms Adair", "Pernell Geotechnics did the foundations as a subcontractor of Calloway Ashdown Civil. Did anyone from Pernell Geotechnics raise the foundation levels with you?"),
        ("Petra Vanecek", "They raised it at the site meeting. I passed it up to the project director. I do not know what happened to it after that."),
        ("Ms Adair", "In 2011 a core was taken from the left wall. The inquiry calls it core sample C-14. Did you see it tested?"),
        ("Petra Vanecek", "I saw it labelled and dated. I was told it was tested by the Vale Water Authority's laboratory. I never saw the result, and I am not able to say where it went."),
        ("Judge Imelda Corrin", "Thank you. We will rise for ten minutes.")],
    2: [(None, "To: Desmond Harlowe, Chief Executive, Vale Water Authority. From: Gareth Lisle, Inspector. Date: 2 June 2015."),
        (None, "On inspection of the Harrowmere spillway on 28 May 2015 I found cracking along the left wall, running from the second construction joint toward the top of the wall."),
        (None, "The cracking is wider than at the 2013 inspection. I recommend that the design certificate DC-0917 be reviewed and that the left wall be surveyed before the winter storms."),
        (None, "I ask that this memorandum be placed on the Authority's record.")],
    3: [(None, "Two years before the night of 14 March 2017, when the Harrowmere spillway failed and Ostley Vale flooded, an inspector of the Vale Water Authority warned his chief executive in writing that the left wall was cracking."),
        (None, "The memorandum, dated 2 June 2015 and seen by the Ostley Gazette, was written by Gareth Lisle. A source inside the Authority, who asked to be called Heron, said the memo was never placed on the record."),
        (None, "In March Desmond Harlowe, chief executive of the Vale Water Authority, said no warning had ever been put in writing. The Authority did not answer questions about the memo by the time of publication."),
        (None, "Calloway Ashdown Civil, which built the spillway in 2009, said it had not seen the memo.")],
    4: [("Nell Ambrose", "Petra, you gave evidence to the Harrowmere Inquiry last November. What was it like to go back to 2009?"),
        ("Petra Vanecek", "Strange. I had the site diary in front of me and it brought the whole summer back. We poured the left wall at night because the weather had held us up."),
        ("Nell Ambrose", "And the core sample, C-14. People keep coming back to it."),
        ("Petra Vanecek", "I labelled it myself in 2011. It went to the Authority's laboratory. After that it is a gap. I have been asked about it in every interview since the inquiry."),
        ("Nell Ambrose", "Do you think somebody lost it on purpose?"),
        ("Petra Vanecek", "I am not going to guess at that. I can tell you what I saw: it was labelled, dated and signed out. That is all I know firsthand.")],
    5: [("Rhea Castellan", "This is The Long Table. In this episode we follow one object: a cylinder of concrete called core sample C-14."),
        ("Rhea Castellan", "It was taken from the left wall of the Harrowmere spillway in 2011. It was tested. And then it disappeared."),
        ("Petra Vanecek", "I signed it out to the laboratory. There was a chain sheet. I would very much like to know where that sheet is now."),
        ("Rhea Castellan", "The Vale Water Authority told the inquiry the sample was lost in a laboratory move in 2014. Owen Thale, who first published the Lisle memo, does not believe that."),
        ("Rhea Castellan", "The Authority's 2018 review, the Report on the Harrowmere Event, does not mention core sample C-14 at all.")],
    6: [(None, "The story people want is concealment. The story the numbers tell is a design margin that was too thin for the storm of 14 March 2017."),
        (None, "The cracking Gareth Lisle reported in 2015 is the kind every spillway of that age shows. It does not prove anyone knew the wall would fail."),
        (None, "The loss of core sample C-14 is careless, not sinister: laboratories lose cores. The Long Table makes too much of it."),
        (None, "None of this excuses the Vale Water Authority. But the inquiry should judge the engineering first and the motives second.")],
    7: [(None, "Present: Anton Vesk (finance director), Mara Quillon (head of treasury), the board of Corvane Holdings."),
        (None, "Item 4. Project Larkspur. The finance director presented the transfer schedule. The board approved Project Larkspur."),
        (None, "The head of treasury asked that her concerns about the routing of the transfers be minuted. Brightwell Fenn LLP, the external auditor, is to be informed."),
        (None, "Item 5. Any other business. None.")],
    8: [(None, "Cable 1. From Anselm Dorr, envoy of Kestria, to the foreign ministry. The Joint Trade Panel resumed on the hardwood levy."),
        (None, "Cable 2. Ilse Morrow, trade minister of Velmora, defended the levy. Our information is that the rate was set on the advice of the Timber Exporters' League."),
        (None, "Cable 3. Greenhollow Trading is a front for the Timber Exporters' League. Greenhollow Trading is funded by the League's members and run by its secretariat."),
        (None, "Cable 4. Velmora and Kestria remain apart. The Joint Trade Panel is expected to rule in 2014.")],
}

TIMED = {1, 4, 5}   # recordings: their text is held as timed transcript rows as well as the attachment

ANNOTATIONS = [
    # rec_no, coder, code, body, attributed_to, created
    (1, "analyst 1", "claim:design-and-construction", "The left wall was poured at night in August 2009 after weather delays.", "Petra Vanecek", "2026-10-20"),
    (1, "analyst 1", "claim:inspection-and-warnings", "Pernell Geotechnics raised the foundation levels at a site meeting; the concern went to the project director.", "Petra Vanecek", "2026-10-20"),
    (1, "analyst 2", "claim:design-and-construction", "Core sample C-14 was labelled and dated in 2011; the witness never saw the test result.", "Petra Vanecek", "2026-10-20"),
    (2, "analyst 1", "claim:inspection-and-warnings", "Cracking along the left wall, wider than in 2013, reported on 2 June 2015.", "Gareth Lisle", "2026-10-20"),
    (3, "analyst 2", "claim:decision-makers", "The chief executive said no warning had been put in writing.", "Desmond Harlowe", "2026-10-20"),
    (3, "analyst 2", "claim:inspection-and-warnings", "An anonymous source says the memo was never placed on the record.", "Heron", "2026-10-20"),
    (6, "analyst 1", "claim:design-and-construction", "The failure reflects a thin design margin, not concealment.", "Ivo Strand", "2026-10-21"),
    (7, "analyst 2", "claim:money-and-contracts", "The board approved Project Larkspur; the head of treasury's concerns were minuted.", "Mara Quillon", "2026-10-21"),
    (8, "analyst 1", "claim:decision-makers", "The levy's rate was set on the advice of the Timber Exporters' League.", "Anselm Dorr", "2026-10-21"),
]

SCHEMA = """
    PRAGMA foreign_keys = ON;
    CREATE TABLE records (rec_no INTEGER PRIMARY KEY, headline TEXT NOT NULL, aired TEXT, outlet TEXT, presenter TEXT, participants TEXT,
                          src_link TEXT, kind_code TEXT, blurb TEXT, keywords TEXT, entered TEXT, run_time TEXT);
    CREATE TABLE attachments (att_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), mime TEXT, location TEXT,
                              byte_size INTEGER, label TEXT);
    CREATE TABLE transcript_rows (row_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), seq INTEGER, t_offset INTEGER,
                                  spk TEXT, utterance TEXT);
    CREATE TABLE annotations (ann_id INTEGER PRIMARY KEY, rec_no INTEGER NOT NULL REFERENCES records(rec_no), coder TEXT, code TEXT, body TEXT,
                              attributed_to TEXT, created TEXT);
"""


def attachment_text(rec_no):
    lines = []
    for spk, text in TEXTS[rec_no]:
        lines.append(f"{spk}: {text}" if spk else text)
    return "\n\n".join(lines) + "\n"


CHARTER = """The Harrowmere Waterworks Charter (1888), an invented canon text of the casebook

Clause 1. The Commissioners shall hold the reservoir at Harrowmere and its works in trust for the inhabitants of Ostley Vale.
Clause 2. The Commissioners shall cause the dam, the spillway and every channel to be inspected not less than once in each year.
Clause 3. Every inspection shall be reported in writing and the report entered in the book of the works before the next meeting.
Clause 4. No report of a defect shall be withdrawn from the book; a later report may answer it but shall not replace it.
Clause 5. Any inhabitant may read the book of the works at the office of the Commissioners on any day of business.
"""


def build(out):
    """Write the database to `out`, its attachments to media/ and the canon text to canon/ beside it; returns `out`."""
    out = os.path.abspath(out)
    if os.path.exists(out): os.remove(out)
    media = os.path.join(os.path.dirname(out), "media")
    os.makedirs(media, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(out), "canon"), exist_ok=True)
    with open(os.path.join(os.path.dirname(out), "canon", "charter-1888.txt"), "w", encoding="utf-8", newline="\n") as f: f.write(CHARTER)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)
    for r in RECORDS:
        con.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", r)
        rec_no = r[0]
        name = r[6].split("/", 1)[1]
        path = os.path.join(media, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(attachment_text(rec_no))
        con.execute("INSERT INTO attachments (rec_no, mime, location, byte_size, label) VALUES (?,?,?,?,?)",
                    (rec_no, "text/plain", "media/" + name, os.path.getsize(path), "transcript" if rec_no in TIMED else "text"))
        if rec_no in TIMED:
            t = 0
            for seq, (spk, text) in enumerate(TEXTS[rec_no], 1):
                con.execute("INSERT INTO transcript_rows (rec_no, seq, t_offset, spk, utterance) VALUES (?,?,?,?,?)", (rec_no, seq, t, spk, text))
                t += 45 + 7 * seq
    for a in ANNOTATIONS:
        con.execute("INSERT INTO annotations (rec_no, coder, code, body, attributed_to, created) VALUES (?,?,?,?,?,?)", a)
    con.commit(); con.close()
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    print(build(sys.argv[1]))
