"""robots.txt for the acquire layer (phase 3 follow-up 2, 2026-10-22; the owner's fetching policy, wip/platform-phase6b/handoffs.md
item 8): the web adapter reads and honours robots.txt for the ledger's own product token and for Claude-User (the agent the ledger
runs as), honours Crawl-delay, and fails a disallowed URL with the deciding robots line recorded.

The matcher follows RFC 9309 (the Robots Exclusion Protocol), not urllib.robotparser, which takes the first matching rule rather
than the longest and cannot say which line decided:
- groups: one or more `User-agent:` lines and the rules after them; the group for an agent is every group whose user-agent value
  equals the agent's product token, case-insensitively; with none, the `*` groups; with neither, everything is allowed;
- rules: `Allow:` and `Disallow:` with `*` (any characters) and a final `$` (end of the path); the longest matching pattern
  decides, an Allow winning a tie; an empty `Disallow:` allows everything; /robots.txt itself is always allowed;
- the path matched is the URL's path and query, percent-encoding left as written;
- `Crawl-delay:` (not in the RFC, widely used): the group's value in seconds;
- fetching (the caller's): a 2xx body is parsed; a 4xx (no robots.txt) allows everything (RFC 9309 2.3.1.3); a 5xx, a network
  failure or a redirect loop is "unreachable" and disallows everything (2.3.1.4).
"""
import re, urllib.parse

CLAUDE_USER = "Claude-User"


class Robots:
    def __init__(self, text="", source="", status="parsed", note=""):
        """status: parsed (the text's rules), allow-all (no robots.txt: a 4xx), disallow-all (unreachable)."""
        self.source = source; self.status = status; self.note = note
        self.groups = []                 # [{agents: [lower-case values], rules: [(allow, pattern, line_no, line)], delay, delay_line}]
        if status == "parsed": self._parse(text)

    def _parse(self, text):
        cur = None; last_was_agent = False
        for n, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line: continue
            key, val = (x.strip() for x in line.split(":", 1)); key = key.lower()
            if key == "user-agent":
                if cur is None or not last_was_agent:
                    cur = dict(agents=[], rules=[], delay=None, delay_line=None, first_line=n); self.groups.append(cur)
                cur["agents"].append(val.lower()); last_was_agent = True
                continue
            last_was_agent = False
            if cur is None: continue                                         # rules before any user-agent line are ignored
            if key in ("allow", "disallow"):
                cur["rules"].append((key == "allow", val, n, raw.strip()))
            elif key == "crawl-delay":
                try: cur["delay"] = float(val); cur["delay_line"] = (n, raw.strip())
                except ValueError: pass

    def groups_for(self, token):
        t = token.lower()
        named = [g for g in self.groups if t in g["agents"]]
        if named: return named, token
        star = [g for g in self.groups if "*" in g["agents"]]
        return star, "*" if star else None

    @staticmethod
    def _pattern_re(p):
        end = p.endswith("$")
        body = re.escape(p[:-1] if end else p).replace(r"\*", ".*")
        return re.compile("^" + body + ("$" if end else ""))

    def check(self, url, token):
        """(allowed, decision) for one agent: decision names the group and the deciding line, or why nothing decided."""
        parts = urllib.parse.urlsplit(url)
        path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        if self.status == "allow-all": return True, f"{self.note or 'no robots.txt'}: everything allowed"
        if self.status == "disallow-all": return False, f"{self.note or 'robots.txt unreachable'}: everything disallowed (RFC 9309 2.3.1.4)"
        if path == "/robots.txt": return True, "/robots.txt is always allowed"
        groups, matched = self.groups_for(token)
        if not groups: return True, f"no group for {token} and no * group: allowed"
        best = None
        for g in groups:
            for allow, pat, n, line in g["rules"]:
                if pat == "":
                    if not allow and best is None: best = (0, True, n, line)        # an empty Disallow allows everything
                    continue
                if self._pattern_re(pat).match(path):
                    cand = (len(pat), allow, n, line)
                    if best is None or cand[0] > best[0] or (cand[0] == best[0] and allow and not best[1]): best = cand
        who = f"group User-agent: {matched}" + ("" if matched == token else f" (no group for {token})")
        if best is None: return True, f"{who}: no rule matches {path}"
        return best[1], f"{who}: line {best[2]} `{best[3]}`"

    def verdict(self, url, tokens):
        """The verdict for every agent token: allowed only if each one is allowed. {allowed, refused_by, decisions{token: text}}."""
        out = dict(allowed=True, refused_by=None, decisions={}, source=self.source)
        for t in tokens:
            ok, why = self.check(url, t)
            out["decisions"][t] = why
            if not ok and out["allowed"]: out.update(allowed=False, refused_by=t)
        return out

    def crawl_delay(self, tokens):
        """(seconds, the line) of the longest Crawl-delay among the agents' groups, or (None, None)."""
        best = (None, None)
        for t in tokens:
            groups, _ = self.groups_for(t)
            for g in groups:
                if g["delay"] is not None and (best[0] is None or g["delay"] > best[0]): best = (g["delay"], f"line {g['delay_line'][0]} `{g['delay_line'][1]}`")
        return best


def summary(v):
    """One line for the hold's metadata or a failed row: the verdict and each agent's deciding line."""
    head = "allowed" if v["allowed"] else f"disallowed for {v['refused_by']}"
    return f"{head} by {v.get('source') or 'robots.txt'}: " + "; ".join(f"{t}: {d}" for t, d in v["decisions"].items())
