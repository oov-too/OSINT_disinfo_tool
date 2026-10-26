#!/usr/bin/env python3
"""Topic corroboration chart: which topics in the database are carried by many distinct speakers, and which by few.

Reads notes.db (tags, claims) and writes research/figures/topic-corroboration.png and .svg plus
research/figures/topic-corroboration.json (the numbers). Run: python3 tools/draw_topic_corroboration.py [--top 50] [--speakers 30]

Method (keep this when editing):
  Topics are the notes' tags that appear in at least MIN_NOTES notes, minus meta tags (hosts, channels, house labels).
  A mention is a claims row whose Claim or Attribution text contains the tag as a whole word (a tag with any capital letter,
  a name, acronym or title, is matched as written; an all-lowercase tag is matched case-insensitively); for a person tag of two or more words the surname
  alone also counts when it is five letters or longer and written capitalised in the row, because the ledgers name people
  by surname (a capitalised surname counts; the same word in lower case does not), unless the surname belongs to more than one person in
  the people table or is also a place or base name (the pack's place_words). Tags that are only numbers are dropped.
  Tag spellings are merged by case, tools/name_aliases.json and the pack's chart-level pairs ([display.corroboration] aliases); only
  multi-word aliases are matched as text. The meta tags, place words, stop words and the footer's note are display settings.
  Speakers are the claims rows' Speaker cells, normalised to a surname (parentheticals stripped; compound speakers such as
  "A and B" or channelled "X via Y" are kept as their own label).
  Distinct speakers is the corroboration proxy the chart ranks by; it counts voices, not independence. A host relaying a guest
  and the guest both count, so read the firsthand marker (rows classed firsthand) as the stricter figure.
  Top panel: bars = total mentions; black diamond = distinct speakers; hollow diamond = distinct speakers with firsthand rows.
  Bottom panel: topic by speaker heatmap of mention counts (log colour), same topic order, top speakers by total mentions.
  Colours: bars #cfd8e3, firsthand-share overlay #2e8b57 at 45% alpha, diamonds #111, heat map Blues, empty #f2f2f2.
"""
import os, re, sys, json, sqlite3, math
from datetime import date
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from collections import defaultdict, Counter
TOP=int(sys.argv[sys.argv.index("--top")+1]) if "--top" in sys.argv else 50
NSPK=int(sys.argv[sys.argv.index("--speakers")+1]) if "--speakers" in sys.argv else 30
MIN_NOTES=3
sys.path.insert(0,"tools"); import packload   # meta tags, spelling pairs, place names, stop words, footer note (pack.toml [display.corroboration]; phase 5)
DC=packload.display("corroboration")
META=set(DC["meta_tags"])|set(DC["meta_tags_extra"])|{packload.objects()["watch_name"]}   # the object watch's name is a house label too
con=sqlite3.connect("notes.db")
tags=defaultdict(set)
for v,t in con.execute("select video, tag from tags"): tags[t.strip()].add(v)
people={r[0].lower() for r in con.execute("select name from people")}
# merge tag spellings: case, the house alias file, and a few chart-level pairs
ALIAS={}
try:
    for k,vs in json.load(open("tools/name_aliases.json",encoding="utf-8")).items():
        if k=="_comment": continue
        for v in vs: ALIAS[v.lower()]=k
except Exception: pass
ALIAS.update(DC["aliases"])
merged=defaultdict(set); canon_name={}
for t,vs in tags.items():
    key=ALIAS.get(t.lower(),None)
    if key is None:
        key=canon_name.get(t.lower(),t); canon_name.setdefault(t.lower(),key)
    merged[key]|=vs
tags=merged
topics=[t for t,vs in tags.items() if len(vs)>=MIN_NOTES and t.lower() not in META and len(t)>2 and re.search(r"[A-Za-z]",t) and not re.fullmatch(r"[\d,.\s$%]+",t)]
def canon_speaker(s):
    s=re.sub(r"\s*\(.*?\)","",s or "").strip()
    if not s: return "unattributed"
    if " via " in s or " and " in s or "," in s or "/" in s: return s
    parts=s.split()
    return parts[-1] if len(parts)>1 and len(parts[-1])>2 else s
