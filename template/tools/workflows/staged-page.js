export const meta = {
  name: 'staged-page',
  description: 'One narrative page per pipeline, pages in parallel: each page runs its phases in order (a phase is one guarded agent or a parallel fan-out of guarded agents, each with its own model); a dead agent is resumed from its wip checkpoint (up to maxResumes), and a death after the last resume runs the bisect-block probes over wip/<task>/current-unit.md',
  whenToUse: 'Narrative revise, attack and build steps split into short-lived agents with small contexts (tools/narratives.md section 8c, 2026-10-09). args: {pages:[{key, phases:[{name, prompt, wip, model?} | {name, fanout:[{name, prompt, wip, model?}]}]}], model?, effort?, maxResumes?, bisectScript?}',
  phases: [{ title: 'Pages' }, { title: 'Resume', detail: 'dead agents restarted from their checkpoint' }, { title: 'Probe', detail: 'bisect-block over the unit a twice-dead agent was handling' }],
}
const model = args.model || 'opus'
const effort = args.effort || 'high'
const maxResumes = args.maxResumes ?? 2
function resumeText(t, n) {
  return t.prompt + `\n\nRESUME ${n} of ${maxResumes} (standing rule, tools/filter-blocks.md section 6): the previous agent on this task died; its output was refused by an API content filter or ended in a terminal API error, cause unknown. Continue from ${t.wip}/progress.md and ${t.wip}/parts/; do not redo recorded work. Before every large output copy the source material of that unit by shell to ${t.wip}/current-unit.md and add one line to progress.md naming the unit and where it goes, so a further death can be bisected without you. Keep output units small and never pass a fetched text through your own output: copy files by shell.`
}
async function guarded(label, t) {
  const m = t.model || model
  let r = await agent(t.prompt, { label, phase: 'Pages', model: m, effort })
  let deaths = 0
  while (r == null && deaths < maxResumes) {
    deaths++
    log(`${label}: agent died; resume ${deaths} of ${maxResumes} from ${t.wip}`)
    r = await agent(resumeText(t, deaths), { label: `resume${deaths}:${label}`, phase: 'Resume', model: m, effort })
  }
  let bisect = null
  if (r == null) {
    log(`${label}: dead after ${maxResumes} resumes; probing ${t.wip}/current-unit.md`)
    try { bisect = await workflow({ scriptPath: args.bisectScript || (args.root ? `${args.root}/tools/workflows/bisect-block.js` : 'tools/workflows/bisect-block.js') }, { file: `${t.wip}/current-unit.md` }) } catch (e) { bisect = { error: String(e) } }
  }
  return { label, model: m, ok: r != null, deaths, reply_head: r == null ? null : String(r).slice(0, 1500), bisect }
}
async function runPage(p) {
  const out = []
  for (const ph of p.phases) {
    if (ph.fanout) {
      const rs = await parallel(ph.fanout.map(t => () => guarded(`${p.key}:${ph.name}:${t.name}`, t)))
      out.push({ phase: ph.name, results: rs })
      if (rs.some(r => !r.ok)) { log(`${p.key}: phase ${ph.name} has a dead agent; the page's later phases are skipped`); return { key: p.key, ok: false, phases: out } }
    } else {
      const r = await guarded(`${p.key}:${ph.name}`, ph)
      out.push({ phase: ph.name, results: [r] })
      if (!r.ok) { log(`${p.key}: phase ${ph.name} dead; later phases skipped`); return { key: p.key, ok: false, phases: out } }
    }
  }
  return { key: p.key, ok: true, phases: out }
}
const results = (await parallel(args.pages.map(p => () => runPage(p)))).filter(Boolean)
log(`done: ${results.filter(o => o.ok).length} of ${args.pages.length} pages completed every phase`)
return results
