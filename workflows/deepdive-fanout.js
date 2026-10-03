export const meta = {
  name: 'smallcap-deepdive-fanout',
  description: 'Full-rubric deep dive on every cheap-pass survivor across 6 themes; each agent reads hard-data JSON + reverse-searches + returns falsifiable long/short verdict',
  phases: [
    { title: 'DeepDive', detail: 'one agent per survivor: scorecard + falsifiable thesis + reverse search' },
  ],
}

// deepdive_data.py prepares this envelope and validates its persisted result.
const request = typeof args === 'string' ? JSON.parse(args) : args
const validBinding = binding => binding && typeof binding === 'object' && !Array.isArray(binding) &&
  typeof binding.artifact === 'string' && binding.artifact.length > 0 &&
  !['.', '..'].includes(binding.artifact) && !/[\\/]/.test(binding.artifact) &&
  Number.isSafeInteger(binding.artifact_bytes) && binding.artifact_bytes >= 0 &&
  typeof binding.artifact_sha256 === 'string' && /^[a-f0-9]{64}$/.test(binding.artifact_sha256) &&
  typeof binding.run_dir === 'string' && binding.run_dir.length > 0
if (!request || request.schema !== 'smallcap.deepdive.request.v1' ||
    !Array.isArray(request.candidates) || !validBinding(request.input) ||
    !validBinding(request.data_results) || request.data_results.run_dir !== request.input.run_dir ||
    !request.completion || request.completion.schema !== 'smallcap.stage.v1' ||
    !['complete', 'partial', 'unavailable'].includes(request.completion.status) ||
    request.completion.row_count !== request.candidates.length ||
    typeof request.request_path !== 'string' || !request.request_path ||
    !/^[a-f0-9]{64}$/.test(request.request_id || '') ||
    typeof request.verdict_date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(request.verdict_date)) {
  throw new Error('Invalid bound deep-dive request; use --prepare-fanout')
}
const survivors = request.candidates
const seenIndices = new Set()
const seenLabels = new Set()
const skippedBands = new Set(['watch', 'large'])
const identity = s => ({ input_index: s.input_index, ticker: s.ticker, cik: s.cik, band: s.band })
// Validate every row, including excluded rows, before invoking the host or an agent.
for (const s of survivors) {
  if (!s || typeof s !== 'object' || Array.isArray(s) ||
      !Number.isSafeInteger(s.input_index) || s.input_index < 0 || seenIndices.has(s.input_index) ||
      typeof s.ticker !== 'string' || typeof s.cik !== 'string' || !(s.ticker || s.cik) ||
      (s.ticker && !/^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$/.test(s.ticker)) ||
      (s.cik && !/^[0-9]{1,10}$/.test(s.cik)) ||
      !['deep', 'watch', 'large', 'unknown'].includes(s.band)) {
    throw new Error('Invalid deep-dive candidate identity or band')
  }
  const label = (s.ticker || `CIK${s.cik}`).toUpperCase()
  if (seenLabels.has(label)) throw new Error('Duplicate deep-dive output identity')
  for (const key of ['name', 'theme', 'theme_slug', 'horizon', 'event_type', 'catalyst']) {
    if (s[key] != null && typeof s[key] !== 'string') throw new Error(`Invalid candidate ${key}`)
  }
  for (const key of ['mktcap', 'health_score', 'killflag_count']) {
    if (s[key] != null && (typeof s[key] !== 'number' || !Number.isFinite(s[key]))) {
      throw new Error(`Invalid candidate ${key}`)
    }
  }
  if (skippedBands.has(s.band)) {
    if (s.data_status !== 'skipped' || s.json_path !== null || s.data_artifact !== null) {
      throw new Error('Excluded candidate has inconsistent data evidence')
    }
  } else if (!['complete', 'partial', 'error'].includes(s.data_status) ||
             typeof s.json_path !== 'string' || !s.json_path || !validBinding(s.data_artifact) ||
             s.data_artifact.run_dir !== request.input.run_dir ||
             typeof s.valuation_path !== 'string' || !s.valuation_path) {
    throw new Error('Missing deep-dive data outcome')
  }
  seenIndices.add(s.input_index)
  seenLabels.add(label)
}