rows=[(v,canon_speaker(sp),(cl or "")+" "+(att or ""),(sc or "").lower()) for v,sp,cl,att,sc in con.execute("select video, speaker, claim, attribution, source_class from claims")]
low=[(v,sp,txt,txt.lower(),sc) for v,sp,txt,sc in rows]
PLACE=set(DC["place_words"])
SURNAMES=Counter(n.split()[-1].lower().strip(".,") for n in people if len(n.split())>=2)
STOP=set(DC["stop_words"])|set(DC["stop_words_extra"])
def patterns(t):
    # every merged spelling of the tag is matched
    # only multi-word aliases are matched as text (single-word ones such as SHE, Lou, Gary, Max are too ambiguous)
    spell={t}|{a for a,k in ALIAS.items() if k==t and len(a.split())>=2 and len(a)>=6}
    pats=[]
    for sp_ in spell:
        # a tag written with any capital (a name, an acronym, a title) is matched as written; an all-lowercase tag
        # (radar, consciousness) is matched case-insensitively
        if any(ch.isupper() for ch in sp_): pats.append(("cap",re.compile(r"\b"+re.escape(sp_)+r"\b")))
        else: pats.append(("low",re.compile(r"\b"+re.escape(sp_.lower())+r"\b")))
    w=t.split()
    if len(w)>=2 and t.lower() in people:
        sur=w[-1].lower().strip(".,")
        # surname match only when the surname belongs to one person in the people table and is not also a place or base name
        if len(sur)>=5 and sur not in STOP and sur not in PLACE and SURNAMES[sur]==1: pats.append(("cap",re.compile(r"\b"+re.escape(w[-1].strip(".,"))+r"\b")))
    return pats
out=[]
for t in topics:
    pats=patterns(t); spk=Counter(); fh=set(); notes=set()
    for v,sp,raw,txt,sc in low:
        if any(p.search(raw if kind=="cap" else txt) for kind,p in pats):
            spk[sp]+=1; notes.add(v)
            if sc.startswith("firsthand"): fh.add(sp)
    m=sum(spk.values())
    if m==0: continue
    out.append({"topic":t,"mentions":m,"speakers":len(spk),"firsthand_speakers":len(fh),"notes_tagged":len(tags[t]),"notes_mentioning":len(notes),"by_speaker":dict(spk.most_common())})
out.sort(key=lambda r:(-r["speakers"],-r["mentions"]))
json.dump({"built":date.today().isoformat(),"min_notes":MIN_NOTES,"topics":out},open("research/figures/topic-corroboration.json","w"),indent=1,ensure_ascii=False)
sel=out[:TOP]
if not sel: print("no topic is mentioned in two or more notes yet: research/figures/topic-corroboration.json written, no chart drawn"); sys.exit(0)   # a new project (phase 7b)
# speakers for the heatmap: most mentions across the selected topics
sc=Counter()
for r in sel:
    for s,c in r["by_speaker"].items(): sc[s]+=c
spk=[s for s,_ in sc.most_common(NSPK)]
n=len(sel); fig=plt.figure(figsize=(22,0.34*n+0.42*len(spk)+9),dpi=150)
gs=fig.add_gridspec(2,1,height_ratios=[0.34*n+2,0.42*len(spk)+3],hspace=0.10)
ax=fig.add_subplot(gs[0]); maxm=max(r["mentions"] for r in sel); ax.set_xlim(0,maxm*1.02); ax.set_ylim(n,-1.4)
ax.add_patch(Rectangle((0,-1.4),maxm*1.02,0.0,color="white",lw=0))
for i,r in enumerate(sel):
    ax.add_patch(Rectangle((0,i+0.12),r["mentions"],0.76,color="#cfd8e3",lw=0))
    fhm=sum(c for s,c in r["by_speaker"].items() if s in set(r["by_speaker"]) )  # placeholder to keep API simple
    ax.text(maxm*1.03,i+0.5,f'{r["mentions"]} mentions · {r["speakers"]} speakers ({r["firsthand_speakers"]} firsthand) · {r["notes_mentioning"]} notes',va="center",ha="left",fontsize=8.5,color="#333")
