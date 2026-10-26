#!/usr/bin/env python3
"""Tests of the setup engine (tools/ledger/setup_stages.py), /settings (settings.py), the members file (members.py), the brief renderer
(briefs.py), the plugin's hooks and lock, and the privacy check (phase 7a of tools/platform-plan.md, 2026-10-22).

Stages 0 to 7 run non-interactively against the shipped sample database (tools/ledger/sampledb.py, the invented casebook) with the
answers file plugin/templates/answers-casebook.json, and the pack files they write are asserted; stage 8 is asserted only to the
launch call (a launcher stub records it; no intake runs). Sockets are refused for the whole module.

    python3 -m unittest tools/ledger/tests/test_setup.py      (from the project root)"""
import copy, json, os, shutil, socket, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
from ledger import setup_stages as SU, settings as ST, members as M, briefs as BR, sampledb, notes as LN

try:
    import tomllib
except ImportError:
    import tomli as tomllib

def _plugin_dir():
    """The plugin these tests exercise: $LEDGER_PLUGIN_ROOT or $CLAUDE_PLUGIN_ROOT as the shell has them, else the project's own plugin/
    (the private project keeps its source there), else the plugin setup stage 0 recorded (a recipient's project: the plugin lives in the
    bundle or Claude Code's plugin cache; phase 7b)."""
    for c in (os.environ.get("LEDGER_PLUGIN_ROOT"), os.environ.get("CLAUDE_PLUGIN_ROOT"), os.path.join(ROOT, "plugin")):
        if c and os.path.isfile(os.path.join(c, ".claude-plugin", "plugin.json")): return c
    st0 = os.path.join(ROOT, "setup", "stage-0.toml")
    if os.path.isfile(st0):
        with open(st0, "rb") as f: c = tomllib.load(f).get("result", {}).get("plugin")
        if c and os.path.isfile(os.path.join(c, ".claude-plugin", "plugin.json")): return c
    return os.path.join(ROOT, "plugin")


PLUGIN = _plugin_dir()
ANSWERS = os.path.join(PLUGIN, "templates", "answers-casebook.json")
ROUTE_VARS = [v for _, v, _ in SU.ROUTES] + ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"] + SU.OVERRIDES
_saved_env, _saved_sock = {}, {}


def setUpModule():
    def refuse(*a, **k): raise ConnectionError("network refused in the setup tests")
    _saved_sock.update(connect=socket.socket.connect, create_connection=socket.create_connection)
    socket.socket.connect = refuse; socket.create_connection = refuse
    for v in ROUTE_VARS + ["LEDGER_MANAGED_SETTINGS", "LEDGER_USER", "CLAUDE_PLUGIN_ROOT", "LEDGER_PLUGIN_ROOT"]:
        _saved_env[v] = os.environ.pop(v, None)


def tearDownModule():
    socket.socket.connect = _saved_sock["connect"]; socket.create_connection = _saved_sock["create_connection"]
    for v, val in _saved_env.items():
        if val is None: os.environ.pop(v, None)
        else: os.environ[v] = val


def load(p):
    with open(p, "rb") as f: return tomllib.load(f)


def casebook_answers(db):
    with open(ANSWERS, encoding="utf-8") as f: d = json.load(f)["answers"]
    d["2.source"] = db
    return d


class Env:
    """A temporary world: a project folder, their database, a managed settings file, a model route and the plugin path."""

    def __init__(self, route=True, managed=True):
        self.base = tempfile.mkdtemp(prefix="ledger-setup-test-")
        self.project = os.path.join(self.base, "project"); os.makedirs(self.project)
        self.db = sampledb.build(os.path.join(self.base, "theirs", "casebook.db"))
        self.ms = os.path.join(self.base, "managed-settings.json")
        if managed:
            with open(self.ms, "w", encoding="utf-8") as f:
                json.dump({"allowedProviders": ["bedrock"], "availableModels": ["opus", "haiku"], "maxEffortLevel": "high",
                           "enabledPlugins": {"ledger@ledger-local": True}, "env": {"CLAUDE_CODE_USE_BEDROCK": "1"}}, f)
        os.environ["LEDGER_MANAGED_SETTINGS"] = self.ms
        for v in ROUTE_VARS: os.environ.pop(v, None)
        if route: os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
        os.environ["LEDGER_USER"] = "sample-admin"
        os.environ["LEDGER_PLUGIN_ROOT"] = PLUGIN

    def close(self): shutil.rmtree(self.base, True)


