export const meta = {
  name: 'staged-intake',
  description: 'Intake of one source per task in short-lived agents, every agent guarded (resume from wip on death, bisect-block after the last resume), a per-task cap on cache-read by records (maxRecords) that stops that task alone. The shipped form, unit writers (intakeForm "unit-writers", the default from 2026-10-25): unit writers in sequence over unit ranges of about 10,000 to 20,000 words write the claims-ledger and audit rows with the unit in context (quotations pasted from ledger quote) -> the parts gate after each (script) -> the assembly (script) -> gate 2 -> [check, optional] -> writer B, the sections (every other section, from the units and the finished ledger) -> gate 2 -> finish (build_db, onboard_check, note_fill, cross-checks, report_check) -> gate 2 again -> sample (every intake, from 2026-10-25: twenty claims rows drawn by seed, read by one Opus reader five ways, the tally written to report.json sample_reading; at the threshold the check phase over the whole ledger, gate 2, and a redraw read once more). The staged form (intakeForm "staged"): read (findings per unit within the item allowance) -> gate 1 (script) -> writer A, the ledger, from the findings -> gate 2 -> [check] -> writer B -> gate 2 -> finish -> gate 2 -> sample. The check (check true, off by default): every claims row read against its span in the order of attention, within checkBudget rows when given, corrected in place, gate 2 after it',
  whenToUse: 'Every document, text, adverse or video intake from 2026-10-16 (tools/intake-staged.md; the split write and the item allowance from 2026-10-23). args: {tasks:[{key, wip, note, form, units, words, source?, label?, ranges?, maxRecords?, recordsBefore?, prompts?:{read,write_a,write_unit,check,write_b,write,finish}, check?, checkBudget?, intakeForm?}], phasesDir?, model?, effort?, gateModel?, maxResumes?, maxGateResumes?, fanoutWords? (default 20000 in the unit-writers form, 35000 in the staged form), readerUnits? (default: sized to fanoutWords), python? (the interpreter of the probes; default the project venv when present, else python3), splitWrite? (default true; false = one writer, prompt key write), mergeWriteFinish?, bisectScript?, root?, intakeForm? ("unit-writers" default from 2026-10-25 | "staged"; also per task, where t.form "unit-writers" or "staged" is accepted as the same: t.form is otherwise the skeleton form, document or video), check? (default false; also per task), checkBudget? (rows the checker reads in the order of attention; default every row; also per task), sample? (default true; false skips the sample phase; also per task), sampleThreshold? (faults of meaning in the twenty that send a note to the check phase; default the pack [intake] sample_threshold, which the draw reports, else 3)}; per task for the unit writers: unitNumbers? (the unit numbers of the manifest when they are not 1 to units), unitRanges? (explicit [[first, last]] ranges); in the unit-writers form fanoutWords defaults to 20,000 (a source over it gets ceil(words / 20,000) writers, so each writes about 10,000 to 20,000 words) and readerUnits, when given, is the units per unit writer. Run with scriptPath tools/workflows/staged-intake.js',
  phases: [
    { title: 'Read', detail: 'one reader per unit range; findings/NNN.md per unit' },
    { title: 'Gate 1', detail: 'tools/intake_gate.py --findings, run by a Haiku probe; readers resumed on failing units' },
    { title: 'Write A', detail: 'writer A, the ledger: metadata, nothing-to-row line, claims ledger, forthrightness audit; ledger-notes.md' },
    { title: 'Write B', detail: 'writer B, the sections: every other section from the findings and the finished ledger by line search' },
    { title: 'Write', detail: 'one writer (splitWrite false): the note from findings, skeleton, context pack and timeline candidates' },
    { title: 'Write units', detail: 'the unit-writers form: one writer per unit range, in sequence, writes parts/u<NNN>-ledger.md and u<NNN>-audit.md with the unit in context' },
    { title: 'Gate parts', detail: 'tools/intake_gate.py --note-parts after each unit writer, run by a Haiku probe; the writer resumed on failure' },
    { title: 'Assemble', detail: 'tools/assemble_parts.py builds the note from the skeleton and the parts (a script, run by a Haiku probe)' },
    { title: 'Check', detail: 'optional (check true): every claims row read against its span in the order of attention and corrected (check.md); gate 2 after it' },
    { title: 'Gate 2', detail: 'tools/intake_gate.py --note after writer A, after writer B and after finish' },
    { title: 'Finish', detail: 'build_db, onboard_check, note_fill, cross-checks, report_check, report JSON' },
    { title: 'Sample', detail: 'ledger sample draw (a script), one Opus reader under phasesDir/sample.md, ledger sample tally into report.json sample_reading; at the threshold the check phase, gate 2 and a redraw' },
    { title: 'Resume', detail: 'dead agents restarted from their checkpoint' },
    { title: 'Probe', detail: 'bisect-block over the unit a twice-dead agent was handling' },
    { title: 'Usage', detail: 'a Haiku probe reads the task\'s cache-read by records (tools/agent_usage.py --task --records) against maxRecords' },
  ],
}
// Modelled on tools/workflows/staged-page.js (phases as short-lived agents) and guarded-intake.js (the blocked-output guard).
// The script has no filesystem access: the orchestrator pre-cuts the units and passes each task's unit count and word count in
// args (from units/manifest.md), and the gates run as Haiku probe agents that execute the script and relay its JSON line.
// The project root: args.root, else none (every path relative, resolved against the session's working folder, the project root;
// the workflow runtime has no filesystem or path API, so the script cannot find its own folder). Never a literal path (2026-10-22).
const ROOT = args.root || ''
const AT = p => ROOT ? `${ROOT}/${p}` : p
const model = args.model || 'opus'
const effort = args.effort || 'high'
const gateModel = args.gateModel || 'haiku'
const maxResumes = args.maxResumes ?? 2
const maxGateResumes = args.maxGateResumes ?? 2
// a source over about 35,000 words gets two or more readers (pilot defect 25, 7b2 2026-10-23); in the unit-writers form a source
// over 20,000 words gets two or more unit writers, each with about 10,000 to 20,000 words in context (2026-10-25)
const fanoutOf = t => args.fanoutWords ?? (formOf(t) === 'unit-writers' ? 20000 : 35000)
const readerUnits = args.readerUnits ?? null        // units per reader (or unit writer); by default sized per task to the fan-out at its own words per unit
// the interpreter of the gate and usage probes (pilot defect 24): args.python, else the project's venv when the install made one,
// else python3; the runtime cannot test for a file, so the probe is told the rule
const PY = args.python || 'python3'
const PYRULE = args.python ? '' : `\nThe interpreter: if ${AT('.ledger/venv/bin/python3')} exists (on Windows ${AT('.ledger/venv/Scripts/python.exe')}), run the command with that file in place of \`python3\` (the project's own environment, made by the install); otherwise run it as written.`
const phasesDir = args.phasesDir || 'wip/intake-staged/phases'
const bisectScript = args.bisectScript || AT('tools/workflows/bisect-block.js')
const splitWrite = args.splitWrite ?? true          // writer A (the ledger) then writer B (the sections), 2026-10-23
const pad = n => String(n).padStart(3, '0')
// the intake form: unit writers by default from 2026-10-25 (wip/quote-tool-adoption/), the staged form on request (2026-10-24)
const formOf = t => (t.intakeForm || (t.form === 'unit-writers' || t.form === 'staged' ? t.form : null) || args.intakeForm || 'unit-writers')
const checkOf = t => !!(t.check ?? args.check)
const checkBudgetOf = t => t.checkBudget ?? args.checkBudget ?? null
// the sample reading (2026-10-25): on every intake unless sample is false on the task or in args
const sampleOf = t => (t.sample ?? args.sample) !== false
// a JSON argument for a shell command in single quotes: an apostrophe inside it becomes a typographic one
const shellJson = v => `'${JSON.stringify(v).replace(/'/g, '\u2019')}'`

const GATE = { type: 'object', properties: { ok: { type: 'boolean' }, failing_units: { type: 'array', items: { type: 'string' } }, uncited_units: { type: 'array', items: { type: 'string' } },
  fails: { type: 'number' }, warns: { type: 'number' }, summary: { type: 'string' }, report: { type: 'string' } }, required: ['ok', 'summary'] }
