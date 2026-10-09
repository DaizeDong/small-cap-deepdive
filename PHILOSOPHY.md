# Design Philosophy, Hybrid architecture, discipline as moat

> 设计原则：确定性取数与模型判断分工，一致执行证据规则。

The skill combines deterministic filing tools with model-assisted judgment. Its design
aims to make coverage, calculations and rating conditions inspectable. The four principles
below define that division of responsibility; they do not establish predictive performance.

> 本工具将确定性申报处理与模型判断结合，使覆盖范围、财务计算和评级条件可检查。
> 以下四项原则规定各层职责；设计本身不证明预测能力。

## P1, Root-cause design, not symptom patching · 改根因，不打补丁

Narrative research can miss going-concern disclosures, death-spiral convertibles and ICFR
failures when it relies on recall or search summaries. The architectural response is to
retrieve and parse filings in Python, then give the resulting JSON to the judgment layer.
The data layer computes financials and mechanical eligibility; the judgment layer applies
the rubric without recalculating financial values.

Historical development notes describe 10 data-layer bugs across two production-bug rounds,
including FTS precision, going-concern assertion checks, concept-series merging, amendment
selection and Form 4 direction parsing. Those observations motivated the separation and
regression checks. They are development context, not proof that current outputs are free
of data errors; current acceptance follows [evidence status](docs/evidence-status.md).

> 依赖模型记忆或搜索摘要，可能漏读持续经营披露、死亡螺旋可转债和内控缺陷。因此由 Python
> 获取、解析申报并计算财务及机械资格，判断层读取 JSON 后应用评分规范，不重新计算财务。
> 历史开发记录中的两轮、共 10 个取数层问题促成了这一分工和回归检查；这些记录不代表当前
> 输出已无数据错误，验收仍须依据当前证据。

## P2, Hybrid, not thin: the data layer earns its keep · Hybrid 而非 thin：数据层有其存在价值

A thin skill delegates acquisition and analysis to an existing engine. A hybrid skill
includes domain-specific deterministic acquisition and delegates judgment to a model.
Source routing can be sufficient for general commercial research, as in market-intel.
SEC research also needs explicit handling of filing semantics:

- Historical development observations reported FTS over-recall of 15 to 25×. Current runs
  must measure their own retrieval scope and theme fit rather than assume that ratio.
- Going-concern language can describe a hypothetical risk. A current connected assertion
  needs the checks in [mechanical-checks.md](reference/mechanical-checks.md), including the
  relationship between going-concern and substantial-doubt language.
- Form 4 `transactionCode` and transaction direction need source-specific parsing and
  verification. Current source availability is defined in [data-sources.md](reference/data-sources.md).

The bundled data layer retains these domain rules so each judgment uses the same acquisition
and calculation procedure. It does not replace the judgment rubric or prove source completeness.

> 通用商业研究可以主要依靠来源路由；SEC 研究还需要处理申报特有的语义。历史开发观察曾记录
> 15 到 25 倍的 FTS 过召回，当前运行仍须单独报告自己的范围。持续经营假设性表述、关联断言、
> Form 4 交易方向等问题需要专门解析。保留确定性取数层，是为了统一这些处理规则和财务计算，
> 不能据此认定来源完整或省略判断规范。

## P3, Discipline as moat, not narrative · 纪律即护城河，非叙事

Apply the same screening, rubric and disconfirmation procedure to every admitted candidate.
This reduces inconsistency from selective reading and investor-relations presentation quality.
Whether it identifies a pricing inefficiency requires separate outcome evidence. The factor
strategy exclusion reflects the concern that transaction costs can remove apparent gross
alpha; this design does not establish net factor performance.

1. **Coverage:** claim complete coverage only with a dated population, retrieval scope and
   completion receipts. Retain caps, missing pages, failed stages and model abstentions.
2. **Consistent decisions:** apply the same kill-flags and rating conditions to each candidate.
   T3 company-sourced evidence cannot support a BUY thesis.
3. **Empty results:** report zero qualifying candidates when the observed set has none, together
   with missing work. This cannot establish that the theme has no investment opportunities.

