export const meta = {
  name: 'bisect-block',
  description: 'Find the smallest span of a file that an API output filter refuses: Haiku probes read a line range and return it verbatim; a probe that dies marks its range',
  whenToUse: 'After an intake agent has died twice at the same step (tools/filter-blocks.md section 7). args: {file, minLines?, startLine?, endLine?, retries?}',
  phases: [{ title: 'Probe', detail: 'count lines, then halve the failing range until the smallest refused span is found' }],
}
// Standing tool of the blocked-output rule (2026-10-02). No filesystem access here: every read is done by a probe agent.
const file = args.file
const minLines = args.minLines || 2
const retries = args.retries ?? 1
const N = { type: 'object', properties: { lines: { type: 'number' } }, required: ['lines'] }
const T = { type: 'object', properties: { text: { type: 'string' } }, required: ['text'] }
let total = args.endLine
if (!total) {
  const r = await agent(`Run from the project root. Count the lines of the file ${file} with: wc -l "${file}" and return the number in "lines". Do not read, print or quote the file's content.`,
    { label: 'count', phase: 'Probe', model: 'haiku', effort: 'low', schema: N })
  if (!r) throw new Error('line count failed')
  total = r.lines
}
const attempts = []
async function probe(a, b) {
  for (let t = 0; t <= retries; t++) {
    const r = await agent(`Run from the project root. Print lines ${a} to ${b} of the file ${file} with: sed -n '${a},${b}p' "${file}" and return exactly that output, unchanged and complete, in the field "text". Nothing else. If you cannot return it, return the single word DECLINED in "text".`,
      { label: `probe:${a}-${b}`, phase: 'Probe', model: 'haiku', effort: 'low', schema: T })
    const state = r == null ? 'blocked' : (typeof r.text === 'string' && r.text.trim() !== 'DECLINED' && r.text.split('\n').length >= Math.max(1, Math.floor((b - a + 1) * 0.5)) ? 'ok' : 'model-declined')
    attempts.push({ lines: [a, b], attempt: t + 1, state })
    log(`lines ${a}-${b}: ${state}`)
    if (state === 'ok') return 'ok'
    if (state === 'model-declined') return 'model-declined'
  }
  return 'blocked'
}
async function bisect(a, b) {
  const st = await probe(a, b)
  if (st === 'ok') return { lines: [a, b], ok: true }
  if (b - a + 1 <= minLines) return { lines: [a, b], ok: false, culprit: true, state: st }
  const m = Math.floor((a + b) / 2)
  const L = await bisect(a, m)
  const R = await bisect(m + 1, b)
  const node = { lines: [a, b], ok: false, state: st, children: [L, R] }
  if (L.ok && R.ok) node.lengthTriggered = true   // the whole fails but both halves pass: chunking, not a human summary
  return node
}
const tree = await bisect(args.startLine || 1, total)
function collect(n, out) {
  if (n.culprit) out.push({ lines: n.lines, state: n.state })
  if (n.lengthTriggered) out.push({ lines: n.lines, state: 'length-triggered' })
  for (const c of (n.children || [])) collect(c, out)
  return out
}
const culprits = collect(tree, [])
log(`${file}: ${tree.ok ? 'whole file passes (not reproducible)' : culprits.length + ' culprit span(s)'}`)
return { file, totalLines: total, wholeBlocked: !tree.ok, culprits, attempts, tree }
