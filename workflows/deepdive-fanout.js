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
  required: ['ticker', 'rating', 'confidence', 'one_liner', 'is_misrecall', 'top_long', 'top_short', 'killflag_notes', 'margin_of_safety_pct', 'mos_basis', 'catalyst', 'report_md'],
  properties: {
    ticker: { type: 'string' },
    rating: { type: 'string', enum: ['买入', '观察', '避开'] },
    confidence: { type: 'integer', minimum: 0, maximum: 100 },
    one_liner: { type: 'string', description: 'one-sentence thesis' },
    is_misrecall: { type: 'boolean', description: 'true if the company is NOT actually in the theme (theme keyword was incidental)' },
    theme_fit: { type: 'string', enum: ['pure_play', 'partial', 'misrecall'], description: 'how well it fits the theme' },
    top_long: { type: 'string', description: 'strongest falsifiable bull point + trigger' },
    top_short: { type: 'string', description: 'strongest falsifiable bear point + trigger' },
    killflag_notes: { type: 'string', description: 'kill-flag recheck: going concern / death spiral / material weakness / dilution' },
    margin_of_safety_pct: { type: ['number', 'null'], description: 'margin_of_safety_pct from valuation.py (fcf_cap basis); null if mos_basis is nav or abstain' },
    mos_basis: { type: 'string', enum: ['fcf_cap', 'nav', 'abstain'], description: 'valuation model routing: fcf_cap | nav | abstain' },
    catalyst: { type: ['string', 'null'], description: 'T1-evidenced catalyst with dated trigger that could produce BUY even at MoS <30%, or null if none' },
    report_md: { type: 'string', description: 'FULL deep-dive report in markdown, ~1500-2500 words, following the rubric template (评级/置信度/7维评分卡/可证伪多空论点/pre-mortem/kill-flag/估值(含mos_basis+MoS%+catalyst)/监控触发器/盲区)' },
  },
}

const PREAMBLE = `你是怀疑派价值投资分析师,对一家被忽视小盘股做深度尽调并给可证伪评判。
严格遵循 reference/judgment-rubric.md 与 reference/disclosure-discipline.md,违反即报告无效。
**核心红线(违反即无效):先报 base rate。强制先搜反方再写空头。不许讲故事,不许给主题概念加分。**
**评级可选:买入 / 观察 / 避开 — 评级字段必须用中文(买入/观察/避开),不得写 BUY/WATCH/AVOID 英文。买入 需满足 judgment-rubric.md §Symmetric BUY Trigger 的机械条件(MoS≥30% 或 T1 enumerated-category catalyst),缺一不可。**
**报告第一行必须写:评级: 买入(或观察/避开),置信度: XX% — 用中文前缀,rank.py 据此解析。**
**kill-flag 零容忍:going_concern/death_spiral/material_weakness 任意一项为 True,禁止评买入,无例外。**
**NAV 路径置信度:mos_basis=nav 时,将原始置信度乘以 0.6 后写入 confidence 字段(例:80% 置信 → 记录 48)。**
**catalyst 仅限以下四类(否则填 null):
  (a) 已提交 Form 10-12B/15-12B 的分拆,有指数基金被迫卖出机制文件;
  (b) 90 天内 ≥2-3 名内部人在公开市场现金买入(Form 4,非期权/授予);
  (c) 法院命令的资产出售/特别分配(8-K 附法院令+完成日期);
  (d) 交易所摘牌警告/合规缺陷(8-K 或交易所通知,形成被迫卖出)。
  业绩指引、产品发布、客户合同、营收增长叙事均不构成 catalyst。**`

phase('DeepDive')

// D2/A3: detect event-mode candidates — theme starts with "event:" OR event_type field present
const _isEventMode = s => (s.theme && s.theme.startsWith('event:')) || !!s.event_type

const reports = await parallel(survivors.map(s => () => {
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
投资主题:${s.theme} [${s.horizon}]。它在 SEC 10-K 全文里提到了该主题关键词,我在筛该主题下被忽视的小盘价值股。
机械预筛:cheap pass 体检分 ${s.health_score}/100,kill-flag ${s.killflag_count},市值约 $${s.mktcap ? (s.mktcap/1e6).toFixed(0)+'M' : '?'}。`

  return agent(
    `${PREAMBLE}

${contextPara}

**第一步读硬数据 JSON**:${s.json_path ? s.json_path : '未提供本地 JSON 路径,请用 WebSearch + edgartools 自行补全'}
(若文件不存在或为空,用 WebSearch + edgartools 概念自行补全,并在盲区标注)

**第二步(必须):估值计算**。运行 \`python tools/valuation.py --json <deepdive_json> --ticker ${s.ticker}\`,
或直接读取 deepdive JSON 顶层 "valuation" 字段(若已预合并)。
记录 mos_basis、margin_of_safety_pct(或 nav_margin_of_safety_pct)、ev_sales、ev_ebitda、
reverse_dcf_implied_growth、data_quality 标志。
按 judgment-rubric.md §Symmetric BUY Trigger 的三路 mos_basis 决策树判断 BUY 是否触发。
输出结构化字段 margin_of_safety_pct、mos_basis、catalyst(T1 evidenced catalyst 或 null)。

按纪律产出完整尽调。${_isEventMode(s) ? '事件模式:不做主题契合度判断(theme_fit 可填 "pure_play"),专注强迫性交易机制核实 + 估值。' : '特别注意判断主题契合度(真受益 vs 误召回)。'}返回结构化结果,report_md 是完整中文报告。`,
    { label: `dd:${s.theme_slug.slice(0, 8)}:${s.ticker || s.cik}`, phase: 'DeepDive', schema: REPORT_SCHEMA }
  ).then(r => ({ ...r, theme: s.theme, horizon: s.horizon || null, theme_slug: s.theme_slug,
                 mktcap: s.mktcap, health_score: s.health_score })).catch(() => null)
}))

const ok = reports.filter(Boolean)
log(`Deep dive complete: ${ok.length}/${survivors.length} reports`)

return { count: ok.length, total: survivors.length, reports: ok }