The rules address factual hallucination, backtest overfitting, unsupported confidence and
halo bias. Their definitions live in [judgment-rubric.md](reference/judgment-rubric.md) and
[disclosure-discipline.md](reference/disclosure-discipline.md).

> 对每个已纳入候选采用相同的筛查、评分和反方检索流程，以减少选择性阅读和叙事偏好。
> 完整覆盖须有带日期的总体、检索范围和完成凭据；上限、漏页、失败步骤和模型弃答必须保留。
> T3 公司自述不能支撑 BUY。可以返回零候选，但必须说明范围和未完成工作；投资优势需要
> 独立的结果证据。规则重点处理事实错误、回测过拟合、缺乏依据的确信和光环偏差。

## P4, Single source of truth, reference before orchestration · 单一真相源，reference 先于编排

`reference/*.md` owns methodology: kill-flags, score dimensions, evidence tiers and cognitive
priors. `SKILL.md` routes the work; runbooks supply commands; `workflows/*.js` loads the
references as its preamble. Change a methodology rule in its owning reference and update
dependent navigation or invocation as needed. Repeating the full rule in each entry creates
independent copies that can diverge.

[CONFIG.md](CONFIG.md) and source contracts own configuration and retention. A PRIVATE
boundary does not make every cache a core record, and local readiness does not prove a live
integration. Retention follows the declared producer, consumer and recovery dependencies.

> 方法规范由 `reference/*.md` 维护，SKILL 负责路由，运行手册提供命令，workflow 加载参考规范。
> 修改规则时更新其权威位置及相关入口，避免多份规则分别演变。配置和保留规则由 CONFIG 及
> 源码合同定义；文件处于私有仓不代表它必须永久保留，本地就绪也不等于服务实测成功。

## Operationalizing the diffusion thesis · 让"信息扩散"论点落地

Static trailing-FCF valuation alone cannot distinguish improving fundamentals from a
declining business with a high historical yield. The design addresses this in two parts:

- **Conservative eligibility checks:** the implemented T1 trajectory veto uses
  `fundamental_decline_flag` (negative revenue slope, `0 < contamination_ratio < 1.0` and
  latest below its own average). The related peak-contamination veto covers a rebound
  followed by deterioration. These checks can downgrade BUY to WATCH; they cannot create
  a BUY. Exact conditions are in [valuation.md](reference/valuation.md).
- **Diagnostic observations:** implemented P16 compares the T1 trajectory with trailing
  6m/12m prices; P17 records 13D/13G and best-effort, staleness-labeled short interest.
  P15 consists of agent-gathered T2 context from available sources such as TrendsMCP,
  GDELT and news volume. [data-sources.md](reference/data-sources.md) owns the fields,
  availability limits and namespace contract.

All diagnostic fields stay in top-level `signals`, alongside `derived`. Valuation,
`buy_eligible` and the BUY trigger must not read them. Tracking preserves their snapshots
for future per-signal Brier calibration. Neither the implementation nor a snapshot proves
that a signal predicts returns; using one in eligibility would require a separately reviewed
methodology change.

> 历史 FCF 估值不能独自区分基本面改善与高历史收益率的衰退企业。已实现的 T1 轨迹和峰值污染
> 检查只能将 BUY 降为 WATCH，不能产生 BUY。P16 比较基本面与过去 6/12 个月价格，P17 记录
> 13D/13G 及尽力获取、注明时效的空头信息；P15 由 agent 从可用来源获取 T2 佐证。
> 这些诊断均已与资格计算隔离，写在 `derived` 旁的 `signals` 中。快照供未来逐信号 Brier
> 校准使用，不能据此认定预测有效；改变其资格作用需要单独审查方法规范。

## The generative test · 生成式检验

Evaluate each proposed tool, rule or calculation against this question:

> **"Does this move output closer to truth, or does it make the narrative more convincing
> without moving closer to truth?"**

A distinct, verifiable observation can improve the evidence. A more elaborate scoring
formula without additional evidence may only increase apparent precision. If a proposed
change conflicts with these principles, revise it or explicitly justify a change here.

> **"这让输出更接近真相，还是只让叙事更有说服力而没有更接近真相？"**
>
> 新规则应提供可验证的证据或改善处理方法。若与上述原则冲突，应修改方案，或在此明确说明
> 修订原则的理由。