class FullRun(unittest.TestCase):
    """Stages 0 to 7 with the casebook answers; stage 8 to the launch call."""

    @classmethod
    def setUpClass(cls):
        cls.env = Env()
        cls.answers = casebook_answers(cls.env.db)
        cls.launches = []
        cls.s = SU.Setup(cls.env.project, SU.Answers(dict(cls.answers)), launcher=lambda spec: cls.launches.append(spec) or {"status": "launched (test stub)"},
                         allow_compile=False)
        cls.done_0_7 = cls.s.run(until=7)
        cls.pack = load(os.path.join(cls.env.project, "packs", "harrowmere", "pack.toml"))
        cls.slots = load(os.path.join(cls.env.project, "packs", "harrowmere", "briefs", "slots.toml"))["slots"]

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def p(self, *a): return os.path.join(self.env.project, *a)

    def test_00_stages_0_to_7_written_in_order(self):
        self.assertEqual(self.done_0_7, [0, 1, 2, 3, 4, 5, 6, 7])
        for n in range(8):
            st = load(self.p("setup", f"stage-{n}.toml"))
            self.assertEqual(st["stage"]["n"], n)
            self.assertEqual(st["stage"]["by"], "Sample Administrator (sample-admin)")
        self.assertFalse(os.path.exists(self.p("setup", "stage-8.toml")))
        self.assertEqual(self.s.next_stage(), 8)

    def test_01_stage_0_environment(self):
        st = load(self.p("setup", "stage-0.toml"))["result"]
        self.assertEqual(st["route"], "bedrock"); self.assertEqual(st["managed_settings"], self.env.ms)
        plat = json.load(open(self.p("setup", "platform.json"), encoding="utf-8"))
        self.assertEqual(plat["route"]["selectors_set"], ["CLAUDE_CODE_USE_BEDROCK"])
        self.assertTrue(plat["managed_settings"]["present"]); self.assertTrue(plat["plugin"]["manifest"])
        self.assertEqual(plat["plugin"]["name"], "ledger")
        self.assertEqual(sorted(plat["plugin"]["skills"]), ["attack", "install", "intake", "narrate", "report", "settings", "setup", "status"])
        self.assertIn("ocr_backend", plat["ocr"]); self.assertIn("on_share", plat["share"])
        led = load(self.p("ledger.toml"))
        self.assertEqual((led["models"]["agents"], led["models"]["effort"], led["models"]["probes"]), ("opus", "high", "haiku"))
        self.assertTrue(led["database"]["local_only"])

    def test_02_stage_1_question_and_pirs(self):
        st = load(self.p("setup", "stage-1.toml"))
        self.assertEqual(st["result"]["referent"], "the public of Ostley Vale")
        pirs = self.pack["pirs"]["pir"]
        self.assertEqual([p["id"] for p in pirs], ["P1", "P2"])
        self.assertTrue(all(p["by"] == "Sample Administrator (sample-admin)" and p["declared"] for p in pirs))
        self.assertIn("never places", self.pack["pirs"]["rule"])
        self.assertEqual(self.pack["actors"]["referent"], "the public of Ostley Vale")
        terms = LN.read_text(self.p("packs", "harrowmere", "keywords", "pir-terms.txt"))
        self.assertIn("Lisle", terms); self.assertIn("levy", terms)
        self.assertIn("P1:", self.slots["pirs"])

    def test_03_stage_2_mapping_dry_run_hold_scan(self):
        m = load(self.p("setup", "mapping.toml"))
        self.assertEqual((m["record"]["table"], m["fields"]["identifier"]["column"], m["fields"]["title"]["column"]), ("records", "rec_no", "headline"))
        self.assertTrue(m["mapping"]["confirmed"]); self.assertEqual(m["mapping"]["confirmed_by"], "Sample Administrator (sample-admin)")
        self.assertEqual(m["fields"]["date"]["format"], "%d/%m/%Y")
        self.assertIn("run_time", m["metadata"]["columns"])   # unmapped columns kept whole as metadata
        self.assertEqual(m["annotations"][0]["teller"], "their database (casebook), table annotations")
        self.assertEqual(m["annotations"][0]["reading"], "the group's reading")
        md = LN.read_text(self.p("setup", "mapping.md"))
        for s in ("Confidence", "Evidence", "Alternatives", "Record unit"): self.assertIn(s, md)
        dry = os.listdir(self.p("wip", "db-dry-run", "casebook", "sources", "db", "casebook"))
        self.assertEqual(len([d for d in dry if d.startswith("records-")]), 5)
        held = [d for d in os.listdir(self.p("sources", "db", "casebook")) if d.startswith("records-")]
        self.assertEqual(len(held), 8)
        self.assertEqual(self.pack["archives"]["database"][0]["name"], "casebook")
        self.assertEqual(self.pack["registers"]["import"][0]["register"], "claims")
        self.assertIn("sources/db/casebook", self.slots["archives"])

    def test_03b_text_sources_and_annotation_columns(self):
        m = load(self.p("setup", "mapping.toml"))
        alts = m["fields"]["text"]["alternatives"]          # the ordered text sources, confirmed (2.text_order)
        self.assertEqual([("segments" in a, a.get("fallback")) for a in alts], [(True, None), (False, "media_text")])
        self.assertEqual(m["annotations"][0]["attributed_to"], "attributed_to")   # set by 2.annotations.annotations.columns
        dry = LN.read_text(self.p("setup", "dry-run.md"))
        self.assertIn("| Text |", dry); self.assertIn("transcript.md", dry)
        self.assertIn("then", LN.read_text(self.p("setup", "mapping.md")))

    def test_04_scan_detection(self):
        sc = json.load(open(self.p("setup", "scan.json"), encoding="utf-8"))
        self.assertEqual(sc["records"], 8)
        actors = {a["name"]: a for a in sc["actors"]}; polities = {p["name"]: p for p in sc["polities"]}
        self.assertEqual(actors["Greenhollow Trading"]["actor_kind"], "front")
        self.assertEqual(actors["Petra Vanecek"]["actor_kind"], "individual")
        self.assertIn("records/1", actors["Petra Vanecek"]["records"])
        self.assertEqual(actors["Vale Water Authority"]["aliases"], ["the Authority"])
        self.assertEqual(polities["Velmora"]["polity_kind"], "state"); self.assertEqual(polities["Kestria"]["polity_kind"], "state")
        self.assertIn("Timber Exporters' League", polities)
        rel = {(p["actor"], p["relation"], p["polity_or_parent"]) for p in sc["placements"]}
        self.assertIn(("Greenhollow Trading", "front for", "Timber Exporters' League"), rel)
        self.assertIn(("Pernell Geotechnics", "subcontractor of", "Calloway Ashdown Civil"), rel)
        self.assertIn(("Ilse Morrow", "minister of", "Velmora"), rel)
        self.assertIn("P1", actors["Gareth Lisle"]["pirs"])
        self.assertEqual(sc["adverse_positions"][0]["record"], "records/6")
        self.assertTrue(any(d["date"] == "2009-08-12" for d in sc["dates"]))

    def test_05_stage_3_subjects_balance(self):
        self.assertEqual(self.pack["subjects"]["audited"], ["infrastructure-safety"])
        self.assertEqual(self.pack["audit"]["mandatory_subjects"], ["infrastructure-safety"])
        self.assertEqual([t["id"] for t in self.pack["audit"]["topics"]][-1], "other")
        self.assertEqual([e["id"] for e in self.pack["eras"]["era"]], ["before-2009", "2009-2016", "2017-onward"])
        c = self.pack["circles"]
        self.assertTrue(c["adverse_rule"]); self.assertEqual(c["quota"], "one adverse source per circle per era")
        ident = {x["id"]: x for x in c["circle"]}
        self.assertEqual(ident["engineering"]["identification"], "declared")
        self.assertEqual(ident["authority"]["adverse_named"], ["Margin Notes (Ivo Strand)"])
        self.assertEqual(ident["press"]["adverse_confirmed"], ["records/6"])
        self.assertIn("never makes adverse sources more reliable", c["rule_text"])
        seeds = LN.read_text(self.p("packs", "harrowmere", "seeds", "circles.md"))
        self.assertIn("lets a sceptic correct a witness", seeds)
        self.assertEqual(self.pack["source_kinds"]["compilers"], ["The Long Table"])
        ext = LN.read_text(self.p("packs", "harrowmere", "schema-extensions.md"))
        self.assertIn("`infrastructure-safety`", ext); self.assertIn("Adverse-source rule: on", ext)
        for k in ("subjects", "audited_subjects", "topics", "eras", "circles", "compilers"): self.assertIn(k, self.slots)

    def test_06_stage_4_review_flags_only(self):
        a = self.pack["actors"]
        self.assertEqual(a["flagged"], ["Greenhollow Trading", "Vale Water Authority"])
        self.assertEqual([s["name"] for s in self.pack["speakers"]["ledgered"]], ["Petra Vanecek"])
        self.assertEqual(self.pack["objects"]["reference"][0]["id"], "c-14")
        cand = LN.read_text(self.p("packs", "harrowmere", "registers", "detected-candidates.md"))
        self.assertIn("| actor | Greenhollow Trading | front |", cand); self.assertIn("Nothing here is a register row", cand)
        self.assertIn("Flagged targets", self.slots["actor_register"])
        self.assertIn("Petra Vanecek", self.slots["speaker_ledgers"])
        self.assertIn("Core sample C-14", self.slots["reference_objects"])

    def test_07_stage_5_canon_codebook(self):
        self.assertEqual(self.pack["canon"]["text"][0]["unit"], "clause")
        self.assertEqual(self.pack["codebook"]["entries"], 1)
        cb = LN.read_text(self.p("packs", "harrowmere", "codebook", "codebook.md"))
        self.assertIn("| weather | argot | an inspection visit |", cb); self.assertIn("never a finding", cb)
        self.assertIn("unit: clause", self.slots["canon"])

    def test_08_stage_6_lens(self):
        inst = self.pack["lenses"]["instance"][0]
        self.assertEqual((inst["id"], inst["source_kind"]), ("pellingham", "text"))
        lens = json.load(open(self.p("packs", "harrowmere", "lenses", "pellingham.json"), encoding="utf-8"))
        self.assertEqual(lens["placements"], [])
        self.assertEqual(len(lens["techniques"]), 2)
        self.assertTrue(all(t["attributed_to"] == "Pellingham Crisis-Communications Manual (2004)" for t in lens["techniques"]))
        self.assertTrue(all(t["maps_to"] == "new" or t["maps_to"].startswith("C") for t in lens["techniques"]))
        self.assertIn("pellingham", self.slots["lenses"])

    def test_09_stage_7_members_policy(self):
        ms = M.load(self.env.project)["member"]
        self.assertEqual([m["name"] for m in ms], ["Sample Administrator", "Sample Researcher"])
        led = load(self.p("ledger.toml"))
        self.assertTrue(led["policy"]["no_omission"]); self.assertIn("Private individuals", led["policy"]["private_individuals"])
        self.assertEqual(self.pack["catalysts"]["threshold_date"], "2017-10-09")
        self.assertIn("Opus at high effort", self.slots["model_policy"])
        claude = LN.read_text(self.p("CLAUDE.md"))
        self.assertIn("Sample Researcher", claude); self.assertIn("Was a written warning", claude); self.assertNotIn("{{", claude)
        rulings = [l for l in LN.read_lines(self.p("rulings.md")) if l.startswith("| ") and l[2:3].isdigit()]
        self.assertGreater(len(rulings), 40)
        self.assertTrue(all("Sample Administrator (sample-admin)" in r for r in rulings))
        self.assertIn(SU.RULINGS_HEADER.split("\n")[0], LN.read_text(self.p("rulings.md")))
        self.assertTrue(all(LN.split_row(r)[-1] == "adopted" for r in rulings))
        pub = self.pack["display"]["publish"]
        self.assertEqual((pub["enabled"], pub["targets"], pub["last_published"]), (False, [], ""))
        self.assertEqual(self.pack["audit"]["heading"], "## Forthrightness audit")

    def test_10_pack_loads_and_briefs_render(self):
        chk = self.s.pack_check() if os.path.isfile(self.s.run_toml_path()) else None
        if chk is None:
            r = BR.render(self.env.project, only=["operations.md", "intake-", "staged/"], check=True)
            self.assertEqual([m for m in r["missing"] if not m.startswith("run.")], [])

    def test_11_stage_8_to_the_launch_call(self):
        self.s.run(until=8)
        self.assertEqual(len(self.launches), 1)
        spec = self.launches[0]
        self.assertEqual(spec["tool"], "Workflow"); self.assertEqual(spec["scriptPath"], "tools/workflows/staged-intake.js")
        t = spec["args"]["tasks"][0]
        self.assertEqual(t["form"], "document"); self.assertTrue(t["note"].startswith("books/memorandum-on-cracking"))
        self.assertTrue(t["source"].startswith("sources/db/casebook/records-2-"))
        self.assertEqual((spec["args"]["model"], spec["args"]["effort"], spec["args"]["gateModel"]), ("opus", "high", "haiku"))
        self.assertTrue(os.path.isfile(self.p(spec["args"]["phasesDir"], "read.md")))
        read = LN.read_lines(self.p(spec["args"]["phasesDir"], "read.md"))
        self.assertEqual([l for l in read if "{{" in l and not l.startswith("| `{{")], [])
        self.assertEqual([c[:3] for c in spec["prepass"]][0], ["ledger", "prepare", "chunk"])
        chk = json.load(open(self.p("setup", "pack-check.json"), encoding="utf-8"))
        self.assertTrue(chk["ok"], chk["problems"]); self.assertEqual(chk["packload"]["eras(pages)"], 3)
        st = load(self.p("setup", "stage-8.toml"))
        self.assertEqual(st["result"]["launch_status"], "launched (test stub)")
        self.assertIsNone(self.s.next_stage())

    def test_12_resume_from_first_missing_stage(self):
        p5 = self.p("setup", "stage-5.toml"); keep = LN.read_text(p5)
        os.remove(p5)
        s2 = SU.Setup(self.env.project, SU.Answers(dict(self.answers)), launcher=lambda spec: {"status": "stub"}, allow_compile=False)
        self.assertEqual(s2.next_stage(), 5)
        self.assertEqual(s2.run(until=5), [5])
        self.assertTrue(os.path.isfile(p5))
        self.assertEqual(load(p5)["result"], tomllib.loads(keep)["result"])

    def test_13_settings_reenter_stage_3(self):
        note = self.p("books", "lisle-memo-2015.md"); os.makedirs(os.path.dirname(note), exist_ok=True)
        LN.write_text(note, "# Memorandum\n\n| | |\n|---|---|\n| **Subjects** | [Public accountability](../subjects/public-accountability.md) |\n| **Added to notes** | 2026-10-22 |\n\nBody.\n")
        before = LN.read_text(note)
        os.environ["LEDGER_USER"] = "sample-researcher"
        with self.assertRaises(M.Refused): ST.reenter(self.env.project, 3, {"3.audited_subjects": ["infrastructure-safety", "public-accountability"]})
        os.environ["LEDGER_USER"] = "sample-admin"
        r = ST.reenter(self.env.project, 3, {"3.audited_subjects": ["infrastructure-safety", "public-accountability"]})
        self.assertIn(("answers.3.audited_subjects", '["infrastructure-safety"]', '["infrastructure-safety", "public-accountability"]'), r["diff"])
        owed = LN.read_text(self.p("owed.md"))
        self.assertIn("retroactive forthrightness audit of books/lisle-memo-2015.md", owed); self.assertIn("render --check", owed)
        self.assertEqual(LN.read_text(note), before)
        last = [l for l in LN.read_lines(self.p("rulings.md")) if l.startswith("| ") and l[2:3].isdigit()][-1]
        self.assertIn("/settings: stage 3 re-entered by Sample Administrator", last)
        self.assertIn("stage 3 of 2026", last)   # the Supersedes cell names the stage file it replaces
        pack = load(self.p("packs", "harrowmere", "pack.toml"))
        self.assertEqual(pack["subjects"]["audited"], ["infrastructure-safety", "public-accountability"])
        shown = ST.show(self.env.project, 3)
        self.assertEqual(shown["pack"]["subjects"]["audited"], ["infrastructure-safety", "public-accountability"])

    def test_13b_proposal_by_a_launcher_is_not_binding(self):
        before = LN.read_text(self.p("setup", "stage-4.toml"))
        r = ST.propose(self.env.project, 4, {"4.flags": ["Corvane Holdings"]}, user="sample-researcher")
        self.assertEqual(r["status"], "proposed"); self.assertTrue(os.path.isfile(self.p(r["proposal"])))
        self.assertEqual(LN.read_text(self.p("setup", "stage-4.toml")), before)
        last = [l for l in LN.read_lines(self.p("rulings.md")) if l.startswith("| ") and l[2:3].isdigit()][-1]
        self.assertEqual(LN.split_row(last)[-1], "proposed"); self.assertIn("Sample Researcher", last)

    def test_13c_publish_setting(self):
        self.assertFalse(ST.publish_check(self.env.project, "docs")["publish"])
        self.assertIn("off", ST.publish_check(self.env.project, "docs")["reason"])
        os.environ["LEDGER_USER"] = "sample-admin"
        ST.reenter(self.env.project, 7, {"7.publish_artifacts": ["docs", "map"]})
        pub = load(self.p("packs", "harrowmere", "pack.toml"))["display"]["publish"]
        self.assertEqual((pub["enabled"], pub["targets"]), (True, ["map", "docs"]))
        r = ST.publish_check(self.env.project, "docs")       # the route is bedrock: no artifacts, the local file only
        self.assertFalse(r["publish"]); self.assertIn("no artifacts", r["reason"])
        self.assertIn("not among", ST.publish_check(self.env.project, "viewer")["reason"])
        self.assertTrue(ST.published(self.env.project, "docs")["last_published"].endswith(" docs"))

    def test_14_stage_0_settings_only_administrator(self):
        os.environ["LEDGER_USER"] = "sample-researcher"
        with self.assertRaises(M.Refused): M.check(self.env.project, "rule", stage=0)
        os.environ["LEDGER_USER"] = "sample-admin"
        self.assertEqual(M.check(self.env.project, "rule", stage=0)["name"], "Sample Administrator")
        self.assertEqual(M.check(self.env.project, "launch", user="sample-researcher")["name"], "Sample Researcher")

    def test_15_members_stamp(self):
        note = self.p("books", "stamp-test.md"); os.makedirs(os.path.dirname(note), exist_ok=True)
        LN.write_text(note, "# A note\n\n| | |\n|---|---|\n| **Channel** | Ostley Gazette |\n| **Uploaded** | 2017-10-09 |\n\n## Summary\n")
        m = M.check(self.env.project, "launch", user="sample-researcher")
        self.assertTrue(M.stamp(note, m, "intake-test-1022", "2026-10-22")); self.assertFalse(M.stamp(note, m, "intake-test-1022"))
        lines = LN.read_lines(note)
        self.assertEqual(lines[6], "| **Launched by** | Sample Researcher, run intake-test-1022, 2026-10-22 |")


