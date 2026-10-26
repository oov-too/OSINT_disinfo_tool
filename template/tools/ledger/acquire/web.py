"""The web adapter (phase 3 of tools/platform-plan.md, 2026-10-22; follow-up 2 from the pilot's first live use,
wip/platform-phase6b/adapter-findings.md): a page, an RSS or Atom feed, or a forum thread of several pages, held byte-for-byte in
<hold root>/web/[<set>/]<date or undated>-<slug>/ with a derived text and the README.

The fetching policy (the owner's, fixed 2026-10-22, handoff 8): every request names the ledger honestly in its user agent
(`LedgerAcquire/<version>` with the project and the operator's contact from ledger.toml [acquire] contact; there is no browser
agent and no per-host override); robots.txt is read per host (robots.py, RFC 9309) and honoured for the ledger's own token and for
Claude-User; a Crawl-delay raises the host's gate; a disallowed URL (or a redirect to one) fails the hold, the failed manifest row
and <state dir>/robots-refusals.jsonl naming the deciding robots line; every hold records the robots verdict in its metadata.

- page(url): the response bytes as `page.<ext>` (held); `text.md` (derived): the page's main content (itemprop=articleBody, else the
  largest <article>, else <main>) rendered to markdown-like text by tools/reddit_rss_patch.py's renderer, with the whole page's
  rendering beside it as `page-full.md` when the two differ; the metadata says which (`text_extent`). A text/plain page that is not
  UTF-8 with LF gains `text.txt` (declared charset, else UTF-8, else cp1252).
- the date: the page's own markup only (meta tags, JSON-LD datePublished or dateCreated, a visible 'Published' dateline, per-site
  rules such as Hacker News's span.age, a <time> element), with `date_basis` naming which; when none is found the date stays empty,
  the basis says so and the hold is named `undated-<slug>`: the fetch date is never the item's date. A caller may give `date` and
  `date_basis` for a page that carries none (e.g. the date on an index page).
- feed(url): `feed.xml` (held); `entries.md` and `entries.json` (derived).
- thread(url, ...) = hold(thread_capture(url, ...)): pages in order (a `{page}` template or rel="next"), each held as page-NNN.<ext>,
  `text.md` in the house per-page form; a Hacker News page renders one header per comment, `[id] author, time, depth n, reply to
  [parent]`, so the reply chain survives (other forums: the generic rendering).
- hold_bytes(url, data, tool): bytes another route captured (the browser pane), held with that route named.
- every capture takes `metadata` (e.g. the pilot's class and circle), and page and thread a `folder`.
- completion (tools/reddit_rss_patch.py's rule, generalised): `compare(held, fresh)`, `is_truncated`, `recapture(folder)`.
- retries: none for a TLS failure (it cannot change); a 429 or 503 waits its Retry-After (at most 300 s) once, and not at all when the
  body is a protection page (a challenge is not a server fault); other 5xx twice (20 s, 40 s); the reason is in the failed row.

file:// URLs work (robots.txt is then the file of that name in the same folder), so tests run with no network call.

    python3 tools/ledger/acquire/web.py page <url> [--set NAME] [--gap 6] [--date YYYY-MM-DD --date-basis TEXT] [--root DIR]
    python3 tools/ledger/acquire/web.py feed <url> [--set NAME]
    python3 tools/ledger/acquire/web.py thread <url-or-template> [--max-pages 50] [--set NAME]
    python3 tools/ledger/acquire/web.py recapture <hold folder>
    python3 tools/ledger/acquire/web.py robots <url>            the verdict for a URL, and the user agent sent
"""
import datetime, email.utils, html, importlib, json, os, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B
from ledger.acquire import robots as R

RP = importlib.import_module("reddit_rss_patch")    # tools/reddit_rss_patch.py: MD, feed_body_to_md, containment, prefix_match, TERMINAL
AGENT_TOKEN = "LedgerAcquire"                       # the ledger's product token: what robots.txt groups are matched against
EXT = {"text/html": "html", "application/xhtml+xml": "html", "application/rss+xml": "xml", "application/atom+xml": "xml",
       "application/xml": "xml", "text/xml": "xml", "application/json": "json", "text/plain": "txt", "application/pdf": "pdf"}
PROTECTION_RE = re.compile(rb"(?i)cf-challenge|challenge-platform|just a moment\.\.\.|attention required|captcha|ddos-guard|access denied|are you a robot")
RETRY_AFTER_CAP = 300


def user_agent(config, version=B.VERSION):
    """The user agent every request sends: the ledger's token and version, the project, the operator's contact, and that it runs
    as Claude-User. Built from ledger.toml [acquire] (agent_token, contact) and [ledger] title; never a browser's."""
    token = config.get("agent_token") or AGENT_TOKEN
    contact = config.get("contact") or "no contact configured (ledger.toml [acquire] contact)"
    title = config.get("project_title") or config.get("project_name") or "a ledger project"
    return f"{token}/{version} (research ledger; {title}; operated through Claude-User; +{contact})"


