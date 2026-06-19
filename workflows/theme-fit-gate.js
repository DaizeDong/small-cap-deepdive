export const meta = {
  name: 'theme-fit-gate',
  description: 'LLM judges true theme membership for each SIC-filtered candidate by reading its 10-K business description — cheap precision gate before expensive deep dive',
  phases: [{ title: 'ThemeFit', detail: 'one quick judgment per candidate: pure_play / partial / misrecall' }],
}

// args: array directly, or {file:"..."} to read from disk, or JSON string.
let candidates = args
if (typeof candidates === 'string') {
  try { candidates = JSON.parse(candidates) } catch (e) { candidates = [] }
}
if (candidates && !Array.isArray(candidates) && candidates.file) {
  // workflow agents can't read files in script context; expect inline. fallback empty.
  candidates = []
}
if (!Array.isArray(candidates)) candidates = []

const FIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ticker', 'theme_fit', 'reason', 'real_business'],
  properties: {
    ticker: { type: 'string' },
    theme_fit: { type: 'string', enum: ['pure_play', 'partial', 'misrecall'],
      description: 'pure_play=core business IS the theme; partial=meaningful exposure as a segment; misrecall=theme keyword was incidental, company is in an unrelated business' },
    reason: { type: 'string', description: 'one sentence: what the company actually does + why it fits/does not fit the theme' },
    real_business: { type: 'string', description: 'the company actual primary business in a few words' },
  },
}

phase('ThemeFit')

const results = await parallel(candidates.map(c => () => {
  // business_blurb: Item 1 "Business" section extracted by cheap_pass.py from the 10-K.
  // Use it as the PRIMARY basis for theme-fit classification — deterministic, no network cost.
  // Only fall back to WebSearch when blurb is absent or very short (< 100 chars).
  const hasBlurb = c.business_blurb && c.business_blurb.length >= 100
  const blurbSection = hasBlurb
    ? `Use the following Item 1 "Business" excerpt from the company's own 10-K filing as your PRIMARY basis for classification. This is T1 source (SEC filing) — rely on it preferentially over any WebSearch result.\n\n--- BEGIN 10-K BUSINESS EXCERPT ---\n${c.business_blurb.slice(0, 2000)}\n--- END EXCERPT ---\n\nDo NOT perform a WebSearch — the excerpt above is sufficient for classification.`
    : `No 10-K business excerpt is available for this company. ${c.json_path ? `Check the hard-data JSON at ${c.json_path} (look at tenk.risk_excerpt).` : ''} Fall back to a quick WebSearch of "${c.name} business overview what does it do" to determine what the company actually does.`

  return agent(
    `Quick theme-fit judgment (do NOT do full due diligence, just classify membership).\n\nCompany: ${c.name} (${c.ticker}), SIC ${c.sic}.\nInvestment theme: "${c.theme}".\n\nThe company's 10-K mentioned a keyword from this theme, but that may be incidental.\n\n${blurbSection}\n\nClassify theme_fit:\n- pure_play: the company's CORE business is this theme (e.g. an actual railcar maker for the railcar theme, an actual TiO2 producer for the TiO2 theme).\n- partial: the theme is a real but secondary segment / meaningful exposure.\n- misrecall: the keyword was incidental — the company is in an unrelated business (e.g. a biotech whose 10-K said "refractory cancer", an ethanol maker that just ships product by railcar, a shoe retailer).\n\nBe strict. The goal is to remove companies that only matched by coincidence so we don't waste deep dive on them. Return ticker, theme_fit, reason, real_business.`,
    { label: `fit:${c.ticker}`, phase: 'ThemeFit', schema: FIT_SCHEMA, effort: 'low' }
  ).then(r => ({ ...r, name: c.name, theme: c.theme, theme_slug: c.theme_slug,
                 cik: c.cik, sic: c.sic, mktcap: c.mktcap,
                 health_score: c.health_score, killflag_count: c.killflag_count,
                 had_blurb: hasBlurb })).catch(() => null)
}))

const ok = results.filter(Boolean)
const keep = ok.filter(r => r.theme_fit === 'pure_play' || r.theme_fit === 'partial')
const withBlurb = ok.filter(r => r.had_blurb).length
log(`Theme-fit: ${keep.length} kept (pure_play+partial) of ${ok.length} judged; ${ok.length - keep.length} misrecalls dropped; ${withBlurb}/${ok.length} used 10-K blurb (no WebSearch), ${ok.length - withBlurb} fell back to WebSearch`)

return { judged: ok.length, kept: keep.length, blurb_used: withBlurb, websearch_fallback: ok.length - withBlurb, all: ok }
