# small-cap-deepdive, 持续优化 Campaign 进度追踪

> 启动 2026-06-20。目标:通过"反思 → 设计 → 实施 → 实测 → 评估"多路迭代,把 skill 持续优化到**现实可用标准**。全自动运行,质量优先,doc 追踪。

## 起点状态
- 版本 v0.2.1(commit `1a94a6b`),结构已重组为自包含(repo 根=skill 根,junction 指向根),批次输出机制(`SMALLCAP_RUN` + `_run.json`)就位。
- 历史数据:`reports/smallcap/2026-06-18_early-runs/`(44)+ `2026-06-19_validation-v0.2.0/`(398);`metrics/verdicts.jsonl`(40);`docs/2026-06-19-validation-report.md`(21-agent 验证结论)。
- 已知核心结论:BUY 扳机可达但 v0.2.0 真实 BUY 全是数据层假阳;v0.2.1 已加护栏。**核心未解问题:"延迟信息扩散"这一立论是否被真正度量(还是只是 cheapness+quality 筛选)。**

## 循环结构(每轮迭代)
1. **Reflect**, 多透镜 subagent 独立审计历史数据+内部实现,提改进建议(各角度:信息源广度/召回/估值模型/评价指标/校准/数据鲁棒/方法论/分析师差距/工效/事件轴)。
2. **Design(brainstorm)**, 主 agent 汇总→完整修改方案→**唯一人工审批门**。
3. **Implement**, subagent 实施 + 复查 + selftest。
4. **Test**, 旧主题重跑(before/after 对比)+ 新主题多样性(前沿热点+刁钻领域),用 market-intel 工具补充信息源,并行 subagent 评估,产出独立报告。
5. **Assess**, 对照现实可用标准,决定继续迭代或收敛。

## 唯一人工门
brainstorming skill 硬性要求:实施前需呈现设计并获批准。这是整个 campaign 唯一的人工 checkpoint(在迭代1 反思之后)。批准后实施→实测→迭代全自动。

## 迭代日志

### 迭代 1
| 阶段 | 状态 | 产出 |
|---|---|---|
| 1 Reflect | ✅ | 10 透镜+综合(1.7M tok),notes `.git/sdd/reflection/`;**核心发现:立论未被度量,MoS≡reverse_dcf,19/19 BUY 按构造定价衰退=价值陷阱生成器** |
| 2 Design+门 | 🔄 审批中 | 设计 `docs/optimization-campaign-2026-06/2026-06-20-smallcap-optimization-design.md`;P1-P14 philosophy-safe + 3 个 gated 决策待批 |
| 3 Implement | ✅ | 工作流 ws8ka7t8b(11 agent,phased+contract+review)。16 文件+2 新工具。**review 抓到真 bug:P6 轨迹否决在真实 SIGA 失效(原始系列被 9 月 stub+错标 FY 污染→全时 slope +1);两 reviewer 分歧,主控裁定后修复(annualize+trailing-5)+ 加真实 SIGA 回归 crystal。** 全 selftest PASS;SIGA 现 slope=-1/decline_flag=True/concentration=kill 双重 block;VSNT 大盘 block;MGPI 不误杀。 |
| 4 Test | ✅ | 工作流 wozfowakg。旧 before/after + 新主题。**P5 召回验证:regbank 0→271、shipping 12→219(静默丢已修);SIGA 双重 block;假阳队列全 buy_eligible=false;royalty→1 干净 BUY(INVA)+诚实 abstain 尾;uranium→正确 0-BUY。** 4/6 新主题完成(ai-dc-power/glp1/defense-drones/title-insurance 因 agent 异步执行 run_theme 未完成→并入迭代2 同步重跑)|
| 5 Assess | ✅ | `iter1-test/_assessment.md`。**裁定:迭代1 达到核心使命的现实可用 bar**(引擎从价值陷阱生成器→避雷扫描器;13 项修复全实证 firing)。**最大遗留=P-A:P6 V 形盲点(NRP 机械 BUY 是真陷阱,仅人工 catch)** + P-B 标签误报 + 卫生项 P-C~H + 推迟的扩展 P7/8/14/11/15-17。→ **决定:迭代** |

### 迭代 2, 硬化核心(correctness + hygiene)
| 阶段 | 状态 | 产出 |
|---|---|---|
| Implement | ✅ | 工作流 w5cya3269 (commit 2599d66, 7 文件 +934)。**P-A peak_contamination_flag(独立于 slope)实测 NRP=True→buy_eligible=False(V形陷阱被机器杀,非仅人工)** + P-B low_revenue_loss_ratio(URG 正确标签,wrong_entity 阈值 2→50,debt_trunc 0.5→0.1)+ P-D 崩溃 ERROR.json + P-C/E/F/G/H 卫生。主控独立复核:全 selftest PASS、NRP 真实 block、INVA 不误杀、SIGA 仍双重 block。 |
| Test | ✅ | 工作流 w1w8xsetq(同步执行修复,4 主题全完成)。**回归全 PASS:NRP BUY→避开(V形被机器杀)/INVA 仍干净 BUY/EU 周期复苏不误杀/SIGA 双重 block。** ai-dc-power/defense-drones/glp1/title-insurance 全 0-BUY(诚实);**金融-SIC 在 title-insurance 压测下守住(SLQT NAV+62.6%→AVOID)**;V形否决 22 个增长股 0 误报。assess 裁定:**达 defensible 现实可用标准**。新缺口→迭代3。 |