class RobotsRefusal(Exception):
    def __init__(self, url, verdict):
        super().__init__(f"{url}: refused by robots.txt: {R.summary(verdict)}")
        self.url = url; self.verdict = verdict


class FetchFailure(IOError):
    def __init__(self, url, reason, retried=0):
        super().__init__(f"{url}: {reason}" + (f" (after {retried} retr{'y' if retried == 1 else 'ies'})" if retried else ""))
        self.url = url; self.reason = reason; self.retried = retried


# ============================================================================================================ completion
def is_truncated(text):
    """A body that ends mid-sentence (no terminal punctuation): tools/reddit_rss_patch.py's suspect test."""
    t = (text or "").strip()
    return bool(t) and not RP.TERMINAL.search(t)


def compare(held, fresh):
    """The completion decision between a held text and a later capture (tools/reddit_rss_patch.py, apply(), generalised):
    identical, not-longer, different (left for a reading), revises (a later edited version) or completes."""
    if B.lf(held).strip() == B.lf(fresh).strip(): return dict(decision="identical", containment=1.0, prefix_similarity=1.0)
    if len(fresh) <= len(held) * 1.02:
        return dict(decision="not-longer", containment=None, prefix_similarity=None,
                    why=f"the later text is not longer ({len(fresh)} against {len(held)} characters): not a truncation")
    ratio = RP.prefix_match(held, fresh); cont = RP.containment(held, fresh)
    out = dict(containment=round(cont, 3), prefix_similarity=round(ratio, 3))
    if cont < 0.85:
        out.update(decision="different", why="the later text does not contain the held text; a different text, left for a reading")
    elif cont < 0.98 or ratio < 0.97:
        out.update(decision="revises", why="the later text is an edited version: wording revised before the cut as well as completed; "
                                           "under the version rule the later, longer version is canonical and the first state is kept as a version")
    else:
        out.update(decision="completes", why="the later text completes the held text without revising it")
    return out


# ============================================================================================================ HTML helpers
def html_to_text(raw):
    """HTML to markdown-like text with tools/reddit_rss_patch.py's renderer (script and style dropped first)."""
    s = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>", " ", raw)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    m = re.search(r"(?is)<body\b[^>]*>(.*)</body>", s)
    p = RP.MD(); p.feed(m.group(1) if m else s)
    t = "".join(p.out)
    t = "\n".join(l.rstrip() for l in t.split("\n")); t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return html.unescape(t) if "&" in t else t


def _meta(raw, *names):
    for n in names:
        m = (re.search(r'(?is)<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n), raw)
             or re.search(r'(?is)<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name|itemprop)=["\']%s["\']' % re.escape(n), raw))
        if m and m.group(1).strip(): return html.unescape(m.group(1).strip()), n
    return None, None


DATE_TEXT_FORMATS = ["%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%A %d %B %Y", "%a %d %b %Y", "%Y-%m-%d"]
DATELINE_RE = re.compile(r"(?i)\b(?:first published|date published|published|posted)(?: on)?\s*:?\s+(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?"
                         r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\.?,?\s+\d{4}|[A-Z][a-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{4}-\d{2}-\d{2})")


def iso_date(raw):
    """YYYY-MM-DD from an ISO timestamp, an RFC 822 date (feeds), or a written date ('11 May 2009', 'May 11, 2009'), else None."""
    if not raw: return None
    raw = str(raw).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m: return m.group(1)
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", raw).replace(".", "").replace(" ,", ",")
    s = re.sub(r"\s+", " ", s).strip()
    for f in DATE_TEXT_FORMATS:
        try: return datetime.datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    try:
        return email.utils.parsedate_to_datetime(raw).date().isoformat()
    except Exception:
        return None


def _jsonld_dates(raw):
    """(value, key) of the first datePublished, else dateCreated, else uploadDate in the page's JSON-LD blocks (@graph and lists
    walked), or (None, None)."""
    found = {}
    def walk(o):
        if isinstance(o, dict):
            for k in ("datePublished", "dateCreated", "uploadDate"):
                if k in o and isinstance(o[k], str) and k not in found: found[k] = o[k]
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    for m in re.finditer(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw):
        try: walk(json.loads(html.unescape(m.group(1).strip()), strict=False))
        except ValueError: continue
    for k in ("datePublished", "dateCreated", "uploadDate"):
        if k in found: return found[k], k
    return None, None


def page_fields(raw, url=None):
    """Title, date (with its basis), authors, site, canonical link and the <title> of an HTML page, from its own markup only.
    The date's sources in order: meta tags (article:published_time, citation_publication_date, datePublished, dc.date, pubdate,
    date), JSON-LD (datePublished, dateCreated, uploadDate), a visible 'Published' dateline, per-site rules (Hacker News: the
    story's span.age title), the first <time datetime>. None found: date None and date_basis 'none found'."""
    og, _ = _meta(raw, "og:title", "citation_title", "twitter:title")
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    title_tag = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else None
    title = og or title_tag
    date_raw, key = _meta(raw, "article:published_time", "citation_publication_date", "datePublished", "dc.date", "pubdate", "date")
    basis = f"the page's meta {key}" if date_raw else None
    if not date_raw:
        date_raw, key = _jsonld_dates(raw)
        if date_raw: basis = f"the page's JSON-LD {key}"
    if not date_raw:
        text = re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)))
        dm = DATELINE_RE.search(html.unescape(text))
        if dm and iso_date(dm.group(1)): date_raw = dm.group(1); basis = f"a visible dateline ('{dm.group(0).strip()[:60]}')"
    if not date_raw and (url and "news.ycombinator.com" in url or 'class="hnuser"' in raw):
        hm = re.search(r'<span class="age" title="([^"]+)"', raw)
        if hm: date_raw = hm.group(1).split(" ")[0]; basis = "the story's span.age title (Hacker News)"
    if not date_raw:
        tm = re.search(r'(?is)<time[^>]+datetime=["\']([^"\']+)["\']', raw)
        if tm: date_raw = tm.group(1); basis = "the page's first <time datetime>"
    date = iso_date(date_raw)
    if date_raw and not date: basis = f"{basis}: {date_raw!r} not read as a date"
    au, _ = _meta(raw, "author", "article:author", "citation_author", "dc.creator")
    site, _ = _meta(raw, "og:site_name", "application-name")
    cm = (re.search(r'(?is)<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', raw)
          or re.search(r'(?is)<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', raw))
    canonical = urllib.parse.urljoin(url or "", html.unescape(cm.group(1))) if cm else None
    return dict(title=title, title_tag=title_tag, og_title=og, date_raw=date_raw, date=date,
                date_basis=basis or "none found (meta tags, JSON-LD, a visible 'Published' dateline, per-site rules, <time>)",
                authors=[au] if au else [], site=site, canonical=canonical)