ax.set_yticks([i+0.5 for i in range(n)]); ax.set_yticklabels([r["topic"] for r in sel],fontsize=10,weight="bold")
ax.set_xlabel("total mentions (claims rows whose text carries the topic)",fontsize=10)
ax2=ax.twiny(); maxs=max(r["speakers"] for r in sel); ax2.set_xlim(0,maxs*1.02); ax2.set_ylim(n,-1.4)
ax2.grid(axis="x",color="#f0f0f0",lw=0.6,ls=":",zorder=0)
for i,r in enumerate(sel):
    ax2.plot(r["speakers"],i+0.5,"D",ms=7,color="#111",zorder=4)
    ax2.plot(r["firsthand_speakers"],i+0.5,"D",ms=7,mfc="white",mec="#111",mew=1.4,zorder=5)
ax2.set_xlabel("◆ distinct speakers carrying the topic (ranking axis)   ◇ of whom speaking firsthand",fontsize=10)
for a in (ax,ax2):
    for sp_ in a.spines.values(): sp_.set_visible(False)
    a.tick_params(length=0)
ax.grid(axis="x",color="#e6e6e6",lw=0.8,zorder=0); ax.set_axisbelow(True)
ax.set_title(f"Corroboration by voice count: the {n} most widely carried topics of {len(out)} tagged in three or more notes, ranked by distinct speakers",fontsize=14,weight="bold",pad=30)
ax3=fig.add_subplot(gs[1]); nT=n; nS=len(spk); ax3.set_xlim(0,nS); ax3.set_ylim(nT,0)
vmax=max(max((r["by_speaker"].get(s,0) for s in spk),default=1) for r in sel); cmap=plt.get_cmap("Blues")
for i,r in enumerate(sel):
    for j,s in enumerate(spk):
        c=r["by_speaker"].get(s,0)
        if c==0: ax3.add_patch(Rectangle((j,i),1,1,color="#f2f2f2",lw=0)); continue
        ax3.add_patch(Rectangle((j,i),1,1,color=cmap(0.25+0.75*math.log1p(c)/math.log1p(vmax)),lw=0))
        if c>=3: ax3.text(j+0.5,i+0.5,str(c),ha="center",va="center",fontsize=7,color="white" if c>vmax**0.5 else "#222")
for j in range(nS+1): ax3.plot([j,j],[0,nT],color="white",lw=1)
for i in range(nT+1): ax3.plot([0,nS],[i,i],color="white",lw=1)
ax3.set_yticks([i+0.5 for i in range(nT)]); ax3.set_yticklabels([r["topic"] for r in sel],fontsize=9)
ax3.set_xticks([j+0.5 for j in range(nS)]); ax3.set_xticklabels(spk,rotation=45,ha="right",fontsize=9)
ax3.set_title(f"Who carries what: mentions per speaker (the {nS} speakers with most mentions across these topics; blank = none; numbers shown from 3)",fontsize=12.5,weight="bold",pad=8)
for sp_ in ax3.spines.values(): sp_.set_visible(False)
ax3.tick_params(length=0)
dist=Counter(min(r["speakers"],11) for r in out); band=lambda a,b: sum(v for k,v in dist.items() if a<=k<=b)
fig.text(0.5,0.028,f"All {len(out)} topics by distinct speakers: 1 speaker {band(1,1)} · 2 {band(2,2)} · 3 to 5 {band(3,5)} · 6 to 10 {band(6,10)} · 11 or more {band(11,11)}. The full table is research/figures/topic-corroboration.json.",ha="center",fontsize=9,color="#222",weight="bold")
fig.text(0.5,0.002,f"Built from notes.db (tags and claims) on {date.today().strftime('%-d %b %Y')} by tools/draw_topic_corroboration.py. A mention is a claims row naming the topic; a speaker count is voices, not independence: hosts relaying a guest count as voices, so read the hollow diamond (firsthand) as the stricter figure.\n{DC['footer_note']}Meta tags (hosts, channels, house labels) are excluded; topics are tags carried by three or more notes.",ha="center",fontsize=9,color="#444")
fig.savefig("research/figures/topic-corroboration.png",bbox_inches="tight",facecolor="white"); fig.savefig("research/figures/topic-corroboration.svg",bbox_inches="tight",facecolor="white")
print("topics",len(out),"drawn",n,"speakers",nS)
for r in sel[:12]: print(r["speakers"],r["firsthand_speakers"],r["mentions"],r["topic"])
