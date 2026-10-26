// Dry runs of tools/workflows/guarded-intake.js (the single-agent form; 2026-10-25, wip/quote-tool-adoption/): the blocked-output
// guard, and the quotation gate after the reply (gate 2 --quotes-only by a Haiku probe; on failure the agent resumed with the report,
// up to maxGateResumes). The single-agent form is the legacy project's; it is not shipped in the bundle.
//   node tools/workflows/tests/test_guarded_intake.mjs        (exit 1 on a failure; tools/ledger/tests/test_guarded_intake_workflow.py runs it)
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { dryRun } from './dryrun.mjs'

const SCRIPT = join(dirname(dirname(fileURLToPath(import.meta.url))), 'guarded-intake.js')
const task = (key, extra = {}) => ({ key, wip: `wip/${key}`, note: `books/${key}.md`, prompt: `INTAKE ${key}`, ...extra })
const PASS = { ok: true, summary: 'PASS: 40 quotations (30 exact, 10 punctuation only (forgiven), 0 changed words, 0 warnings)', report: 'q.md', quote_fails: 0, quote_punct: 10 }
const FAIL = { ok: false, summary: 'FAIL: 40 quotations (20 exact, 5 punctuation only (forgiven), 15 changed words, 0 warnings)', report: 'wip/t1/gate-note-quotes.md', quote_fails: 15 }
function sc(over = {}) {
  return label => {
    if (over[label] !== undefined) return over[label]
    if (label.startsWith('gate2:')) return PASS
    if (label.startsWith('sample-draw')) return { ok: true, summary: '20 of 61 claims rows drawn by seed 7 (no pointer 20 of 61)', file: 'wip/t1/sample.md', rows: 20, total: 61, seed: 7, threshold: 3 }
    if (label.startsWith('sample-tally')) return { ok: true, summary: 'meaning 1 of 20', rows: 20, sound: 14, formal: 5, meaning: 1, meaning_rows: ['12'], threshold: 3, over_threshold: false, action: 'none' }
    if (label.startsWith('sample:')) return { rows: 20, sound: 14, formal: 5, meaning: 1, by_owner: { reader: 0, writer: 6, form: 0 }, meaning_rows: ['12'], files: ['wip/t1/sample-reading.md'] }
    return `{"report": "${label}"}`
  }
}
const order = calls => calls.map(c => c.label.split(':')[0])
const SAMPLED = ['sample-draw', 'sample', 'sample-tally']   // the sample reading after the gate, on every intake with a note (2026-10-25)
const tests = []
const test = (name, f) => tests.push([name, f])

test('the gate runs after the reply; a pass ends the task', async () => {
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc())
  assert.deepEqual(order(calls), ['intake', 'gate2', ...SAMPLED])
  const g = calls.find(c => c.label === 'gate2:t1:quotes:0')
  assert.equal(g.model, 'haiku'); assert.equal(g.phase, 'Gate 2')
  assert.match(g.prompt, /python3 tools\/intake_gate\.py --note books\/t1\.md --wip wip\/t1 --quotes-only --json/); assert.match(g.prompt, /venv/)
  assert.equal(result[0].ok, true); assert.equal(result[0].gate_ok, true); assert.equal(result[0].fixes.length, 0)
})

