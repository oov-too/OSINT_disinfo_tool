// Dry runs of tools/workflows/staged-intake.js (the split write, the per-task maxRecords cap; 2026-10-23, wip/split-write/; the
// unit-writers form and the check phase, 2026-10-24, wip/forms-measure/; unit writers the default, the check optional in either
// form with the order of attention and checkBudget, writers sized by words, 2026-10-25, wip/quote-tool-adoption/). The staged
// form's cases pass intakeForm 'staged'.
//   node tools/workflows/tests/test_staged_intake.mjs        (exit 1 on a failure; tools/ledger/tests/test_staged_intake_workflow.py runs it)
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { dryRun } from './dryrun.mjs'

const SCRIPT = join(dirname(dirname(fileURLToPath(import.meta.url))), 'staged-intake.js')
const task = (key, extra = {}) => ({ key, wip: `wip/${key}`, note: `books/${key}.md`, form: 'document', units: 2, words: 4000, ...extra })

// the default scenario: every agent succeeds, every gate passes, usage probes report `usage[key]` records
function happy(usage = {}, over = {}) {
  return (label, prompt) => {
    if (over[label] !== undefined) return typeof over[label] === 'function' ? over[label](label, prompt) : over[label]
    if (label.startsWith('sample-draw')) return { ok: true, summary: '20 of 40 claims rows drawn by seed 7', file: `wip/${label.split(':')[1]}/sample${label.endsWith(':1') ? '' : '-2'}.md`, rows: 20, total: 40, seed: 7, threshold: 3 }
    if (label.startsWith('sample-tally')) return { ok: true, summary: 'meaning 1 of 20', rows: 20, sound: 15, formal: 4, meaning: 1, meaning_rows: ['7'], threshold: 3, over_threshold: false, action: 'none' }
    if (label.startsWith('sample:')) return { rows: 20, sound: 15, formal: 4, meaning: 1, by_owner: { reader: 0, writer: 5, form: 0 }, meaning_rows: ['7'], files: ['wip/t1/sample-reading.md'] }
    if (label.startsWith('gate-parts')) return { ok: true, summary: 'PASS', report: 'p.md', rows: '1-10', audit_rows: '1-2', last_row: 10, last_audit_row: 2, failing_units: [] }
    if (label.startsWith('gate')) return { ok: true, summary: 'PASS', report: 'r.md', failing_units: [] }
    if (label.startsWith('assemble:')) return { ok: true, summary: 'assembled', claims_rows: 20, audit_rows: 4 }
    if (label.includes('write-unit')) return { units: 'x', rows: '1-10', audit_rows: '1-2', parts: [], verbatim_check: '0', nothing_to_row: [], blocked_passages: [], notes: '' }
    if (label.startsWith('check') || label.includes(':check')) return { rows_read: 20, corrected: 3, by_judgement: { support: 2, grain: 1 }, split_rows: ['4.1'], unsupported: ['row 9'], outside_matter: ['a date from outside'], log: 'wip/t1/check-log.md', notes: '' }
    if (label.startsWith('usage:')) { const k = label.split(':')[1]; return { ok: true, records: usage[k] ?? 0, summary: `${k} usage` } }
    if (label.includes('read')) return { units_done: 2, units: '001-002', blocked_passages: [], notes: '' }
    if (label.includes('write')) return { file: 'n.md', words: 1, claims_rows: 10, parts: 1, verbatim_check: '0', blocked_passages: [], notes: '' }
    return { report: 'json' }
  }
}
const order = calls => calls.map(c => c.label.split(':')[0])
const SAMPLED = ['sample-draw', 'sample', 'sample-tally']   // the sample phase after the finish, on every intake (2026-10-25)
const tests = []
const test = (name, f) => tests.push([name, f])

