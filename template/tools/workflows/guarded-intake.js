export const meta = {
  name: 'guarded-intake',
  description: 'Intake agents in parallel with the blocked-output guard: a dead agent is resumed from its wip checkpoint (up to maxResumes); a death after the last resume runs the bisect-block probes over wip/<task>/current-unit.md. With a task note, the quotation gate after the reply: gate 2 --quotes-only, run by a Haiku probe, and on failure the agent resumed with the report and the duty to clear it (up to maxGateResumes); then the sample reading (2026-10-25, every intake with a note): twenty claims rows drawn by seed (ledger sample draw), one Opus reader under phasesDir/sample.md, the tally into report.json sample_reading (ledger sample tally); this form has no check phase, so a note at the threshold is flagged in the report and the log and still integrates',
  whenToUse: 'Every intake or analysis fan-out (tools/filter-blocks.md section 6). args: {tasks:[{key, prompt, wip, note?, resumePrompt?}], model?, effort?, maxResumes?, maxGateResumes? (default 2), gateModel? (default haiku), quoteGate? (default true; false skips the gate), sample? (default true; false skips the sample phase; also per task), sampleThreshold? (default the pack [intake] sample_threshold the draw reports, else 3), phasesDir? (default wip/intake-staged/phases), python?, root?, bisectScript?}; run with scriptPath tools/workflows/guarded-intake.js',
  phases: [{ title: 'Intake' }, { title: 'Resume', detail: 'dead agents restarted from their checkpoint' }, { title: 'Probe', detail: 'bisect-block over the unit a twice-dead agent was handling' },
    { title: 'Gate 2', detail: 'tools/intake_gate.py --note <note> --wip <wip> --quotes-only after the reply, run by a Haiku probe' },
    { title: 'Gate fix', detail: 'the intake agent resumed with the gate report: every changed-words quotation corrected from ledger quote' },
    { title: 'Sample', detail: 'ledger sample draw (a Haiku probe), one Opus reader under phasesDir/sample.md, ledger sample tally into report.json sample_reading; at the threshold the note is flagged' }],
}
const tasks = args.tasks
const model = args.model || 'opus'
const effort = args.effort || 'high'
const maxResumes = args.maxResumes ?? 2
const maxGateResumes = args.maxGateResumes ?? 2   // the quotation gate's fix loop, as staged-intake.js runs it for its writers (2026-10-25)
const gateModel = args.gateModel || 'haiku'
const ROOT = args.root || ''
const PY = args.python || 'python3'
const PYRULE = args.python ? '' : `\nThe interpreter: if ${ROOT ? ROOT + '/' : ''}.ledger/venv/bin/python3 exists (on Windows .ledger/venv/Scripts/python.exe), run the command with that file in place of \`python3\`; otherwise run it as written.`
const phasesDir = args.phasesDir || 'wip/intake-staged/phases'
const sampleOf = t => (t.sample ?? args.sample) !== false
const DRAW = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, file: { type: 'string' }, rows: { type: 'number' }, total: { type: 'number' }, seed: { type: 'number' }, threshold: { type: 'number' } }, required: ['ok', 'summary'] }
const SAMPLE = { type: 'object', properties: { rows: { type: 'number' }, sound: { type: 'number' }, formal: { type: 'number' }, meaning: { type: 'number' },
  by_owner: { type: 'object', properties: { reader: { type: 'number' }, writer: { type: 'number' }, form: { type: 'number' } } }, meaning_rows: { type: 'array', items: { type: ['string', 'number'] } },
  files: { type: 'array', items: { type: 'string' } } }, required: ['rows', 'sound', 'formal', 'meaning', 'by_owner', 'meaning_rows', 'files'] }
const TALLY = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, rows: { type: 'number' }, sound: { type: 'number' }, formal: { type: 'number' }, meaning: { type: 'number' },
  meaning_rows: { type: 'array', items: { type: ['string', 'number'] } }, threshold: { type: 'number' }, over_threshold: { type: 'boolean' }, action: { type: 'string' } }, required: ['ok', 'summary'] }
// a JSON argument for a shell command in single quotes: an apostrophe inside it becomes a typographic one
const shellJson = v => `'${JSON.stringify(v).replace(/'/g, '\u2019')}'`
const GATE = { type: 'object', properties: { ok: { type: 'boolean' }, summary: { type: 'string' }, report: { type: 'string' }, quotations_checked: { type: 'number' },
  quote_exact: { type: 'number' }, quote_punct: { type: 'number' }, quote_fails: { type: 'number' }, quote_warns: { type: 'number' } }, required: ['ok', 'summary'] }

function resumeText(t, n, base) {
  return (base ?? (t.resumePrompt || t.prompt)) + `\n\nRESUME ${n} of ${maxResumes} (standing rule, tools/filter-blocks.md section 6): the previous agent on this task died; its output was refused by an API content filter or ended in a terminal API error, cause unknown. Continue from ${t.wip}/progress.md and ${t.wip}/parts/; do not redo recorded work. Before every large output (a note part, a source write-up, a long table) copy the source material of that unit by shell to ${t.wip}/current-unit.md and add one line to progress.md naming the unit and where it goes, so a further death can be bisected without you. Keep output units small (parts of about 1,500 words) and never pass a fetched text through your own output: copy files by shell.`
}