class Questions(unittest.TestCase):
    """Refusals and questions: no managed settings, no route, an unanswered question, a name placed by hand."""

    def tearDown(self): self.env.close()

    def test_no_managed_settings_refused(self):
        self.env = Env(managed=False)
        s = SU.Setup(self.env.project, SU.Answers({}), allow_compile=False, render_test=False)
        with self.assertRaises(SU.Refusal) as cm: s.run(until=0)
        self.assertIn("no managed settings file", str(cm.exception)); self.assertFalse(s.done(0))

    def test_no_route_asks_then_refuses(self):
        self.env = Env(route=False)
        s = SU.Setup(self.env.project, SU.Answers({}), allow_compile=False, render_test=False)
        with self.assertRaises(SU.NeedAnswer) as cm: s.run(until=0)
        self.assertEqual(cm.exception.q["qid"], "0.privacy_settings")   # the privacy settings are confirmed first (owner, 2026-10-26)
        self.assertIn("Location metadata", cm.exception.q["prompt"]); self.assertTrue(cm.exception.q.get("explain"))
        s = SU.Setup(self.env.project, SU.Answers({"0.privacy_settings": True}), allow_compile=False, render_test=False)
        with self.assertRaises(SU.NeedAnswer) as cm: s.run(until=0)
        self.assertEqual(cm.exception.q["qid"], "0.route"); self.assertIn("none", cm.exception.q["choices"])
        s = SU.Setup(self.env.project, SU.Answers({"0.privacy_settings": True, "0.route": "none"}), allow_compile=False, render_test=False)
        with self.assertRaises(SU.Refusal): s.run(until=0)
        self.assertFalse(s.done(0))

    def test_unanswered_question_after_a_written_stage(self):
        self.env = Env()
        s = SU.Setup(self.env.project, SU.Answers({"0.privacy_settings": True, "0.continue_without": True, "0.administrator": "Sample Administrator"}), allow_compile=False, render_test=False)
        with self.assertRaises(SU.NeedAnswer) as cm: s.run()
        self.assertTrue(s.done(0)); self.assertEqual(cm.exception.q["qid"], "1.pack_name")
        self.assertEqual(cm.exception.q["default"], "project")     # offered, never taken without an answer

    def test_adverse_rule_is_explained_before_it_is_asked(self):
        self.env = Env()
        a = casebook_answers(self.env.db); a.pop("3.adverse_rule")
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        with self.assertRaises(SU.NeedAnswer) as cm: s.run()
        q = cm.exception.q
        self.assertEqual(q["qid"], "3.adverse_rule")
        for s_ in ("never makes adverse sources more reliable", "scores who is right", "lets a sceptic correct a witness"): self.assertIn(s_, q["explain"])

    def test_nothing_placed_by_hand(self):
        self.env = Env()
        a = casebook_answers(self.env.db); a["4.flags"] = ["An Actor Nobody Detected"]
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        with self.assertRaises(SU.NeedAnswer) as cm: s.run()
        self.assertEqual(cm.exception.q["qid"], "4.flags"); self.assertIn("nothing is placed by hand", cm.exception.q["error"])

    def test_stage_1_never_overwrites_a_pack(self):
        self.env = Env()
        os.makedirs(os.path.join(self.env.project, "packs", "other"))
        with open(os.path.join(self.env.project, "packs", "other", "pack.toml"), "w") as f: f.write('[pack]\nname = "other"\n')
        a = casebook_answers(self.env.db); a["1.pack_name"] = "other"
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False)
        with self.assertRaises(SU.Refusal) as cm: s.run(until=1)
        self.assertIn("never overwrites a pack", str(cm.exception))
        self.assertEqual(LN.read_text(os.path.join(self.env.project, "packs", "other", "pack.toml")), '[pack]\nname = "other"\n')

    def test_stage_2_needs_stage_1(self):
        self.env = Env()
        s = SU.Setup(self.env.project, SU.Answers(casebook_answers(self.env.db)), allow_compile=False, render_test=False)
        s.run(until=0)
        with self.assertRaises(SU.Refusal) as cm: s.stage_2()
        self.assertIn("stage 2 needs stage 1", str(cm.exception))

    def test_text_order_reorder_and_refusal(self):
        self.env = Env()
        a = casebook_answers(self.env.db); a["2.text_order"] = [3, 1]
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        with self.assertRaises(SU.NeedAnswer) as cm: s.run(until=2)
        self.assertEqual(cm.exception.q["qid"], "2.text_order"); self.assertIn("distinct numbers from 1 to 2", cm.exception.q["error"])
        s = SU.Setup(self.env.project, SU.Answers(dict(a, **{"2.text_order": [2]})), allow_compile=False, render_test=False, launcher=lambda x: {})
        s.run(until=2)
        t = load(os.path.join(self.env.project, "setup", "mapping.toml"))["fields"]["text"]
        self.assertEqual((t.get("fallback"), "alternatives" in t), ("media_text", False))

    def test_cli_exit_codes(self):
        self.env = Env()
        af = os.path.join(self.env.base, "answers.json")
        with open(af, "w", encoding="utf-8") as f: json.dump({"answers": {"0.privacy_settings": True, "0.continue_without": True}}, f)
        env = dict(os.environ)
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "ledger", "setup_stages.py"), "run", "--project", self.env.project, "--answers", af,
                            "--no-render-test"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(json.loads(r.stdout)["qid"], "0.administrator")