const READ = { type: 'object', properties: { units_done: { type: 'number' }, units: { type: 'string' }, blocked_passages: { type: 'array' }, notes: { type: 'string' } }, required: ['units_done', 'blocked_passages'] }
const WRITE = { type: 'object', properties: { file: { type: 'string' }, words: { type: 'number' }, claims_rows: { type: 'number' }, parts: { type: 'number' }, verbatim_check: { type: 'string' }, blocked_passages: { type: 'array' }, notes: { type: 'string' } }, required: ['file', 'claims_rows', 'blocked_passages'] }

const PARTS_GATE = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, report: { type: 'string' }, rows: { type: 'string' }, audit_rows: { type: 'string' },
  last_row: { type: ['number', 'null'] }, last_audit_row: { type: ['number', 'null'] }, failing_units: { type: 'array', items: { type: 'string' } }, uncited_units: { type: 'array', items: { type: 'string' } },
  fails: { type: 'number' }, warns: { type: 'number' } }, required: ['ok', 'summary'] }
const WRITE_UNIT = { type: 'object', properties: { units: { type: 'string' }, rows: { type: 'string' }, audit_rows: { type: 'string' }, parts: { type: 'array', items: { type: 'string' } },
  verbatim_check: { type: 'string' }, nothing_to_row: { type: 'array', items: { type: 'object', properties: { unit: { type: 'string' }, reason: { type: 'string' } } } },
  blocked_passages: { type: 'array' }, notes: { type: 'string' } }, required: ['units', 'rows', 'nothing_to_row', 'blocked_passages'] }
const ASSEMBLE = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, claims_rows: { type: 'number' }, audit_rows: { type: 'number' }, words: { type: 'number' } }, required: ['ok', 'summary'] }
const CHECK = { type: 'object', properties: { rows_read: { type: 'number' }, corrected: { type: 'number' },
  by_judgement: { type: 'object', properties: { verbatim: { type: 'number' }, support: { type: 'number' }, grain: { type: 'number' }, class_move: { type: 'number' }, chain: { type: 'number' } } },
  split_rows: { type: 'array', items: { type: 'string' } }, unsupported: { type: 'array' }, outside_matter: { type: 'array' }, log: { type: 'string' }, notes: { type: 'string' } },
  required: ['rows_read', 'corrected'] }
const DRAW = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, file: { type: 'string' }, rows: { type: 'number' }, total: { type: 'number' }, seed: { type: 'number' }, threshold: { type: 'number' } }, required: ['ok', 'summary'] }
const SAMPLE = { type: 'object', properties: { rows: { type: 'number' }, sound: { type: 'number' }, formal: { type: 'number' }, meaning: { type: 'number' },
  by_owner: { type: 'object', properties: { reader: { type: 'number' }, writer: { type: 'number' }, form: { type: 'number' } } }, meaning_rows: { type: 'array', items: { type: ['string', 'number'] } },
  files: { type: 'array', items: { type: 'string' } } }, required: ['rows', 'sound', 'formal', 'meaning', 'by_owner', 'meaning_rows', 'files'] }
const TALLY = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, rows: { type: 'number' }, sound: { type: 'number' }, formal: { type: 'number' }, meaning: { type: 'number' },
  meaning_rows: { type: 'array', items: { type: ['string', 'number'] } }, threshold: { type: 'number' }, over_threshold: { type: 'boolean' }, action: { type: 'string' } }, required: ['ok', 'summary'] }
const USAGE = { type: 'object', properties: { ok: { type: 'boolean' }, records: { type: 'number' }, agents: { type: 'number' }, run: { type: 'string' }, summary: { type: 'string' } }, required: ['ok', 'records', 'summary'] }

function resumeText(prompt, wip, n, what) {
  return prompt + `\n\nRESUME ${n} of ${maxResumes} (standing rule, tools/filter-blocks.md section 6): the previous agent on this task died; its output was refused by an API content filter or ended in a terminal API error, cause unknown. Continue from ${wip}/progress.md and ${what}; do not redo recorded work. Before every large output copy the unit in hand by shell to ${wip}/current-unit.md and add one line to progress.md naming it and where its output goes, so a further death can be bisected without you. Keep output units small and never pass a fetched text through your own output: copy files by shell.`
}

// the per-task cap (2026-10-23): the task's cache-read by records, the measure tools/agent_usage.py reports, read by a Haiku probe
// that runs agent_usage.py --task <key> --records (the script has no filesystem and agent() returns no usage). Checked between
// phases and inside the guard before each resume and each gate fix; past t.maxRecords that task alone stops. No maxRecords, no
// probe. t.recordsBefore adds what an earlier run of the same task spent (a task resumed in a new run).
const probes = {}, lastRecords = {}   // per task key: usage probes run, the last figure read (the args are not mutated)
const checkOut = {}                   // per task key: the check phase's unsupported rows and outside matter, for writer B and the finisher
async function overCap(t, where) {
  if (!t || !t.maxRecords) return null
  const cmd = `${PY} tools/agent_usage.py --task ${t.key} --records`
  const prompt = `Run from the project root ${ROOT || '(your working folder, the folder holding ledger.toml)'}, exactly this command and nothing else:\n  ${cmd}${PYRULE}\nThe command prints one JSON object. Return its fields (ok, records, agents, run, summary) as your structured output, unchanged. Do not read anything else; do not fix anything.`
  probes[t.key] = (probes[t.key] || 0) + 1
  const u = await agent(prompt, { label: `usage:${t.key}:${probes[t.key]}`, phase: 'Usage', model: gateModel, effort: 'low', schema: USAGE })
  if (u == null || typeof u.records !== 'number') { log(`${t.key}: usage probe at ${where} gave no figure; the cap is not checked here`); return null }
  const rec = u.records + (t.recordsBefore || 0)
  log(`${t.key}: ${where}: cache-read by records ${(rec / 1e6).toFixed(1)}M of maxRecords ${(t.maxRecords / 1e6).toFixed(1)}M`)
  lastRecords[t.key] = rec
  if (rec > t.maxRecords) return `cache-read by records ${(rec / 1e6).toFixed(1)}M passed maxRecords ${(t.maxRecords / 1e6).toFixed(1)}M at ${where} (${u.summary || ''})`
  return null
}

// with args.root, every agent prompt opens with the project root (2026-10-25): the workflow runtime starts its agents in the
// session's folder, which need not be the project, and the prompts' paths are relative to the project
const ROOTLINE = ROOT ? `The project root is ${ROOT}: run every command from it (\`cd ${ROOT} && <command>\`) and read every relative path below against it; never read or write anything outside it.\n\n` : ''

// the blocked-output guard: resume on death up to maxResumes, then probe current-unit.md with bisect-block; with opts.task, the
// task's maxRecords is checked before each resume
async function guarded(label, phase, prompt, wip, what, opts = {}) {
  prompt = ROOTLINE + prompt
  const m = opts.model || model
  let r = await agent(prompt, { label, phase, model: m, effort, schema: opts.schema })
  let deaths = 0
  while (r == null && deaths < maxResumes) {
    const cap = await overCap(opts.task, `before resume ${deaths + 1} of ${label}`)
    if (cap) { log(`${label}: ${cap}; the task stops`); return { label, model: m, ok: false, deaths, result: null, bisect: null, capped: cap } }
    deaths++
    log(`${label}: agent died; resume ${deaths} of ${maxResumes} from ${wip}`)
    r = await agent(resumeText(prompt, wip, deaths, what), { label: `resume${deaths}:${label}`, phase: 'Resume', model: m, effort, schema: opts.schema })
  }
  let bisect = null
  if (r == null) {
    log(`${label}: dead after ${maxResumes} resumes; probing ${wip}/current-unit.md`)
    try { bisect = await workflow({ scriptPath: bisectScript }, { file: `${wip}/current-unit.md` }) } catch (e) { bisect = { error: String(e) } }
  }
  return { label, model: m, ok: r != null, deaths, result: r == null ? null : (typeof r === 'string' ? r.slice(0, 3000) : r), bisect }
}

