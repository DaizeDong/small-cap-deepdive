// Authored host tests. Export downstream_producer_completion_scenarios() through
// tools/make_fixtures.py to SMALLCAP_PRODUCER_FIXTURE_JSON before an authorized run.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const fixturePath = process.env.SMALLCAP_PRODUCER_FIXTURE_JSON
if (!fixturePath) throw new Error('Set SMALLCAP_PRODUCER_FIXTURE_JSON to the shared generator export')
const sample = JSON.parse(await readFile(fixturePath, 'utf8'))
const source = await readFile(new URL('../workflows/deepdive-fanout.js', import.meta.url), 'utf8')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const workflow = new AsyncFunction('args', 'parallel', 'agent', 'phase', 'log',
  source.replace(/^export const meta\b/, 'const meta'))
const copy = value => structuredClone(value)
const runDir = '/synthetic-run'
const binding = (artifact, payload) => {
  const bytes = Buffer.from(JSON.stringify(payload))
  return { artifact, artifact_bytes: bytes.length,
    artifact_sha256: createHash('sha256').update(bytes).digest('hex'), run_dir: runDir }
}

function request() {
  const candidates = copy(sample.survivor_rows).map(row => {
    const name = 'deepdive_' + row.ticker + '_' + sample.verdict_date + '.json'
    return { ...row, data_status: 'partial', json_path: runDir + '/' + name,
      data_artifact: binding(name, { ...sample.pull_data, ticker: row.ticker, cik: row.cik }),
      valuation_path: runDir + '/valuation_' + row.ticker + '_' + sample.verdict_date + '.json' }
  })
  return { schema: 'smallcap.deepdive.request.v1',
    input: binding('candidates_gate2_survivors.json', sample.survivor_rows),
    data_results: binding('deepdive_data_results.json', candidates),
    request_path: runDir + '/deepdive_request.json',
    request_id: createHash('sha256').update(JSON.stringify(candidates)).digest('hex'),
    verdict_date: sample.verdict_date, candidates,
    completion: { schema: 'smallcap.stage.v1', status: 'partial', row_count: candidates.length } }
}

async function run(args, results) {
  const calls = { agents: [], parallel: 0 }
  const output = await workflow(args, async jobs => {
    calls.parallel += 1
    return Promise.all(jobs.map(job => job()))
  }, async (prompt, options) => {
    const result = results[calls.agents.length]
    calls.agents.push({ prompt, options })
    if (result instanceof Error) throw result
    return result
  }, () => {}, () => {})
  return { output, calls }
}

const invalidCases = [
  ['null', () => sample.malformed_rows.nonobject],
  ['array', () => copy(sample.empty)],
  ['killflag_unsafe_integer', () => copy(sample.fanout_outcomes.killflag_unsafe_integer[0].report)],
  ['killflag_overflow', () => copy(sample.fanout_outcomes.killflag_overflow[0].report)],
  ['missing_field', () => {
    const report = copy(sample.fanout_outcomes.success[0].report)
    delete report.confidence
    return report
  }],
  ['wrong_ticker', () => copy(sample.fanout_outcomes.mismatched_report_ticker[0].report)],
  ['missing_rating_block', () => {
    const report = copy(sample.fanout_outcomes.success[0].report)
    report.report_md = report.one_liner
    return report
  }],
]
for (const [name, malformed] of invalidCases) {
  test('fulfilled ' + name + ' retains the valid peer and an explicit bound error', async () => {
    const input = request()
    const { output } = await run(input, [malformed(), copy(sample.fanout_outcomes.success[1].report)])
    assert.equal(output.all.length, input.candidates.length)
    assert.equal(output.all[0].report_status, 'error')
    assert.equal(output.all[0].error_code, 'invalid_agent_result')
    assert.equal(output.all[0].input_index, sample.survivor_rows[0].input_index)
    assert.equal(output.all[0].ticker, sample.survivor_rows[0].ticker)
    assert.equal(output.all[1].report_status, 'complete')
    assert.deepEqual(output.all[1].report, sample.fanout_outcomes.success[1].report)
    assert.equal(output.status, 'partial')
  })
}

for (const sampleCase of sample.source22_policy) {
  test('frozen BUY policy: ' + sampleCase.name, async () => {
    const input = request()
    const report = copy(sampleCase.report)
    report.ticker = input.candidates[0].ticker
    const peer = copy(sample.fanout_outcomes.success[1].report)
    const { output } = await run(input, [report, peer])
    assert.equal(output.all[0].report_status, sampleCase.accepted ? 'complete' : 'error')
    if (!sampleCase.accepted) assert.equal(output.all[0].error_code, 'invalid_agent_result')
    assert.equal(output.all[1].report_status, 'complete')
    assert.deepEqual(output.all[1].report, peer)
  })
}

test('largest safe integer report count retains both reports', async () => {
  const reports = sample.fanout_outcomes.killflag_safe_max.map(row => copy(row.report))
  const { output } = await run(request(), reports)
  assert.deepEqual(output.all.map(row => row.report_status), ['complete', 'complete'])
  assert.deepEqual(output.all.map(row => row.report), reports)
})

test('rejected agent keeps a bound error and its valid peer', async () => {
  const { output } = await run(request(), [
    new Error(sample.pull_errors[0].error_code), copy(sample.fanout_outcomes.success[1].report),
  ])
  assert.equal(output.all[0].error_code, 'agent_failed')
  assert.equal(output.all[1].report_status, 'complete')
})

test('actual prompt uses standalone valuation adapter and preserves request bindings', async () => {
  const input = request()
  const before = JSON.stringify(input)
  const { output, calls } = await run(input, sample.fanout_outcomes.success.map(row => copy(row.report)))
  assert.equal(JSON.stringify(input), before)
  assert.deepEqual(output.input, input.input)
  assert.equal(output.request_id, input.request_id)
  assert.equal(calls.agents.length, input.candidates.length)
  for (const [index, call] of calls.agents.entries()) {
    assert.match(call.prompt, /python tools\/deepdive_data\.py --valuation-request/)
    assert.ok(call.prompt.includes('--input-index ' + input.candidates[index].input_index))
    assert.ok(call.prompt.includes(input.candidates[index].valuation_path))
    assert.doesNotMatch(call.prompt, /valuation\.py --json/)
    assert.equal('model' in call.options, false)
  }
})

test('complete empty request does not initialize agent or fanout', async () => {
  const input = request()
  input.candidates = copy(sample.empty)
  input.completion = { schema: 'smallcap.stage.v1', status: 'complete', row_count: 0 }
  const { output, calls } = await run(input, [])
  assert.deepEqual(output.all, [])
  assert.equal(output.status, 'complete')
  assert.equal(calls.agents.length, 0)
  assert.equal(calls.parallel, 0)
})

test('malformed excluded row fails before any host invocation', async () => {
  const input = request()
  input.candidates[0] = copy(sample.malformed_rows.malformed_watch)
  let calls = 0
  await assert.rejects(workflow(input, () => { calls += 1 }, () => { calls += 1 },
    () => { calls += 1 }, () => {}), /identity or band/)
  assert.equal(calls, 0)
})

test('malformed JSON cannot become a complete empty result', async () => {
  let calls = 0
  await assert.rejects(workflow('{', () => { calls += 1 }, () => { calls += 1 },
    () => { calls += 1 }, () => {}), SyntaxError)
  assert.equal(calls, 0)
})
