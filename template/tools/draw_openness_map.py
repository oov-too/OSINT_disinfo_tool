#!/usr/bin/env python3
"""Openness map: the house chart type for the candour-audit dataset (the notes' forthrightness audits; renamed 2026-10-22, the
figure text keeps the legacy term until the owner-approved corpus pass).

Reads research/figures/openness-dataset.json, refreshes its topic_summary counts, and writes
research/figures/openness-map.png and .svg. Run from anywhere: python3 tools/draw_openness_map.py [--dataset-only]
(--dataset-only refreshes the dataset's counts and topic summary and stops, drawing nothing: the step `ledger present` runs.)

Chart contract (keep this when editing):
  Top panel: the pack's topics (the residual "other" is excluded) as 100%-share stacked bars, most open at the top,
  ordered by the closure index (open 0, partial 0.33, contested 0.5, closed-subtle 0.8, closed-outright 1.0,
  averaged over the sources touching the topic). The index is drawn as a black diamond on each bar, and a zone band
  above the bars names its range (OPEN / MOSTLY OPEN / CONTESTED / MOSTLY CLOSED / CLOSED). Each bar is annotated at
  the right with source counts (human / channelled) and stated declines.
  Colours: open green #2e8b57, partial yellow #e0b400, contested purple #7b5ea7 hatched, closed-subtle orange #e07a1f,
  closed-outright red #b8232f, untouched light #f2f2f2.
  Bottom panel: source-by-topic heatmap of the dominant class, same column order, human witnesses above a black
  divider and channelled voices below it; a red stated-declines bar per source at the right, with pseudo-declines
  appended in hatched purple.
  Footer: provenance and the two reading rules.
Adding a source: append it to "sources" and its cells to "cells" in the dataset, then run this script.
A cell's basis names the stated basis of a decline (classification, promise, NDA, pending investigation, not tasked);
"n/a" and "none stated" do not count as stated declines.
"""
import os, sys
from datetime import date
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
os.chdir(ROOT); sys.path.insert(0, "tools")
from ledger import notes as LN    # the parser library: LF writes (tools/ledger/notes.py, phase 2)
import packload   # the pack's topic labels and audit captions (packs/ufo/pack.toml [audit]; moved 2026-10-22)
CAP = packload.audit_captions()
STRIP = packload.display("openness")["label_strip"]   # text removed from a source's row label (pack.toml [display.openness]; phase 5)
def _strip(t):
    for x in STRIP: t=t.replace(x,"")
    return t
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from collections import Counter
DS="research/figures/openness-dataset.json"
# a new project has no dataset yet: it begins empty, one topic row per pack topic, and is written below (phase 7b)
d=json.load(open(DS)) if os.path.exists(DS) else {"sources": [], "cells": [], "topic_summary": [{"topic": t} for t, _ in packload.topics()], "notes": "the forthrightness audits' openness dataset: tools/integrate_report.py adds one source per audited intake; tools/draw_openness_map.py refreshes the counts"}
# Sync each source's counts to its note's "Audit counts:" line (via notes.db) unless the source is a per-speaker
# or per-witness subset of a note (counts_manual: true), so the map never drifts from the notes.
try:
    import sqlite3
    _db=sqlite3.connect("notes.db"); _rows={r[0]:r[1:] for r in _db.execute("select video, open, partial, closed_outright, closed_subtle, stated_declines, pseudo_declines from audit_counts")}
    for _s in d["sources"]:
        _vid=(_s.get("note") or "").replace("videos/","").replace(".md","")
        if _vid in _rows and not _s.get("counts_manual"):
            _s["counts"]=dict(zip(("open","partial","closed_outright","closed_subtle","stated_declines","pseudo_declines"),[int(x or 0) for x in _rows[_vid]]))
except Exception as _e: print("counts sync skipped:", _e)
NO_BASIS={None,"","n/a","none stated"}
for t in d["topic_summary"]:
    cs=[c for c in d["cells"] if c["topic"]==t["topic"]]; cnt=Counter(c["class"] for c in cs)
    sc=sum({"open":0,"partial":0.33,"contested":0.5,"closed-subtle":0.8,"closed-outright":1.0}[c["class"]] for c in cs)/max(len(cs),1)
    t.update(open=cnt.get("open",0),partial=cnt.get("partial",0),closed_outright=cnt.get("closed-outright",0),closed_subtle=cnt.get("closed-subtle",0),
             contested=cnt.get("contested",0),declines=sum(1 for c in cs if c.get("basis") not in NO_BASIS),cells=len(cs),
             zone="open" if sc<0.15 else "mostly-open" if sc<0.32 else "contested" if sc<0.55 else "mostly-closed" if sc<0.75 else "closed")