// a gate: a Haiku probe runs the script and relays its JSON line; it reads nothing else
async function gate(label, cmd, wip) {
  const prompt = `Run from the project root ${ROOT || '(your working folder, the folder holding ledger.toml)'}, exactly this command and nothing else:\n  ${cmd}${PYRULE}\nThe command prints one JSON object on its last line and writes a report file. Return that JSON object's fields (ok, summary, report, and failing_units or uncited_units and the counts fails/warns when present) as your structured output, unchanged. Do not read the report, the note or the findings; do not fix anything.`
  const r = await agent(prompt, { label, phase: label.startsWith('gate1') ? 'Gate 1' : 'Gate 2', model: gateModel, effort: 'low', schema: GATE })
  if (r == null) return { ok: false, summary: 'gate probe died', failing_units: [], uncited_units: [], report: `${wip}/gate-${label.startsWith('gate1') ? 'findings' : 'note'}.md` }
  return r
}

// a script run by a Haiku probe that relays its JSON line (the parts gate, the assembly; 2026-10-24)
async function probe(label, phase, cmd, schema, fields, fallback) {
  const prompt = `Run from the project root ${ROOT || '(your working folder, the folder holding ledger.toml)'}, exactly this command and nothing else:\n  ${cmd}${PYRULE}\nThe command prints one JSON object on its last line. Return that JSON object's fields (${fields}) as your structured output, unchanged. Do not read the report, the note or the parts; do not fix anything.`
  const r = await agent(prompt, { label, phase, model: gateModel, effort: 'low', schema })
  return r == null ? fallback : r
}

function readerRanges(t) {
  if (t.ranges) return t.ranges
  const units = t.units
  const fanoutWords = fanoutOf(t)
  const per = readerUnits ?? Math.max(1, Math.floor(fanoutWords / Math.max(1, (t.words || 0) / Math.max(1, units))))
  if (!(t.words > fanoutWords) || units <= per) return [[1, units]]
  const n = Math.ceil(units / per), size = Math.ceil(units / n), out = []
  for (let a = 1; a <= units; a += size) out.push([a, Math.min(units, a + size - 1)])
  return out
}

function readPrompt(t, a, b, extra) {
  const base = (t.prompts && t.prompts.read) || `Task ${t.key} (${t.label || t.note}): the READ phase of the staged intake. Read ${phasesDir}/read.md first and follow it, then ${t.wip}/TASK.md. Your units are ${pad(a)} to ${pad(b)} of ${t.wip}/units/ (manifest: ${t.wip}/units/manifest.md). Write one findings file per unit to ${t.wip}/findings/NNN.md in the fixed form read.md gives, marking the manifest as you go. The writer never reads the source whole: it navigates your findings by their pointers and pulls the source's words by pointer (python3 ledger.py quote), so the findings are a digest in the compact form read.md gives, not a copy, and a claim, date, quotation, name, document, object, kind or relation that is not an item in your findings file does not reach the note.`
  return base + (extra ? `\n\n${extra}` : '') + `\n\nReply with the structured fields read.md asks for (units_done, units, blocked_passages, notes).`
}

async function readPhase(t) {
  const ranges = readerRanges(t)
  log(`${t.key}: read phase, ${ranges.length} reader(s) over ${t.units} units (${t.words} words)`)
  const readers = await parallel(ranges.map(([a, b]) => () => guarded(`read:${t.key}:${pad(a)}-${pad(b)}`, 'Read', readPrompt(t, a, b), t.wip, `${t.wip}/findings/ (python3 tools/intake_gate.py --findings --wip ${t.wip} --status names the first unit without a passing findings file)`, { schema: READ, task: t })))
  const out = { phase: 'read', ranges, readers }
  const capped = readers.find(r => r && r.capped)
  if (capped) { out.capped = capped.capped; return out }
  if (readers.some(r => !r || !r.ok)) { out.dead = true; return out }
  // gate 1, with reader resumes on the failing units
  const gates = []
  for (let g = 0; g <= maxGateResumes; g++) {
    const res = await gate(`gate1:${t.key}:${g}`, `${PY} tools/intake_gate.py --findings --wip ${t.wip} --mark --json`, t.wip)
    gates.push(res)
    log(`${t.key}: gate 1 (${g}): ${res.summary}`)
    if (res.ok) break
    if (g === maxGateResumes) { out.gateFailed = true; break }
    const failing = (res.failing_units || []).map(Number).filter(n => n > 0)
    if (!failing.length) { out.gateFailed = true; break }
    const cap = await overCap(t, `before the gate 1 fix ${g + 1}`)
    if (cap) { out.capped = cap; break }
    // group the failing units by the reader range that read them, one resume agent per range
    const groups = ranges.map(([a, b]) => failing.filter(n => n >= a && n <= b)).filter(g => g.length)
    const fixes = await parallel(groups.map(units => () => guarded(`read-fix:${t.key}:${pad(units[0])}-${pad(units[units.length - 1])}`, 'Read',
      readPrompt(t, units[0], units[units.length - 1], `GATE 1 FAILED on units ${units.map(pad).join(', ')}. Read ${res.report || t.wip + '/gate-findings.md'} first: it names each unit's failures (a quotation not verbatim with the nearest source line, a pointer off its line, a missing section, a wrong header, a findings file over its item allowance without a valid exception line). Fix those findings files against the unit text, by shell, and leave passing units alone: a file over its allowance is cut to the form's fields (key words, no sentences), never by dropping an item, or carries the exception line in the form read.md step 3 gives. Do not re-read passing units.`),
      t.wip, `${t.wip}/findings/`, { schema: READ, task: t })))
    out.fixes = (out.fixes || []).concat(fixes)
    const fc = fixes.find(f => f && f.capped)
    if (fc) { out.capped = fc.capped; return out }
    if (fixes.some(f => !f || !f.ok)) { out.dead = true; return out }
  }
  out.gates = gates
  return out
}

const REPLY_WRITE = `Reply with the structured fields write.md asks for (file, words, claims_rows, parts, verbatim_check, blocked_passages, notes).`
const NEVER_SOURCE = t => `Never read ${t.wip}/units/ or the held source whole: every row comes from the findings files, which carry the unit and line each rests on, and every quotation from the span python3 ledger.py quote --wip ${t.wip} u NNN:L-M prints for its pointer (write.md, Pulling the source's words).`

