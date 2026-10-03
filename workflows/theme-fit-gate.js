export const meta = {
  name: 'theme-fit-gate',
  description: 'LLM judges true theme membership for each SIC-filtered candidate by reading its SEC filing business description; cheap precision gate before expensive deep dive',
  phases: [{ title: 'ThemeFit', detail: 'one quick judgment per candidate: pure_play / partial / misrecall' }],
}

// Pass the inline request prepared by run_theme.py through the configured workflow host.
// The host supplies agent/parallel and retains its installed llmcall routing defaults.
const invalidInput = code => ({
  schema: 'smallcap.gate2.result.v1', input: null, all: [], judged: 0, kept: 0, errored: 0,
  completion: { schema: 'smallcap.stage.v1', stage: 'gate2', status: 'invalid',
    row_count: 0, empty: true, requested_work: 1, completed_work: 0,
    work: [{ source: 'gate2_request', query: '', page: null, status: 'invalid', reason: code }],
    upstream: [], reasons: [] },
})
let request = args
const validCompletion = (record, depth = 0) => {
  if (depth > 20 || !record || record.schema !== 'smallcap.stage.v1' || typeof record.stage !== 'string'
      || !Number.isInteger(record.row_count) || record.row_count < 0
      || !Array.isArray(record.work) || !Array.isArray(record.upstream) || !Array.isArray(record.reasons)) return false
  if (record.work.some(w => !w || typeof w.source !== 'string' || !w.source
      || !['complete', 'partial', 'unavailable', 'invalid'].includes(w.status))
      || record.upstream.some(u => !validCompletion(u, depth + 1))) return false
  const states = [...record.work.map(w => w.status), ...record.upstream.map(u => u.status)]
  const expected = states.includes('invalid') ? 'invalid'
    : states.length && states.every(s => s === 'complete') && !record.reasons.length ? 'complete'
    : record.row_count || states.some(s => s === 'complete' || s === 'partial') ? 'partial' : 'unavailable'
  return record.status === expected && record.empty === (record.row_count === 0)
    && record.requested_work === record.work.length
    && record.completed_work === record.work.filter(w => w.status === 'complete').length
}
if (typeof request === 'string') {
  try { request = JSON.parse(request) } catch { return invalidInput('malformed_json') }
}
if (!request || request.schema !== 'smallcap.gate2.request.v1' || !Array.isArray(request.candidates)
    || !request.input || typeof request.input.artifact !== 'string'
    || typeof request.input.run_dir !== 'string'
    || !/^[a-f0-9]{64}$/.test(request.input.artifact_sha256)
    || !Number.isInteger(request.input.artifact_bytes) || request.input.artifact_bytes < 0
    || !validCompletion(request.completion)
    || request.completion.row_count !== request.candidates.length
    || !['complete', 'partial', 'unavailable'].includes(request.completion.status)) {
  return invalidInput('invalid_request_envelope')
}
const candidates = request.candidates
const identities = new Set()
for (const [index, c] of candidates.entries()) {
  if (!c || c.input_index !== index || typeof c.ticker !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$/.test(c.ticker)
      || typeof c.cik !== 'string' || !/^[0-9]{1,10}$/.test(c.cik)
      || !['deep', 'watch', 'unknown'].includes(c.band)) return invalidInput('invalid_candidate_identity')
  const identity = c.ticker
  if (identities.has(identity)) return invalidInput('duplicate_candidate_identity')
  identities.add(identity)
}
const failed = (c, error_code) => ({ ...c, judgment_status: 'error', theme_fit: null, error_code })

const FIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ticker', 'theme_fit', 'reason', 'real_business'],
  properties: {
    ticker: { type: 'string' },
    theme_fit: { type: 'string', enum: ['pure_play', 'partial', 'misrecall'],
      description: 'pure_play=core business IS the theme; partial=meaningful exposure as a segment; misrecall=the actual business is unrelated to the theme; any keyword match may be incidental' },
    reason: { type: 'string', description: 'one sentence: what the company actually does + why it fits/does not fit the theme' },
    real_business: { type: 'string', description: 'the company actual primary business in a few words' },
  },
}

const recallSource = c => {
  switch (c.recall_channel) {
    case "fts": return "Discovery source: SEC filing full-text keyword search. A keyword match may be incidental and does not establish theme membership."
    case "sic_reverse": return "Discovery source: dedicated-SIC enumeration only. No SEC filing keyword match is recorded; assess theme membership from business evidence."
    case "sic": return "Discovery source: dedicated-SIC enumeration only. No SEC filing keyword match is recorded; assess theme membership from business evidence."
    case "both": return "Discovery source: both SEC filing full-text keyword search and dedicated-SIC enumeration. Neither source establishes theme membership."
    default: return "Discovery source was not recorded. Do not assume an SEC filing keyword match; assess theme membership from business evidence."
  }
}