### 迭代 3, 闭合 iter2 新缺口 + 召回度量(🔄 实施中 wpxplzb7g)
A1 退化基线守卫(BWIN 负 contamination_ratio bug)· A2 concentration_unquantified(文本-only/pre-XBRL 集中度盲点,SWMR)· A3 保险子公司/SIC-65 holdco override(BOC)· A4 wrong_entity 收严+low_revenue_loss_ratio 极端分级 · A5 Gate-2 分母 · **P8 SIC 反向召回+recall@gold(首次度量召回)**。

### 迭代 4, 信息源广度 / 立论操作化(✅ commit 223b0a4)
**firewalled 诊断侧信道**:`signals.py`(P16 价格背离 + P17 持仓)+ 集成(deepdive 顶层 signals / make_report T2 段 / track_forward signals_snapshot inert)+ P-G。**FIREWALL 验证:valuation/finalize/rank 对 signals 零引用,buy_eligible 加/不加 signals 字节相同。** 真实数据:MGPI=unpriced_improvement(基本面升+价格-40%=买入论点,**立论首次被度量**)/ SIGA=aligned。P15 alt-data 保持 agent 采集 T2。全 9 selftest PASS。**campaign 最深问题(立论未度量)已闭合(诊断层)。**

### 迭代 5, 收官:P7 二次源(✅ commit d4ae2e8)
SEC-XBRL vs yfinance 交叉校验 → cross_source_mismatch 数据完整性门。**HRI 双重捕获(SEC debt $11.2M vs yf $9.6B=861×→cross_source_mismatch + debt_truncation)**;INVA 不误杀;SIGA 不变。全 9 selftest PASS。**原诊断 #4(单一源脆弱)闭合。**

### 进一步路线图(收敛后文档化,非阻塞现实可用)
P14 取证脊柱 · P11-full 催化剂机制验证(当前安全冻结)· 侧信道 per-signal Brier 校准(待 verdict 成熟 2027)。

**核心诊断(迭代1 反思):** ①立论"延迟信息扩散"代码里零度量,MoS 与 reverse_dcf 代数相同→19/19 BUY 按构造定价衰退;②v0.2.1 护栏是 advisory 字符串,扳机从不 block(VSNT $5.4B/ARDT $6.3B 过 BUY);③校准环 inert(40 verdict 全 abstain,与 19 BUY 交集空);④单一 SEC 源无二次校验;⑤召回从不度量,yfinance-null 静默丢 91-100%。

## 决策记录
- **2026-06-20 审批门(迭代1):** Q1=操作化立论(P6 保守半,现在)、Q2=盘间数据建为隔离诊断侧信道(P15/16/17,严格 firewall)、Q3=冻结催化剂 MoS 豁免。
- **迭代1 范围决定(quality-first 拆分):** 迭代1 只做信任脊柱+保守立论修复+诚实输出/校准基础 = P1,P2,P3,P4,P5,P6,P9,P10,P12,P13 + P11-freeze(1 行安全) + SSOT 修(rubric:222 carve-out / data-sources:90 / PHILOSOPHY 操作化注)。**扩展项 P7(二次源)、P8(召回底+recall@gold)、P14(取证脊柱)、P11-full(催化剂机制)、P15/16/17(侧信道)推迟到迭代2**,由迭代1 实测结果指导。理由:reflection 自身 sequencing「先信任后扩展」;重文件重叠需分相;多迭代结构正好承接。

## 最终结论(campaign 收敛 2026-06-20)

**5 轮迭代,原始 4 大诊断全部闭合**,引擎从"价值陷阱生成器"→"校准化避雷扫描器 + 操作化(诊断)立论层"。完整汇总见 **`2026-06-20-campaign-final-report.md`**。

- ① 立论未度量 → iter4 price_divergence 诊断(MGPI=unpriced_improvement,firewall 验证)
- ② 护栏不阻断 → iter1 buy_eligible 机械门(VSNT/ARDT/SIGA 全 block)
- ③ 校准 inert → iter1 P12(回填 19 假阳 + de-risk 指标)
- ④ 无二次源 → iter5 P7(HRI 双重捕获 861×)
- 附:集中度(P3)、V 形陷阱(iter2 P-A)、召回度量(iter3 recall@gold 100%)、大量鲁棒/卫生修复

**测试驱动闭环每轮都 catch 到 selftest 漏掉的真 bug**(P6 污染序列 / V 形盲点 / 负 ratio / EFTS 空查询),主控裁定了一次 reviewer 分歧。**达到并超过现实可用标准**;0-BUY 是常态正确输出,机械 BUY 仍需人工核对资产负债表。

**前向路线图(非阻塞,已文档化):** P14 取证 · P11-full 催化剂(安全冻结中)· 侧信道 per-signal Brier 校准(待 2027 verdict 成熟)· P15 alt-data 自动化 · recall@gold gold-list 扩展。

提交链:reflection(wtndselbs)→ 设计 acf16d9 →迭代1 e0f0039/0877b99 →迭代2 2599d66/c88fb60 →迭代3 b28245a →迭代4 223b0a4 →迭代5 d4ae2e8 →最终报告。