// the writer roles: the split write (2026-10-23) has writer A (the ledger) and writer B (the sections); splitWrite false keeps one writer
function writerRole(t, role) {
  const p = t.prompts || {}
  if (role === 'a') return {
    key: 'write_a', label: `write-a:${t.key}`, phase: 'Write A', gateTag: 'write-a',
    what: `${t.wip}/parts/aNN.md (writer A's parts already written), ${t.wip}/ledger-notes.md and the note as it stands`,
    prompt: (p.write_a || `Task ${t.key} (${t.label || t.note}): the WRITE phase of the staged intake, as writer A, the ledger. Read ${phasesDir}/write.md first: its opening, its "Shared rules (both writers)" section, its "Writer A: the ledger" section and its closing WIP section, and not the Writer B section; then ${t.wip}/TASK.md. You write only writer A's part: the metadata table, the line \`Units with nothing to row:\` directly above the \`## Claims ledger\` heading where a unit's findings file says \`## Nothing to row\`, the claims ledger and the forthrightness audit, from ${t.wip}/findings/ (every unit's file, in order), in parts ${t.wip}/parts/aNN.md of about 3,000 words. You read only what write.md lists for writer A: the schema and the standing briefs by heading and line range, never in full; the metadata, ledger and audit sections of ${t.wip}/skeleton.md; sections 1 to 3 of ${t.wip}/context.md; not ${t.wip}/timeline-candidates.md and nothing writer B reads. The ledger's grain is the proposition, never the sentence (write.md). Assemble the note ${t.note} as the skeleton with your metadata, the nothing-to-row line, the ledger and the audit in place and every other section as the skeleton gives it (Status: in progress), run the gate on it, and write ${t.wip}/ledger-notes.md for writer B. ${NEVER_SOURCE(t)}`) + `\n\n${REPLY_WRITE}`,
    fix: report => `GATE 2 FAILED after your write (writer A). Read ${report} first: it lists every quotation of the note whose words are not the source's word for word (\`changed words\`, with the nearest unit lines and the difference; a \`punctuation only\` line is not a failure), every unit the note cites nowhere (cite it, or add it to the note's \`Units with nothing to row:\` line, directly above \`## Claims ledger\`, with a reason), and every claims row whose unit line does not hold the words of its claim. Fix each one in your sections from the findings files and the spans python3 ledger.py quote prints for their pointers, by shell, re-running python3 tools/verbatim_check.py on each part you touch, reassemble the note and bring ${t.wip}/ledger-notes.md in line; change nothing else.`,
  }
  if (role === 'b' && formOf(t) === 'unit-writers') return {
    key: 'write_b', label: `write-b:${t.key}`, phase: 'Write B', gateTag: 'write-b',
    what: `${t.wip}/parts/bNN.md (writer B's parts already written) and the note as it stands`,
    prompt: (p.write_b || `Task ${t.key} (${t.label || t.note}): the WRITE phase of the unit-writers form, as writer B, the sections. Read ${phasesDir}/write.md first: its opening, its "Shared rules (both writers)" section, its "Writer B: the sections" section and its closing WIP section, and not the Writer A section; then ${t.wip}/TASK.md. The unit writers (${phasesDir}/write-unit.md) have written the claims ledger and the forthrightness audit's rows, one writer per unit range with the unit in context; a script assembled them into ${t.note} from ${t.wip}/skeleton.md, and the note passed gate 2; their map of the ledger is ${t.wip}/ledger-notes.md.${checkOf(t) ? ` The check phase (${phasesDir}/check.md) then read the claims rows against their spans and corrected rows in place (log ${t.wip}/check-log.md); the note passed gate 2 after it. The rows it marked unsupported and the outside matter it removed for your Open questions: ${JSON.stringify(checkOut[t.key] || {})}.` : ''} Two things differ from the staged form, and bind you: (1) this form has no read phase and no findings files: wherever write.md sends you to the findings (Names, Documents and works cited, Objects, Actors, Relations, Dated events, Tensions, Open threads, Quotations), read the units instead, one at a time in manifest order (\`cat -n ${t.wip}/units/NNN.txt\`, each once), and pull a quotation's words by pointer (python3 ledger.py quote --wip ${t.wip} u NNN:L-M); (2) the unit writers wrote rows only, so the metadata table (writer A's part in write.md: the keys you can fill from TASK.md and the source; the markers left for note_fill; the Status row the assembly added stays \`in progress\` until the finish), the forthrightness audit's prose subsections below its rows, and writer A's report.json keys (claims_rows, first_telling_rows, blocked_passages, narrative_rows_addressed) are yours too. You write every other section of the skeleton (the Cross-checks placeholder left for the finisher), in parts ${t.wip}/parts/bNN.md of about 3,000 words, and read only what write.md lists for writer B with the units in place of the findings: the schema and the standing briefs by heading and line range, never in full; ${t.wip}/skeleton.md; ${t.wip}/ledger-notes.md; sections 1, 3, 4 and 5 of ${t.wip}/context.md (section 2 only by grep); ${t.wip}/timeline-candidates.md. The ledger and the audit rows you never read in full: a row you cite is found by grep -n on the note. You do not change a ledger or audit row; a defect you find in one goes in your notes with the row number. Assemble your sections into ${t.note} in their skeleton places with the rows unchanged, and run the skeleton check and the gate on it. Your claims_rows is the ledger's count, unchanged.`) + `\n\n${REPLY_WRITE}`,
    fix: report => `GATE 2 FAILED after your write (writer B). Read ${report} first: it lists every quotation of the note whose words are not the source's word for word (\`changed words\`, with the nearest unit lines and the difference; a \`punctuation only\` line is not a failure), every unit the note cites nowhere, and every claims row whose unit line does not hold the words of its claim. Fix each failure in your sections from the units and the spans python3 ledger.py quote prints for their pointers, by shell, re-running python3 tools/verbatim_check.py on each part you touch, and reassemble the note. A failure in a claims-ledger or audit row is the unit writers', which passed this gate before you wrote: fix only the cell the report names, from the span its pointer prints, and name the row in your notes; change nothing else.`,
  }
  if (role === 'b') return {
    key: 'write_b', label: `write-b:${t.key}`, phase: 'Write B', gateTag: 'write-b',
    what: `${t.wip}/parts/bNN.md (writer B's parts already written) and the note as it stands`,
    prompt: (p.write_b || `Task ${t.key} (${t.label || t.note}): the WRITE phase of the staged intake, as writer B, the sections. Read ${phasesDir}/write.md first: its opening, its "Shared rules (both writers)" section, its "Writer B: the sections" section and its closing WIP section, and not the Writer A section; then ${t.wip}/TASK.md. Writer A has written the metadata table, the claims ledger and the forthrightness audit into ${t.note}, which passed gate 2; its map of the ledger is ${t.wip}/ledger-notes.md.${checkOf(t) ? ` The check phase (${phasesDir}/check.md) then read every claims row against its span and corrected rows in place (log ${t.wip}/check-log.md); the note passed gate 2 after it. The rows it marked unsupported and the outside matter it removed for your Open questions: ${JSON.stringify(checkOut[t.key] || {})}.` : ''} You write only every other section of the skeleton (the Cross-checks placeholder left for the finisher), in parts ${t.wip}/parts/bNN.md of about 3,000 words, and read only what write.md lists for writer B: the schema and the standing briefs by heading and line range, never in full; ${t.wip}/skeleton.md; ${t.wip}/ledger-notes.md; sections 1, 3, 4 and 5 of ${t.wip}/context.md (section 2 only by grep); ${t.wip}/timeline-candidates.md; the findings files. The ledger and the audit you never read in full: a row you cite is found by grep -n on the note. You do not change a ledger or audit row; a defect you find in one goes in your notes with the row number. Assemble your sections into ${t.note} in their skeleton places with writer A's unchanged, and run the skeleton check and the gate on it. Your claims_rows is writer A's count, unchanged. ${NEVER_SOURCE(t)}`) + `\n\n${REPLY_WRITE}`,
    fix: report => `GATE 2 FAILED after your write (writer B). Read ${report} first: it lists every quotation of the note whose words are not the source's word for word (\`changed words\`, with the nearest unit lines and the difference; a \`punctuation only\` line is not a failure), every unit the note cites nowhere, and every claims row whose unit line does not hold the words of its claim. Fix each failure in your sections from the findings files and the spans python3 ledger.py quote prints for their pointers, by shell, re-running python3 tools/verbatim_check.py on each part you touch, and reassemble the note. A failure in a claims-ledger or audit row is writer A's, which passed this gate before you wrote: fix only the cell the report names, from its findings item and the span its pointer prints, and name the row in your notes; change nothing else.`,
  }
  return {
    key: 'write', label: `write:${t.key}`, phase: 'Write', gateTag: 'write',
    what: `${t.wip}/parts/ (the parts already written; the note as it stands)`,
    prompt: (p.write || `Task ${t.key} (${t.label || t.note}): the WRITE phase of the staged intake, one writer for the whole note (the form before the split write of 2026-10-23). Read ${phasesDir}/write.md first and follow its shared rules and both writers' sections as one agent, then ${t.wip}/TASK.md. Build the note ${t.note} from ${t.wip}/findings/ (every unit's file, in order), ${t.wip}/skeleton.md, ${t.wip}/context.md and ${t.wip}/timeline-candidates.md. ${NEVER_SOURCE(t)}`) + `\n\n${REPLY_WRITE}`,
    fix: report => `GATE 2 FAILED after your write. Read ${report} first: it lists every quotation of the note whose words are not the source's word for word (\`changed words\`; a \`punctuation only\` line is not a failure), every unit the note cites nowhere (cite it, or add it to the note's \`Units with nothing to row:\` line with a reason), and every claims row whose unit line does not hold the words of its claim. Fix each one from the findings files and the spans python3 ledger.py quote prints for their pointers, by shell, re-running python3 tools/verbatim_check.py on each part you touch; change nothing else.`,
  }
}