const REPORT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ticker', 'rating', 'confidence', 'one_liner', 'is_misrecall', 'top_long', 'top_short', 'killflag_notes', 'margin_of_safety_pct', 'mos_basis', 'catalyst', 'eligibility', 'report_md'],
  properties: {
    ticker: { type: 'string' },
    rating: { type: 'string', enum: ['买入', '观察', '避开'] },
    confidence: { type: 'integer', minimum: 0, maximum: 100 },
    one_liner: { type: 'string', description: 'one-sentence thesis' },
    is_misrecall: { type: 'boolean', description: 'true if the company actual business is unrelated to the theme' },
    theme_fit: { type: 'string', enum: ['pure_play', 'partial', 'misrecall'], description: 'how well it fits the theme' },
    top_long: { type: 'string', description: 'strongest falsifiable bull point + trigger' },
    top_short: { type: 'string', description: 'strongest falsifiable bear point + trigger' },
    killflag_notes: { type: 'string', description: 'kill-flag recheck: going concern / death spiral / material weakness / dilution' },
    margin_of_safety_pct: { type: ['number', 'null'], description: 'margin_of_safety_pct from valuation.py (fcf_cap basis); null if mos_basis is nav or abstain' },
    mos_basis: { type: 'string', enum: ['fcf_cap', 'nav', 'abstain'], description: 'valuation model routing: fcf_cap | nav | abstain' },
    catalyst: { type: ['string', 'null'], description: 'Verified dated T1 catalyst for WATCH-with-catalyst; it never waives the frozen MoS threshold' },
    eligibility: { type: 'object', additionalProperties: false,
      required: ['buy_eligible', 'active_mos_pct', 'tier3_load_bearing'],
      properties: { buy_eligible: { type: 'boolean' }, active_mos_pct: { type: ['number', 'null'] },
        tier3_load_bearing: { type: 'boolean' } } },
    report_md: { type: 'string', description: 'FULL deep-dive report in markdown, ~1500-2500 words, following the rubric template (评级/置信度/7维评分卡/可证伪多空论点/pre-mortem/kill-flag/估值(含mos_basis+MoS%+catalyst)/监控触发器/盲区)' },
  },
}

function validAgentReport(report, row) {
  if (!report || typeof report !== 'object' || Array.isArray(report) ||
      REPORT_SCHEMA.required.some(key => !(key in report)) ||
      Object.keys(report).some(key => !(key in REPORT_SCHEMA.properties))) return false
  if (report.ticker !== row.ticker || !['买入', '观察', '避开'].includes(report.rating) ||
      !Number.isInteger(report.confidence) || report.confidence < 0 || report.confidence > 100 ||
      typeof report.is_misrecall !== 'boolean' || !['fcf_cap', 'nav', 'abstain'].includes(report.mos_basis) ||
      ('theme_fit' in report && !['pure_play', 'partial', 'misrecall'].includes(report.theme_fit))) return false
  for (const key of ['one_liner', 'top_long', 'top_short', 'killflag_notes', 'report_md']) {
    if (typeof report[key] !== 'string' || !report[key].trim()) return false
  }
  if (report.margin_of_safety_pct !== null &&
      (typeof report.margin_of_safety_pct !== 'number' || !Number.isFinite(report.margin_of_safety_pct))) return false
  if (report.catalyst !== null && (typeof report.catalyst !== 'string' || !report.catalyst.trim())) return false
  const blocks = [...report.report_md.matchAll(/^\x60{3}rating[ \t]*\r?\n([\s\S]*?)^\x60{3}[ \t]*$/gm)]
  if (blocks.length !== 1) return false
  const fields = Object.create(null)
  for (const line of blocks[0][1].split(/\r?\n/)) {
    const colon = line.indexOf(':')
    if (colon < 0) continue
    const key = line.slice(0, colon).trim().toLowerCase()
    if (key in fields) return false
    fields[key] = line.slice(colon + 1).split('#', 1)[0].trim()
  }
  if (['rating', 'confidence', 'verdict_date', 'mos_basis', 'mos_pct', 'buy_eligible', 'killflag_count']
      .some(key => !(key in fields))) return false
  if (fields.rating !== report.rating || fields.mos_basis !== report.mos_basis ||
      fields.verdict_date !== request.verdict_date || !/^[0-9]+$/.test(fields.confidence) ||
      Number(fields.confidence) !== report.confidence || !/^[0-9]+$/.test(fields.killflag_count) ||
      !Number.isSafeInteger(Number(fields.killflag_count)) ||
      !['true', 'false'].includes(fields.buy_eligible.toLowerCase())) return false
  const mos = fields.mos_pct === 'null' ? null : Number(fields.mos_pct)
  if (mos !== null && (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(fields.mos_pct) ||
                       !Number.isFinite(mos))) return false
  if (report.mos_basis === 'fcf_cap' && mos !== report.margin_of_safety_pct) return false
  const evidence = report.eligibility
  if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence) ||
      Object.keys(evidence).sort().join(',') !== 'active_mos_pct,buy_eligible,tier3_load_bearing' ||
      typeof evidence.buy_eligible !== 'boolean' || typeof evidence.tier3_load_bearing !== 'boolean' ||
      (evidence.active_mos_pct !== null &&
       (typeof evidence.active_mos_pct !== 'number' || !Number.isFinite(evidence.active_mos_pct))) ||
      evidence.buy_eligible !== (fields.buy_eligible.toLowerCase() === 'true') ||
      evidence.active_mos_pct !== mos) return false
  if (report.rating === '买入' && (!['fcf_cap', 'nav'].includes(report.mos_basis) ||
      mos === null || mos < 30 || !evidence.buy_eligible || evidence.tier3_load_bearing ||
      Number(fields.killflag_count) !== 0)) return false
  return true
}