test('a failing gate resumes the agent with the report and the duty to clear it, then the gate again', async () => {
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc({ 'gate2:t1:quotes:0': FAIL }))
  assert.deepEqual(order(calls), ['intake', 'gate2', 'gate-fix', 'gate2', ...SAMPLED])
  const f = calls.find(c => c.label === 'gate-fix:t1:0')
  assert.equal(f.model, 'opus'); assert.equal(f.effort, 'high'); assert.equal(f.phase, 'Gate fix')
  assert.match(f.prompt, /^INTAKE t1\n\nTHE QUOTATION GATE FAILED/); assert.match(f.prompt, /wip\/t1\/gate-note-quotes\.md/)
  assert.match(f.prompt, /python3 ledger\.py quote --wip wip\/t1 --find "<a few of the words>"/); assert.match(f.prompt, /u NNN:L-M/)
  assert.match(f.prompt, /"## Punctuation only" are not failures/); assert.match(f.prompt, /--quotes-only` yourself until it passes/)
  assert.equal(result[0].gate_ok, true); assert.equal(result[0].fixes.length, 1)
})

test('maxGateResumes bounds the loop (default 2); the result says the gate still fails', async () => {
  let { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc({ 'gate2:t1:quotes:0': FAIL, 'gate2:t1:quotes:1': FAIL, 'gate2:t1:quotes:2': FAIL }))
  assert.deepEqual(order(calls), ['intake', 'gate2', 'gate-fix', 'gate2', 'gate-fix', 'gate2', ...SAMPLED])
  assert.equal(result[0].ok, true); assert.equal(result[0].gate_ok, false)
  ;({ result, calls } = await dryRun(SCRIPT, { maxGateResumes: 0, tasks: [task('t1')] }, sc({ 'gate2:t1:quotes:0': FAIL })))
  assert.deepEqual(order(calls), ['intake', 'gate2', ...SAMPLED]); assert.equal(result[0].gate_ok, false)
})

test('no note, or quoteGate false: no gate (the old behaviour)', async () => {
  let { calls } = await dryRun(SCRIPT, { tasks: [task('t1', { note: undefined })] }, sc())
  assert.deepEqual(order(calls), ['intake'])
  ;({ calls } = await dryRun(SCRIPT, { quoteGate: false, tasks: [task('t1')] }, sc()))
  assert.deepEqual(order(calls), ['intake', ...SAMPLED])
})

test('a dead agent is resumed before the gate; a dead fix is resumed with the fix in its prompt', async () => {
  let { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc({ 'intake:t1': null }))
  assert.deepEqual(order(calls), ['intake', 'resume1', 'gate2', ...SAMPLED])
  assert.match(calls.find(c => c.label === 'resume1:intake:t1').prompt, /^INTAKE t1\n\nRESUME 1 of 2/)
  ;({ result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc({ 'gate2:t1:quotes:0': FAIL, 'gate-fix:t1:0': null })))
  assert.deepEqual(order(calls), ['intake', 'gate2', 'gate-fix', 'resume1', 'gate2', ...SAMPLED])
  assert.match(calls.find(c => c.label === 'resume1:gate-fix:t1:0').prompt, /THE QUOTATION GATE FAILED[\s\S]*RESUME 1 of 2/)
  assert.equal(result[0].deaths, 1)
})

test('a task dead after every resume gets the bisect probe and no gate', async () => {
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1'), task('t2')] }, sc({ 'intake:t1': null, 'resume1:intake:t1': null, 'resume2:intake:t1': null }))
  const r1 = result.find(r => r.key === 't1')
  assert.equal(r1.ok, false); assert.deepEqual(r1.bisect, { probed: true }); assert.equal(r1.gate_ok, null)
  assert.ok(!calls.some(c => c.label === 'gate2:t1:quotes:0')); assert.ok(calls.some(c => c.label === 'gate2:t2:quotes:0'))
})

test('args.python and args.root reach the probe', async () => {
  const { calls } = await dryRun(SCRIPT, { python: '/opt/py/bin/python3', root: '/p/dup', tasks: [task('t1')] }, sc())
  const g = calls.find(c => c.label.startsWith('gate2')).prompt
  assert.match(g, /\/opt\/py\/bin\/python3 tools\/intake_gate\.py/); assert.match(g, /project root \/p\/dup/); assert.doesNotMatch(g, /venv/)
})

// ---------------------------------------------------------------- the sample phase (2026-10-25, wip/sample-phase/)
test('the sample reading runs after the gate: the draw, one Opus reader (by --find, no pointers), the tally with --on-threshold flag', async () => {
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc())
  const d = calls.find(c => c.label === 'sample-draw:t1:1'), r = calls.find(c => c.label === 'sample:t1:1'), y = calls.find(c => c.label === 'sample-tally:t1:1')
  assert.equal(d.model, 'haiku'); assert.match(d.prompt, /python3 ledger\.py sample draw books\/t1\.md --wip wip\/t1 --n 20 --json/)
  assert.equal(r.model, 'opus'); assert.equal(r.effort, 'high'); assert.equal(r.phase, 'Sample')
  assert.match(r.prompt, /wip\/intake-staged\/phases\/sample\.md/); assert.match(r.prompt, /--find/); assert.match(r.prompt, /every writer fault is `writer`/)
  assert.match(y.prompt, /sample tally --wip wip\/t1 --round 1 --threshold 3 --on-threshold flag --reply '\{"rows":20/)
  assert.equal(result[0].sample_reading.meaning, 1); assert.equal(result[0].flagged, undefined)
})

test('at the threshold the note is flagged in the result and the log, and nothing else runs; sample false skips', async () => {
  const OVER = { ok: true, summary: 'meaning 4 of 20', rows: 20, sound: 10, formal: 6, meaning: 4, meaning_rows: ['3', '8', '11', '19'], threshold: 3, over_threshold: true, action: 'flag' }
  let { result, calls, logs } = await dryRun(SCRIPT, { tasks: [task('t1')] }, sc({ 'sample-tally:t1:1': OVER }))
  assert.deepEqual(order(calls), ['intake', 'gate2', ...SAMPLED])
  assert.match(result[0].flagged, /4 of 20 reach the threshold 3 \(rows 3, 8, 11, 19\); the single-agent form has no check phase/)
  assert.ok(logs.some(l => /FLAGGED: faults of meaning 4/.test(l))); assert.ok(logs.some(l => /FLAGGED at the sample threshold: t1/.test(l)))
  ;({ result, calls } = await dryRun(SCRIPT, { sample: false, tasks: [task('t1')] }, sc()))
  assert.deepEqual(order(calls), ['intake', 'gate2']); assert.deepEqual(result[0].sample_reading, { skipped: 'sample false' })
  ;({ result, calls } = await dryRun(SCRIPT, { sampleThreshold: 6, tasks: [task('t1', { sample: true })] }, sc({ 'sample:t1:1': null })))
  assert.match(calls.find(c => c.label === 'resume1:sample:t1:1').prompt, /SAMPLE phase[\s\S]*RESUME 1 of 2/)
  assert.match(calls.find(c => c.label === 'sample-tally:t1:1').prompt, /--threshold 6 /)
})

let failed = 0
for (const [name, f] of tests) {
  try { await f(); console.log(`ok   ${name}`) } catch (e) { failed++; console.log(`FAIL ${name}\n     ${e.message.split('\n').join('\n     ')}`) }
}
console.log(`${tests.length - failed} of ${tests.length} passed`)
process.exit(failed ? 1 : 0)