// one writer and gate 2 after it, with the fix loop
async function writeStep(t, role) {
  const w0 = writerRole(t, role)
  const w = await guarded(w0.label, w0.phase, w0.prompt, t.wip, w0.what, { schema: WRITE, task: t })
  const out = { phase: w0.key, writer: w }
  if (w.capped) { out.capped = w.capped; return out }
  if (!w.ok) { out.dead = true; return out }
  const gates = []
  for (let g = 0; g <= maxGateResumes; g++) {
    const res = await gate(`gate2:${t.key}:${w0.gateTag}:${g}`, `${PY} tools/intake_gate.py --note ${t.note} --wip ${t.wip} --json`, t.wip)
    gates.push(res)
    log(`${t.key}: gate 2 after ${w0.label.split(':')[0]} (${g}): ${res.summary}`)
    if (res.ok) break
    if (g === maxGateResumes) { out.gateFailed = true; break }
    const cap = await overCap(t, `before the gate 2 fix ${g + 1} of ${w0.label}`)
    if (cap) { out.capped = cap; break }
    const fix = await guarded(`${w0.label.split(':')[0]}-fix:${t.key}:${g}`, w0.phase, w0.prompt + `\n\n` + w0.fix(res.report || t.wip + '/gate-note.md'), t.wip, w0.what, { schema: WRITE, task: t })
    out.fixes = (out.fixes || []).concat([fix])
    if (fix.capped) { out.capped = fix.capped; return out }
    if (!fix.ok) { out.dead = true; return out }
  }
  out.gates = gates
  return out
}

// ---------------------------------------------------------------- the unit-writers form (2026-10-24; phasesDir/write-unit.md)
// no read phase: unit writers in sequence over unit ranges sized by words (unitRanges), each told its range and the row its ledger
// and its audit start at (the last rows the parts gate counted for the writer before, plus one); after each, the parts gate
// (tools/intake_gate.py --note-parts) with the fix loop; then the assembly script (tools/assemble_parts.py) and gate 2 on the
// assembled note with the fix loop. Writer B and the finish then run as in the staged form.
function unitNumbers(t) {
  if (t.unitNumbers) return t.unitNumbers.map(n => Number(n))
  return Array.from({ length: t.units }, (_, i) => i + 1)
}
function unitRanges(t) {
  if (t.unitRanges) return t.unitRanges
  // by words (2026-10-25): ceil(words / fanout) writers, the units shared evenly; readerUnits, when given, is the units per writer
  const nums = unitNumbers(t)
  const n = readerUnits ? Math.max(1, Math.ceil(nums.length / readerUnits)) : Math.max(1, Math.min(nums.length, Math.ceil((t.words || 0) / fanoutOf(t))))
  const size = Math.ceil(nums.length / n), out = []
  for (let i = 0; i < nums.length; i += size) { const g = nums.slice(i, i + size); out.push([g[0], g[g.length - 1]]) }
  return out
}
const REPLY_UNIT = `Reply with the structured fields write-unit.md asks for (units, rows, audit_rows, parts, verbatim_check, nothing_to_row, blocked_passages, notes).`

function unitPrompt(t, k, n, a, b, row, arow, extra) {
  const inRange = unitNumbers(t).filter(x => x >= a && x <= b).map(pad)
  const base = (t.prompts && t.prompts.write_unit) || `Task ${t.key} (${t.label || t.note}): the WRITE-UNIT phase of the unit-writers form, unit writer ${k} of ${n}. Read ${phasesDir}/write-unit.md first and follow it, then ${t.wip}/TASK.md. Your units are ${pad(a)} to ${pad(b)} (${inRange.join(', ')}, in manifest order; manifest ${t.wip}/units/manifest.md): read each with cat -n, copied first to ${t.wip}/current-unit.md, and write its claims-ledger rows to ${t.wip}/parts/u<NNN>-ledger.md and its forthrightness-audit rows to ${t.wip}/parts/u<NNN>-audit.md, table rows only, every row ending with its pointer. Your claims ledger starts at row ${row} and your audit at row ${arow}; both run on without gaps across your units.${k > 1 ? ` Unit writers before you wrote the parts of the units before ${pad(a)}: do not read or change them; ${t.wip}/ledger-notes.md is theirs so far, and you append to it.` : ` You begin ${t.wip}/ledger-notes.md for writer B.`} You never read the other units, the findings (there are none in this form), timeline-candidates.md or the rest of the schema and briefs beyond what write-unit.md lists. Every quotation is pasted from the output of \`python3 ledger.py quote --wip ${t.wip} u NNN:L-M\` (the lines by pointer) or \`python3 ledger.py quote --wip ${t.wip} --find "<a few of the words>"\` (the exact span and its pointer, located by word), never typed from the unit in your context. Before you reply, run \`python3 tools/intake_gate.py --note-parts ${t.wip}/parts --wip ${t.wip} --units ${pad(a)}-${pad(b)} --start-row ${row} --start-audit ${arow} --nothing-to-row '<your nothing_to_row list as JSON>'\` and clear every failure it lists: a \`changed words\` quotation is corrected to the source's words from ledger quote or its repair is marked ([brackets], [sic]); a \`punctuation only\` line is not a failure (the caption rule: punctuation and capitals may be added, never a word changed, added or dropped). Never reply with a quotation failure open.`
  return base + (extra ? `\n\n${extra}` : '') + `\n\n${REPLY_UNIT}`
}
const nothingOf = r => (r && typeof r === 'object' && Array.isArray(r.nothing_to_row)) ? r.nothing_to_row.filter(x => x && x.unit).map(x => ({ unit: pad(String(x.unit).match(/\d+/) ? Number(String(x.unit).match(/\d+/)[0]) : x.unit), reason: String(x.reason || '') })) : []

