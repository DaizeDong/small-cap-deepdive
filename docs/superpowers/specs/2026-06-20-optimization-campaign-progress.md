# small-cap-deepdive — 持续优化 Campaign 进度追踪

> 启动 2026-06-20。目标:通过"反思 → 设计 → 实施 → 实测 → 评估"多路迭代,把 skill 持续优化到**现实可用标准**。全自动运行,质量优先,doc 追踪。

## 起点状态
- 版本 v0.2.1(commit `1a94a6b`),结构已重组为自包含(repo 根=skill 根,junction 指向根),批次输出机制(`SMALLCAP_RUN` + `_run.json`)就位。
- 历史数据:`reports/smallcap/2026-06-18_early-runs/`(44)+ `2026-06-19_validation-v0.2.0/`(398);`metrics/verdicts.jsonl`(40);`docs/2026-06-19-validation-report.md`(21-agent 验证结论)。
- 已知核心结论:BUY 扳机可达但 v0.2.0 真实 BUY 全是数据层假阳;v0.2.1 已加护栏。**核心未解问题:"延迟信息扩散"这一立论是否被真正度量(还是只是 cheapness+quality 筛选)。**

## 循环结构(每轮迭代)
1. **Reflect** — 多透镜 subagent 独立审计历史数据+内部实现,提改进建议(各角度:信息源广度/召回/估值模型/评价指标/校准/数据鲁棒/方法论/分析师差距/工效/事件轴)。
2. **Design(brainstorm)** — 主 agent 汇总→完整修改方案→**唯一人工审批门**。
3. **Implement** — subagent 实施 + 复查 + selftest。
4. **Test** — 旧主题重跑(before/after 对比)+ 新主题多样性(前沿热点+刁钻领域),用 market-intel 工具补充信息源,并行 subagent 评估,产出独立报告。
5. **Assess** — 对照现实可用标准,决定继续迭代或收敛。

## 唯一人工门
brainstorming skill 硬性要求:实施前需呈现设计并获批准。这是整个 campaign 唯一的人工 checkpoint(在迭代1 反思之后)。批准后实施→实测→迭代全自动。

## 迭代日志

### 迭代 1
| 阶段 | 状态 | 产出 |
|---|---|---|
| 1 Reflect | ✅ | 10 透镜+综合(1.7M tok),notes `.git/sdd/reflection/`;**核心发现:立论未被度量,MoS≡reverse_dcf,19/19 BUY 按构造定价衰退=价值陷阱生成器** |
| 2 Design+门 | 🔄 审批中 | 设计 `docs/superpowers/specs/2026-06-20-smallcap-optimization-design.md`;P1-P14 philosophy-safe + 3 个 gated 决策待批 |
| 3 Implement | ⏳ | |
| 4 Test | ⏳ | |
| 5 Assess | ⏳ | |

**核心诊断(迭代1 反思):** ①立论"延迟信息扩散"代码里零度量,MoS 与 reverse_dcf 代数相同→19/19 BUY 按构造定价衰退;②v0.2.1 护栏是 advisory 字符串,扳机从不 block(VSNT $5.4B/ARDT $6.3B 过 BUY);③校准环 inert(40 verdict 全 abstain,与 19 BUY 交集空);④单一 SEC 源无二次校验;⑤召回从不度量,yfinance-null 静默丢 91-100%。

## 决策记录
（按时间追加:每个设计决策、philosophy 变更、收敛判断）

## 最终结论
（campaign 结束时汇总）
