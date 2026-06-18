export const meta = {
  name: 'smallcap-deepdive-fanout',
  description: 'Full-rubric deep dive on every cheap-pass survivor across 6 themes; each agent reads hard-data JSON + reverse-searches + returns falsifiable long/short verdict',
  phases: [
    { title: 'DeepDive', detail: 'one agent per survivor: scorecard + falsifiable thesis + reverse search' },
  ],
}

// args = array of survivors (may arrive as JSON string; normalize).
let survivors = args
if (typeof survivors === 'string') {
  try { survivors = JSON.parse(survivors) } catch (e) { survivors = [] }
}
if (!Array.isArray(survivors)) survivors = []

const REPORT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ticker', 'rating', 'confidence', 'one_liner', 'is_misrecall', 'top_long', 'top_short', 'killflag_notes', 'report_md'],
  properties: {
    ticker: { type: 'string' },
    rating: { type: 'string', enum: ['买入', '观察', '避开'] },
    confidence: { type: 'integer', minimum: 0, maximum: 100 },
    one_liner: { type: 'string', description: 'one-sentence thesis' },
    is_misrecall: { type: 'boolean', description: 'true if the company is NOT actually in the theme (theme keyword was incidental)' },
    theme_fit: { type: 'string', enum: ['pure_play', 'partial', 'incidental_misrecall'], description: 'how well it fits the theme' },
    top_long: { type: 'string', description: 'strongest falsifiable bull point + trigger' },
    top_short: { type: 'string', description: 'strongest falsifiable bear point + trigger' },
    killflag_notes: { type: 'string', description: 'kill-flag recheck: going concern / death spiral / material weakness / dilution' },
    report_md: { type: 'string', description: 'FULL deep-dive report in markdown, ~1500-2500 words, following the rubric template (评级/置信度/7维评分卡/可证伪多空论点/pre-mortem/kill-flag/估值/监控触发器/盲区)' },
  },
}

const PREAMBLE = `你是怀疑派价值投资分析师,对一家被忽视小盘股做深度尽调并给可证伪评判。
严格遵循 reference/judgment-rubric.md 与 reference/disclosure-discipline.md,违反即报告无效。
**核心红线(违反即无效):先报 base rate。强制先搜反方再写空头。不许讲故事,不许给主题概念加分。**`

phase('DeepDive')

const reports = await parallel(survivors.map(s => () =>
  agent(
    `${PREAMBLE}

公司:${s.name} (${s.ticker}),CIK ${s.cik}。
投资主题:${s.theme} [${s.horizon}]。它在 SEC 10-K 全文里提到了该主题关键词,我在筛该主题下被忽视的小盘价值股。
机械预筛:cheap pass 体检分 ${s.health_score}/100,kill-flag ${s.killflag_count},市值约 $${s.mktcap ? (s.mktcap/1e6).toFixed(0)+'M' : '?'}。

**第一步读硬数据 JSON**:${s.json_path ? s.json_path : '未提供本地 JSON 路径,请用 WebSearch + edgartools 自行补全'}
(若文件不存在或为空,用 WebSearch + edgartools 概念自行补全,并在盲区标注)

按纪律产出完整尽调。特别注意判断主题契合度(真受益 vs 误召回)。返回结构化结果,report_md 是完整中文报告。`,
    { label: `dd:${s.theme_slug.slice(0, 8)}:${s.ticker}`, phase: 'DeepDive', schema: REPORT_SCHEMA }
  ).then(r => ({ ...r, theme: s.theme, horizon: s.horizon, theme_slug: s.theme_slug,
                 mktcap: s.mktcap, health_score: s.health_score })).catch(() => null)
))

const ok = reports.filter(Boolean)
log(`Deep dive complete: ${ok.length}/${survivors.length} reports`)

return { count: ok.length, total: survivors.length, reports: ok }