class HoldSource(unittest.TestCase):
    """Stage 2 from a folder of holds already in the hold schema (phase 7b): the hold schema is the mapping, five holds are verified as
    the dry run, the holds are copied into the project's sources/ and verified again, and the scan runs over them; a hold whose bytes
    no longer match its hold.json is refused."""

    @classmethod
    def setUpClass(cls):
        cls.env = Env()
        first = SU.Setup(cls.env.project, SU.Answers(casebook_answers(cls.env.db)), allow_compile=False, render_test=False)
        first.run(until=2)   # the casebook database held record by record: a folder of holds to take as a source
        cls.holds = os.path.join(cls.env.project, "sources", "db", "casebook")
        cls.scan_db = SU.B.read_json(os.path.join(cls.env.project, "setup", "scan.json"))

    @classmethod
    def tearDownClass(cls): cls.env.close()

    def project(self, answers):
        proj = tempfile.mkdtemp(prefix="ledger-holds-", dir=self.env.base)
        a = casebook_answers(self.env.db); a.update(answers)
        return proj, SU.Setup(proj, SU.Answers(a), allow_compile=False, render_test=False)

    def test_holds_copied_verified_and_scanned(self):
        proj, s = self.project({"2.source": "holds:" + self.holds, "2.name": "casebook-holds"})
        self.assertTrue(SU.is_hold_source("holds:" + self.holds)); self.assertTrue(SU.is_hold_source(self.holds))
        self.assertFalse(SU.is_hold_source(self.env.db))
        s.run(until=2)
        st = load(os.path.join(proj, "setup", "stage-2.toml"))["result"]
        self.assertEqual((st["source"], st["holds"], st["held"]), ("holds", len(SU.hold_folders(self.holds)), len(SU.hold_folders(self.holds))))
        for f in SU.hold_folders(os.path.join(proj, "sources")): self.assertEqual(SU.B.verify_hold(f), [])
        sc = SU.B.read_json(os.path.join(proj, "setup", "scan.json"))
        self.assertEqual(sc["records"], self.scan_db["records"])
        pk = load(os.path.join(proj, "packs", "harrowmere", "pack.toml"))
        self.assertEqual(pk["archives"]["holds"][0]["name"], "casebook-holds")
        self.assertIn("identity", LN.read_text(os.path.join(proj, "setup", "mapping.md")))

    def test_a_changed_hold_is_refused(self):
        bad = os.path.join(self.env.base, "tampered")
        shutil.copytree(self.holds, bad)
        h = SU.hold_folders(bad)[0]
        f = next(x["name"] for x in SU.B.read_json(os.path.join(h, "hold.json"))["files"] if x["role"] != "linked" and x["name"] != "README.md")
        with open(os.path.join(h, f), "a", encoding="utf-8") as fh: fh.write("changed\n")
        proj, s = self.project({"2.source": bad, "2.name": "tampered"})
        with self.assertRaises(SU.Refusal) as cm: s.run(until=2)
        self.assertIn("failed verification", str(cm.exception)); self.assertFalse(s.done(2))


