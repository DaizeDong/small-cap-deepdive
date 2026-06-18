# small-cap-deepdive

面向被忽视的美股小盘股的纪律化尽调编排 skill。给定一个投资主题或一个 ticker，自 SEC 申报全库枚举候选，施加机械避雷硬规则，以强制反方为前提做可证伪的深度尽调，并对幸存候选排序。

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![依赖](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![版本](https://img.shields.io/badge/version-0.1.0-purple?style=flat)](CHANGELOG.md)

[English](README.md) | [中文版](README_CN.md)

---

## 先读这里：这个工具是什么，不是什么

**被忽视 ≠ 被低估。**

无分析师覆盖的小盘股满足了必要条件，但这不是充分条件。被忽视本身已被有效定价。真正制造可利用低效的，是围绕基本面真实变化的信息扩散延迟。这个工具的作用是找到可能满足该条件的公司——并在任何判断开始之前，机械地淘汰掉那些不可能满足的。

**产出是避雷扫描器，不是买入清单。**

排名靠前的公司意味着它通过了所有淘汰门、有真实的主题敞口、值得完整人工尽调——不代表买入。这个工具的核心价值，在于它**排除**了什么：持续经营疑虑的候选、死亡螺旋的稀释者、不正常申报的公司——这些在任何判断动用之前就已被挡在门外。

**0 买入是功能，不是 bug。**

若某主题产出零个 4 分以上候选，工具在告诉你：当前该主题的小盘股中，没有干净的产业受益者。这是正确且有用的答案。一个无法输出"什么都没找到"的扫描器，不是扫描器，是叙事生成机。

📜 **[阅读设计哲学 → PHILOSOPHY.md](PHILOSOPHY.md)**

---

## 它做什么

1. **枚举 SEC 全库**：用 EDGAR 全文检索（FTS）按主题拉取候选。过召回是设计意图——后续精度门负责清场。

2. **两阶段精度门（强制）**：门 1（`filter_by_sic.py`）：基于 SIC 行业码粗排除明显无关行业。门 2（LLM）：读每家公司 10-K 业务描述，判 `pure_play / tangential / false_positive`。典型失败案例：用 `refractory`（难治性）作为铁路车厢隔热主题关键词，FTS 拉回整个肿瘤 biotech 板块，零家铁路公司。缺少这两道门会把错误的候选送进后续尽调。

3. **机械避雷**（`cheap_pass.py`）：直接读 SEC 申报的硬红线——持续经营审计段、死亡螺旋可转债、内控重大缺陷。触发的公司不进入判断，无论叙事质量如何。

4. **取数**（`deepdive_data.py`）：XBRL 财务序列、Form 4 内部人交易、货架/ATM 状态、稀释历史、重大事件时间线。

5. **强制反方判断**：评分前先锚定基准概率，对每个候选强制反方 WebSearch，7 维评分卡配硬上限规则。证据按 Tier 标注（T1 第一方 SEC 申报 → T5 推断）；T3 证据不得作为买入支撑。

6. **排序**（`rank.py`）：按综合分排列幸存候选，附漏斗计数、淘汰原因、显式数据盲区。

---

## 它不做什么

- 多因子/量化选股或回测——实证证明扣除交易成本后因子 alpha 消失，这个决策空间不进本工具。
- 交易信号、执行或组合管理。
- 实时行情——所有数据来自 SEC 申报，典型延迟 1–4 天。
- 大盘/卖方覆盖——工具针对无或极少分析师覆盖的小盘/微盘股校准。
- 自动买入建议——每份输出以"值得人工尽调"结尾，不以"买入"结尾。

---

## 安装

```bash
git clone https://github.com/DaizeDong/small-cap-deepdive.git
cd small-cap-deepdive
pip install -r tools/requirements.txt
```

然后一次性配置：

```bash
cp skills/small-cap-deepdive/reference/config.example.json \
   skills/small-cap-deepdive/reference/config.json
```

打开 `config.json`，将 `"sec_user_agent"` 设为你的真实姓名和邮箱：

```json
"sec_user_agent": "张三 zhangsan@example.com"
```

这是唯一必填字段。EDGAR 要求每次请求带有效 `User-Agent` 头（SEC 政策），缺失或使用假值会导致 `efts.sec.gov` 返回 403。

部署为 Claude Code skill（建立 junction/symlink）：

```bash
# Windows（以管理员身份运行）
cmd /c mklink /J "%USERPROFILE%\.claude\skills\small-cap-deepdive" "skills\small-cap-deepdive"

# macOS / Linux
ln -s "$(pwd)/skills/small-cap-deepdive" "$HOME/.claude/skills/small-cap-deepdive"
```

---

## 三种入口模式

### 1. 主题跑——全库筛选

获取某主题的小盘纯玩家排名：

```
/small-cap-deepdive theme "铁路车厢租赁"
/small-cap-deepdive theme "railcar leasing"
```

或在任何 Claude Code 会话里用自然语言：

```
对"铁路车厢租赁"主题跑 small-cap-deepdive
```

完整步骤：**[runbooks/theme-run.md](runbooks/theme-run.md)**

预计 token 预算：~30 万 token，约 $0.30，小众主题约 1–3 小时。

### 2. 单只票深度尽调

对已知公司做严格的可证伪报告：

```
/small-cap-deepdive ticker EGAN
/small-cap-deepdive ticker EGAN --theme "合规行业 SaaS"
```

完整步骤：**[runbooks/single-deepdive.md](runbooks/single-deepdive.md)**

预计 token 预算：~1–1.5 万 token，<$0.02。

### 3. 批量重排已有评分

不重跑发现和尽调，对已有输出换权重或重排：

```bash
python tools/rank.py --scores-dir reports/railcar_scores/ --out ranked.md
python tools/rank.py --scores-dir reports/railcar_scores/ --weight-overrides '{"dim1":0.35,"dim4":0.25,...}'
```

完整步骤：**[runbooks/batch-rank.md](runbooks/batch-rank.md)**

预计 token 预算：零——纯确定性计算，无 LLM 调用。

---

## 架构

```
取数层（确定性 Python，只摆数据，永不做投资判断）
  tools/_common.py       — 配置、EDGAR session、速率限制、重试退避
  tools/discover.py      — EDGAR FTS 全库枚举
  tools/filter_by_sic.py — 门 1：SIC 粗排除
  tools/cheap_pass.py    — 机械避雷硬红线
  tools/deepdive_data.py — XBRL + Form 4 + 货架状态取数
  tools/rank.py          — 确定性评分与排序
  tools/run_theme.py     — 主题端到端驱动

判断层（LLM，只读 JSON 做判断，永不计算财务数据）
  skills/small-cap-deepdive/SKILL.md         — 编排 + 世界观 + 硬规则
  skills/small-cap-deepdive/reference/*.md   — 方法论不变量（单一真相源）
  workflows/theme-fit-gate.js  — 可选：门 2 并行加速
  workflows/deepdive-fanout.js — 可选：尽调并行加速
```

**边界是硬性的：** `tools/*.py` 只出数，不做投资判断；判断层只读 JSON，不算财务。这个分工在 10 个真实生产 bug 中得到验证——所有 bug 都在取数层，架构边界阻止了它们污染判断输出。

---

## 依赖

| 包 | 许可 | 用途 |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | EDGAR FTS、XBRL 解析、Form 4 检索 |
| yfinance | Apache 2.0 | 市值/股价便利层 |
| pandas | BSD | 数据处理 |
| requests | Apache 2.0 | 带速率纪律的 HTTP |

无专有依赖，核心数据层无需 API key。

**market-intel（可选只读复用）：** 若已安装 `market-intel` skill，判断层会读取其源目录来路由定性检索（X 舆情、行业新闻、竞品网络存在感）到最优 MCP 工具。market-intel 不会在运行时被当作 skill 调用——只读取 catalog 作为文档。完整的防递归设计见 `reference/data-sources.md §market-intel`。

---

## 公开版说明

**openinsider 脆弱性：** 默认 `insider_source` 配置使用 `openinsider.com` 解析 Form 4 买卖方向。该第三方服务无明确的自动访问条款。工具在 openinsider 不可用时自动回退到直接 EDGAR Form 4 解析，并在报告中标注数据来源。

推荐生产和公开部署使用 EDGAR 模式：

```json
"insider_source": "edgar"
```

该模式使用 `edgartools` Form 4 检索 + 自定义方向解析器（`transactionCode` 字段：`P`=购买，`S`=出售）。

**workflow .js 文件为可选项：** `workflows/theme-fit-gate.js` 和 `workflows/deepdive-fanout.js` 在 Claude Code 会话中有 Workflow 工具时可加速并行步骤。它们不是必要依赖——`SKILL.md` 中的自然语言编排是主路径，任意 Claude Code 会话均可运行。

**X 舆情路由：** 需要某只票的 X/Twitter 舆情时，若已通过 market-intel 配置文件配置了 twitterapi.io key，则走 ② resale 路由（供应商账号池+代理，用户账号零风险）；不可用时回退到搜索引擎索引 X 内容。永久排除路线 ③（用户自己账号的 twikit/playwright 登录）——存在账号封禁风险。

---

## 评分速查

| 分数 | 含义 | 行动 |
|---|---|---|
| 4–5 | 通过全部门，真实主题敞口，无结构性红线 | 值得完整人工尽调 |
| 3 | 边界——某一维度偏弱 | 读维度详情后再决定 |
| 1–2 | 硬上限规则生效 | 存在已命名的结构性问题；在解决前不应投资 |
| 已淘汰 | cheap_pass 触发 kill-flag | 停止——不必重新审查 |

综合分 = 7 维加权平均。硬上限规则凌驾于叙事质量之上。完整评分卡：`skills/small-cap-deepdive/reference/judgment-rubric.md`。
