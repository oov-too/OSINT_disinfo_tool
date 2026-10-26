#!/usr/bin/env python3
"""Parse the Project Gutenberg King James Bible (eBook #10, public domain) into books/sources/kjv.txt,
one verse per line: '<book code> <chapter>:<verse>\t<text>', using the same book codes as tanakh-wlc.txt
(Gen, Exod, ... Ezek, Dan ...) plus New Testament codes. Input: a downloaded pg10.txt."""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
src = sys.argv[1]; out = "books/sources/kjv.txt"
NAMES = [("The First Book of Moses: Called Genesis","Gen"),("The Second Book of Moses: Called Exodus","Exod"),("The Third Book of Moses: Called Leviticus","Lev"),
 ("The Fourth Book of Moses: Called Numbers","Num"),("The Fifth Book of Moses: Called Deuteronomy","Deut"),("The Book of Joshua","Josh"),("The Book of Judges","Judg"),
 ("The Book of Ruth","Ruth"),("The First Book of Samuel","1Sam"),("The Second Book of Samuel","2Sam"),("The First Book of the Kings","1Kgs"),("The Second Book of the Kings","2Kgs"),
 ("The First Book of the Chronicles","1Chr"),("The Second Book of the Chronicles","2Chr"),("Ezra","Ezra"),("The Book of Nehemiah","Neh"),("The Book of Esther","Esth"),
 ("The Book of Job","Job"),("The Book of Psalms","Ps"),("The Proverbs","Prov"),("Ecclesiastes","Eccl"),("The Song of Solomon","Song"),("The Book of the Prophet Isaiah","Isa"),
 ("The Book of the Prophet Jeremiah","Jer"),("The Lamentations of Jeremiah","Lam"),("The Book of the Prophet Ezekiel","Ezek"),("The Book of Daniel","Dan"),("Hosea","Hos"),
 ("Joel","Joel"),("Amos","Amos"),("Obadiah","Obad"),("Jonah","Jonah"),("Micah","Mic"),("Nahum","Nah"),("Habakkuk","Hab"),("Zephaniah","Zeph"),("Haggai","Hag"),
 ("Zechariah","Zech"),("Malachi","Mal"),("The Gospel According to Saint Matthew","Matt"),("The Gospel According to Saint Mark","Mark"),("The Gospel According to Saint Luke","Luke"),
 ("The Gospel According to Saint John","John"),("The Acts of the Apostles","Acts"),("The Epistle of Paul the Apostle to the Romans","Rom"),
 ("The First Epistle of Paul the Apostle to the Corinthians","1Cor"),("The Second Epistle of Paul the Apostle to the Corinthians","2Cor"),
 ("The Epistle of Paul the Apostle to the Galatians","Gal"),("The Epistle of Paul the Apostle to the Ephesians","Eph"),("The Epistle of Paul the Apostle to the Philippians","Phil"),
 ("The Epistle of Paul the Apostle to the Colossians","Col"),("The First Epistle of Paul the Apostle to the Thessalonians","1Thess"),
 ("The Second Epistle of Paul the Apostle to the Thessalonians","2Thess"),("The First Epistle of Paul the Apostle to Timothy","1Tim"),
 ("The Second Epistle of Paul the Apostle to Timothy","2Tim"),("The Epistle of Paul the Apostle to Titus","Titus"),("The Epistle of Paul the Apostle to Philemon","Phlm"),
 ("The Epistle of Paul the Apostle to the Hebrews","Heb"),("The General Epistle of James","Jas"),("The First Epistle General of Peter","1Pet"),
 ("The Second General Epistle of Peter","2Pet"),("The First Epistle General of John","1John"),("The Second Epistle General of John","2John"),
 ("The Third Epistle General of John","3John"),("The General Epistle of Jude","Jude"),("The Revelation of Saint John the Divine","Rev")]
lines = open(src, encoding="utf-8-sig").read().split("\n")
# skip the table of contents: the body starts at the second occurrence of the Genesis header
starts = [i for i, l in enumerate(lines) if l.strip() == NAMES[0][0]]
body = lines[starts[1]:] if len(starts) > 1 else lines
name_to_code = dict(NAMES); verses = []
# book sections: a header line, then paragraphs in which verses may begin mid-line ("...Hiddekel; 10:5 Then I lifted up");
# Samuel is headed "The First Book of Samuel" and, four lines on, "The First Book of the Kings" (otherwise called), so a header within 6 lines of the last is ignored
sections = []; last_hdr = -99
for i, l in enumerate(body):
    t = l.strip()
    if t.startswith("*** END OF"): break
    if t in name_to_code and i - last_hdr > 6:
        sections.append([name_to_code[t], []]); last_hdr = i
    elif sections and not (t in name_to_code):
        sections[-1][1].append(t)
vre = re.compile(r"(?:^|(?<=\s))(\d+):(\d+)\s")
for code, ls in sections:
    text = " ".join(ls); text = re.sub(r"\s+", " ", text)
    parts = vre.split(text)   # [pre, c, v, text, c, v, text, ...]
    for k in range(1, len(parts) - 2, 3):
        verses.append([code, int(parts[k]), int(parts[k + 1]), parts[k + 2].strip()])
with LN.open_write(LP.new_hold(out)) as f:
    f.write("# The King James Version, Project Gutenberg eBook #10 (public domain), one verse per line: book code chapter:verse, tab, text. Book codes as in tanakh-wlc.txt. Parsed by tools/fetch_kjv.py.\n")
    for b, c, v, txt in verses: f.write(f"{b} {c}:{v}\t{txt}\n")
print("verses:", len(verses), "books:", len({v[0] for v in verses}))