const PREAMBLE = `你是怀疑派价值投资分析师,对一家被忽视小盘股做深度尽调并给可证伪评判。
严格遵循 reference/judgment-rubric.md 与 reference/disclosure-discipline.md,违反即报告无效。
**核心红线(违反即无效):先报 base rate。强制先搜反方再写空头。不许讲故事,不许给主题概念加分。**
**评级可选:买入 / 观察 / 避开 — 评级字段必须用中文(买入/观察/避开),不得写 BUY/WATCH/AVOID 英文。买入 需满足 judgment-rubric.md §Symmetric BUY Trigger 的机械条件(fcf_cap 或 NAV 的有效 MoS≥30%、buy_eligible=true、零 kill-flag、无 T3 承重证据；催化剂不豁免 MoS 门槛),缺一不可。**
**报告第一行必须写:评级: 买入(或观察/避开),置信度: XX% — 用中文前缀,rank.py 据此解析。**
**kill-flag 零容忍:going_concern/death_spiral/material_weakness 任意一项为 True,禁止评买入,无例外。**
**NAV 路径置信度:mos_basis=nav 时,将原始置信度乘以 0.6 后写入 confidence 字段(例:80% 置信 → 记录 48)。**
**catalyst 仅限以下四类(否则填 null):
  (a) 已提交 Form 10-12B/15-12B 的分拆,有指数基金被迫卖出机制文件;
  (b) 90 天内 ≥2-3 名内部人在公开市场现金买入(Form 4,非期权/授予);
  (c) 法院命令的资产出售/特别分配(8-K 附法院令+完成日期);
  (d) 交易所摘牌警告/合规缺陷(8-K 或交易所通知,形成被迫卖出)。
  业绩指引、产品发布、客户合同、营收增长叙事均不构成 catalyst。**`

const OUTPUT_CONTRACT = [
  '保留上面的首行评级要求。报告中还必须包含且仅包含一个 fenced rating 区块，字段不得留空：',
  '```rating',
  'rating: 与结构化 rating 一致',
  'confidence: 与结构化 confidence 一致的整数',
  `verdict_date: ${request.verdict_date}`,
  'mos_basis: 与结构化 mos_basis 一致',
  'mos_pct: 当前估值依据对应的安全边际数值，无法计算则 null',
  'buy_eligible: 按既有 rubric 的判断填 true 或 false',
  'killflag_count: 按既有 rubric 复核后的非负整数',
  '```',
  '结构化 eligibility 同步记录 buy_eligible、active_mos_pct 和 tier3_load_bearing；催化剂只支持 WATCH-with-catalyst，不豁免买入条件。',
  'fcf_cap 时 mos_pct 必须与结构化 margin_of_safety_pct 一致。不要补造数据或改动既有评级条件。',
].join('\n')

phase('DeepDive')

// D2/A3: detect event-mode candidates — theme starts with "event:" OR event_type field present
const recallSource = c => {
  switch (c.recall_channel) {
    case "fts": return "召回来源：SEC 披露文件全文关键词搜索。关键词命中可能只是偶然提及，不能据此认定主题归属。"
    case "sic_reverse": return "召回来源：仅来自主题专属 SIC 枚举。没有记录到 SEC 披露文件关键词命中，请根据实际业务判断主题归属。"
    case "sic": return "召回来源：仅来自主题专属 SIC 枚举。没有记录到 SEC 披露文件关键词命中，请根据实际业务判断主题归属。"
    case "both": return "召回来源：SEC 披露文件全文关键词搜索和主题专属 SIC 枚举均命中。两者都不能替代对实际业务的核实。"
    default: return "未记录召回来源。不要假定公司命中了 SEC 披露文件关键词，请根据实际业务判断主题归属。"
  }
}

const _isEventMode = s => (s.theme && s.theme.startsWith('event:')) || !!s.event_type