phase('ThemeFit')

let results
try {
results = candidates.length ? await parallel(candidates.map(c => async () => {
  // business_blurb: business-description excerpt extracted by cheap_pass.py from an SEC filing.
  // Use it as the PRIMARY basis for theme-fit classification — deterministic, no network cost.
  // Only fall back to WebSearch when blurb is absent or very short (< 100 chars).
  const hasBlurb = typeof c.business_blurb === 'string' && c.business_blurb.length >= 100
  const blurbSection = hasBlurb
    ? `Use the following business-description excerpt from the company's own SEC filing as your PRIMARY basis for classification. This is T1 source (SEC filing); rely on it preferentially over any WebSearch result.\n\n--- BEGIN SEC FILING BUSINESS EXCERPT ---\n${c.business_blurb.slice(0, 2000)}\n--- END EXCERPT ---\n\nDo NOT perform a WebSearch — the excerpt above is sufficient for classification.`
    : `No SEC filing business-description excerpt is available for this company. ${c.json_path ? `Check the hard-data JSON at ${c.json_path} (look at tenk.risk_excerpt).` : ''} Fall back to a quick WebSearch of "${c.name} business overview what does it do" to determine what the company actually does.`

  try {
  const r = await agent(
    `Quick theme-fit judgment (do NOT do full due diligence, just classify membership).\n\nCompany: ${c.name} (${c.ticker}), SIC ${c.sic}.\nInvestment theme: "${c.theme}".\n\n${recallSource(c)}\n\n${blurbSection}\n\nClassify theme_fit:\n- pure_play: the company's CORE business is this theme (e.g. an actual railcar maker for the railcar theme, an actual TiO2 producer for the TiO2 theme).\n- partial: the theme is a real but secondary segment / meaningful exposure.\n- misrecall: the company is in an unrelated business; any keyword match was incidental (e.g. a biotech whose SEC filing said "refractory cancer", an ethanol maker that just ships product by railcar, a shoe retailer).\n\nBe strict. The goal is to remove companies that only matched by coincidence so we don't waste deep dive on them. Return ticker, theme_fit, reason, real_business.`,
    { label: `fit:${c.ticker}`, phase: 'ThemeFit', schema: FIT_SCHEMA }
  )
  if (!r || r.ticker !== c.ticker || !['pure_play', 'partial', 'misrecall'].includes(r.theme_fit)
      || typeof r.reason !== 'string' || !r.reason.trim()
      || typeof r.real_business !== 'string' || !r.real_business.trim()) return failed(c, 'invalid_judgment')
  return { ...c, theme_fit: r.theme_fit, reason: r.reason, real_business: r.real_business,
    judgment_status: 'complete', had_blurb: hasBlurb }
  } catch { return failed(c, 'agent_failed') }
})) : []
} catch { results = candidates.map(c => failed(c, 'parallel_failed')) }

const ok = results.filter(r => r.judgment_status === 'complete')
const keep = ok.filter(r => r.theme_fit === 'pure_play' || r.theme_fit === 'partial')
const withBlurb = ok.filter(r => r.had_blurb).length
const work = results.map(r => ({ source: 'theme_fit', query: `${r.cik}:${r.ticker}`.slice(0, 200),
  page: null, status: r.judgment_status === 'complete' ? 'complete' : 'unavailable',
  reason: r.judgment_status === 'complete' ? '' : r.error_code,
  input_index: r.input_index, band: r.band }))
const reasons = results.some(r => r.band === 'unknown') ? ['unresolved_candidate_band'] : []
const states = [...work.map(w => w.status), request.completion.status]
const status = states.every(s => s === 'complete') && !reasons.length ? 'complete'
  : results.length || states.some(s => s === 'complete' || s === 'partial') ? 'partial' : 'unavailable'
const completion = { schema: 'smallcap.stage.v1', stage: 'gate2', status,
  row_count: results.length, empty: !results.length, requested_work: work.length,
  completed_work: ok.length, work, upstream: [request.completion], reasons }
log(`Theme-fit status: ${status}; ${keep.length} kept of ${ok.length} judged; ${results.length - ok.length} errors; ${ok.length - keep.length} explicit misrecalls`)

return { schema: 'smallcap.gate2.result.v1', input: request.input, completion,
  judged: ok.length, kept: keep.length, errored: results.length - ok.length,
  blurb_used: withBlurb, websearch_fallback: ok.length - withBlurb, all: results }