class Renderer(unittest.TestCase):
    def test_identical_to_the_prototype(self):
        proto = os.path.join(ROOT, "wip", "platform-phase4", "render_briefs.py")
        sys.path.insert(0, TOOLS); import packload
        pack = os.path.relpath(packload.pack_dir(), ROOT) if os.path.isdir(packload.pack_dir()) else ""
        run = os.path.join(ROOT, pack, "briefs", "runs", "intake-1008.toml")   # the prototype's own run, in the project that has it
        if not (pack and os.path.isfile(proto) and os.path.isfile(run)): self.skipTest("the prototype or its run is not here (the private project's equivalence check)")
        d = tempfile.mkdtemp(prefix="ledger-briefs-"); self.addCleanup(shutil.rmtree, d, True)
        a, b = os.path.join(d, "proto"), os.path.join(d, "module")
        r = subprocess.run([sys.executable, proto, "--pack", pack, "--run", run, "--only", "operations.md", "intake-", "staged/", "--out", a], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = BR.render(ROOT, pack, run, ["operations.md", "intake-", "staged/"], b)
        self.assertEqual(res["missing"], [])
        fa = sorted(os.path.relpath(os.path.join(dp, f), a) for dp, _, fs in os.walk(a) for f in fs)
        fb = sorted(os.path.relpath(os.path.join(dp, f), b) for dp, _, fs in os.walk(b) for f in fs)
        self.assertEqual(fa, fb)
        for f in fa:
            with open(os.path.join(a, f), "rb") as x, open(os.path.join(b, f), "rb") as y: self.assertEqual(x.read(), y.read(), f)
        self.assertEqual(BR.TOKEN.pattern, r"\{\{(pack|run|ledger)\.([a-z_.]+)\}\}")


class PluginScripts(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ledger-plugin-test-"); self.addCleanup(shutil.rmtree, self.d, True)
        with open(os.path.join(self.d, "ledger.toml"), "w", encoding="utf-8") as f: f.write('[ledger]\nname = "t"\n')
        os.makedirs(os.path.join(self.d, "tools")); shutil.copyfile(os.path.join(TOOLS, "report_check.py"), os.path.join(self.d, "tools", "report_check.py"))

    def hook(self, mode, payload):
        env = dict(os.environ, LEDGER_ROOT=self.d)
        return subprocess.run([sys.executable, os.path.join(PLUGIN, "hooks", "ledger_hook.py"), mode], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_report_hook_blocks_then_lets_go(self):
        rp = os.path.join(self.d, "wip", "t", "report.json"); os.makedirs(os.path.dirname(rp))
        with open(rp, "w") as f: json.dump({"page": "x"}, f)
        payload = {"hook_event_name": "SubagentStop", "agent_id": "a1", "cwd": self.d,
                   "last_assistant_message": "done\n\nreport: wip/t/report.json\nform: attack\n"}
        for i in range(3):
            r = self.hook("report", payload); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["decision"], "block"); self.assertIn(f"check {i + 1} of 3", json.loads(r.stdout)["reason"])
        r = self.hook("report", payload)
        self.assertIn("systemMessage", json.loads(r.stdout))

    def test_hooks_are_inert_outside_their_files(self):
        r = self.hook("verbatim", {"tool_input": {"file_path": os.path.join(self.d, "notes.txt")}, "cwd": self.d})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.hook("report", {"last_assistant_message": "no report line here", "cwd": self.d})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.hook("dbbuild", {"tool_input": {"file_path": os.path.join(self.d, "books", "x.md")}, "cwd": self.d})
        self.assertEqual(r.returncode, 0)

    def test_lock_is_one_writer(self):
        lk = os.path.join(PLUGIN, "scripts", "lock.py"); env = dict(os.environ, LEDGER_ROOT=self.d)
        r1 = subprocess.run([sys.executable, lk, "acquire", "notes", "--run", "a"], capture_output=True, text=True, env=env)
        r2 = subprocess.run([sys.executable, lk, "acquire", "notes", "--run", "b"], capture_output=True, text=True, env=env)
        self.assertEqual((r1.returncode, r2.returncode), (0, 1)); self.assertIn("locked by run a", r2.stdout)
        r3 = subprocess.run([sys.executable, lk, "release", "notes", "--run", "b"], capture_output=True, text=True, env=env)
        r4 = subprocess.run([sys.executable, lk, "release", "notes", "--run", "a"], capture_output=True, text=True, env=env)
        self.assertEqual((r3.returncode, r4.returncode), (1, 0))

    def test_plugin_manifest_and_agents(self):
        pj = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8"))
        self.assertEqual(pj["name"], "ledger")
        hooks = json.load(open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8"))
        self.assertIn("hooks", hooks); self.assertEqual(set(hooks["hooks"]), {"PostToolUse", "SubagentStop"})
        for name, model, effort in [("reader", "opus", "high"), ("writer", "opus", "high"), ("finisher", "opus", "high"), ("builder", "opus", "high"),
                                    ("attacker", "opus", "high"), ("reviser", "opus", "high"), ("probe", "haiku", "low")]:
            head = LN.read_text(os.path.join(PLUGIN, "agents", f"{name}.md")).split("---")[1]
            self.assertIn(f"name: {name}", head); self.assertIn(f"model: {model}", head); self.assertIn(f"effort: {effort}", head)
        try:
            import yaml
        except ImportError:
            return
        import glob
        for p in glob.glob(os.path.join(PLUGIN, "agents", "*.md")) + glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")):
            fm = yaml.safe_load(LN.read_text(p).split("---")[1])   # a ": " in an unquoted value would fail here, and Claude Code would drop the file's fields
            self.assertTrue(fm.get("description"), p)


class SlotsAndPackKeys(unittest.TestCase):
    """Every brief slot and pack section is asked for by one stage (phase 6a's finding): the grouped answers and the single keys reach
    pack.toml and slots.toml, and a key outside the stage's sections is refused."""

    def tearDown(self):
        if getattr(self, "env", None): self.env.close()

    def test_every_core_slot_has_a_stage(self):
        defaults = load(os.path.join(PLUGIN, "templates", "briefs", "slots-default.toml"))["slots"]
        self.assertEqual(sorted(set(defaults) - set(SU.SLOT_STAGE)), [])
        named = [s for secs in SU.PACK_SECTIONS.values() for s in secs]
        self.assertEqual(len(named), len(set(named)))                      # one owner per section
        for n, keys in SU.PACK_KEYS.items():
            for k, _, _ in keys: self.assertIn(k.split(".")[0], SU.PACK_SECTIONS[n], k)

    def test_answers_reach_the_pack(self):
        self.env = Env()
        a = casebook_answers(self.env.db)
        a["4.pack.actors.rows_key"] = "party_rows"                           # a single key wins over the grouped answer
        a["7.pack"] = {"archive_tool": {"viewer_rule": "route by named viewer"}, "catalysts.register": "research/first-telling-register.md"}
        a["7.slot.exemplars.document"] = "books/lisle-memo-2015.md (a document set)"
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        s.run(until=7)
        pk = load(os.path.join(self.env.project, "packs", "harrowmere", "pack.toml"))
        sl = load(os.path.join(self.env.project, "packs", "harrowmere", "briefs", "slots.toml"))["slots"]
        self.assertEqual((pk["objects"]["register"], pk["objects"]["watch_name"]), ("research/core-sample-register.md", "core sample watch"))
        self.assertEqual((pk["actors"]["findings_heading"], pk["actors"]["rows_key"]), ("Parties and blocs", "party_rows"))
        self.assertEqual(pk["archive_tool"], {"viewer_rule": "route by named viewer"})      # a pack's own section: stage 7's
        self.assertEqual(pk["catalysts"]["register"], "research/first-telling-register.md")
        self.assertEqual(pk["catalysts"]["threshold_date"], "2017-10-09")                   # deep-merged: the stage's own keys kept
        self.assertEqual((sl["reference_objects.watch_name"], sl["actor_register.findings_heading"]), ("core sample watch", "Parties and blocs"))
        self.assertEqual(sl["exemplars.document"], "books/lisle-memo-2015.md (a document set)")
        st4 = load(os.path.join(self.env.project, "setup", "stage-4.toml"))["answers"]
        self.assertIn("4.pack.actors.rows_key", st4)

    def test_a_key_outside_the_stage_is_refused(self):
        self.env = Env()
        a = casebook_answers(self.env.db); a["3.pack"] = {"objects.register": "x.md"}
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        with self.assertRaises(SU.NeedAnswer) as cm: s.run(until=3)
        self.assertEqual(cm.exception.q["qid"], "3.pack"); self.assertIn("audit", cm.exception.q["error"])
        a["3.pack"] = {"pack.name": "other"}
        s = SU.Setup(self.env.project, SU.Answers(a), allow_compile=False, render_test=False, launcher=lambda x: {})
        with self.assertRaises(SU.NeedAnswer): s.run(until=3)


def walk(d, path=()):
    """(path, value) for every string in a pack table; a path is a tuple of keys and list indexes."""
    if isinstance(d, dict):
        for k, v in d.items(): yield from walk(v, path + (k,))
    elif isinstance(d, list):
        for i, v in enumerate(d): yield from walk(v, path + (i,))
    elif isinstance(d, str): yield path, d


def at(d, path):
    for p in path:
        try: d = d[p]
        except (KeyError, IndexError, TypeError): return None
    return d


def pack_file_keys(pk, pack_dir):
    """[(path, value, [file tails])] for every pack value that names a file or folder of its own pack (pack.root excluded; the files
    setup writes from the answers excluded)."""
    root = pk["pack"]["root"].rstrip("/") + "/"; out = []
    for path, v in walk(pk):
        if path == ("pack", "root") or not v.startswith(root): continue
        tail = v[len(root):]; src = os.path.join(pack_dir, *tail.split("/"))
        if tail in SU.FROM_ANSWERS or not os.path.exists(src): continue
        if os.path.isdir(src):
            tails = sorted(os.path.relpath(os.path.join(dp, f), pack_dir).replace(os.sep, "/") for dp, dns, fs in os.walk(src)
                           if "__pycache__" not in dp for f in fs)
        else: tails = [tail]
        out.append((path, v, tails))
    return out


def bundle_dirs():
    """The release bundles this project can see (build_bundle.py's layout: plugin/ and example-pack/ side by side): the folder above
    the plugin these tests exercise, and the folder above the plugin setup stage 0 recorded (an installed project's setup/stage-0.toml)."""
    plugins = [PLUGIN]
    st0 = os.path.join(ROOT, "setup", "stage-0.toml")
    if os.path.isfile(st0):
        c = load(st0).get("result", {}).get("plugin")
        if c: plugins.append(c)
    out = []
    for p in plugins:
        d = os.path.dirname(os.path.abspath(p))
        if os.path.isdir(os.path.join(d, "example-pack")) and d not in out: out.append(d)
    return out


def is_example_source(pack_dir):
    """Whether this project's packs/<name> is the example pack's source (the private project), not a pack this project's own setup
    wrote from the example (an installed project: setup/stage-1.toml names the pack)."""
    st1 = os.path.join(ROOT, "setup", "stage-1.toml")
    return not (os.path.isfile(st1) and load(st1).get("result", {}).get("pack_name") == os.path.basename(pack_dir))


def example_pack():
    """The pack the import test re-creates: $LEDGER_EXAMPLE_PACK, else the bundle's example pack (example-pack/pilot beside the plugin),
    else this project's packs/pilot only where it is the example's source (7b2 item 1: an installed project's own setup-generated
    packs/pilot is never taken for the example)."""
    cands = [os.environ.get("LEDGER_EXAMPLE_PACK")] + [os.path.join(b, "example-pack", "pilot") for b in bundle_dirs()]
    own = os.path.join(ROOT, "packs", "pilot")
    if is_example_source(own): cands.append(own)
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "pack.toml")): return c
    return None


def import_answers(src, skip=("circles.adverse_rule",)):
    """Every stage's N.pack and N.slots from a source pack: each section's keys as the pack holds them, the values that name the pack's
    own files given as absolute paths (so setup imports them). `skip`: keys whose form setup writes itself (the adverse rule, a boolean)."""
    pk = load(os.path.join(src, "pack.toml")); root = pk["pack"]["root"].rstrip("/") + "/"
    def absolute(v):
        if isinstance(v, str): return os.path.join(src, *v[len(root):].split("/")) if v.startswith(root) else v
        if isinstance(v, list): return [absolute(x) for x in v]
        if isinstance(v, dict): return {k: absolute(x) for k, x in v.items()}
        return v
    named = {s for secs in SU.PACK_SECTIONS.values() for s in secs}
    slots = load(os.path.join(src, "briefs", "slots.toml")).get("slots", {}) if os.path.isfile(os.path.join(src, "briefs", "slots.toml")) else {}
    out = {}
    for n in range(1, 8):
        secs = list(SU.PACK_SECTIONS[n]) + ([s for s in pk if s not in named] if n == SU.OTHER_SECTIONS_STAGE else [])
        out[f"{n}.pack"] = {f"{s}.{k}": absolute(v) for s in secs for k, v in (pk.get(s) or {}).items()
                            if f"{s}.{k}" not in SU.PACK_FIXED and f"{s}.{k}" not in skip}
        out[f"{n}.slots"] = {k: v for k, v in slots.items() if SU.SLOT_STAGE.get(k) == n and k != "name"}
    return out


class FreshPack(unittest.TestCase):
    """A pack from the answers alone (the casebook answers; no pack to import from): every file a key names is generated by the stage
    that owns it, every slot is the pack's own (zero from core defaults) and the pack check passes; the baseline is frozen after stage 7."""

    @classmethod
    def setUpClass(cls):
        cls.env = Env()
        cls.s = SU.Setup(cls.env.project, SU.Answers(casebook_answers(cls.env.db)), launcher=lambda spec: {"status": "launched (test stub)"},
                         allow_compile=False)
        cls.done = cls.s.run()
        cls.pk = load(os.path.join(cls.env.project, "packs", "harrowmere", "pack.toml"))

    @classmethod
    def tearDownClass(cls): cls.env.close()

    def p(self, *a): return os.path.join(self.env.project, *a)

    def test_pack_check_passes_with_zero_slots_from_core_defaults(self):
        self.assertEqual(self.done, list(range(9)))
        with open(self.p("setup", "pack-check.json"), encoding="utf-8") as f: chk = json.load(f)
        self.assertTrue(chk["ok"], chk["problems"])
        self.assertEqual(chk["slots_from_defaults"], 0)
        self.assertGreater(chk["slots_from_pack"], 30)
        self.assertEqual(chk["packload"]["skeleton_forms"], 0)   # no exemplar yet: the core forms

    def test_every_file_a_key_names_exists(self):
        own = [(path, v) for path, v in walk(self.pk) if v.startswith("packs/harrowmere/") and path != ("pack", "root")]
        self.assertGreater(len(own), 15)
        for path, v in own: self.assertTrue(os.path.exists(self.p(*v.split("/"))), f"{'.'.join(map(str, path))} = {v}")
        for key in ("actors.register", "objects.register"):   # the register pages, generated in the core form when absent
            self.assertTrue(os.path.isfile(self.p(*SU._get_dotted(self.pk, key).split("/"))), key)
        for f in ("people.txt", "organisations.txt", "terms.txt", "actor-polity.txt", "catalyst-keywords.txt", "pir-terms.txt", "README.md"):
            self.assertTrue(os.path.isfile(self.p("packs", "harrowmere", "keywords", f)), f)
        self.assertIn("Petra Vanecek", LN.read_text(self.p("packs", "harrowmere", "keywords", "people.txt")))
        self.assertEqual(self.pk["canon"]["schemes"], ["packs/harrowmere/canon/schemes/charter-1888.json"])
        with open(self.p("packs", "harrowmere", "canon", "schemes", "charter-1888.json"), encoding="utf-8") as f: sch = json.load(f)
        self.assertEqual(sch["scheme"]["kind"], "headings")
        self.assertFalse(os.path.exists(self.p("setup", "imports.json")))
        gen = [g for n in range(1, 8) for g in load(self.p("setup", f"stage-{n}.toml")).get("generated", {}).get("files", [])]
        self.assertIn("research/actor-register.md", gen); self.assertIn("packs/harrowmere/skeleton-forms.toml", gen)

    def test_register_pages_parse_empty(self):
        act, stm = LN.actor_register(self.p(*self.pk["actors"]["register"].split("/")))
        self.assertEqual((act, stm), ([], []))   # the candidates table is not a register table
        rows = LN.register_rows(self.p(*self.pk["objects"]["register"].split("/")), "## Register",
                                ("#", "video", "timestamp", "who", "object", "match", "strength"), 7)
        self.assertEqual(rows, [])

    def test_baseline_frozen_after_stage_7(self):
        self.assertTrue(load(self.p("setup", "stage-7.toml"))["result"]["baseline"].startswith("frozen"))
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "baseline.py"), "--check"], cwd=self.env.project, capture_output=True, text=True,
                           env=dict(os.environ, LEDGER_ROOT=self.env.project))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipUnless(example_pack(), "no example pack to import from (packs/pilot, the bundle's example-pack/pilot or $LEDGER_EXAMPLE_PACK)")