test('split write is the default: read, gate 1, writer A, gate 2, writer B, gate 2, finish, gate 2', async () => {
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1')] }, happy())
  assert.deepEqual(order(calls), ['read', 'gate1', 'write-a', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.equal(result.results[0].ok, true)
  assert.deepEqual(result.results[0].phases.map(p => p.phase), ['read', 'write_a', 'write_b', 'finish', 'sample'])
  const a = calls.find(c => c.label === 'write-a:t1'), b = calls.find(c => c.label === 'write-b:t1')
  assert.equal(a.phase, 'Write A'); assert.equal(b.phase, 'Write B')
  assert.match(a.prompt, /writer A, the ledger/); assert.match(a.prompt, /"Writer A: the ledger" section/); assert.match(a.prompt, /not the Writer B section/)
  assert.match(a.prompt, /ledger-notes\.md/); assert.match(a.prompt, /parts\/aNN\.md/); assert.match(a.prompt, /Units with nothing to row:/)
  assert.match(b.prompt, /writer B, the sections/); assert.match(b.prompt, /not the Writer A section/); assert.match(b.prompt, /parts\/bNN\.md/)
  assert.match(b.prompt, /claims_rows is writer A's count/)
  assert.ok(!calls.some(c => c.label.startsWith('usage:')), 'no maxRecords, no usage probe')
})

test('splitWrite false keeps one writer with the prompt key write', async () => {
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', splitWrite: false, tasks: [task('t1', { prompts: { write: 'MY WRITE PROMPT' } })] }, happy())
  assert.deepEqual(order(calls), ['read', 'gate1', 'write', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.match(calls.find(c => c.label === 'write:t1').prompt, /^MY WRITE PROMPT/)
  assert.equal(result.results[0].ok, true)
})

test('prompts.write_a and prompts.write_b replace the generated prompts', async () => {
  const { calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { prompts: { write_a: 'PA', write_b: 'PB' } })] }, happy())
  assert.match(calls.find(c => c.label === 'write-a:t1').prompt, /^PA\n\nReply with the structured fields/)
  assert.match(calls.find(c => c.label === 'write-b:t1').prompt, /^PB\n\nReply/)
})

test('gate 2 failing after writer A sends writer A its report, then writer B runs', async () => {
  let n = 0
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1')] }, happy({}, { 'gate2:t1:write-a:0': { ok: false, summary: 'FAIL', report: 'wip/t1/gate-note.md' } }))
  assert.deepEqual(order(calls), ['read', 'gate1', 'write-a', 'gate2', 'write-a-fix', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  const fix = calls.find(c => c.label === 'write-a-fix:t1:0')
  assert.equal(fix.phase, 'Write A'); assert.match(fix.prompt, /GATE 2 FAILED after your write \(writer A\)/); assert.match(fix.prompt, /wip\/t1\/gate-note\.md/)
  assert.equal(result.results[0].ok, true)
})

test('a dead writer is resumed from its parts (aNN for A, bNN for B)', async () => {
  const dead = { 'write-a:t1': null, 'write-b:t1': null }
  const { calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1')] }, happy({}, dead))
  assert.match(calls.find(c => c.label === 'resume1:write-a:t1').prompt, /RESUME 1 of 2[\s\S]*parts\/aNN\.md/)
  assert.match(calls.find(c => c.label === 'resume1:write-b:t1').prompt, /RESUME 1 of 2[\s\S]*parts\/bNN\.md/)
})

test('maxRecords stops that task alone between phases; the other task finishes', async () => {
  // t1's probe reports 50 before writer A and 150 before writer B (cap 100); t2 has no cap
  let probes = 0
  const sc = happy({}, { 'usage:t1:1': { ok: true, records: 50, summary: 's' }, 'usage:t1:2': { ok: true, records: 150, summary: 'over' } })
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { maxRecords: 100 }), task('t2')] }, sc)
  const r1 = result.results.find(r => r.key === 't1'), r2 = result.results.find(r => r.key === 't2')
  assert.equal(r1.ok, false); assert.equal(r1.stopped_at, 'write_b'); assert.match(r1.reason, /passed maxRecords/); assert.equal(r1.records, 150)
  assert.ok(!calls.some(c => c.label === 'write-b:t1'), 'writer B of the capped task never starts')
  assert.equal(r2.ok, true); assert.ok(calls.some(c => c.label === 'finish:t2'))
  assert.ok(!calls.some(c => c.label.startsWith('usage:t2')), 'no cap on t2, no probe')
  const probe = calls.find(c => c.label === 'usage:t1:1')
  assert.equal(probe.phase, 'Usage'); assert.equal(probe.model, 'haiku'); assert.match(probe.prompt, /agent_usage\.py --task t1 --records/)
})

test('maxRecords is checked inside the guard before a resume', async () => {
  const sc = happy({}, { 'write-a:t1': null, 'usage:t1:1': { ok: true, records: 10, summary: 's' }, 'usage:t1:2': { ok: true, records: 500, summary: 'over' } })
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { maxRecords: 100 })] }, sc)
  const r = result.results[0]
  assert.equal(r.stopped_at, 'write_a'); assert.match(r.reason, /before resume 1 of write-a:t1/)
  assert.ok(!calls.some(c => c.label.startsWith('resume1:')), 'no resume past the cap')
})