// one agent with the guard: resumed on death up to maxResumes, then the bisect-block probes
async function guarded(t, prompt, label, phase, schema) {
  let r = await agent(prompt, { label, phase, model, effort, schema })
  let deaths = 0
  while (r == null && deaths < maxResumes) {
    deaths++
    log(`${label}: agent died (output refused or terminal API error); resume ${deaths} of ${maxResumes} from ${t.wip}`)
    r = await agent(resumeText(t, deaths, prompt === t.prompt ? undefined : prompt), { label: `resume${deaths}:${label}`, phase: 'Resume', model, effort, schema })
  }
  let bisect = null
  if (r == null) {
    log(`${label}: dead after ${maxResumes} resumes; probing ${t.wip}/current-unit.md with bisect-block`)
    try { bisect = await workflow({ scriptPath: args.bisectScript || (ROOT ? `${ROOT}/tools/workflows/bisect-block.js` : 'tools/workflows/bisect-block.js') }, { file: `${t.wip}/current-unit.md` }) } catch (e) { bisect = { error: String(e) } }
  }
  return { r, deaths, bisect }
}

// the quotation gate: a Haiku probe runs gate 2 --quotes-only and relays its JSON line; it reads nothing else
async function quoteGate(t, g) {
  const cmd = `${PY} tools/intake_gate.py --note ${t.note} --wip ${t.wip} --quotes-only --json`
  const prompt = `Run from the project root ${ROOT || '(your working folder, the folder holding ledger.toml)'}, exactly this command and nothing else:\n  ${cmd}${PYRULE}\nThe command prints one JSON object on its last line and writes a report file. Return that JSON object's fields (ok, summary, report, quotations_checked, quote_exact, quote_punct, quote_fails, quote_warns) as your structured output, unchanged. Do not read the report or the note; do not fix anything.`
  const r = await agent(prompt, { label: `gate2:${t.key}:quotes:${g}`, phase: 'Gate 2', model: gateModel, effort: 'low', schema: GATE })
  return r == null ? { ok: false, summary: 'gate probe died', report: `${t.wip}/gate-note-quotes.md` } : r
}

function fixText(t, res) {
  return `\n\nTHE QUOTATION GATE FAILED on your note (gate 2 --quotes-only, run after your reply: ${res.summary}). Read ${res.report || t.wip + '/gate-note-quotes.md'} first. Every line under "## Failures" is a quotation whose words are not the source's word for word (a word changed, added or dropped), with the nearest unit lines and the difference. For each one: pull the source's words with \`python3 ledger.py quote --wip ${t.wip} --find "<a few of the words>"\` (or by pointer, \`python3 ledger.py quote --wip ${t.wip} u NNN:L-M\`) and paste them over the quotation, cutting only with \`...\` and marking a repair with [brackets] or [sic]; where the words are not the source's at all, take the quotation marks off and paraphrase. Lines under "## Punctuation only" are not failures (a caption quotation may add punctuation and capitals; the caption rule) and stay as they are; the warnings in sections that quote other notes are not yours to fix. Change nothing else in the note. Then run \`python3 tools/intake_gate.py --note ${t.note} --wip ${t.wip} --quotes-only\` yourself until it passes, update ${t.wip}/progress.md, and reply as your brief asks (the same report shape as before).`
}

// a script run by a Haiku probe that relays its JSON line (the sample draw and tally)
async function probe(label, cmd, schema, fields, fallback) {
  const prompt = `Run from the project root ${ROOT || '(your working folder, the folder holding ledger.toml)'}, exactly this command and nothing else:\n  ${cmd}${PYRULE}\nThe command prints one JSON object on its last line. Return that JSON object's fields (${fields}) as your structured output, unchanged. Do not read the note or the sample; do not fix anything.`
  const r = await agent(prompt, { label, phase: 'Sample', model: gateModel, effort: 'low', schema })
  return r == null ? fallback : r
}

