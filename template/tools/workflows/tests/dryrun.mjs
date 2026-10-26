// A dry run of a Workflow script outside the runtime (2026-10-23, wip/split-write/): the script's body is wrapped in an async
// function and run with stub hooks (agent, parallel, pipeline, log, phase, workflow, budget), so its control flow can be tested
// without spawning an agent. `scenario(label, prompt, opts)` returns what the stub agent returns (an object, a string, or null
// for a death). Every call is recorded: {label, phase, model, effort, prompt}.
import { readFileSync } from 'node:fs'

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

export function load(scriptPath) {
  const src = readFileSync(scriptPath, 'utf8').replace(/^export const meta\s*=/m, 'const meta =')
  return new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'log', 'phase', 'workflow', 'budget', src)
}

export async function dryRun(scriptPath, args, scenario) {
  const calls = [], logs = []
  const agent = async (prompt, opts = {}) => {
    const c = { label: opts.label, phase: opts.phase, model: opts.model, effort: opts.effort, prompt }
    calls.push(c)
    return scenario(opts.label || '', prompt, opts, calls)
  }
  const parallel = async thunks => Promise.all(thunks.map(async f => { try { return await f() } catch (e) { logs.push('thrown: ' + e); return null } }))
  const pipeline = async (items, ...stages) => Promise.all(items.map(async (it, i) => { let v = it; for (const s of stages) v = await s(v, it, i); return v }))
  const log = m => logs.push(m)
  const phase = () => {}
  const workflow = async () => ({ probed: true })
  const budget = { total: null, spent: () => 0, remaining: () => Infinity }
  const result = await load(scriptPath)(args, agent, parallel, pipeline, log, phase, workflow, budget)
  return { result, calls, logs }
}
