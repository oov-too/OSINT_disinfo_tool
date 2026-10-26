#!/usr/bin/env python3
"""Per-interview candour chart (the forthrightness chart; renamed 2026-10-22, the filenames and the figure text keep the legacy
term until the owner-approved corpus pass), in the openness map's house style (same classes, colours, closure index and zones).

Usage: python3 tools/draw_forthrightness_chart.py <note slug>                 -> research/figures/<prefix>-<slug>.png, .svg, .json
       python3 tools/draw_forthrightness_chart.py --group "<Label>" <slug> ... -> <prefix>-person-<label>.png (recordings pooled; one strip per recording)
       python3 tools/draw_forthrightness_chart.py --overview                   -> <prefix>-by-interviewee.png from research/figures/<prefix>-groups.json,
                                                                                   then rewrites research/<prefix>-charts.md
       python3 tools/draw_forthrightness_chart.py --all                        -> every audited recording's chart, the groups file from the pack's
                                                                                   ledgered speakers, their pooled charts, then --overview (the
                                                                                   present step; pilot defect 8, 7b2 2026-10-23); skipped when the
                                                                                   pack's [display.candour] auto_charts is false
<prefix>, the chart titles' term and the audited set's name are the pack's display settings (pack.toml [display.candour]: file_prefix,
term, set_name; core defaults candour, Candour, the audited set); the topic labels are the pack's [audit.topics].
Reads notes.db: audit_rows (the note's candour audit) and claims (to give each audit row a topic: the claims rows whose
Note cell says "Audit N" give row N their topic; failing that, the claims rows that share the audit row's start time; failing that,
claims rows the audit row's text cites as "row N"; else "other").
Panel A: the whole interview as one 100%-share bar of the audit's Move classes, with the closure index diamond and zone band.
Panel B: the 18 topics touched, 100%-share bars, most open at top, diamond = closure index, counts at right.
Panel C: the interview in time: one tick per audit row at its timestamp, coloured by Move; stated declines (a basis other than
n/a or none stated) marked with a black bar below the strip.
Does not touch research/figures/openness-map.* (the whole-database map is drawn only by tools/draw_openness_map.py).
"""
import os, re, sys, json, sqlite3
from datetime import date
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0,"tools")
import packload   # topic labels (pack.toml [audit.topics]) and the chart wording and file prefix (pack.toml [display.candour]; phase 5, 2026-10-22)
C=packload.display("candour"); PX=C["file_prefix"]; TERM=C["term"]; TERML=C["term_lower"]
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from collections import Counter, defaultdict
con=sqlite3.connect("notes.db")
args=[a for a in sys.argv[1:] if not a.startswith("--")]
MODE="group" if "--group" in sys.argv else "overview" if "--overview" in sys.argv else "all" if "--all" in sys.argv else "single"
GROUPS_FILE=f"research/figures/{PX}-groups.json"
LABEL=packload.topic_labels()
W={"open":0,"partial":0.33,"contested":0.5,"closed-subtle":0.8,"closed-outright":1.0}
COL={"open":"#2e8b57","partial":"#e0b400","contested":"#7b5ea7","closed-subtle":"#e07a1f","closed-outright":"#b8232f"}
NO_BASIS={None,"","n/a","none stated"}
def norm_move(m):
    m=(m or "").strip().lower().split(" then ")[0].split(";")[0].strip()
    m={"closed outright":"closed-outright","closed subtle":"closed-subtle","yes":"open","no":"closed-outright"}.get(m,m)
    return m if m in W else None
def secs(t):
    m=re.search(r"(\d+):(\d\d):(\d\d)",t or "") or re.search(r"(\d+):(\d\d)",t or "")
    if not m: return None
    g=[int(x) for x in m.groups()]
    return g[0]*3600+g[1]*60+g[2] if len(g)==3 else g[0]*60+g[1]