class PackByImport(unittest.TestCase):
    """The example pack re-created by import: every stage answered with the example pack's own keys and slots (its files named by
    absolute path), stage 2 from the casebook database. Every file a key of the example pack names is copied byte for byte, the key
    names it at the same place, the provenance is recorded, and the pack check passes."""

    @classmethod
    def setUpClass(cls):
        cls.src = example_pack(); cls.src_pk = load(os.path.join(cls.src, "pack.toml")); cls.name = cls.src_pk["pack"]["name"]
        cls.env = Env()
        a = casebook_answers(cls.env.db); a["1.pack_name"] = cls.name
        a.update(import_answers(cls.src))
        cls.s = SU.Setup(cls.env.project, SU.Answers(a), launcher=lambda spec: {"status": "launched (test stub)"}, allow_compile=False)
        cls.done = cls.s.run()
        cls.pk = load(os.path.join(cls.env.project, "packs", cls.name, "pack.toml"))

    @classmethod
    def tearDownClass(cls): cls.env.close()

    def p(self, *a): return os.path.join(self.env.project, *a)

    def test_every_file_a_key_names_is_byte_equal(self):
        self.assertEqual(self.done, list(range(9)))
        keys = pack_file_keys(self.src_pk, self.src)
        self.assertGreater(len(keys), 15)
        compared = 0
        for path, v, tails in keys:
            got = at(self.pk, path)
            self.assertEqual(got, v, f"{'.'.join(map(str, path))}: the key names the same place in the new pack")
            for t in tails:
                with open(os.path.join(self.src, *t.split("/")), "rb") as f: want = f.read()
                with open(self.p("packs", self.name, *t.split("/")), "rb") as f: self.assertEqual(f.read(), want, t)
                compared += 1
        self.assertGreater(compared, 25)

    def test_provenance_recorded(self):
        with open(self.p("setup", "imports.json"), encoding="utf-8") as f: imp = json.load(f)
        files = {k: v for k, v in imp.items() if v["kind"] == "file"}
        self.assertTrue(files)
        for rel, rec in files.items():
            with open(self.p(*rel.split("/")), "rb") as f: self.assertEqual(__import__("hashlib").sha256(f.read()).hexdigest(), rec["sha256"], rel)
            self.assertTrue(rec["key"] and rec["stage"] in range(1, 8))
        staged = [r for n in range(1, 8) for r in load(self.p("setup", f"stage-{n}.toml")).get("imported", [])]
        self.assertEqual(sorted({r["to"] for r in staged}), sorted(imp))

    def test_slots_carried_and_pack_check_passes(self):
        src_slots = load(os.path.join(self.src, "briefs", "slots.toml"))["slots"]
        got = load(self.p("packs", self.name, "briefs", "slots.toml"))["slots"]
        self.assertEqual({k: got.get(k) for k in src_slots if k in SU.SLOT_STAGE}, {k: v for k, v in src_slots.items() if k in SU.SLOT_STAGE})
        with open(self.p("setup", "pack-check.json"), encoding="utf-8") as f: chk = json.load(f)
        self.assertTrue(chk["ok"], chk["problems"]); self.assertEqual(chk["slots_from_defaults"], 0)

    def test_slot_named_files_and_seeds_byte_equal(self):
        """7b2 item 2: the files the source pack's slot texts name (registers/ledgered-speakers.md, named by no key) arrive with the
        key-named ones, and the seeds are the source's, never generated empty over it."""
        same_place(self, self.src, self.p("packs", self.name))

    def test_actor_register_in_the_slots_row_shape(self):
        register_shape(self, self.p(*self.pk["actors"]["register"].split("/")), load(self.p("packs", self.name, "briefs", "slots.toml"))["slots"])