async function unitWritePhase(t) {
  const ranges = unitRanges(t)
  log(`${t.key}: unit-writers form, ${ranges.length} unit writer(s) over ${unitNumbers(t).length} units (${t.words} words): ${ranges.map(([a, b]) => `${pad(a)}-${pad(b)}`).join(', ')}`)
  const out = { phase: 'write_units', ranges, writers: [], gates: [] }
  let row = 1, arow = 1
  const nothing = {}
  for (let k = 0; k < ranges.length; k++) {
    const [a, b] = ranges[k]
    if (k > 0) { const cap = await overCap(t, `before unit writer ${k + 1}`); if (cap) { out.capped = cap; return out } }
    const label = `write-unit:${t.key}:${pad(a)}-${pad(b)}`
    const what = `${t.wip}/parts/ (the u<NNN>-ledger.md and u<NNN>-audit.md parts of your units already written: continue from the first unit of your range without both) and ${t.wip}/ledger-notes.md`
    const w = await guarded(label, 'Write units', unitPrompt(t, k + 1, ranges.length, a, b, row, arow), t.wip, what, { schema: WRITE_UNIT, task: t })
    out.writers.push(w)
    if (w.capped) { out.capped = w.capped; return out }
    if (!w.ok) { out.dead = true; return out }
    let nl = nothingOf(w.result)
    let res
    for (let g = 0; g <= maxGateResumes; g++) {
      const cmd = `${PY} tools/intake_gate.py --note-parts ${t.wip}/parts --wip ${t.wip} --units ${pad(a)}-${pad(b)} --start-row ${row} --start-audit ${arow} --nothing-to-row ${shellJson(nl)} --json`
      res = await probe(`gate-parts:${t.key}:${pad(a)}-${pad(b)}:${g}`, 'Gate parts', cmd, PARTS_GATE, 'ok, summary, report, rows, audit_rows, last_row, last_audit_row, failing_units, uncited_units, fails, warns',
        { ok: false, summary: 'gate probe died', report: `${t.wip}/gate-parts-${pad(a)}-${pad(b)}.md` })
      out.gates.push(res)
      log(`${t.key}: parts gate ${pad(a)}-${pad(b)} (${g}): ${res.summary}`)
      if (res.ok) break
      if (g === maxGateResumes) { out.gateFailed = true; return out }
      const cap = await overCap(t, `before the parts gate fix ${g + 1} of ${label}`)
      if (cap) { out.capped = cap; return out }
      const fix = await guarded(`write-unit-fix:${t.key}:${pad(a)}-${pad(b)}:${g}`, 'Write units', unitPrompt(t, k + 1, ranges.length, a, b, row, arow,
        `THE PARTS GATE FAILED on your range. Read ${res.report || `${t.wip}/gate-parts-${pad(a)}-${pad(b)}.md`} first: it names every quotation whose words are not word for word in its pointer's unit (\`changed words\`, with the difference; and the unit that holds it, when one does: fix the pointer; a \`punctuation only\` line is not a failure), every row without a pointer or whose pointer's lines do not hold its words, every gap or repeat in the numbering, every heading or header line in a part, and every unit of your range cited by no row and not in your nothing_to_row. Fix each against the unit text, by shell, in your parts only, re-running python3 tools/verbatim_check.py on each part you touch; change nothing else, and reply with your fields again (nothing_to_row as it now stands).`),
        t.wip, what, { schema: WRITE_UNIT, task: t })
      out.writers.push(fix)
      if (fix.capped) { out.capped = fix.capped; return out }
      if (!fix.ok) { out.dead = true; return out }
      if (fix.result && Array.isArray(fix.result.nothing_to_row)) nl = nothingOf(fix.result)
    }
    for (const x of nl) nothing[x.unit] = x.reason
    if (typeof res.last_row === 'number') row = res.last_row + 1
    if (typeof res.last_audit_row === 'number') arow = res.last_audit_row + 1
  }
  out.nothing_to_row = nothing
  // the assembly (a script) and gate 2 on the assembled note, with the fix loop
  const asmCmd = `${PY} tools/assemble_parts.py --wip ${t.wip} --note ${t.note} --nothing-to-row ${shellJson(nothing)} --json`
  const asm = await probe(`assemble:${t.key}:0`, 'Assemble', asmCmd, ASSEMBLE, 'ok, summary, claims_rows, audit_rows, words', { ok: false, summary: 'assembly probe died' })
  out.assembly = [asm]
  log(`${t.key}: assembly: ${asm.summary}`)
  if (!asm.ok) { out.assemblyFailed = true; return out }
  for (let g = 0; g <= maxGateResumes; g++) {
    const res = await gate(`gate2:${t.key}:assembled:${g}`, `${PY} tools/intake_gate.py --note ${t.note} --wip ${t.wip} --json`, t.wip)
    out.gates.push(res)
    log(`${t.key}: gate 2 on the assembled note (${g}): ${res.summary}`)
    if (res.ok) return out
    if (g === maxGateResumes) { out.gateFailed = true; return out }
    const cap = await overCap(t, `before the gate 2 fix ${g + 1} of the assembled note`)
    if (cap) { out.capped = cap; return out }
    const [a, b] = [ranges[0][0], ranges[ranges.length - 1][1]]
    const what = `${t.wip}/parts/ and ${t.wip}/gate-note.md`
    const fix = await guarded(`write-unit-fix:${t.key}:assembled:${g}`, 'Write units', unitPrompt(t, ranges.length, ranges.length, a, b, 1, 1,
      `GATE 2 FAILED on the note assembled from every unit writer's parts (units ${pad(a)} to ${pad(b)}; this is a fix, not a new range: the rows keep their numbers). Read ${res.report || `${t.wip}/gate-note.md`} first and fix each failure it names in the parts it comes from (never in ${t.note}, which the script rebuilds), against the unit text, by shell; then run \`${asmCmd}\` to rebuild the note and \`python3 tools/intake_gate.py --note ${t.note} --wip ${t.wip}\` to confirm. Change nothing else.`),
      t.wip, what, { schema: WRITE_UNIT, task: t })
    out.writers.push(fix)
    if (fix.capped) { out.capped = fix.capped; return out }
    if (!fix.ok) { out.dead = true; return out }
    const asm2 = await probe(`assemble:${t.key}:${g + 1}`, 'Assemble', asmCmd, ASSEMBLE, 'ok, summary, claims_rows, audit_rows, words', { ok: false, summary: 'assembly probe died' })
    out.assembly.push(asm2)
    if (!asm2.ok) { out.assemblyFailed = true; return out }
  }
  return out
}

// ---------------------------------------------------------------- the check phase (2026-10-24; phasesDir/check.md)
// between gate 2 after writer A and writer B: one agent reads every claims row against its span and corrects in place; gate 2
// after it with the fix loop. Its unsupported rows and outside matter go to writer B's and the finisher's prompts.
const ATTENTION = `The order of attention (check.md): first every row classed \`firsthand\` in a document note and every \`host\` row whose span names a source; second every row whose span carries a hedge, bound or qualifier (appear, seem, suggested, alleged, earliest, only, unless, may, as far as, as practiced, could, might) that the row's quotation marks do not contain; third every row whose span holds a second named actor, a pronoun subject or an embedded telling (told, said, set out, read out, a statement, an email, a post about a post); fourth every row whose quotation ends mid-sentence before a clause beginning as, unless, but, if, which or provided; then the rest.`
async function checkStep(t, opts = {}) {
  const uw = formOf(t) === 'unit-writers'
  const budget = opts.whole ? null : checkBudgetOf(t)   // after the sample reading, the whole ledger (2026-10-25)
  const tag = opts.tag ? `:${opts.tag}` : ''
  const who = uw ? `The unit writers (${phasesDir}/write-unit.md) have written the claims ledger and the forthrightness audit's rows into ${t.note} with the units in context, a script assembled them, and the note passed gate 2.` : `Writer A has written the metadata table, the claims ledger and the forthrightness audit into ${t.note}, which passed gate 2.`
  const prompt = (t.prompts && t.prompts.check) || `Task ${t.key} (${t.label || t.note}): the CHECK phase (${uw ? 'after the unit writers' : 'the checked-staged form'}). Read ${phasesDir}/check.md first and follow it, then ${t.wip}/TASK.md. ${who}${opts.extra ? ' ' + opts.extra : ''} Read the claims rows against the span each pointer pulls (python3 ledger.py quote --wip ${t.wip} u NNN:L-M, two lines either side, ten to twenty rows a call), in the order of attention, make the five judgements check.md gives, correct each failing row in place by exact replacement of that one row (python), log every change in ${t.wip}/check-log.md, and run the gate and the skeleton check. ${ATTENTION} ${budget ? `Your budget is ${budget} rows: read them in that order and stop at the budget, naming in progress.md and your notes the tier and the last row reached.` : 'Read every row.'} A corrected quotation is pasted from ledger quote (by pointer, or --find "<a few of the words>"), never typed. Before you reply, \`python3 tools/intake_gate.py --note ${t.note} --wip ${t.wip}\` passes: clear every failure it lists (a \`punctuation only\` line is not a failure); never reply with a quotation failure open. Never read ${t.wip}/units/ whole${uw ? '' : ' or the findings'}.\n\nReply with the structured fields check.md asks for (rows_read, corrected, by_judgement, split_rows, unsupported, outside_matter, log, notes).`
  const what = `${t.wip}/check-log.md (the last row logged) and the note as it stands`
  const c = await guarded(`check:${t.key}${tag}`, 'Check', prompt, t.wip, what, { schema: CHECK, task: t })
  const out = { phase: 'check', checker: c }
  if (c.capped) { out.capped = c.capped; return out }
  if (!c.ok) { out.dead = true; return out }
  const keep = r => r && typeof r === 'object' ? { unsupported: r.unsupported || [], outside_matter: r.outside_matter || [], split_rows: r.split_rows || [] } : {}
  checkOut[t.key] = keep(c.result)
  const gates = []
  for (let g = 0; g <= maxGateResumes; g++) {
    const res = await gate(`gate2:${t.key}:check${opts.tag ? '-' + opts.tag : ''}:${g}`, `${PY} tools/intake_gate.py --note ${t.note} --wip ${t.wip} --json`, t.wip)
    gates.push(res)
    log(`${t.key}: gate 2 after the check (${g}): ${res.summary}`)
    if (res.ok) break
    if (g === maxGateResumes) { out.gateFailed = true; break }
    const cap = await overCap(t, `before the gate 2 fix ${g + 1} of the check`)
    if (cap) { out.capped = cap; break }
    const fix = await guarded(`check-fix:${t.key}${tag}:${g}`, 'Check', prompt + `\n\nGATE 2 FAILED after the check. Read ${res.report || t.wip + '/gate-note.md'} first: it lists every quotation whose words are not the source's word for word (\`changed words\`; a \`punctuation only\` line is not a failure), every unit cited nowhere and every claims row whose pointer's lines do not hold its words. Fix each in the row you corrected (or split), against the span its pointer prints, by exact replacement, logging each fix in ${t.wip}/check-log.md; change nothing else.`, t.wip, what, { schema: CHECK, task: t })
    out.fixes = (out.fixes || []).concat([fix])
    if (fix.capped) { out.capped = fix.capped; return out }
    if (!fix.ok) { out.dead = true; return out }
    if (fix.result && typeof fix.result === 'object') checkOut[t.key] = { ...checkOut[t.key], ...keep(fix.result) }
  }
  out.gates = gates
  return out
}