def load(slug):
    """Scored audit rows of one note, each with a topic."""
    topic_of={int(n):t for n,t in con.execute("select n, topic from claims where video=?",(slug,)) if str(n).isdigit()}
    audit_topics=defaultdict(Counter)   # the claims ledger points at the audit ("Audit 116" in a Note cell)
    for n,t,note in con.execute("select n, topic, note from claims where video=?",(slug,)):
        for a in re.findall(r"[Aa]udit\s+(\d+)",note or ""): audit_topics[int(a)][t]+=1
    time_topics=defaultdict(Counter)
    for t,tp in con.execute("select time, topic from claims where video=?",(slug,)):
        m=re.match(r"\s*(\d+:\d\d:\d\d|\d+:\d\d)",t or "")
        if m and tp!="other": time_topics[m.group(1)][tp]+=1
    def topics_for(text,n=None,time=None):
        if n is not None and str(n).isdigit() and audit_topics.get(int(n)):
            return audit_topics[int(n)].most_common(1)[0][0]
        m=re.match(r"\s*(\d+:\d\d:\d\d|\d+:\d\d)",time or "")
        if m and time_topics.get(m.group(1)):
            return time_topics[m.group(1)].most_common(1)[0][0]
        ns=set()
        for a,b in re.findall(r"rows?\s+(\d+)(?:\s*(?:to|-|–)\s*(\d+))?",text or ""):
            a=int(a); b=int(b) if b else a
            if b-a<=12: ns.update(range(a,b+1))
        ts=[topic_of[n] for n in ns if n in topic_of]
        return Counter(ts).most_common(1)[0][0] if ts else "other"
    rows=con.execute("select n, time, asked_by, question, answer, move, basis from audit_rows where video=? order by cast(n as integer)",(slug,)).fetchall()
    out=[]
    for n,t,ab,q,a,mv,basis in rows:
        m=norm_move(mv)
        if m is None: continue
        out.append(dict(video=slug,n=n,secs=secs(t),time=t,move=m,basis=(basis or "").strip().lower(),topic=topics_for((a or "")+" "+(q or ""),n,t)))
    return out,len(rows)
def stats(sc):
    tot=Counter(r["move"] for r in sc); N=len(sc)
    return tot,N,(sum(W[r["move"]] for r in sc)/N if N else 0),sum(1 for r in sc if r["basis"] not in NO_BASIS)
if MODE=="all":
    import subprocess
    if not C.get("auto_charts", True): print(f"candour charts: the pack keeps its charts by hand ([display.candour] auto_charts = false); nothing drawn"); sys.exit(0)
    audited=set(packload.audited_subjects())
    def asked(sl):   # an interview or hearing: most audit rows name the asker (a monologue's rows mostly do not)
        rs=con.execute("select asked_by from audit_rows where video=?",(sl,)).fetchall()
        return rs and sum(1 for (a,) in rs if (a or "").strip().lower() not in ("","n/a","none","-","reader")) * 2 >= len(rs)
    cands=[v for (v,) in con.execute("select id from videos where file like 'videos/%' order by id")]
    subj={}
    for v,s in con.execute("select video, subject from video_subjects"): subj.setdefault(v,set()).add(s)
    drawn=[]; failed=0
    for sl in cands:
        if audited and not (subj.get(sl,set()) & audited): continue
        if not asked(sl) or not load(sl)[0]: continue
        r=subprocess.run([sys.executable,os.path.abspath(__file__),sl],capture_output=True,text=True)
        print(("drawn " if r.returncode==0 else "FAILED ")+sl); drawn+= [sl] if r.returncode==0 else []; failed+= r.returncode!=0
    guest={v:(g or "") for v,g in con.execute("select id, guest from videos")}
    groups=[]
    for sp in packload.pack().get("speakers",{}).get("ledgered",[]):
        nm=sp.get("name","").strip(); sls=[sl for sl in drawn if nm and nm.lower() in guest.get(sl,"").lower()]
        if sls: groups.append({"label":nm,"slugs":sls})
    os.makedirs(os.path.dirname(GROUPS_FILE),exist_ok=True)
    LN_=__import__("ledger.notes",fromlist=["write_text"]); LN_.write_text(GROUPS_FILE,json.dumps(groups,indent=1)+"\n")
    print(f"groups: {len(groups)} from the pack's ledgered speakers -> {GROUPS_FILE}")
    for g in groups:
        if len(g["slugs"])>1: subprocess.run([sys.executable,os.path.abspath(__file__),"--group",g["label"]]+g["slugs"],capture_output=True,text=True)
    r=subprocess.run([sys.executable,os.path.abspath(__file__),"--overview"],capture_output=True,text=True)
    print((r.stdout.strip().splitlines() or [""])[0] if r.returncode==0 else "overview FAILED: "+(r.stderr.strip()[-300:]))
    print(f"candour charts: {len(drawn)} recordings drawn, {len(groups)} groups")
    sys.exit(0 if r.returncode==0 and not failed else 1)