test('recordsBefore counts an earlier run of the task against the cap', async () => {
  const sc = happy({ t1: 60 })
  const { result } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { maxRecords: 100, recordsBefore: 50 })] }, sc)
  assert.equal(result.results[0].stopped_at, 'write_a'); assert.equal(result.results[0].records, 110)
})

test('a usage probe that dies does not stop the task', async () => {
  const sc = happy({}, { 'usage:t1:1': null, 'usage:t1:2': null, 'usage:t1:3': null })
  const { result, logs } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { maxRecords: 100 })] }, sc)
  assert.equal(result.results[0].ok, true)
  assert.ok(logs.some(l => /usage probe .* gave no figure/.test(l)))
})

test('fan-out (pilot defect 25): a 40,000-word source of 16 units gets two readers; 30,000 words one; readerUnits overrides', async () => {
  const readers = calls => calls.filter(c => c.label.startsWith('read:')).map(c => c.label.split(':')[2])
  let r = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { units: 16, words: 40000 })] }, happy())
  assert.deepEqual(readers(r.calls), ['001-008', '009-016'])
  r = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { units: 12, words: 30000 })] }, happy())
  assert.deepEqual(readers(r.calls), ['001-012'])
  r = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { units: 19, words: 46937 })] }, happy())
  assert.deepEqual(readers(r.calls), ['001-010', '011-019'])
  r = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { units: 16, words: 40000 })], readerUnits: 4 }, happy())
  assert.equal(readers(r.calls).length, 4)
})

test('the gate and usage probes are told to use the project venv (pilot defect 24); args.python replaces the rule', async () => {
  let { calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { maxRecords: 1e12 })] }, happy())
  const g = calls.find(c => c.label.startsWith('gate1')), u = calls.find(c => c.label.startsWith('usage:'))
  for (const c of [g, u]) { assert.match(c.prompt, /\.ledger\/venv\/bin\/python3 exists/); assert.match(c.prompt, /Scripts\/python\.exe/) }
  ;({ calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1')], python: '/opt/py/bin/python3' }, happy()))
  const g2 = calls.find(c => c.label.startsWith('gate1'))
  assert.match(g2.prompt, /\/opt\/py\/bin\/python3 tools\/intake_gate\.py/); assert.doesNotMatch(g2.prompt, /venv/)
})

const uwTask = (key, extra = {}) => task(key, { intakeForm: 'unit-writers', units: 9, unitNumbers: ['001', '002', '003', '004', '005', '006', '008', '009', '010'], words: 21305, ...extra })