// the sample reading after the quotation gate (2026-10-25): the draw, one guarded Opus reader, the tally; no check phase in this
// form, so a note whose faults of meaning reach the threshold is flagged (report, result and log) and still integrates
async function sample(t) {
  const out = {}
  out.draw = await probe(`sample-draw:${t.key}:1`, `${PY} ledger.py sample draw ${t.note} --wip ${t.wip} --n 20 --json`, DRAW, 'ok, summary, file, rows, total, seed, threshold', { ok: false, summary: 'draw probe died' })
  log(`${t.key}: sample draw: ${out.draw.summary}`)
  if (!out.draw.ok) { out.failed = 'the draw'; return out }
  const prompt = `Task ${t.key}: the SAMPLE phase of the intake (the single-agent form). Read ${phasesDir}/sample.md first and follow it. The note ${t.note} is finished and has passed the quotation gate. Your sample is ${out.draw.file || t.wip + '/sample.md'} (${out.draw.summary}): its rows carry no unit pointer, so locate each passage with \`python3 ledger.py quote --wip ${t.wip} --find "<a few of the row's quoted words>"\` or by the Time cell in ${t.wip}/units/, make the five judgements, and write ${t.wip}/sample-reading.md, ${t.wip}/sample-reading.tsv and ${t.wip}/sample-reading.progress.md (your checkpoint: one line per row read). This form has no findings files: every writer fault is \`writer\`. You correct nothing.\n\nReply with the structured fields sample.md asks for (rows, sound, formal, meaning, by_owner, meaning_rows, files).`
  const g = await guarded(t, prompt, `sample:${t.key}:1`, 'Sample', SAMPLE)
  out.deaths = g.deaths
  if (g.r == null) { out.failed = 'the reader'; out.bisect = g.bisect; return out }
  const thr = args.sampleThreshold ?? (typeof out.draw.threshold === 'number' ? out.draw.threshold : 3)
  const reply = typeof g.r === 'object' ? g.r : {}
  out.tally = await probe(`sample-tally:${t.key}:1`, `${PY} ledger.py sample tally --wip ${t.wip} --round 1 --threshold ${thr} --on-threshold flag --reply ${shellJson(reply)} --json`, TALLY,
    'ok, summary, rows, sound, formal, meaning, meaning_rows, threshold, over_threshold, action', { ok: false, summary: 'tally probe died' })
  log(`${t.key}: sample tally: ${out.tally.summary}`)
  if (!out.tally.ok) { out.failed = 'the tally'; return out }
  if (out.tally.over_threshold) {
    out.flagged = `faults of meaning ${out.tally.meaning} of ${out.tally.rows} reach the threshold ${out.tally.threshold} (rows ${(out.tally.meaning_rows || []).join(', ')}); the single-agent form has no check phase, so the note integrates flagged`
    log(`${t.key}: FLAGGED: ${out.flagged}`)
  }
  return out
}

async function run(t) {
  const first = await guarded(t, t.prompt, `intake:${t.key}`, 'Intake')
  let r = first.r, deaths = first.deaths, bisect = first.bisect
  const gates = [], fixes = []
  if (r != null && t.note && args.quoteGate !== false) {
    for (let g = 0; g <= maxGateResumes; g++) {
      const res = await quoteGate(t, g)
      gates.push(res)
      log(`${t.key}: quotation gate (${g}): ${res.summary}`)
      if (res.ok || g === maxGateResumes) break
      const fx = await guarded(t, t.prompt + fixText(t, res), `gate-fix:${t.key}:${g}`, 'Gate fix')
      fixes.push({ deaths: fx.deaths, ok: fx.r != null, reply_head: fx.r == null ? null : String(fx.r).slice(0, 1500), bisect: fx.bisect })
      deaths += fx.deaths
      if (fx.r == null) { bisect = fx.bisect; break }
      r = fx.r
    }
  }
  const gateOk = gates.length ? !!gates[gates.length - 1].ok : null
  let sampled = null
  if (r != null && t.note) sampled = sampleOf(t) ? await sample(t) : { skipped: 'sample false' }
  if (sampled && sampled.deaths) deaths += sampled.deaths
  const sr = sampled == null ? null : sampled.skipped ? { skipped: sampled.skipped } : sampled.tally && sampled.tally.ok ? sampled.tally : { failed: sampled.failed }
  return { key: t.key, ok: r != null, deaths, gate_ok: gateOk, gates, fixes, reply_head: r == null ? null : String(r).slice(0, 3000), bisect: bisect || (sampled && sampled.bisect) || null,
    ...(sampled ? { sample_reading: sr, sample: sampled } : {}), ...(sampled && sampled.flagged ? { flagged: sampled.flagged } : {}) }
}
const results = (await parallel(tasks.map(t => () => run(t)))).filter(Boolean)
const dead = results.filter(o => !o.ok)
const gated = results.filter(o => o.gate_ok !== null)
log(`done: ${results.filter(o => o.ok).length} of ${tasks.length} replied; ${results.filter(o => o.deaths > 0 && o.ok).length} recovered by resume; ${dead.length} dead after resumes` +
  (gated.length ? `; quotation gate passed on ${gated.filter(o => o.gate_ok).length} of ${gated.length} (${gated.reduce((a, o) => a + o.fixes.length, 0)} fix run(s))` : '') +
  (results.some(o => o.sample) ? `; sample read on ${results.filter(o => o.sample_reading && typeof o.sample_reading.rows === 'number').length}, failed on ${results.filter(o => o.sample_reading && o.sample_reading.failed).length}` : '') +
  (results.some(o => o.flagged) ? `; FLAGGED at the sample threshold: ${results.filter(o => o.flagged).map(o => o.key).join(', ')}` : ''))
return results