if MODE=="overview":
    groups=json.load(open(GROUPS_FILE)); res=[]
    for g in groups:
        sc=[]; nrows=0
        for sl in g["slugs"]:
            a,b=load(sl); sc+=a; nrows+=b
        tot,N,idx,decl=stats(sc)
        if N: res.append(dict(label=g["label"],slugs=g["slugs"],counts=dict(tot),scored=N,rows=nrows,index=round(idx,3),declines=decl))
    res.sort(key=lambda r:r["index"]); n=len(res)
    fig=plt.figure(figsize=(20,0.42*n+4),dpi=150); ax=fig.add_subplot(111); ax.set_xlim(0,1); ax.set_ylim(n,-1.4)
    for i,r in enumerate(res):
        c=Counter(r["counts"]); t=sum(c.values()); x=0
        for cls in ("open","partial","contested","closed-subtle","closed-outright"):
            v=c.get(cls,0)
            if v: ax.add_patch(Rectangle((x,i+0.12),v/t,0.76,color=COL[cls],hatch="//" if cls=="contested" else None,ec="white",lw=0)); x+=v/t
        ax.plot(r["index"],i+0.5,"D",ms=8,color="#111",zorder=4)
        ax.text(1.005,i+0.5,f'{r["scored"]} turns in {len(r["slugs"])} recording{"s" if len(r["slugs"])>1 else ""} · open {c.get("open",0)} · partial {c.get("partial",0)} · closed-subtle {c.get("closed-subtle",0)} · closed-outright {c.get("closed-outright",0)} · {r["declines"]} stated declines · index {r["index"]:.2f}',va="center",ha="left",fontsize=8.5,color="#333",clip_on=False)
    for x0,x1,lab,col in [(0,0.15,"OPEN","#cfe9d6"),(0.15,0.32,"MOSTLY OPEN","#e4edc9"),(0.32,0.55,"CONTESTED","#f3e4bd"),(0.55,0.75,"MOSTLY CLOSED","#f3d2b8"),(0.75,1.0,"CLOSED","#ebc0c0")]:
        ax.add_patch(Rectangle((x0,-1.2),x1-x0,0.85,color=col,lw=0,clip_on=False)); ax.text((x0+x1)/2,-0.78,lab,ha="center",va="center",fontsize=9.5,weight="bold",color="#333")
    ax.set_yticks([i+0.5 for i in range(n)]); ax.set_yticklabels([r["label"] for r in res],fontsize=10,weight="bold")
    ax.set_xticks([0,0.25,0.5,0.75,1]); ax.set_xticklabels(["0%","25%","50%","75%","100%"],fontsize=9)
    ax.set_xlabel("share of the audited turns, by Move  ·  ◆ = closure index (open 0 · partial 0.33 · contested 0.5 · closed-subtle 0.8 · closed-outright 1.0)",fontsize=10)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(length=0); ax.grid(axis="x",color="#ddd",lw=0.8,zorder=0); ax.set_axisbelow(True)
    ax.set_title(f"{TERM} by interviewee: {n} audited voices in {C['set_name']}, most open at the top (all their audited recordings pooled)",fontsize=14,weight="bold",pad=36)
    leg=[Patch(color=COL["open"],label="open"),Patch(color=COL["partial"],label="partial"),Patch(color=COL["closed-subtle"],label="closed-subtle"),Patch(color=COL["closed-outright"],label="closed-outright")]
    ax.legend(handles=leg,loc="upper left",bbox_to_anchor=(0,-0.03-1.0/(n+1.4)),ncol=4,fontsize=9,frameon=False)
    fig.text(0.5,0.002,f"Built from the notes' {TERML} audits in notes.db on {date.today().strftime('%-d %b %Y')} by tools/draw_forthrightness_chart.py --overview. Classes are each note's own. The counting scale differs between notes (some audits score questions, some score turns), so read the index as a within-source shape, not a cross-source ratio. A closed turn is a boundary the speaker marked, not a finding that the topic is secret.",ha="center",fontsize=8.5,color="#444")
    fig.savefig(f"research/figures/{PX}-by-interviewee.png",bbox_inches="tight",facecolor="white"); fig.savefig(f"research/figures/{PX}-by-interviewee.svg",bbox_inches="tight",facecolor="white")
    json.dump(res,open(f"research/figures/{PX}-by-interviewee.json","w"),indent=1)
    print("overview",n)
    import subprocess; subprocess.run([sys.executable,os.path.join(ROOT,"tools","build_forthrightness_page.py")])
    sys.exit()
