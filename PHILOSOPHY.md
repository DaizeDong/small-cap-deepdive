# Design Philosophy — Hybrid architecture, discipline as moat

> **设计哲学 —— Hybrid 架构，纪律即护城河**

This is the organizing principle of small-cap-deepdive. Every tool, every invariant, every
hard rule in this repo exists because of the four principles below. They are the lens that
produced each design decision, and the test every future change must pass.

> 这是 small-cap-deepdive 的统领原则。本仓库里的每个工具、每个不变量、每条硬规则，都源于下面四条。
> 它们是催生每个设计决定的透镜，也是未来每次改动都必须通过的检验。

**The one-sentence version:** the tool's edge is mechanical discipline applied consistently
across the full candidate set, not narrative synthesis on any individual company.

> **一句话：** 工具的 edge 是机械纪律一致地施加于全量候选，而非对某家公司的叙事综合。

---

## P1 — Root-cause design, not symptom patching · 改根因，不打补丁

The design started from a specific failure mode: LLM-native "stock research" agents produce
confident narratives that are internally consistent but factually wrong on the key data points
that matter — going-concern disclosures, death-spiral convertibles, ICFR failures — because
they rely on recall or web-search summaries rather than deterministic SEC filing retrieval.

The patch would be: add instructions to "check SEC filings carefully."

The root fix: **separate the data layer from the judgment layer with a hard architectural
boundary.** The Python tools (`tools/*.py`) are purely deterministic — they never produce
investment judgment. The LLM layer (`SKILL.md`, `reference/*.md`, `workflows/*.js`) never
computes financials — it reads a JSON that the deterministic layer produced and applies a
rubric.

This boundary was not designed upfront and then validated. It was **forced by 10 production
bugs**, all in the data layer (FTS precision failure, going-concern double-confirmation
requirement, concept series merging, amendment exclusion, Form 4 direction parsing).
The boundary prevented every one of those bugs from contaminating the judgment output.

> - **补丁：** 加指令"仔细检查 SEC 申报"。
> - **根因修复：** 用硬性架构边界把数据层和判断层分开。Python 工具（`tools/*.py`）纯确定性——永不做投资
>   判断。LLM 层（`SKILL.md`、`reference/*.md`、`workflows/*.js`）永不计算财务——只读确定性层生成的
>   JSON 并施加评分卡。
> - **为何重要：** 这条边界由 10 个生产 bug 强制产生，不是事后合理化。边界挡住了每一个 bug 对判断输出
>   的污染。

---

## P2 — Hybrid, not thin: the data layer earns its keep · Hybrid 而非 thin：数据层有其存在价值

Two architectural patterns exist for agent skills:

- **Thin:** delegate everything to an existing engine. The skill is a prompt that calls
  `deep-research` or `WebSearch`.
- **Hybrid:** bundle a deterministic data layer; delegate only the judgment to LLM.