def next_link(raw, base_url):
    m = (re.search(r'(?is)<link[^>]+rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']', raw)
         or re.search(r'(?is)<a[^>]+rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']', raw))
    return urllib.parse.urljoin(base_url, html.unescape(m.group(1))) if m else None


# ============================================================================================================ main content (finding 14)
class _Spans(HTMLParser):
    """Character spans of the candidate main-content elements: itemprop=articleBody, <article>, <main>."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.raw = raw; self.offsets = [0]
        for line in raw.split("\n"): self.offsets.append(self.offsets[-1] + len(line) + 1)
        self.stack = []; self.spans = []

    def pos(self):
        ln, col = self.getpos(); return self.offsets[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID: return
        a = dict(attrs)
        kind = "articleBody" if a.get("itemprop") == "articleBody" else tag if tag in ("article", "main") else None
        self.stack.append((tag, kind, self.pos()))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                t, kind, start = self.stack[i]; del self.stack[i:]
                if kind:
                    end = self.raw.find(">", self.pos()) + 1
                    self.spans.append((kind, start, end))
                return


def main_content(raw):
    """(html of the main content, the element it came from) or (None, 'whole page'): itemprop=articleBody first, then the <article>
    with the most text, then <main>; a candidate rendering under 200 characters is not taken."""
    p = _Spans(raw)
    try: p.feed(raw); p.close()
    except Exception: return None, "whole page"
    for kind in ("articleBody", "article", "main"):
        cands = [(len(html_to_text(raw[s:e])), raw[s:e]) for k, s, e in p.spans if k == kind]
        cands = [c for c in cands if c[0] >= 200]
        if cands:
            return max(cands)[1], {"articleBody": "the itemprop=articleBody element", "article": "the largest <article> element", "main": "the <main> element"}[kind]
    return None, "whole page"


# ============================================================================================================ thread renderers (finding 13)
def render_hn(raw):
    """A Hacker News item page as text: the story's header and text, then one header per comment, `[id] author, time, depth n,
    reply to [parent id]` (reply to the story at depth 0), its body below; vote, hide and navigation links dropped. None when the
    page is not in Hacker News's markup."""
    if 'class="athing comtr' not in raw and 'class="athing submission' not in raw and 'class="fatitem"' not in raw: return None
    out = []
    t = re.search(r'(?is)<span class="titleline"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', raw)
    sub = re.search(r'(?is)<td class="subtext"[^>]*>(.*?)</td>', raw)
    head = "## " + (html.unescape(re.sub(r"<[^>]+>", "", t.group(2))) if t else "Hacker News item")
    out += [head, ""]
    if t: out.append(f"- Link: {html.unescape(t.group(1))}")
    if sub:
        by = re.search(r'class="hnuser">([^<]+)<', sub.group(1)); age = re.search(r'<span class="age" title="([^"]+)"', sub.group(1))
        pts = re.search(r'<span class="score"[^>]*>([^<]+)<', sub.group(1))
        out.append(f"- By: {by.group(1) if by else ''}; time: {age.group(1).split(' ')[0] if age else ''}; {pts.group(1) if pts else ''}")
    top = re.search(r'(?is)<div class="toptext">(.*?)</div>', raw)
    if top: out += ["", html_to_text(top.group(1))]
    rows = list(re.finditer(r'<tr class="athing comtr\s*"?\s*id="(\d+)"', raw))
    parents = []
    for i, m in enumerate(rows):
        seg = raw[m.start(): rows[i + 1].start() if i + 1 < len(rows) else len(raw)]
        ind = re.search(r'<td class=["\']ind["\'][^>]*indent=["\'](\d+)["\']', seg)
        depth = int(ind.group(1)) if ind else 0
        by = re.search(r'class="hnuser">([^<]+)<', seg); age = re.search(r'<span class="age" title="([^"]+)"', seg)
        body = re.search(r'(?is)<div class="commtext[^"]*">(.*?)</div>\s*(?:<div class="reply">|</span>|<div)', seg) or re.search(r'(?is)<div class="commtext[^"]*">(.*?)</div>', seg)
        parents = parents[:depth]
        parent = parents[-1] if parents else None
        out += ["", f"[{m.group(1)}] {by.group(1) if by else '[deleted]'}, {age.group(1).split(' ')[0] if age else ''}, depth {depth}, "
                    + (f"reply to [{parent}]" if parent else "reply to the story"), ""]
        out.append(html_to_text(body.group(1)) if body else "[no text]")
        parents.append(m.group(1))
    return "\n".join(out).strip()


THREAD_RENDERERS = [("Hacker News", render_hn)]      # (forum, renderer returning text or None); others: the generic rendering


def render_thread_page(raw):
    for forum, fn in THREAD_RENDERERS:
        t = fn(raw)
        if t is not None: return t, forum
    return html_to_text(raw), None


# ============================================================================================================ feeds
ATOM = "{http://www.w3.org/2005/Atom}"


def parse_feed(data):
    """RSS 2.0 or Atom entries: [{title, link, author, date_raw, date, body_html, body}] in feed order."""
    root = ET.fromstring(data)
    out = []
    if root.tag == ATOM + "feed":
        for e in root.findall(ATOM + "entry"):
            link = e.find(ATOM + "link"); content = e.find(ATOM + "content")
            if content is None: content = e.find(ATOM + "summary")
            au = e.find(ATOM + "author/" + ATOM + "name")
            d = (e.findtext(ATOM + "published") or e.findtext(ATOM + "updated") or "").strip()
            out.append(dict(title=(e.findtext(ATOM + "title") or "").strip(), link=link.get("href") if link is not None else None,
                            author=au.text.strip() if au is not None and au.text else None, date_raw=d or None, date=iso_date(d),
                            body_html=content.text if content is not None else ""))
    else:
        ch = root.find("channel")
        for e in (ch.findall("item") if ch is not None else []):
            d = (e.findtext("pubDate") or e.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
            body = e.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or e.findtext("description") or ""
            out.append(dict(title=(e.findtext("title") or "").strip(), link=(e.findtext("link") or "").strip() or None,
                            author=(e.findtext("author") or e.findtext("{http://purl.org/dc/elements/1.1/}creator") or "").strip() or None,
                            date_raw=d or None, date=iso_date(d), body_html=body))
    for e in out:
        b = e["body_html"] or ""
        e["body"] = RP.feed_body_to_md(b) if '<div class="md">' in b else html_to_text(b)
    return out


def feed_title(data):
    root = ET.fromstring(data)
    if root.tag == ATOM + "feed": return (root.findtext(ATOM + "title") or "").strip()
    ch = root.find("channel"); return (ch.findtext("title") or "").strip() if ch is not None else ""


# ============================================================================================================ the adapter
class WebAdapter(B.Adapter):
    name = "web"

    def __init__(self, root=None, gap=6.0, set_name=None, timeout=60, clock=None, sleep=None, **kw):
        super().__init__(root=root, **kw)
        self.gap = float(gap); self.set_name = set_name; self.timeout = timeout
        self.clock = clock or time.time; self.sleep = sleep or time.sleep
        self.token = self.config.get("agent_token") or AGENT_TOKEN
        self.ua = user_agent(self.config, self.version)
        self.robot_tokens = (self.token, R.CLAUDE_USER)
        self.gates = {}; self.robots_cache = {}; self.last = {}

    # ---------------------------------------------------------------------------------------------------- gates and robots
    @staticmethod
    def host_of(url):
        parts = urllib.parse.urlsplit(url)
        return parts.netloc or ("local:" + os.path.dirname(urllib.request.url2pathname(parts.path)) if parts.scheme == "file" else "local")

    def gate(self, url):
        host = urllib.parse.urlsplit(url).netloc or "local"
        if host not in self.gates:
            self.gates[host] = B.RateGate("web-" + B.safe_slug(host, 40), self.gap, self.state_dir, clock=self.clock, sleep=self.sleep)
        return self.gates[host]

    def robots_for(self, url):
        """The host's Robots (cached per run): fetched through the host's gate with the ledger's user agent."""
        parts = urllib.parse.urlsplit(url)
        if parts.scheme == "file":
            d = os.path.dirname(urllib.request.url2pathname(parts.path)); key = "file:" + d; src = os.path.join(d, "robots.txt")
            if key in self.robots_cache: return self.robots_cache[key]
            rb = (R.Robots(B.read_bytes(src).decode("utf-8", "replace"), source=src) if os.path.isfile(src)
                  else R.Robots(source=src, status="allow-all", note="no robots.txt beside the file"))
        else:
            key = f"{parts.scheme}://{parts.netloc}"
            if key in self.robots_cache: return self.robots_cache[key]
            rurl = key + "/robots.txt"
            try:
                data, status, _ = self._request(rurl, check_redirects=False)
                rb = R.Robots(data.decode("utf-8", "replace"), source=rurl)
            except urllib.error.HTTPError as e:
                rb = (R.Robots(source=rurl, status="allow-all", note=f"{rurl}: HTTP {e.code} (no robots.txt; RFC 9309 2.3.1.3)") if 400 <= e.code < 500
                      else R.Robots(source=rurl, status="disallow-all", note=f"{rurl}: HTTP {e.code}"))
            except Exception as e:
                rb = R.Robots(source=rurl, status="disallow-all", note=f"{rurl} unreachable ({type(e).__name__}: {str(e)[:80]})")
        delay, line = rb.crawl_delay(self.robot_tokens)
        if delay and delay > self.gate(url).gap:
            self.gate(url).gap = float(delay); self.log(f"{parts.netloc}: Crawl-delay {delay:g} s from robots.txt {line}; the gate's gap raised")
        rb.crawl_delay_applied = (delay, line)
        self.robots_cache[key] = rb
        return rb

    def check(self, url):
        """The robots verdict for a URL (for the ledger's token and Claude-User); RobotsRefusal when it is disallowed."""
        v = self.robots_for(url).verdict(url, self.robot_tokens)
        if not v["allowed"]:
            rec = dict(time=B.utc_now(), url=url, user_agent=self.ua, verdict=v)
            try:
                os.makedirs(self.state_dir, exist_ok=True)
                B.LN.append_text(os.path.join(self.state_dir, "robots-refusals.jsonl"), json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError: pass
            raise RobotsRefusal(url, v)
        return v

    # ---------------------------------------------------------------------------------------------------- requests
    def _request(self, url, check_redirects=True):
        """One request through the host's gate with the ledger's user agent: (bytes, status, response). A redirect is followed
        only when its target passes robots.txt too."""
        adapter = self

        class Redirects(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if check_redirects: adapter.check(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(Redirects)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Language": "en-GB,en;q=0.9"})
        with self.gate(url):
            r = opener.open(req, timeout=self.timeout)
            with r: data = r.read()
        return data, getattr(r, "status", 200) or 200, r

    def get_full(self, url):
        """{data, content_type, charset, final_url, status, robots, headers} of one URL, through robots.txt and the host's gate, with
        the retry policy of the module docstring. Raises RobotsRefusal or FetchFailure (the reason in it)."""
        v = self.check(url)
        retried = 0
        while True:
            try:
                data, status, r = self._request(url)
                ctype_full = r.headers.get("Content-Type") or ""
                ctype = ctype_full.split(";")[0].strip().lower() or self._guess_type(url, data)
                cm = re.search(r"charset=([\w.-]+)", ctype_full, re.I)
                out = dict(data=data, content_type=ctype, charset=cm.group(1).lower() if cm else None,
                           final_url=r.geturl(), status=status, robots=v, headers=dict(r.headers.items()))
                self.last = out
                return out
            except RobotsRefusal:
                raise
            except urllib.error.HTTPError as e:
                body = b""
                try: body = e.read()[:20000]
                except Exception: pass
                if e.code in (429, 503):
                    if PROTECTION_RE.search(body): raise FetchFailure(url, f"HTTP {e.code} with a protection page (a challenge, not a server fault): not retried", retried)
                    ra = e.headers.get("Retry-After") if e.headers else None
                    if retried >= 1: raise FetchFailure(url, f"HTTP {e.code}" + (f" (Retry-After {ra})" if ra else ""), retried)
                    wait = self._retry_after(ra)
                    self.sleep(min(wait if wait is not None else 20, RETRY_AFTER_CAP)); retried += 1; continue
                if 500 <= e.code < 600 and retried < 2:
                    self.sleep(20 * (retried + 1)); retried += 1; continue
                raise FetchFailure(url, f"HTTP {e.code}", retried)
            except urllib.error.URLError as e:
                reason = e.reason
                if isinstance(reason, (ssl.SSLError, ssl.CertificateError)) or "SSL" in str(reason) or "CERTIFICATE" in str(reason).upper():
                    raise FetchFailure(url, f"TLS failure, not retried (it cannot change): {str(reason)[:160]}", retried)
                if url.startswith("file:") or retried >= 1: raise FetchFailure(url, f"{type(reason).__name__}: {str(reason)[:160]}", retried)
                self.sleep(20); retried += 1
            except (ssl.SSLError, ssl.CertificateError) as e:
                raise FetchFailure(url, f"TLS failure, not retried (it cannot change): {str(e)[:160]}", retried)
            except (TimeoutError, ConnectionError, OSError) as e:
                if url.startswith("file:") or retried >= 1: raise FetchFailure(url, f"{type(e).__name__}: {str(e)[:160]}", retried)
                self.sleep(20); retried += 1

    @staticmethod
    def _retry_after(v):
        if not v: return None
        v = v.strip()
        if v.isdigit(): return float(v)
        try: return max(0.0, (email.utils.parsedate_to_datetime(v) - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        except Exception: return None

    def get(self, url):
        """(bytes, content type, final URL, HTTP status): get_full's four values, the form callers of the first turn use."""
        f = self.get_full(url)
        return f["data"], f["content_type"], f["final_url"], f["status"]

    @staticmethod
    def _guess_type(url, data):
        head = data[:400].lstrip().lower()
        if head.startswith(b"%pdf"): return "application/pdf"
        if head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head: return "application/xml"
        if head.startswith((b"{", b"[")): return "application/json"
        if b"<html" in head or b"<!doctype html" in head: return "text/html"
        ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
        return {".html": "text/html", ".htm": "text/html", ".xml": "application/xml", ".rss": "application/xml", ".txt": "text/plain",
                ".json": "application/json", ".pdf": "application/pdf"}.get(ext, "application/octet-stream")

    def folder(self, date, title, url):
        """<hold root>/web/[<set>/]<date>-<slug>, or undated-<slug> when the item has no date of its own (never the fetch date)."""
        host = urllib.parse.urlsplit(url).netloc
        label = title or (host + " " + urllib.parse.urlsplit(url).path)
        kind = "web/" + B.safe_slug(self.set_name, 40) if self.set_name else "web"
        return self.hold_path(kind, date or "undated", label)

    def _failed(self, url, kind, title, e):
        rec = B.Record(url, kind, title or url, provenance=url)
        rec.capture_time = B.utc_now(); rec.capture_tool = self.tool
        row = self._row(rec, None, "failed", str(e), [])
        if isinstance(e, RobotsRefusal): row["robots"] = R.summary(e.verdict); row["note"] = f"refused by robots.txt: {R.summary(e.verdict)}"
        if isinstance(e, FetchFailure): row["fetch_failure"] = e.reason
        self.log(row["note"])
        return row

    # ---------------------------------------------------------------------------------------------------- a page
    def _page_capture(self, url, data, ctype, final, status, tool=None, how=None, set_note="", charset=None, robots=None,
                      metadata=None, date=None, date_basis=None, folder=None):
        ext = EXT.get(ctype, "bin")
        files = [B.HeldFile(f"page.{ext}", data=data, how=how or f"HTTP {status} response body of {final}, {ctype}")]
        f = dict(title=None, title_tag=None, og_title=None, date=None, date_raw=None, authors=[], site=None, canonical=None,
                 date_basis="none found (not an HTML page)")
        text_name = None; md = {}
        if ext == "html":
            raw = data.decode(charset or "utf-8", "replace"); f = page_fields(raw, final)
            full = html_to_text(raw) + "\n"
            main_html, extent = main_content(raw)
            if main_html is not None:
                main = html_to_text(main_html) + "\n"
                files.append(B.HeldFile("text.md", text=main, role="derived", derived_from=f"page.{ext}",
                                        tool=f"ledger.acquire.web main content ({extent}), rendered by tools/reddit_rss_patch.py's renderer"))
                if main.strip() != full.strip():
                    files.append(B.HeldFile("page-full.md", text=full, role="derived", derived_from=f"page.{ext}",
                                            tool="ledger.acquire.web.html_to_text (the whole page, menus and all)"))
            else:
                files.append(B.HeldFile("text.md", text=full, role="derived", derived_from=f"page.{ext}",
                                        tool="ledger.acquire.web.html_to_text (the whole page: no article or main element found)"))
            md["text_extent"] = extent; text_name = "text.md"
        elif ext == "txt":
            if B.needs_text_copy(data, charset):
                copy, enc = B.normalised_copy("text.txt", data, "page.txt", charset)   # marked as page.txt's normalised copy
                files.append(copy)
                text_name = "text.txt"; md["text_encoding"] = enc
            else:
                text_name = "page.txt"
        title = f["title"] or urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(final).path)) or final
        if date:
            f["date"] = date; f["date_raw"] = f.get("date_raw") if f.get("date") == date else None
            f["date_basis"] = date_basis or "given by the caller"
        md.update({"content_type": ctype, "http_status": status, "final_url": final if final != url else None, "site": f["site"],
                   "date_basis": f["date_basis"], "canonical_url": f["canonical"] if f["canonical"] and f["canonical"] not in (url, final) else None,
                   "page_title": f["title_tag"] if f["og_title"] and f["title_tag"] and f["title_tag"] != f["og_title"] else None,
                   "robots": R.summary(robots) if robots else None, "charset": charset})
        md.update(metadata or {})
        rec = B.Record(url, "web-page", title, date=f["date"], date_raw=f["date_raw"], speaker_or_author=f["authors"],
                       text=text_name, media_link=None, venue=f["site"] or urllib.parse.urlsplit(final).netloc, provenance=url, capture_tool=tool,
                       metadata={k: v for k, v in md.items() if v is not None})
        return B.Capture(rec, files, folder=folder or self.folder(f["date"], title, url), status_note=set_note)

    def page(self, url, metadata=None, date=None, date_basis=None, folder=None):
        try: g = self.get_full(url)
        except (RobotsRefusal, FetchFailure) as e: return [self._failed(url, "web-page", None, e)]
        return [self.hold(self._page_capture(url, g["data"], g["content_type"], g["final_url"], g["status"], charset=g["charset"],
                                             robots=g["robots"], metadata=metadata, date=date, date_basis=date_basis, folder=folder))]

    def hold_bytes(self, url, data, tool, content_type=None, how=None, metadata=None, date=None, date_basis=None, folder=None):
        """Hold bytes another route captured (e.g. the browser pane): `tool` names that route; nothing is fetched."""
        ctype = content_type or self._guess_type(url, data)
        cap = self._page_capture(url, data, ctype, url, 200, tool=f"{self.tool} via {tool}",
                                 how=how or f"saved byte-for-byte by {tool} from {url}", metadata=metadata, date=date, date_basis=date_basis,
                                 folder=folder)
        return self.hold(cap)

    # ---------------------------------------------------------------------------------------------------- a feed
    def feed(self, url, metadata=None):
        try: g = self.get_full(url)
        except (RobotsRefusal, FetchFailure) as e: return [self._failed(url, "feed", None, e)]
        data, ctype, final, status = g["data"], g["content_type"], g["final_url"], g["status"]
        entries = parse_feed(data)
        lines = []
        for i, e in enumerate(entries, 1):
            lines += [f"## {i}. {e['title'] or '[untitled entry]'}", "", f"- Link: {e['link'] or ''}", f"- Author: {e['author'] or ''}",
                      f"- Date: {e['date'] or ''}" + (f" ({e['date_raw']})" if e['date_raw'] and e['date_raw'] != e['date'] else ""), "",
                      e["body"].strip(), ""]
        title = feed_title(data) or url
        dates = sorted(e["date"] for e in entries if e["date"])
        md = {"entries": len(entries), "content_type": ctype, "http_status": status,
              "date_basis": "the latest entry's date" if dates else "none found (no entry carries a date)",
              "first_entry_date": dates[0] if dates else None, "truncation_suspects": sum(is_truncated(e["body"]) for e in entries),
              "robots": R.summary(g["robots"])}
        md.update(metadata or {})
        rec = B.Record(url, "feed", title, date=dates[-1] if dates else None, date_raw=None, text="entries.md",
                       speaker_or_author=sorted({e["author"] for e in entries if e["author"]}), venue=urllib.parse.urlsplit(final).netloc,
                       provenance=url, metadata={k: v for k, v in md.items() if v is not None})
        files = [B.HeldFile("feed.xml", data=data, how=f"HTTP {status} response body of {final}, {ctype}"),
                 B.HeldFile("entries.md", text="\n".join(lines).rstrip() + "\n", role="derived", derived_from="feed.xml",
                            tool="ledger.acquire.web.parse_feed (entry bodies by tools/reddit_rss_patch.py's renderer)"),
                 B.HeldFile("entries.json", text=json.dumps([{k: v for k, v in e.items() if k != "body_html"} for e in entries],
                                                            indent=1, ensure_ascii=False) + "\n",
                            role="derived", derived_from="feed.xml", tool="ledger.acquire.web.parse_feed")]
        return [self.hold(B.Capture(rec, files, folder=self.folder(rec.date, title, url)))]

    # ---------------------------------------------------------------------------------------------------- a thread
    def thread_capture(self, url, max_pages=50, first_page=1, title=None, metadata=None, folder=None, date=None, date_basis=None):
        """The Capture of a forum thread (finding 12): `url` is a template with {page} (page numbers from first_page) or the first page,
        whose rel="next" links are followed. Stops when a page's bytes repeat an earlier page, a request fails or is refused, or at
        max_pages. Raises RobotsRefusal or FetchFailure when not even the first page could be fetched."""
        pages = []; seen = set(); cur = url.format(page=first_page) if "{page}" in url else url; n = first_page; stop = "max_pages"
        verdict = None; err = None
        while cur and len(pages) < max_pages:
            try: g = self.get_full(cur)
            except (RobotsRefusal, FetchFailure) as e:
                err = e; stop = ("refused by robots.txt: " + R.summary(e.verdict)) if isinstance(e, RobotsRefusal) else f"request failed: {e}"; break
            verdict = verdict or g["robots"]
            d = B.sha256(g["data"])
            if d in seen: stop = "a page repeated an earlier page"; break
            seen.add(d); pages.append((cur, g["data"], g["content_type"], g["status"], g["charset"]))
            if "{page}" in url: n += 1; cur = url.format(page=n)
            else:
                nxt = next_link(g["data"].decode(g["charset"] or "utf-8", "replace"), g["final_url"])
                cur = nxt if nxt and nxt not in [p[0] for p in pages] else None
                if not cur: stop = "no next link"
        if not pages: raise err or FetchFailure(url, f"no page fetched ({stop})")
        files = []; texts = []; forums = set()
        for i, (u, data, ctype, status, cs) in enumerate(pages, 1):
            ext = EXT.get(ctype, "bin")
            files.append(B.HeldFile(f"page-{i:03d}.{ext}", data=data, how=f"HTTP {status} response body of {u}"))
            if ext == "html":
                t, forum = render_thread_page(data.decode(cs or "utf-8", "replace"))
                if forum: forums.add(forum)
            else:
                t = B.decode_text(data, cs)[0]
            texts.append(f"--- page {i} ---\n" + t)
        first_raw = pages[0][1].decode(pages[0][4] or "utf-8", "replace")
        f = page_fields(first_raw, url) if EXT.get(pages[0][2]) == "html" else dict(title=None, date=None, date_raw=None, site=None,
                                                                                    date_basis="none found (not an HTML page)")
        if date: f["date"] = date; f["date_raw"] = None; f["date_basis"] = date_basis or "given by the caller"
        t = title or f.get("title") or url
        renderer = (f"ledger.acquire.web thread renderer ({', '.join(sorted(forums))}: one header per comment with its depth and parent)"
                    if forums else "ledger.acquire.web.html_to_text, per page")
        files.append(B.HeldFile("text.md", text="\n\n".join(texts) + "\n", role="derived",
                                derived_from=f"page-001 to page-{len(pages):03d}", tool=renderer))
        md = {"pages": len(pages), "stopped": stop, "page_urls": [p[0] for p in pages], "date_basis": f["date_basis"],
              "robots": R.summary(verdict) if verdict else None, "thread_renderer": ", ".join(sorted(forums)) or "generic"}
        md.update(metadata or {})
        rec = B.Record(url, "thread", t, date=f.get("date"), date_raw=f.get("date_raw"), text="text.md",
                       venue=f.get("site") or urllib.parse.urlsplit(url).netloc, provenance=url, metadata={k: v for k, v in md.items() if v is not None})
        return B.Capture(rec, files, folder=folder or self.folder(rec.date, t, url))

    def thread(self, url, max_pages=50, first_page=1, title=None, metadata=None, folder=None, date=None, date_basis=None):
        try: cap = self.thread_capture(url, max_pages, first_page, title, metadata, folder, date, date_basis)
        except (RobotsRefusal, FetchFailure) as e: return [self._failed(url, "thread", title, e)]
        return [self.hold(cap)]

    # ---------------------------------------------------------------------------------------------------- recapture
    def recapture(self, folder):
        """Fetch a held page again and record the completion decision against the first capture's text."""
        af = self.abs(folder); h = B.load_hold(af)
        if not h: raise FileNotFoundError(f"{folder}: no hold.json")
        url = h["record"]["provenance"]; text_name = h["record"].get("text")
        held_text = B.LN.read_text(os.path.join(af, text_name)) if text_name and os.path.isfile(os.path.join(af, text_name)) else ""
        try: g = self.get_full(url)
        except (RobotsRefusal, FetchFailure) as e: return self._failed(url, h["record"].get("media_kind") or "web-page", h["record"].get("title"), e)
        cap = self._page_capture(url, g["data"], g["content_type"], g["final_url"], g["status"], charset=g["charset"], robots=g["robots"])
        fresh = next((f.text for f in cap.files if f.name == text_name and f.text is not None), None)
        if fresh is None and text_name and text_name.startswith("page."): fresh = g["data"].decode("utf-8", "replace")
        if fresh is not None and held_text:
            c = compare(held_text, fresh)
            cap.record.metadata["completion"] = c
            cap.status_note = (f"Re-capture of {B.utc_now()[:10]} against the first: {c['decision']}"
                               + (f" (held 8-word shingles found in the later text {c['containment']}; prefix similarity {c['prefix_similarity']})" if c.get("containment") is not None else "")
                               + f". {c.get('why', '')}")
            if c["decision"] in ("completes", "revises"):
                cap.record.metadata["canonical_capture"] = "the later capture (version rule); the first state is kept as a version"
        cap.folder = folder
        return self.hold(cap)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["page", "feed", "thread", "recapture", "robots"]); ap.add_argument("target")
    ap.add_argument("--set"); ap.add_argument("--gap", type=float, default=6.0); ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--date"); ap.add_argument("--date-basis"); ap.add_argument("--root"); ap.add_argument("--hold-root")
    a = ap.parse_args(argv)
    w = WebAdapter(root=a.root, gap=a.gap, set_name=a.set, hold_root=a.hold_root)
    if a.cmd == "robots":
        print(w.ua)
        try: print(R.summary(w.check(a.target)))
        except RobotsRefusal as e: print(e)
        return
    rows = (w.page(a.target, date=a.date, date_basis=a.date_basis) if a.cmd == "page" else w.feed(a.target) if a.cmd == "feed" else
            w.thread(a.target, max_pages=a.max_pages, date=a.date, date_basis=a.date_basis) if a.cmd == "thread" else [w.recapture(a.target)])
    for r in rows: print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