async function finishPhase(t) {
  const uw = formOf(t) === 'unit-writers'
  const base = (t.prompts && t.prompts.finish) || `Task ${t.key} (${t.label || t.note}): the FINISH phase of the staged intake. Read ${phasesDir}/finish.md first and follow it, then ${t.wip}/TASK.md. The note ${t.note} is written and has passed gate 2. Run the checks and the cross-checks finish.md lists (build_db to ${t.wip}/check.db, onboard_check, note_fill, cross-checks read on both sides, report_check), complete ${t.wip}/report.json, and reply with the report JSON.` +
    (uw ? ` The note was written in the unit-writers form (${phasesDir}/write-unit.md): unit writers wrote the claims ledger and audit rows with the units in context, a script assembled them, and writer B the rest; there are no findings files, so wherever finish.md names the findings, read the span by pointer (python3 ledger.py quote). Writer B's reply notes, if any, name ledger or audit rows it found defective; ${t.wip}/ledger-notes.md is the unit writers' map of the ledger.`
      : splitWrite ? ` The note was written by two writers (write.md): writer B's reply notes, if any, name ledger or audit rows it found defective; ${t.wip}/ledger-notes.md is writer A's map of the ledger.` : '') +
    (checkOf(t) ? ` The check phase (${phasesDir}/check.md) corrected rows against their spans ${uw ? 'after the unit writers' : 'between the writers'} (log ${t.wip}/check-log.md); the rows it marked \`check: unsupported by the span\` are yours to settle: ${JSON.stringify((checkOut[t.key] || {}).unsupported || [])}.` : '')
  const f = await guarded(`finish:${t.key}`, 'Finish', base + (sampleOf(t) ? SAMPLE_NEXT : ''), t.wip, `${t.wip}/report.json and ${t.wip}/onboard.md`, { task: t })
  const out = { phase: 'finish', finisher: f }
  if (f.capped) { out.capped = f.capped; return out }
  if (!f.ok) { out.dead = true; return out }
  const gates = []
  for (let g = 0; g <= maxGateResumes; g++) {
    const res = await gate(`gate2:${t.key}:finish:${g}`, `${PY} tools/intake_gate.py --note ${t.note} --wip ${t.wip} --json`, t.wip)
    gates.push(res)
    log(`${t.key}: gate 2 after finish (${g}): ${res.summary}`)
    if (res.ok) break
    if (g === maxGateResumes) { out.gateFailed = true; break }
    const cap = await overCap(t, `before the gate 2 fix ${g + 1} of finish`)
    if (cap) { out.capped = cap; break }
    const fix = await guarded(`finish-fix:${t.key}:${g}`, 'Finish', base + `\n\nGATE 2 FAILED after the finish phase. Read ${res.report || t.wip + '/gate-note.md'} first and fix what it lists (a quotation not verbatim, a unit cited nowhere, a claims row whose unit line does not hold its words) from ${uw ? 'the units' : t.wip + '/findings/'} and the spans python3 ledger.py quote prints for their pointers, by shell; then re-run build_db, note_fill --check and report_check, update report.json and reply with it.`, t.wip, `${t.wip}/report.json`, { task: t })
    out.fixes = (out.fixes || []).concat([fix])
    if (fix.capped) { out.capped = fix.capped; return out }
    if (!fix.ok) { out.dead = true; return out }
  }
  out.gates = gates
  return out
}

// ---------------------------------------------------------------- the sample reading (2026-10-25; phasesDir/sample.md)
// after the finish phase and its gate, on every intake: the draw (a script, ledger sample draw), one guarded Opus reader of the
// twenty rows, the tally (a script, ledger sample tally) into report.json's sample_reading. When the faults of meaning reach the
// threshold and the task did not run the check phase, the check runs over the whole ledger, gate 2 after it, and the sample is
// redrawn with a new seed (round 2) and read once more; the report keeps both tallies (sample_reading and sample_reading.redraw).
const SAMPLE_NEXT = ` The sample phase runs after you: the workflow draws twenty claims rows of the finished note and writes the reading's tally into ${'report.json'}'s \`sample_reading\` key, so run report_check with --pre-sample (\`sample_reading\` is not yours to write).`
function samplePrompt(t, round, draw) {
  const sfx = round > 1 ? `-${round}` : ''
  return `Task ${t.key} (${t.label || t.note}): the SAMPLE phase of the intake${round > 1 ? `, round ${round} (the redraw after the check phase corrected the note)` : ''}. Read ${phasesDir}/sample.md first and follow it, then ${t.wip}/TASK.md. The note ${t.note} is finished and has passed gate 2. Your sample is ${draw.file || `${t.wip}/sample${sfx}.md`} (${draw.summary || 'twenty claims rows'}): read each row against the passage it rests on (python3 ledger.py quote --wip ${t.wip} u NNN:L-M, or --find "<a few of the words>"), make the five judgements, and write ${t.wip}/sample-reading${sfx}.md, ${t.wip}/sample-reading${sfx}.tsv and ${t.wip}/sample-reading${sfx}.progress.md${round > 1 ? ' (these round-2 names, in place of the ones sample.md gives)' : ''}. You correct nothing.\n\nReply with the structured fields sample.md asks for (rows, sound, formal, meaning, by_owner, meaning_rows, files).`
}

async function sampleRound(t, round, onThreshold) {
  const out = { round }
  const sfx = round > 1 ? `-${round}` : ''
  const drawCmd = `${PY} ledger.py sample draw ${t.note} --wip ${t.wip} --n 20 --round ${round} --json`
  out.draw = await probe(`sample-draw:${t.key}:${round}`, 'Sample', drawCmd, DRAW, 'ok, summary, file, rows, total, seed, threshold', { ok: false, summary: 'draw probe died' })
  log(`${t.key}: sample draw (round ${round}): ${out.draw.summary}`)
  if (!out.draw.ok) { out.failed = 'the draw'; return out }
  out.reader = await guarded(`sample:${t.key}:${round}`, 'Sample', samplePrompt(t, round, out.draw), t.wip, `${t.wip}/sample-reading${sfx}.progress.md (the last row read) and ${t.wip}/sample-reading${sfx}.tsv`, { schema: SAMPLE, task: t })
  if (out.reader.capped) { out.capped = out.reader.capped; return out }
  if (!out.reader.ok) { out.dead = true; return out }
  const thr = args.sampleThreshold ?? (typeof out.draw.threshold === 'number' ? out.draw.threshold : 3)
  const reply = out.reader.result && typeof out.reader.result === 'object' ? out.reader.result : {}
  const tallyCmd = `${PY} ledger.py sample tally --wip ${t.wip} --round ${round} --threshold ${thr} --on-threshold ${onThreshold} --reply ${shellJson(reply)} --json`
  out.tally = await probe(`sample-tally:${t.key}:${round}`, 'Sample', tallyCmd, TALLY, 'ok, summary, rows, sound, formal, meaning, meaning_rows, threshold, over_threshold, action', { ok: false, summary: 'tally probe died' })
  log(`${t.key}: sample tally (round ${round}): ${out.tally.summary}`)
  if (!out.tally.ok) out.failed = 'the tally'
  return out
}