# the six files pilot-1023 found missing or generated empty in an installed pilot (REPORT.md section 2, finding 2)
SIX = ["codebook/argot.md", "keywords/id-patterns.tsv", "registers/ledgered-speakers.md", "registers/order-of-battle-seed.md",
       "seeds/narratives.md", "seeds/theses.json"]


def same_place(tc, src, dest):
    n = 0
    for t in SIX:
        s = os.path.join(src, *t.split("/"))
        if not os.path.isfile(s): continue
        with open(s, "rb") as f: want = f.read()
        d = os.path.join(dest, *t.split("/"))
        tc.assertTrue(os.path.isfile(d), t)
        with open(d, "rb") as f: tc.assertEqual(f.read(), want, t)
        n += 1
    tc.assertGreaterEqual(n, 5)


def register_shape(tc, register, slots):
    """7b2 item 23: the generated actor register's first table is the slot's actor row shape (else the core header), and its polity
    statement table is ledger integrate's (tools/ledger/cli.py STATEMENT_HEADER)."""
    from ledger import cli
    want = SU.actor_row_shape(slots.get("actor_register")) or cli.CORE_ACTOR_HEADER
    heads = [LN.split_row(l) for l in LN.read_lines(register) if l.startswith("| #")]
    tc.assertEqual(heads[0], want)
    tc.assertIn(cli.STATEMENT_HEADER, heads)
    tc.assertEqual(LN.actor_register(register), ([], []))