const outcomes = survivors.length === 0 ? [] : await parallel(survivors.map(s => () => {
  if (skippedBands.has(s.band)) return { ...identity(s), report_status: 'skipped' }
  if (s.data_status === 'error') {
    return { ...identity(s), report_status: 'error', error_code: 'data_pull_failed' }
  }
  // D2: build context paragraph — different framing for event-mode vs theme-mode
  const contextPara = _isEventMode(s)
    ? `公司:${s.name} (${s.ticker || '(无 ticker,CIK ' + s.cik + ')'}),CIK ${s.cik}。
事件驱动候选:该公司由事件 [${s.theme}] 枚举产生,而非主题关键词匹配。
事件类型:${s.event_type || s.theme} — 已定义催化剂(强迫性交易):${s.catalyst || '见候选记录'}。
⚠️ 重要:候选记录中预填的 \`catalyst\` 字段是发现阶段提示(T2),不是符合评级标准的 T1 证据。
你必须独立核实以下内容,再决定 catalyst 修饰符是否适用:
  (a) 若为 spinoff:确认该公司已提交 Form 10-12B/15-12B;确认指数基金被迫卖出机制文件存在(T1=EDGAR 10-12B 原文)。
  (b) 若为 cluster insider buy:从 EDGAR Form 4 原始文件确认是公开市场现金购买(非期权/授予),≥2–3 名内部人,90 天内;确认具体日期和金额(T1=Form 4)。
核实通过后,按 judgment-rubric.md §Catalyst 的五项要求重新填写 catalyst 字段;未能核实则填 null。
机械预筛:cheap pass 体检分 ${s.health_score}/100,kill-flag ${s.killflag_count},市值约 $${s.mktcap ? (s.mktcap/1e6).toFixed(0)+'M' : '?'}。
不做主题契合度评分(事件模式跳过 Gate 1/2)。`
    : `公司:${s.name} (${s.ticker}),CIK ${s.cik}。
投资主题:${s.theme} [${s.horizon}]。筛选该主题下被忽视的小盘价值股。
${recallSource(s)}
机械预筛:cheap pass 体检分 ${s.health_score}/100,kill-flag ${s.killflag_count},市值约 $${s.mktcap ? (s.mktcap/1e6).toFixed(0)+'M' : '?'}。`

  return Promise.resolve().then(() => agent(
    `${PREAMBLE}

${contextPara}

**第一步读硬数据 JSON**:${s.json_path ? s.json_path : '未提供本地 JSON 路径,请用 WebSearch + edgartools 自行补全'}
(若文件不存在或为空,用 WebSearch + edgartools 概念自行补全,并在盲区标注)

**第二步(必须):估值计算**。运行 \`python tools/deepdive_data.py --valuation-request "${request.request_path}" --input-index ${s.input_index}\`。
读取独立估值文件 ${s.valuation_path}；这个适配器复用原估值函数和市值查询，不改写已绑定的硬数据 JSON。
上游证据不完整时命令会返回 2 并保留 partial 产物；产物 status=ERROR 表示估值失败，不得补造估值。
记录 mos_basis、margin_of_safety_pct(或 nav_margin_of_safety_pct)、ev_sales、ev_ebitda、
reverse_dcf_implied_growth、data_quality 标志。
按 judgment-rubric.md §Symmetric BUY Trigger 的三路 mos_basis 决策树判断 BUY 是否触发。
输出结构化字段 margin_of_safety_pct、mos_basis、catalyst(T1 evidenced catalyst 或 null)。

按纪律产出完整尽调。${_isEventMode(s) ? '事件模式:不做主题契合度判断(theme_fit 可填 "pure_play"),专注强迫性交易机制核实 + 估值。' : '特别注意判断主题契合度(真受益 vs 误召回)。'}返回结构化结果,report_md 是完整中文报告。`
      + '\n\n' + OUTPUT_CONTRACT,
    { label: `dd:${(s.theme_slug || '').slice(0, 8)}:${s.ticker || s.cik}`, phase: 'DeepDive', schema: REPORT_SCHEMA }
  )).then(r => validAgentReport(r, s)
    ? { ...identity(s), report_status: 'complete', report: r,
        theme: s.theme, horizon: s.horizon || null, theme_slug: s.theme_slug,
        mktcap: s.mktcap, health_score: s.health_score }
    : { ...identity(s), report_status: 'error', error_code: 'invalid_agent_result' })
    .catch(() => ({ ...identity(s), report_status: 'error', error_code: 'agent_failed' }))
}))

const count = outcomes.filter(r => r.report_status === 'complete').length
const failed = outcomes.some(r => r.report_status === 'error')
const status = !failed && request.completion && request.completion.status === 'complete' ? 'complete' : 'partial'
log(`Deep dive ${status}: ${count}/${survivors.length} reports; persist all outcomes with --fanout-request`)

return { schema: 'smallcap.deepdive.result.v1', input: request.input, request_id: request.request_id,
         status, count, total: survivors.length, all: outcomes }