test('unit-writers form: no read phase; writers in sequence over ranges sized by words, the parts gate after each, the assembly, gate 2, writer B, finish', async () => {
  const sc = happy({}, {
    'gate-parts:t1:001-005:0': { ok: true, summary: 'PASS', rows: '1-40', audit_rows: '1-7', last_row: 40, last_audit_row: 7 },
    'write-unit:t1:001-005': { units: '001-005', rows: '1-40', audit_rows: '1-7', parts: [], verbatim_check: '0', nothing_to_row: [{ unit: '004', reason: "a caption page (the editors' box)" }], blocked_passages: [], notes: '' },
  })
  const { result, calls } = await dryRun(SCRIPT, { tasks: [uwTask('t1')] }, sc)
  assert.deepEqual(order(calls), ['write-unit', 'gate-parts', 'write-unit', 'gate-parts', 'assemble', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.equal(result.results[0].ok, true)
  assert.deepEqual(result.results[0].phases.map(p => p.phase), ['write_units', 'write_b', 'finish', 'sample'])
  const w1 = calls.find(c => c.label === 'write-unit:t1:001-005'), w2 = calls.find(c => c.label === 'write-unit:t1:006-010')
  assert.equal(w1.phase, 'Write units'); assert.equal(w1.model, 'opus')
  assert.match(w1.prompt, /write-unit\.md/); assert.match(w1.prompt, /unit writer 1 of 2/); assert.match(w1.prompt, /001, 002, 003, 004, 005/)
  assert.match(w1.prompt, /ledger starts at row 1 and your audit at row 1/)
  assert.match(w2.prompt, /006, 008, 009, 010/); assert.match(w2.prompt, /ledger starts at row 41 and your audit at row 8/); assert.match(w2.prompt, /you append to it/)
  const g1 = calls.find(c => c.label === 'gate-parts:t1:001-005:0'), g2 = calls.find(c => c.label === 'gate-parts:t1:006-010:0')
  assert.equal(g1.model, 'haiku'); assert.equal(g1.phase, 'Gate parts')
  assert.match(g1.prompt, /--note-parts wip\/t1\/parts --wip wip\/t1 --units 001-005 --start-row 1 --start-audit 1 --nothing-to-row '\[\{"unit":"004","reason":"a caption page \(the editors’ box\)"\}\]' --json/)
  assert.match(g2.prompt, /--units 006-010 --start-row 41 --start-audit 8 --nothing-to-row '\[\]'/)
  const asm = calls.find(c => c.label === 'assemble:t1:0')
  assert.equal(asm.phase, 'Assemble'); assert.match(asm.prompt, /tools\/assemble_parts\.py --wip wip\/t1 --note books\/t1\.md --nothing-to-row '\{"004":"a caption page/)
  assert.ok(calls.some(c => c.label === 'gate2:t1:assembled:0'))
  const b = calls.find(c => c.label === 'write-b:t1')
  assert.match(b.prompt, /unit-writers form, as writer B/); assert.match(b.prompt, /no read phase and no findings files/); assert.match(b.prompt, /the metadata table/)
  assert.match(calls.find(c => c.label === 'finish:t1').prompt, /unit-writers form/)
  assert.ok(!calls.some(c => c.label.startsWith('read') || c.label.startsWith('write-a') || c.label.startsWith('gate1')))
})

test('unit-writers: a failing parts gate sends the writer its report; the fix reply replaces nothing_to_row', async () => {
  const sc = happy({}, {
    'gate-parts:t1:001-002:0': { ok: false, summary: 'FAIL', report: 'wip/t1/gate-parts-001-002.md', failing_units: ['002'] },
    'write-unit-fix:t1:001-002:0': { units: '001-002', rows: '1-9', nothing_to_row: [{ unit: '2', reason: 'blank page' }], blocked_passages: [] },
  })
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1', { form: 'unit-writers', units: 2, words: 4913 })] }, sc)
  assert.deepEqual(order(calls), ['write-unit', 'gate-parts', 'write-unit-fix', 'gate-parts', 'assemble', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  const fix = calls.find(c => c.label === 'write-unit-fix:t1:001-002:0')
  assert.match(fix.prompt, /THE PARTS GATE FAILED/); assert.match(fix.prompt, /wip\/t1\/gate-parts-001-002\.md/)
  assert.match(calls.find(c => c.label === 'gate-parts:t1:001-002:1').prompt, /--nothing-to-row '\[\{"unit":"002","reason":"blank page"\}\]'/)
  assert.equal(result.results[0].ok, true)
})

test('unit-writers: a failed assembly stops the task; gate 2 failing on the assembled note sends a fix and re-assembles', async () => {
  let r = await dryRun(SCRIPT, { tasks: [uwTask('t1')] }, happy({}, { 'assemble:t1:0': { ok: false, summary: 'exists and is not an earlier assembly' } }))
  assert.equal(r.result.results[0].ok, false); assert.equal(r.result.results[0].stopped_at, 'write_units'); assert.match(r.result.results[0].reason, /assembly script failed/)
  r = await dryRun(SCRIPT, { tasks: [uwTask('t1')] }, happy({}, { 'gate2:t1:assembled:0': { ok: false, summary: 'FAIL', report: 'wip/t1/gate-note.md' } }))
  assert.deepEqual(order(r.calls).slice(4), ['assemble', 'gate2', 'write-unit-fix', 'assemble', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.match(r.calls.find(c => c.label === 'write-unit-fix:t1:assembled:0').prompt, /GATE 2 FAILED on the note assembled/)
  assert.equal(r.result.results[0].ok, true)
})

test('unit-writers: maxRecords is read between unit writers', async () => {
  const sc = happy({}, { 'usage:t1:1': { ok: true, records: 500, summary: 'over' } })
  const { result, calls } = await dryRun(SCRIPT, { tasks: [uwTask('t1', { maxRecords: 100 })] }, sc)
  assert.equal(result.results[0].stopped_at, 'write_units'); assert.match(result.results[0].reason, /before unit writer 2/)
  assert.ok(!calls.some(c => c.label === 'write-unit:t1:006-010'))
})

test('check true: read, gate 1, writer A, gate 2, check, gate 2, writer B, gate 2, finish, gate 2; its lists reach writer B and the finisher', async () => {
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { check: true }), task('t2')] }, happy())
  const t1 = calls.filter(c => c.label.split(':')[1] === 't1')
  assert.deepEqual(order(t1), ['read', 'gate1', 'write-a', 'gate2', 'check', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.deepEqual(result.results.find(r => r.key === 't1').phases.map(p => p.phase), ['read', 'write_a', 'check', 'write_b', 'finish', 'sample'])
  const c = calls.find(c => c.label === 'check:t1')
  assert.equal(c.phase, 'Check'); assert.equal(c.model, 'opus'); assert.match(c.prompt, /check\.md/); assert.match(c.prompt, /rows_read, corrected, by_judgement, split_rows, unsupported, outside_matter, log, notes/)
  assert.match(calls.find(c => c.label === 'write-b:t1').prompt, /a date from outside/)
  assert.match(calls.find(c => c.label === 'finish:t1').prompt, /row 9/)
  assert.ok(!calls.some(c => c.label === 'check:t2'), 'check is per task')
})

test('check true: gate 2 failing after the check sends the checker its report', async () => {
  const { result, calls } = await dryRun(SCRIPT, { intakeForm: 'staged', check: true, tasks: [task('t1')] }, happy({}, { 'gate2:t1:check:0': { ok: false, summary: 'FAIL', report: 'wip/t1/gate-note.md' } }))
  assert.deepEqual(order(calls), ['read', 'gate1', 'write-a', 'gate2', 'check', 'gate2', 'check-fix', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.match(calls.find(c => c.label === 'check-fix:t1:0').prompt, /GATE 2 FAILED after the check/)
  assert.equal(result.results[0].ok, true)
})

test('defaults (2026-10-25): a task with no form runs unit writers, the check off; form "staged" per task runs the read phase', async () => {
  let { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, happy())
  assert.deepEqual(order(calls), ['write-unit', 'gate-parts', 'assemble', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.deepEqual(result.results[0].phases.map(p => p.phase), ['write_units', 'write_b', 'finish', 'sample'])
  assert.ok(!calls.some(c => c.label.startsWith('check')), 'the check is off by default')
  ;({ calls } = await dryRun(SCRIPT, { tasks: [task('t1', { form: 'staged' }), task('t2')] }, happy()))
  assert.deepEqual(order(calls.filter(c => c.label.split(':')[1] === 't1')), ['read', 'gate1', 'write-a', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.equal(order(calls.filter(c => c.label.split(':')[1] === 't2'))[0], 'write-unit')
  ;({ calls } = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { intakeForm: 'unit-writers' })] }, happy()))
  assert.equal(order(calls)[0], 'write-unit', 'a task\'s intakeForm wins over the args\'')
})

test('unit writers are sized by words: about 10,000 to 20,000 words each; readerUnits and fanoutWords override', async () => {
  const writers = calls => calls.filter(c => /^write-unit:/.test(c.label)).map(c => c.label.split(':')[2])
  let r = await dryRun(SCRIPT, { tasks: [task('t1', { units: 2, words: 4913 })] }, happy())
  assert.deepEqual(writers(r.calls), ['001-002'])
  r = await dryRun(SCRIPT, { tasks: [uwTask('t1')] }, happy())
  assert.deepEqual(writers(r.calls), ['001-005', '006-010'])
  r = await dryRun(SCRIPT, { tasks: [task('t1', { units: 24, words: 60000 })] }, happy())
  assert.deepEqual(writers(r.calls), ['001-008', '009-016', '017-024'])
  r = await dryRun(SCRIPT, { tasks: [task('t1', { units: 8, words: 19000 })] }, happy())
  assert.deepEqual(writers(r.calls), ['001-008'])
  r = await dryRun(SCRIPT, { readerUnits: 3, tasks: [uwTask('t1')] }, happy())
  assert.deepEqual(writers(r.calls), ['001-003', '004-006', '008-010'])
  r = await dryRun(SCRIPT, { fanoutWords: 8000, tasks: [uwTask('t1')] }, happy())
  assert.equal(writers(r.calls).length, 3)
  r = await dryRun(SCRIPT, { intakeForm: 'staged', tasks: [task('t1', { units: 12, words: 30000 })] }, happy())
  assert.deepEqual(r.calls.filter(c => c.label.startsWith('read:')).map(c => c.label.split(':')[2]), ['001-012'], 'the staged form keeps its 35,000-word readers')
})

test('the unit writer prompt carries write-unit.md\'s obligations: quote by tool, clear the parts gate, punctuation only is not a failure', async () => {
  const { calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, happy())
  const w = calls.find(c => c.label === 'write-unit:t1:001-002').prompt
  assert.match(w, /python3 ledger\.py quote --wip wip\/t1 u NNN:L-M/); assert.match(w, /python3 ledger\.py quote --wip wip\/t1 --find "<a few of the words>"/)
  assert.match(w, /never typed from the unit/); assert.match(w, /clear every failure it lists/); assert.match(w, /`punctuation only` line is not a failure/)
  assert.match(w, /Never reply with a quotation failure open/)
  const fix = (await dryRun(SCRIPT, { tasks: [task('t1')] }, happy({}, { 'gate-parts:t1:001-002:0': { ok: false, summary: 'FAIL', report: 'r.md' } }))).calls.find(c => c.label === 'write-unit-fix:t1:001-002:0')
  assert.match(fix.prompt, /changed words/)
})

test('check true in the unit-writers form: after the assembled note\'s gate 2, before writer B; the order of attention; checkBudget', async () => {
  let { result, calls } = await dryRun(SCRIPT, { check: true, tasks: [task('t1')] }, happy())
  assert.deepEqual(order(calls), ['write-unit', 'gate-parts', 'assemble', 'gate2', 'check', 'gate2', 'write-b', 'gate2', 'finish', 'gate2', ...SAMPLED])
  assert.deepEqual(result.results[0].phases.map(p => p.phase), ['write_units', 'check', 'write_b', 'finish', 'sample'])
  const c = calls.find(c => c.label === 'check:t1').prompt
  assert.match(c, /after the unit writers/); assert.match(c, /The order of attention/); assert.match(c, /first every row classed `firsthand` in a document note/)
  assert.match(c, /fourth every row whose quotation ends mid-sentence/); assert.match(c, /Read every row\./); assert.doesNotMatch(c, /or the findings/)
  assert.match(c, /--find/); assert.match(c, /never reply with a quotation failure open/)
  assert.match(calls.find(c => c.label === 'write-b:t1').prompt, /a date from outside/)
  assert.match(calls.find(c => c.label === 'finish:t1').prompt, /after the unit writers[\s\S]*row 9/)
  ;({ calls } = await dryRun(SCRIPT, { check: true, checkBudget: 40, tasks: [task('t1'), task('t2', { checkBudget: 15 })] }, happy()))
  assert.match(calls.find(c => c.label === 'check:t1').prompt, /Your budget is 40 rows/)
  assert.match(calls.find(c => c.label === 'check:t2').prompt, /Your budget is 15 rows/)
})

test('args.root opens every agent prompt with the project root (2026-10-25); without it, no root line', async () => {
  let { calls } = await dryRun(SCRIPT, { root: '/p/dup', tasks: [task('t1')] }, happy({}, { 'write-b:t1': null }))
  for (const l of ['write-unit:t1:001-002', 'write-b:t1', 'resume1:write-b:t1', 'finish:t1'])
    assert.match(calls.find(c => c.label === l).prompt, /^The project root is \/p\/dup: run every command from it/, l)
  assert.doesNotMatch(calls.find(c => c.label.startsWith('gate-parts')).prompt, /^The project root is/)
  ;({ calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, happy()))
  assert.match(calls.find(c => c.label === 'write-unit:t1:001-002').prompt, /^Task t1/)
})

// ---------------------------------------------------------------- the sample phase (2026-10-25, wip/sample-phase/)
const OVER = { ok: true, summary: 'meaning 3 of 20; threshold 3 reached', rows: 20, sound: 12, formal: 5, meaning: 3, meaning_rows: ['4', '9', '12'], threshold: 3, over_threshold: true, action: 'check' }

test('the sample phase runs after the finish and its gate: the draw, one Opus reader, the tally into report.json', async () => {
  const { result, calls } = await dryRun(SCRIPT, { tasks: [task('t1')] }, happy())
  assert.deepEqual(order(calls).slice(-5), ['finish', 'gate2', 'sample-draw', 'sample', 'sample-tally'])
  const d = calls.find(c => c.label === 'sample-draw:t1:1'), r = calls.find(c => c.label === 'sample:t1:1'), y = calls.find(c => c.label === 'sample-tally:t1:1')
  assert.equal(d.model, 'haiku'); assert.equal(d.phase, 'Sample')
  assert.match(d.prompt, /python3 ledger\.py sample draw books\/t1\.md --wip wip\/t1 --n 20 --round 1 --json/)
  assert.equal(r.model, 'opus'); assert.equal(r.effort, 'high'); assert.equal(r.phase, 'Sample')
  assert.match(r.prompt, /wip\/intake-staged\/phases\/sample\.md/); assert.match(r.prompt, /wip\/t1\/sample\.md/); assert.match(r.prompt, /sample-reading\.tsv/); assert.match(r.prompt, /You correct nothing/)
  assert.match(y.prompt, /ledger\.py sample tally --wip wip\/t1 --round 1 --threshold 3 --on-threshold check --reply '\{"rows":20/)
  assert.match(calls.find(c => c.label === 'finish:t1').prompt, /--pre-sample/)
  assert.equal(result.results[0].ok, true); assert.equal(result.results[0].sample_reading.meaning, 1)
  assert.equal(result.results[0].phases.at(-1).phase, 'sample')
})

test('sample false, in args or on a task, skips the phase; the result says so', async () => {
  let { result, calls } = await dryRun(SCRIPT, { sample: false, tasks: [task('t1')] }, happy())
  assert.ok(!calls.some(c => c.label.startsWith('sample'))); assert.deepEqual(result.results[0].sample_reading, { skipped: 'sample false' })
  assert.doesNotMatch(calls.find(c => c.label === 'finish:t1').prompt, /--pre-sample/)
  ;({ result, calls } = await dryRun(SCRIPT, { tasks: [task('t1', { sample: false }), task('t2')] }, happy()))
  assert.ok(!calls.some(c => c.label.startsWith('sample') && c.label.includes(':t1:'))); assert.ok(calls.some(c => c.label === 'sample:t2:1'))
})

test('at the threshold without a check phase: the check over the whole ledger, gate 2, then a redraw read once more', async () => {
  const { result, calls } = await dryRun(SCRIPT, { checkBudget: 10, tasks: [task('t1')] }, happy({}, { 'sample-tally:t1:1': OVER }))
  const labels = calls.map(c => c.label)
  const i = labels.indexOf('sample-tally:t1:1')
  assert.deepEqual(labels.slice(i), ['sample-tally:t1:1', 'check:t1:sample', 'gate2:t1:check-sample:0', 'sample-draw:t1:2', 'sample:t1:2', 'sample-tally:t1:2'])
  const ck = calls.find(c => c.label === 'check:t1:sample')
  assert.match(ck.prompt, /Read every row\./); assert.doesNotMatch(ck.prompt, /Your budget is 10 rows/)
  assert.match(ck.prompt, /the sample reading found 3 faults of meaning in 20 sampled rows \(rows 4, 9, 12; wip\/t1\/sample-reading\.md\)/)
  assert.match(calls.find(c => c.label === 'sample-draw:t1:2').prompt, /--round 2 --json/)
  assert.match(calls.find(c => c.label === 'sample:t1:2').prompt, /round 2[\s\S]*sample-reading-2\.tsv/)
  assert.match(calls.find(c => c.label === 'sample-tally:t1:2').prompt, /--round 2 --threshold 3 --on-threshold flag/)
  const r = result.results[0]
  assert.equal(r.ok, true); assert.equal(r.sample_reading.meaning, 3); assert.equal(r.sample_reading.redraw.meaning, 1); assert.equal(r.flagged, undefined)
})

test('at the threshold when the check already ran: no second check; the note is flagged and integrates', async () => {
  const { result, calls, logs } = await dryRun(SCRIPT, { check: true, tasks: [task('t1')] }, happy({}, { 'sample-tally:t1:1': OVER }))
  assert.equal(calls.filter(c => c.label.startsWith('check:')).length, 1)
  assert.ok(!calls.some(c => c.label === 'sample-draw:t1:2'))
  assert.match(calls.find(c => c.label === 'sample-tally:t1:1').prompt, /--on-threshold flag/)
  assert.equal(result.results[0].ok, true); assert.match(result.results[0].flagged, /reach the threshold 3; the check phase already ran/)
  assert.ok(logs.some(l => /sample flagged: t1/.test(l)))
})

test('sampleThreshold overrides the pack threshold the draw reports; a dead reader is resumed; a failed tally stops the task at sample', async () => {
  let { result, calls } = await dryRun(SCRIPT, { sampleThreshold: 5, tasks: [task('t1')] }, happy({}, { 'sample:t1:1': null }))
  assert.match(calls.find(c => c.label === 'sample-tally:t1:1').prompt, /--threshold 5 /)
  assert.match(calls.find(c => c.label === 'resume1:sample:t1:1').prompt, /RESUME 1 of 2[\s\S]*sample-reading\.progress\.md/)
  ;({ result } = await dryRun(SCRIPT, { tasks: [task('t1')] }, happy({}, { 'sample-tally:t1:1': { ok: false, summary: 'no reading to count' } })))
  assert.equal(result.results[0].ok, false); assert.equal(result.results[0].stopped_at, 'sample'); assert.match(result.results[0].reason, /the tally failed/)
})

let failed = 0
for (const [name, f] of tests) {
  try { await f(); console.log(`ok   ${name}`) } catch (e) { failed++; console.log(`FAIL ${name}\n     ${e.message.split('\n').join('\n     ')}`) }
}
console.log(`${tests.length - failed} of ${tests.length} passed`)
process.exit(failed ? 1 : 0)
