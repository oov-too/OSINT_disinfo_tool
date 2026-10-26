"""Pull the final JSON report out of a subagent's task output JSONL: the SubagentHandback tool call's message field."""
import json, sys
src, out = sys.argv[1], sys.argv[2]
best=None
for line in open(src):
    try: o=json.loads(line)
    except: continue
    m=o.get("message",{})
    if not isinstance(m,dict) or m.get("role")!="assistant": continue
    for c in (m.get("content") or []):
        if not (isinstance(c,dict) and c.get("type")=="tool_use" and c.get("name")=="SubagentHandback"): continue
        t=c["input"].get("message") or c["input"].get("report") or json.dumps(c["input"])
        i=t.find("{"); j=t.rfind("}")
        try: best=json.loads(t[i:j+1])
        except Exception as e: print("parse error", e)
if best is None: sys.exit("not found in "+src)
json.dump(best,open(out,"w"),indent=1,ensure_ascii=False); print("saved",out,list(best.keys())[:5])