For general commercial research, thin delegation (market-intel's pattern) is correct: the
skill's only unique function is source routing and quality guardrails.

For small-cap SEC research, **thin fails**: the 10 production bugs above are all domain-specific
filing edge cases that no general-purpose web-search or LLM-with-tools architecture handles
reliably. A thin skill would re-encounter every one of these bugs on every run:

- EDGAR FTS over-recalls by 15–25×; without `filter_by_sic` + LLM gate, the analyst
  pipeline is flooded with off-topic companies.
- "Going concern" in a filing often appears in the risk-factor section describing hypothetical
  scenarios. The double-confirmation requirement (going-concern paragraph AND substantial-doubt
  language) is not in any general LLM's training for SEC analysis.
- `edgartools` Form 4 direction parsing was unreliable in production (the `transactionCode`
  field semantics are non-obvious). No thin wrapper would have caught this.

The bundled data layer is therefore not overhead — it is **institutional knowledge crystallized
from real production failures.**

The boundary between layers is the implementation of this principle: data layer has no
judgment; judgment layer has no data computation.

> - **为何 Hybrid 而非 thin：** thin 会在每次运行时重踩上述所有坑。数据层不是额外开销——它是真实生产
>   失败结晶的机构知识。判断层 thin 才是对的（LLM 的价值在于读 JSON 应用纪律，而非算财务或拼 FTS 字符串）。

---

## P3 — Discipline as moat, not narrative · 纪律即护城河，非叙事

The market has efficient mechanisms for pricing widely available qualitative information
about small-cap companies. What it prices slowly is **systematic, consistent, mechanical
coverage** of the full SEC-filing universe of a theme.

An individual analyst reading 20 companies will miss going-concern disclosures buried in the
auditor's section. They will not check Form 4 net buy/sell for all candidates. They will be
influenced by which companies have the best IR presentation.

The tool's competitive advantage — to the extent one exists — is:

1. **Complete coverage:** every SEC-filing company in the theme universe, not a curated subset.
2. **Consistent application:** the same kill-flags, the same rubric, the same disconfirmation
   search, for every candidate without attention bias.
3. **Honest zeroing:** the willingness to produce zero shortlist candidates when the universe
   does not support it. Narrative synthesis cannot say "there is nothing here" — it will find
   something. The mechanical kill-flags can.

This is why the rating hard-rules are non-negotiable: **a T3-evidence buy thesis is not a
thesis, it is a rationalization.** The hard rules exist to prevent the LLM judgment layer
from constructing narratives that outrun the evidence.

The fintwit/Reddit critique of LLM investing agents converges on four failure modes:
hallucinated facts, backtest overfitting, confident-but-wrong, and halo bias. Every hard rule
in `reference/judgment-rubric.md` and every kill-flag in `cheap_pass.py` maps to one of these
failure modes. The discipline is not cosmetic; it is the product.

> - **纪律才是护城河：** 市场对广泛可得的定性信息定价有效。它定价慢的，是对 SEC 全库主题候选系统、一致、
>   机械的覆盖。T3 证据的买入论点不是论点，是合理化。硬规则防止 LLM 判断层构建超越证据的叙事。
> - **0 买入是功能：** 叙事综合无法说"这里什么都没有"——它总会找到什么。机械 kill-flag 可以。

---

## P4 — Single source of truth, reference before orchestration · 单一真相源，reference 先于编排

The methodology invariants live in `skills/small-cap-deepdive/reference/*.md`. These files are
the **single source of truth** for how kill-flags are defined, how dimensions are scored, how
evidence is tiered, and what cognitive priors anchor the judgment.

`SKILL.md` orchestrates by *pointing at* these files; it does not inline their content.
`workflows/*.js` loads them as a PREAMBLE; it does not duplicate them.

This design prevents the most common failure mode in agentic systems: **reference drift**,
where the orchestration layer and the reference layer diverge silently over time until they
contradict each other.

The rule: **any change to a methodology invariant is made once, in `reference/`**. The
orchestration and workflow layers are downstream consumers; they change only when the
reference changes, not in parallel.

> - **单一真相源：** 方法论不变量在 `reference/*.md`。`SKILL.md` 通过引用（不内联）使用它们；
>   `workflows/*.js` 作为 PREAMBLE 加载（不复制）。
> - **为何重要：** 防止 reference 漂移——编排层和参考层静默分叉、最终自相矛盾，是 agent 系统最常见的
>   失效模式。

---

## The generative test · 生成式检验

Every future change to this skill — a new tool, a new invariant, a new kill-flag — must pass
one test:

> **"Does this move output closer to truth, or does it make the narrative more convincing
> without moving closer to truth?"**

Adding a tool that retrieves a genuinely distinct data signal: moves closer to truth.
Adding a more sophisticated scoring formula without additional evidence: makes the narrative
more convincing without moving closer to truth.

When the two conflict, the test result wins — or the principle is explicitly, deliberately
revised here. Never quietly violated.

> 未来每次改动——新工具、新不变量、新 kill-flag——都必须通过一个检验：
>
> **"这让输出更接近真相，还是只让叙事更有说服力而没有更接近真相？"**
>
> 当两者冲突，检验结果胜出——或者在这里显式、审慎地修订原则。绝不悄悄违反。