if MODE=="group":
    label=args[0]; slugs=args[1:]; slug="person-"+re.sub(r"[^a-z0-9]+","-",label.lower()).strip("-")
else:
    slugs=[args[0].replace("videos/","").replace(".md","")]; slug=slugs[0]; label=slug
scored=[]; nrows=0
for sl in slugs:
    a,b=load(sl); scored+=a; nrows+=b
if not scored: sys.exit("no scored audit rows for "+label)
rows=[None]*nrows
tot=Counter(r["move"] for r in scored); N=len(scored); idx=sum(W[r["move"]] for r in scored)/N
decl=sum(1 for r in scored if r["basis"] not in NO_BASIS)
bytopic=defaultdict(Counter)
for r in scored: bytopic[r["topic"]][r["move"]]+=1
topics=sorted([t for t in bytopic if t!="other"],key=lambda t:sum(W[m]*c for m,c in bytopic[t].items())/sum(bytopic[t].values()))
if "other" in bytopic: topics.append("other")
nT=len(topics); dur=max((r["secs"] or 0) for r in scored)
nrec=len(slugs)
fig=plt.figure(figsize=(20,4.2+0.5*nT+2.2*nrec+1.6),dpi=150); gs=fig.add_gridspec(2+nrec,1,height_ratios=[1.6,0.5*nT+1.2]+[2.2]*nrec,hspace=0.55)
def zone(ax,y0=-1.05,h=0.8):
    for x0,x1,lab,col in [(0,0.15,"OPEN","#cfe9d6"),(0.15,0.32,"MOSTLY OPEN","#e4edc9"),(0.32,0.55,"CONTESTED","#f3e4bd"),(0.55,0.75,"MOSTLY CLOSED","#f3d2b8"),(0.75,1.0,"CLOSED","#ebc0c0")]:
        ax.add_patch(Rectangle((x0,y0),x1-x0,h,color=col,lw=0,clip_on=False)); ax.text((x0+x1)/2,y0+h/2,lab,ha="center",va="center",fontsize=9,weight="bold",color="#333")
def bar(ax,i,cnt):
    t=sum(cnt.values()); x=0
    for cls in ("open","partial","contested","closed-subtle","closed-outright"):
        v=cnt.get(cls,0)
        if v: ax.add_patch(Rectangle((x,i+0.12),v/t,0.76,color=COL[cls],hatch="//" if cls=="contested" else None,ec="white",lw=0)); x+=v/t
    ax.plot(sum(W[m]*c for m,c in cnt.items())/t,i+0.5,"D",ms=8,color="#111",zorder=4)
def strip(ax):
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(length=0); ax.grid(axis="x",color="#ddd",lw=0.8,zorder=0); ax.set_axisbelow(True)
axA=fig.add_subplot(gs[0]); axA.set_xlim(0,1); axA.set_ylim(1,-1.2); bar(axA,0,tot); zone(axA)
axA.set_yticks([0.5]); axA.set_yticklabels(["whole interview"],fontsize=11,weight="bold"); axA.set_xticks([0,0.25,0.5,0.75,1]); axA.set_xticklabels(["0%","25%","50%","75%","100%"],fontsize=9); strip(axA)
axA.text(1.005,0.5,f"{N} scored turns · open {tot.get('open',0)} · partial {tot.get('partial',0)} · closed-subtle {tot.get('closed-subtle',0)} · closed-outright {tot.get('closed-outright',0)} · {decl} stated declines · closure index {idx:.2f}",va="center",ha="left",fontsize=9,color="#333",clip_on=False)
axA.set_title(f"{TERM} audit: {label}"+(f" ({nrec} recordings pooled)" if nrec>1 else ""),fontsize=14,weight="bold",pad=30)
axB=fig.add_subplot(gs[1]); axB.set_xlim(0,1); axB.set_ylim(nT,-1.2)
for i,t in enumerate(topics):
    bar(axB,i,bytopic[t]); c=bytopic[t]; s=sum(c.values())
    axB.text(1.005,i+0.5,f"{s} turns · open {c.get('open',0)} · partial {c.get('partial',0)} · closed {c.get('closed-subtle',0)+c.get('closed-outright',0)}",va="center",ha="left",fontsize=8.5,color="#333",clip_on=False)
