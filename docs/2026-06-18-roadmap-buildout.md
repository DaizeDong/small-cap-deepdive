# small-cap-deepdive — ROADMAP Buildout 进度追踪

> 自动推进 ROADMAP P2-P7 + 余项。每阶段:实现 → 审查 subagent → 修复 → 优化/整理 subagent(多轮)→ 验证 → commit → 更新本文档 → 下一阶段。不偷工减料。
> 起始 commit: 99daf7a (P1 已完成)。目标版本 v0.2.0。

## 阶段清单与状态

| # | 阶段 | ROADMAP 项 | 状态 | commit |
|---|---|---|---|---|
| 1 | 机械层加固 | insider 金额+方向 / P6 material_weakness 误报 / P7 theme-fit 冗余 | ✅ done | e2b74bd |
| 2 | 估值模块 | P2 valuation.py(反向DCF+倍数+行业分位+周期谷底EBITDA)+ 资产型NAV路径 | ✅ done | 06416de |
| 3 | BUY 扳机+催化剂轴 | P3 安全边际≥30% 对称买入硬规则 + catalyst 维度 + 护栏 | ✅ done | 801e16b |
| 4 | 召回改进 | P4 20-F/40-F + SIC降级不drop + 双市值带 + per-theme关键词 | ✅ done | fc3d932 |
| 5 | 事件驱动发现 | P5 spinoff(10-12B)+ cluster insider(Form4)发现轴 + events 入口 | ✅ done | 9f5a978 |
| 6 | track-forward | metrics/verdicts.jsonl + track_forward.py(Brier 记分) | ✅ done | 8c2b9d8 |
| 7 | 终集成+全审+版本 | 端到端测试 + 全 skill 对抗审查 + README/SKILL/CHANGELOG/版本 v0.2.0 | ✅ done | 76d8297 |

**🎉 全部 7 阶段完成,v0.2.0 已发布并 push(76d8297)。**

## 每阶段质量门(no corners)
1. 实现 subagent(带 selftest/验证)
2. 审查 subagent(spec 合规 + 代码质量 + 不变量未破坏 + 单一真相源未漂移)
3. 修复 Critical/Important
4. 优化/整理 subagent(结构整齐、命名一致、去冗余、文档对齐)—— 多轮直到干净
5. 控制器独立复验(re-run selftests + 关键断言)
6. commit + push + 更新本文档

## 不变量护栏(贯穿所有阶段,不得破坏)
- 取数层只出数不做判断;判断层只读 JSON 不算财务;reference 单一真相源被引用非复制。
- 零功能性硬编码(config 化);bug-fix结晶完整(amendment 排除/concept fp 选择/going-concern 双命中/SIC 粗排除/FTS 退避)。
- MIT 依赖;openinsider 脆弱性已标注;market-intel 只读 catalog 防递归。
- 新增 BUY 能力必须:仅 T1 估值承重、周期股用谷底 EBITDA、保留 pre-mortem+强制反方;不得退回讲故事。

## 进度日志
- 2026-06-18: 起始。P1(数据正确性+召回窗口)已完成并 push(99daf7a)。开始阶段 1。

## 完成总结 (2026-06-19)
- **P1** 机械层加固 (e2b74bd) · **P2** 估值引擎 (06416de) · **P3** BUY扳机+催化剂轴 (801e16b) · **P4** 召回改进 (fc3d932) · **P5** 事件驱动发现 (9f5a978) · **P6** track-forward校准 (8c2b9d8) · **P7** 终集成+发布 v0.2.0 (76d8297)。
- 每阶段经 实现→审查subagent(抓真问题)→修复→控制器复验 闭环;6个审查均判 NEEDS-FIXES/APPROVE-WITH-MINOR 并修复后才进。
- 端到端集成 PASS:funeral 主题 141→34→1 pure_play(SNFCA)→深查→MoS 128.7% 但 material_weakness kill-flag → 正确不买(保守性成立)。
- 不变量全程保持;新增能力(估值/BUY/事件/校准)未退回讲故事;0-BUY 仍是合法输出。