async function samplePhase(t) {
  const out = { phase: 'sample', rounds: [] }
  const checked = checkOf(t)
  const r1 = await sampleRound(t, 1, checked ? 'flag' : 'check')
  out.rounds.push(r1)
  if (r1.capped) { out.capped = r1.capped; return out }
  if (r1.dead) { out.dead = true; return out }
  if (r1.failed) { out.sampleFailed = r1.failed; return out }
  out.tally = r1.tally
  if (!r1.tally.over_threshold) return out
  if (checked) {
    out.flagged = `faults of meaning ${r1.tally.meaning} of ${r1.tally.rows} reach the threshold ${r1.tally.threshold}; the check phase already ran on this task, so the note integrates flagged`
    log(`${t.key}: ${out.flagged}`)
    return out
  }
  log(`${t.key}: faults of meaning ${r1.tally.meaning} of ${r1.tally.rows} reach the threshold ${r1.tally.threshold}: the check phase over the whole ledger, gate 2, then a redraw`)
  const cap = await overCap(t, 'before the check after the sample')
  if (cap) { out.capped = cap; return out }
  const extra = `This check runs after the finish phase: the sample reading found ${r1.tally.meaning} faults of meaning in ${r1.tally.rows} sampled rows (rows ${(r1.tally.meaning_rows || []).join(', ')}; ${t.wip}/sample-reading.md), the pack's threshold. Read that reading first: its rows and its Patterns are where the faults are; then read every row of the ledger, not only the sampled ones.`
  const c = await checkStep(t, { whole: true, tag: 'sample', extra })
  out.check = c
  if (c.capped) { out.capped = c.capped; return out }
  if (c.dead || c.gateFailed) { out.dead = !!c.dead; out.gateFailed = !!c.gateFailed; return out }
  const r2 = await sampleRound(t, 2, 'flag')
  out.rounds.push(r2)
  if (r2.capped) { out.capped = r2.capped; return out }
  if (r2.dead) { out.dead = true; return out }
  if (r2.failed) { out.sampleFailed = r2.failed; return out }
  out.redraw = r2.tally
  if (r2.tally.over_threshold) { out.flagged = `after the check the redraw still finds ${r2.tally.meaning} faults of meaning in ${r2.tally.rows}; the note integrates flagged`; log(`${t.key}: ${out.flagged}`) }
  return out
}

// a phase's end: null to go on, else the task's result (stopped at that phase, with the reason)
function stopAt(t, name, p, phases, extra = {}) {
  if (p.capped) { log(`${t.key}: stopped at ${name}: ${p.capped}; the other tasks go on`); return { key: t.key, ok: false, stopped_at: name, reason: p.capped, records: lastRecords[t.key], phases, ...extra } }
  if (p.dead || p.gateFailed || p.assemblyFailed || p.sampleFailed) {
    const why = p.dead ? 'a dead agent' : p.assemblyFailed ? 'the assembly script failed' : p.sampleFailed ? `the sample phase: ${p.sampleFailed} failed` : `${name === 'read' ? 'gate 1' : name === 'write_units' ? 'the parts gate or gate 2' : 'gate 2'} still failing after ${maxGateResumes} fixes`
    log(`${t.key}: ${name} phase has ${why}; later phases skipped`)
    return { key: t.key, ok: false, stopped_at: name, reason: why, phases, ...extra }
  }
  return null
}

async function capBetween(t, name, phases) {
  const cap = await overCap(t, `before ${name}`)
  return cap ? stopAt(t, name, { capped: cap }, phases) : null
}

async function finishTail(t, phases) {
  let stop
  if ((stop = await capBetween(t, 'finish', phases))) return stop
  const f = await finishPhase(t); phases.push(f)
  if ((stop = stopAt(t, 'finish', f, phases, { report: f.finisher && f.finisher.result }))) return stop
  return sampleTail(t, phases, f.finisher.result)
}

// the sample phase after the finish (2026-10-25); sample false skips it, and the task's result says so
async function sampleTail(t, phases, report) {
  let stop
  if (!sampleOf(t)) return { key: t.key, ok: true, stopped_at: null, phases, report, sample_reading: { skipped: 'sample false' } }
  if ((stop = await capBetween(t, 'sample', phases))) return stop
  const sp = await samplePhase(t); phases.push(sp)
  if ((stop = stopAt(t, 'sample', sp, phases, { report }))) return stop
  return { key: t.key, ok: true, stopped_at: null, phases, report, sample_reading: { ...sp.tally, ...(sp.redraw ? { redraw: sp.redraw } : {}) }, ...(sp.flagged ? { flagged: sp.flagged } : {}) }
}

async function runTask(t) {
  const phases = []
  let stop
  if (formOf(t) === 'unit-writers') {
    // no read phase: the unit writers, the parts gates, the assembly, gate 2; then writer B and the finish (2026-10-24)
    const u = await unitWritePhase(t); phases.push(u)
    if ((stop = stopAt(t, 'write_units', u, phases))) return stop
    if (checkOf(t)) {
      // the check, optional in this form too (2026-10-25): after the assembled note passes gate 2, before writer B
      if ((stop = await capBetween(t, 'check', phases))) return stop
      const c = await checkStep(t); phases.push(c)
      if ((stop = stopAt(t, 'check', c, phases))) return stop
    }
    if ((stop = await capBetween(t, 'write_b', phases))) return stop
    const w = await writeStep(t, 'b'); phases.push(w)
    if ((stop = stopAt(t, 'write_b', w, phases))) return stop
    return finishTail(t, phases)
  }
  const r = await readPhase(t); phases.push(r)
  if ((stop = stopAt(t, 'read', r, phases))) return stop
  if (args.mergeWriteFinish) {
    // one agent writes and finishes (the old single-agent tail, one writer); gate 2 once, after
    const t2 = { ...t, prompts: { ...(t.prompts || {}), finish: ((t.prompts && t.prompts.write) || '') } }
    if ((stop = await capBetween(t, 'write', phases))) return stop
    const w = await writeStep(t, 'one'); phases.push(w)
    if ((stop = stopAt(t, 'write', w, phases))) return stop
    const f = await finishPhase(t2); phases.push(f)
    if ((stop = stopAt(t, 'finish', f, phases, { report: f.finisher && f.finisher.result }))) return stop
    return sampleTail(t, phases, f.finisher && f.finisher.result)
  }
  const roles = splitWrite ? [['a', 'write_a'], ['b', 'write_b']] : [['one', 'write']]
  for (const [role, name] of roles) {
    if ((stop = await capBetween(t, name, phases))) return stop
    const w = await writeStep(t, role); phases.push(w)
    if ((stop = stopAt(t, name, w, phases))) return stop
    if (role === 'a' && checkOf(t)) {
      // the checked-staged form: the check phase and gate 2 after it, before writer B (2026-10-24)
      if ((stop = await capBetween(t, 'check', phases))) return stop
      const c = await checkStep(t); phases.push(c)
      if ((stop = stopAt(t, 'check', c, phases))) return stop
    }
  }
  return finishTail(t, phases)
}

const results = (await parallel(args.tasks.map(t => () => runTask(t)))).filter(Boolean)
const blocked = []
for (const r of results) for (const p of r.phases) for (const a of [].concat(p.readers || [], p.fixes || [], p.writer || [], p.writers || [], p.checker || [], p.finisher || [], (p.rounds || []).map(r => r.reader).filter(Boolean))) {
  const res = a && a.result
  if (res && typeof res === 'object' && Array.isArray(res.blocked_passages)) blocked.push(...res.blocked_passages.map(b => ({ task: r.key, agent: a.label, ...b })))
}
const stopped = results.filter(o => !o.ok).map(o => `${o.key} at ${o.stopped_at} (${o.reason || 'no reason recorded'})`)
const flagged = results.filter(o => o.flagged).map(o => `${o.key} (${o.flagged})`)
log(`done: ${results.filter(o => o.ok).length} of ${args.tasks.length} task(s) completed every phase and every gate; ${blocked.length} blocked passage(s) reported` + (stopped.length ? `; stopped: ${stopped.join('; ')}` : '') + (flagged.length ? `; sample flagged: ${flagged.join('; ')}` : ''))
return { results, blocked_passages: blocked }