LN.write_text(DS,json.dumps(d,indent=1,ensure_ascii=False))
if "--dataset-only" in sys.argv: print("refreshed",DS,len(d["sources"]),"sources",len(d["cells"]),"cells (dataset only; the map not drawn)"); sys.exit(0)   # the dataset step of `ledger present`
if not d["cells"]: print("no audit cells in",DS,"yet: nothing to draw (the map follows the first audited intake)"); sys.exit(0)
TOPICS=[t for t in d["topic_summary"] if t["topic"]!="other"]
LABEL=packload.topic_labels()
W={"open":0,"partial":0.33,"contested":0.5,"closed-subtle":0.8,"closed-outright":1.0}
COL={"open":"#2e8b57","partial":"#e0b400","contested":"#7b5ea7","closed-subtle":"#e07a1f","closed-outright":"#b8232f"}
cells=[c for c in d["cells"] if c["topic"]!="other"]
comp={}; score={}
for t in TOPICS:
    cs=[c for c in cells if c["topic"]==t["topic"]]
    comp[t["topic"]]=Counter(c["class"] for c in cs); score[t["topic"]]=sum(W[c["class"]] for c in cs)/len(cs)
order=sorted(TOPICS,key=lambda t:score[t["topic"]])
humans=[s for s in d["sources"] if s["kind"]=="human"]; chan=[s for s in d["sources"] if s["kind"]!="human"]
def _label(s):
    """A source's row label. A note audited per speaker carries a dict label {speaker: label} (written so by integrate_report from a
    multi-speaker report); its row shows the speakers' names and their shared tail (fix 2026-10-22: the dict crashed set_yticklabels)."""
    lab=s["label"]
    if isinstance(lab,str): return lab
    vals=[str(v) for v in (lab.values() if isinstance(lab,dict) else lab)]
    if not vals: return s["id"]
    tails={v.split(",",1)[1].strip() if "," in v else "" for v in vals}
    if len(tails)==1 and next(iter(tails)): return " / ".join(v.split(",",1)[0] for v in vals)+", "+next(iter(tails))
    return vals[0]+(f" (+{len(vals)-1} more)" if len(vals)>1 else "")
sources=humans+chan; cell={(c["source"],c["topic"]):c for c in cells}; hum_ids={s["id"] for s in humans}
nS=len(sources); ncell=len(cells)
fig=plt.figure(figsize=(22,12.5+0.36*nS),dpi=150); gs=fig.add_gridspec(2,1,height_ratios=[7.5,0.36*nS+2],hspace=0.16)
ax=fig.add_subplot(gs[0]); n=len(order); ax.set_xlim(0,1.0); ax.set_ylim(n,-1.2)
for i,t in enumerate(order):
    k=t["topic"]; c=comp[k]; tot=sum(c.values()); x=0
    for cls in ("open","partial","contested","closed-subtle","closed-outright"):
        v=c.get(cls,0)
        if v: ax.add_patch(Rectangle((x,i+0.12),v/tot,0.76,color=COL[cls],hatch="//" if cls=="contested" else None,ec="white",lw=0)); x+=v/tot
    ax.plot(score[k],i+0.5,"D",ms=7,color="#111",zorder=4)
    hum=sum(1 for c2 in cells if c2["topic"]==k and c2["source"] in hum_ids)
    decl=t["declines"]
    ax.text(1.005,i+0.5,f"{tot} sources ({hum} human, {tot-hum} channelled) · {decl} stated declines",va="center",ha="left",fontsize=8.5,color="#333",clip_on=False)
ax.set_yticks([i+0.5 for i in range(n)]); ax.set_yticklabels([LABEL[t["topic"]] for t in order],fontsize=11,weight="bold")
ax.set_xticks([0,0.25,0.5,0.75,1.0]); ax.set_xticklabels(["0%","25%","50%","75%","100%"],fontsize=9)
ax.set_xlabel("share of the sources that touch the topic, by the class their audit recorded  ·  ◆ = closure index (open 0 · partial 0.33 · contested 0.5 · closed-subtle 0.8 · closed-outright 1.0)",fontsize=10)
for x0,x1,lab,col in [(0,0.15,"OPEN","#cfe9d6"),(0.15,0.32,"MOSTLY OPEN","#e4edc9"),(0.32,0.55,"CONTESTED","#f3e4bd"),(0.55,0.75,"MOSTLY CLOSED","#f3d2b8"),(0.75,1.0,"CLOSED","#ebc0c0")]:
    ax.add_patch(Rectangle((x0,-1.1),x1-x0,0.85,color=col,lw=0,clip_on=False)); ax.text((x0+x1)/2,-0.68,lab,ha="center",va="center",fontsize=10,weight="bold",color="#333")