@unittest.skipUnless(example_pack(), "no example pack to import from (packs/pilot, the bundle's example-pack/pilot or $LEDGER_EXAMPLE_PACK)")
class ImportBeyondTheKeys(unittest.TestCase):
    """7b2 item 2: answers that name the source pack through one key only (the lens file, by absolute path) and give the source's slot
    wording, every other key left to setup (as the older pilot answers did): setup still brings every pack-relative path the source's
    slot texts and pack.toml name, and imports its seeds instead of generating them empty."""

    @classmethod
    def setUpClass(cls):
        cls.src = example_pack(); cls.name = load(os.path.join(cls.src, "pack.toml"))["pack"]["name"]
        cls.env = Env()
        a = casebook_answers(cls.env.db); a["1.pack_name"] = cls.name
        names_file = lambda v: any(s.startswith(cls.src + os.sep) for _, s in walk({"v": v}))
        for k, v in import_answers(cls.src).items():
            if k.endswith(".pack"): v = {kk: vv for kk, vv in v.items() if kk.startswith("lenses.") or not names_file(vv)}
            a[k] = v
        cls.s = SU.Setup(cls.env.project, SU.Answers(a), launcher=lambda spec: {"status": "stub"}, allow_compile=False, render_test=False)
        cls.done = cls.s.run(until=7)

    @classmethod
    def tearDownClass(cls): cls.env.close()

    def p(self, *a): return os.path.join(self.env.project, *a)

    def test_six_files_byte_equal(self):
        self.assertEqual(self.done, list(range(8)))
        same_place(self, self.src, self.p("packs", self.name))

    def test_seeds_not_generated_and_provenance_recorded(self):
        gen1 = load(self.p("setup", "stage-1.toml")).get("generated", {}).get("files", [])
        for t in ("seeds/narratives.md", "seeds/theses.json"):
            if os.path.isfile(os.path.join(self.src, *t.split("/"))): self.assertNotIn(f"packs/{self.name}/{t}", gen1)
        with open(self.p("setup", "imports.json"), encoding="utf-8") as f: imp = json.load(f)
        rec = imp[f"packs/{self.name}/registers/ledgered-speakers.md"]
        self.assertEqual((rec["named_in"], rec["key"]), ("briefs/slots.toml", "slot speaker_ledgers"))
        for rel, r in imp.items():
            if r["kind"] != "file": continue
            with open(self.p(*rel.split("/")), "rb") as f: self.assertEqual(__import__("hashlib").sha256(f.read()).hexdigest(), r["sha256"], rel)
        staged = [r for n in range(1, 8) for r in load(self.p("setup", f"stage-{n}.toml")).get("imported", [])]
        self.assertEqual(sorted({r["to"] for r in staged}), sorted(imp))

    def test_z_an_edited_pack_file_is_kept_on_reentry(self):
        rel = f"packs/{self.name}/registers/ledgered-speakers.md"
        with open(self.p(*rel.split("/")), "a", encoding="utf-8") as f: f.write("\nthe group's own line\n")
        s = SU.Setup(self.env.project, SU.Answers(dict(self.s.answers.data)), launcher=lambda spec: {"status": "stub"}, allow_compile=False, render_test=False)
        s.rerun(4)
        self.assertIn("the group's own line", LN.read_text(self.p(*rel.split("/"))))
        kept = load(self.p("setup", "stage-4.toml")).get("import_kept", [])
        self.assertIn(rel, [k["to"] for k in kept])


class ActorRowShape(unittest.TestCase):
    """7b2 item 23: the actor row shape is the first backticked table row of the slot that is not the statement shape."""

    def test_shapes(self):
        from ledger import cli
        stm = "`| " + " | ".join(cli.STATEMENT_HEADER) + " |`"
        pilot = "`| # | Actor as named (teller's spelling) | Kind | Polity | Teller and note row | Firsthand / relayed (chain) | Confidence |`"
        self.assertIsNone(SU.actor_row_shape("return `actor_rows` in the register's row shape, and `polity_statements` as " + stm))
        self.assertEqual(SU.actor_row_shape("rows " + pilot + " and statements " + stm)[1], "Actor as named (teller's spelling)")
        self.assertEqual(SU.actor_row_shape("statements first " + stm + ", then rows " + pilot)[3], "Polity")
        self.assertIsNone(SU.actor_row_shape("a table `| a | b |` that is no actor table"))
        self.assertIsNone(SU.actor_row_shape(None))

    def test_fresh_pack_register(self):
        env = Env()
        try:
            s = SU.Setup(env.project, SU.Answers(casebook_answers(env.db)), launcher=lambda spec: {}, allow_compile=False, render_test=False)
            s.run(until=4)
            pk = load(os.path.join(env.project, "packs", "harrowmere", "pack.toml"))
            register_shape(self, os.path.join(env.project, *pk["actors"]["register"].split("/")),
                           load(os.path.join(env.project, "packs", "harrowmere", "briefs", "slots.toml"))["slots"])
        finally: env.close()


class ExamplePackOrder(unittest.TestCase):
    """7b2 item 1: $LEDGER_EXAMPLE_PACK, then the bundle's example-pack/pilot (beside the plugin, or beside the plugin setup stage 0
    recorded), then the project's packs/pilot only where it is the example's source (no setup of its own wrote it)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ledger-example-order-"); g = globals()
        self.saved = {k: g[k] for k in ("ROOT", "PLUGIN")}; self.env = os.environ.pop("LEDGER_EXAMPLE_PACK", None)
        self.root = os.path.join(self.tmp, "project"); self.bundle = os.path.join(self.tmp, "bundle")
        for d in (os.path.join(self.root, "packs", "pilot"), os.path.join(self.bundle, "example-pack", "pilot"), os.path.join(self.bundle, "plugin")):
            os.makedirs(d)
            if "pilot" in d:
                with open(os.path.join(d, "pack.toml"), "w") as f: f.write('[pack]\nname = "pilot"\n')
        os.makedirs(os.path.join(self.root, "setup"))
        g["ROOT"] = self.root; g["PLUGIN"] = os.path.join(self.tmp, "elsewhere", "plugin")

    def tearDown(self):
        globals().update(self.saved)
        if self.env is not None: os.environ["LEDGER_EXAMPLE_PACK"] = self.env
        shutil.rmtree(self.tmp, True)

    def st(self, n, body):
        with open(os.path.join(self.root, "setup", f"stage-{n}.toml"), "w") as f: f.write(body)

    def test_order(self):
        own, ex = os.path.join(self.root, "packs", "pilot"), os.path.join(self.bundle, "example-pack", "pilot")
        self.assertEqual(example_pack(), own)                                   # the source project: no setup wrote packs/pilot
        self.st(1, '[result]\npack_name = "pilot"\n')
        self.assertIsNone(example_pack())                                       # an installed project, no bundle in sight
        self.st(0, f'[result]\nplugin = "{os.path.join(self.bundle, "plugin")}"\n')
        self.assertEqual(example_pack(), ex)                                    # the bundle through stage 0's plugin path
        os.remove(os.path.join(self.root, "setup", "stage-1.toml"))
        self.assertEqual(example_pack(), ex)                                    # the bundle before the project's own
        os.environ["LEDGER_EXAMPLE_PACK"] = own
        try: self.assertEqual(example_pack(), own)
        finally: os.environ.pop("LEDGER_EXAMPLE_PACK")


if __name__ == "__main__":
    unittest.main()