zone(axB); axB.set_yticks([i+0.5 for i in range(nT)]); axB.set_yticklabels([LABEL.get(t,t) for t in topics],fontsize=10,weight="bold"); axB.set_xticks([0,0.25,0.5,0.75,1]); axB.set_xticklabels(["0%","25%","50%","75%","100%"],fontsize=9); strip(axB)
axB.set_xlabel("share of the audit's turns on the topic, by Move  ·  ◆ = closure index (open 0 · partial 0.33 · closed-subtle 0.8 · closed-outright 1.0)",fontsize=9.5)
axB.set_title("By topic (each audit row takes the topic of the claims rows that cite it, or that share its timestamp), most open at the top",fontsize=12,weight="bold",pad=28)
leg=[Patch(color=COL["open"],label="open: answered as asked"),Patch(color=COL["partial"],label="partial: in part, or with a stated limit"),Patch(color=COL["closed-subtle"],label="closed-subtle: slid away, redirected, dropped"),Patch(color=COL["closed-outright"],label="closed-outright: refused on a stated basis")]
axB.legend(handles=leg,loc="upper left",bbox_to_anchor=(0,-0.02-0.9/(nT+1.2)),ncol=4,fontsize=9,frameon=False)
for k,sl in enumerate(slugs):
    rs=[r for r in scored if r["video"]==sl]; d_=max((r["secs"] or 0) for r in rs) if rs else 60
    axC=fig.add_subplot(gs[2+k]); axC.set_xlim(0,d_/60+2); axC.set_ylim(-1.6,1.2)
    tw=max(0.05,(d_/60)/600)   # tick width scales with the recording's length
    for r in rs:
        if r["secs"] is None: continue
        x=r["secs"]/60; axC.add_patch(Rectangle((x-tw,0),2*tw,1,color=COL[r["move"]],lw=0))
        if r["basis"] not in NO_BASIS: axC.add_patch(Rectangle((x-1.4*tw,-0.55),2.8*tw,0.35,color="#111",lw=0))
    t_,N_,i_,d2=stats(rs)
    axC.set_yticks([0.5,-0.375]); axC.set_yticklabels(["Move","stated decline"],fontsize=9); axC.set_xlabel("minutes into the recording",fontsize=9.5)
    for sp in axC.spines.values(): sp.set_visible(False)
    axC.tick_params(length=0); axC.set_title(("Turn by turn through the recording: where the closures fall" if nrec==1 else f"{sl}")+f"  ·  {N_} turns, index {i_:.2f}, {d2} stated declines",fontsize=11 if nrec>1 else 12,weight="bold",pad=6)
fig.text(0.5,0.002,f"Built from the note{'s' if nrec>1 else ''}' {TERML} audit ({N} scored turns of {nrows} rows; n/a rows not scored) in notes.db on {date.today().strftime('%-d %b %Y')} by tools/draw_forthrightness_chart.py. Classes are the note's own; nothing reclassified. Same colours, closure index and zones as the openness map. A closed turn is a boundary the speaker marked, not a finding that the topic is secret.",ha="center",fontsize=8.5,color="#444")
out=f"research/figures/{PX}-{slug}"
fig.savefig(out+".png",bbox_inches="tight",facecolor="white"); fig.savefig(out+".svg",bbox_inches="tight",facecolor="white")
json.dump({"slug":slug,"label":label,"recordings":slugs,"scored":N,"counts":dict(tot),"stated_declines":decl,"closure_index":round(idx,3),"by_topic":{t:dict(c) for t,c in bytopic.items()}},open(out+".json","w"),indent=1)
print(out+".png", N, dict(tot), "declines", decl, "index", round(idx,3)); print({t:sum(c.values()) for t,c in bytopic.items()})