ax.text(0.5,-1.25,"zone of the closure index →",ha="center",va="bottom",fontsize=8.5,color="#555",style="italic")
ax.grid(axis="x",color="#ddd",lw=0.8,zorder=0); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0)
ax.set_title(f"Where the boundary sits: {n} topics ranked from most open to most closed across {nS} audited sources ({ncell} cells)",fontsize=14,weight="bold",pad=34)
leg=[Patch(color=COL["open"],label="open: answered as asked"),Patch(color=COL["partial"],label="partial: in part, or with a stated limit"),Patch(color=COL["contested"],hatch="//",label="contested: open and closed items on the same topic"),Patch(color=COL["closed-subtle"],label="closed-subtle: slid away, redirected, dropped"),Patch(color=COL["closed-outright"],label="closed-outright: refused on a stated basis"),Patch(color="#f2f2f2",label="not touched by the audit (heatmap only)")]
ax.legend(handles=leg,loc="upper left",bbox_to_anchor=(0,-0.09),ncol=3,fontsize=9,frameon=False)
ax2=fig.add_subplot(gs[1]); T=[t["topic"] for t in order]; nT=len(T); ax2.set_xlim(0,nT+3.6); ax2.set_ylim(nS,-0.9)
for j,s in enumerate(sources):
    for i,t in enumerate(T):
        c=cell.get((s["id"],t))
        if c is None: ax2.add_patch(Rectangle((i,j),1,1,color="#f2f2f2",lw=0)); continue
        k=c["class"]; ax2.add_patch(Rectangle((i,j),1,1,color=COL.get(k,"#999"),lw=0,hatch="//" if k=="contested" else None,ec="white"))
    dec=s["counts"]["stated_declines"] or 0; ps=s["counts"]["pseudo_declines"] or 0
    ax2.add_patch(Rectangle((nT+0.3,j+0.2),dec/24*2.6,0.6,color="#b8232f"))
    if ps: ax2.add_patch(Rectangle((nT+0.3+dec/24*2.6,j+0.2),ps/24*2.6,0.6,color="#7b5ea7",hatch="//",ec="white"))
    ax2.text(nT+0.3+dec/24*2.6+ps/24*2.6+0.05,j+0.5,f"{dec}"+(f" (+{ps} pseudo)" if ps else ""),va="center",fontsize=8,color="#333")
for i in range(nT+1): ax2.plot([i,i],[0,nS],color="white",lw=1.2)
for j in range(nS+1): ax2.plot([0,nT],[j,j],color="white",lw=1.2)
ax2.plot([0,nT+3.5],[len(humans),len(humans)],color="#222",lw=2)
ax2.text(0.15,len(humans)-0.12,f"{CAP['human']} ↑",ha="left",va="bottom",fontsize=9,color="white",style="italic",weight="bold",bbox=dict(boxstyle="round,pad=0.2",fc="#222",ec="none"))
ax2.text(0.15,len(humans)+0.12,f"{CAP['channelled']} ↓",ha="left",va="top",fontsize=9,color="white",style="italic",weight="bold",bbox=dict(boxstyle="round,pad=0.2",fc="#222",ec="none"))
ax2.set_yticks([j+0.5 for j in range(nS)]); ax2.set_yticklabels([_strip(_label(s)) for s in sources],fontsize=9)
ax2.set_xticks([i+0.5 for i in range(nT)]); ax2.set_xticklabels([LABEL[t] for t in T],rotation=40,ha="right",fontsize=9)
ax2.text(nT+1.6,-0.45,"stated declines\n(refusals with a basis)",ha="center",va="center",fontsize=8.5,weight="bold")
ax2.set_title("Source by topic: the dominant response class each audit recorded (columns in the same order as above; blank = the audit did not touch the topic)",fontsize=12.5,weight="bold",pad=8)
for sp in ax2.spines.values(): sp.set_visible(False)
ax2.tick_params(length=0)
fig.text(0.5,0.002,f"Built from the forthrightness audits in the {packload.ledger()['ledger'].get('name', 'ledger')} database (research/figures/openness-dataset.json), {date.today().day} {date.today().strftime('%b %Y')}. Classes are each note's own; nothing reclassified. {CAP['footer']}\nReading rule: a closed cell is a boundary the witness marked, not a finding that the topic is secret; a channelled row with no closures is an unfalsifiable source, not an open one.",ha="center",fontsize=9,color="#444")
fig.savefig("research/figures/openness-map.png",bbox_inches="tight",facecolor="white"); fig.savefig("research/figures/openness-map.svg",bbox_inches="tight",facecolor="white"); print("redrawn",nS,ncell)
