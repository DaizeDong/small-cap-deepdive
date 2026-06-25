# small-cap-deepdive

机械化排雷 SEC 小盘股全库——给定主题或 ticker，先排掉地雷，再深挖幸存者。

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![避雷扫描器](https://img.shields.io/badge/%E9%81%BF%E9%9B%B7-%E6%89%AB%E6%8F%8F%E5%99%A8-green?style=flat)](#-先读这里--设计哲学)
[![依赖](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![语言](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-EN%20%2F%20CN-blue?style=flat)](#语言)
[![Roadmap](https://img.shields.io/badge/Roadmap-v0.3.3-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## ⭐ 先读这里 — 设计哲学

**被忽视 ≠ 被低估。**

无分析师覆盖的小盘股满足了必要条件，但这不是充分条件。被忽视本身已被有效定价。真正制造可利用低效的，是围绕基本面真实变化的信息扩散延迟。这个工具的作用是找到可能满足该条件的公司——并在任何判断开始之前，机械地淘汰掉那些不可能满足的。

**产出是避雷扫描器，不是买入清单。**

排名靠前的公司意味着它通过了所有淘汰门、有真实的主题敞口、值得完整人工尽调——不代表买入。这个工具的核心价值，在于它**排除**了什么：持续经营疑虑的候选、死亡螺旋的稀释者、不正常申报的公司——这些在任何判断动用之前就已被挡在门外。

**0 买入是功能，不是 bug。**

若某主题产出零个 4 分以上候选，工具在告诉你：当前该主题的小盘股中，没有干净的产业受益者。这是正确且有用的答案。一个无法输出"什么都没找到"的扫描器，不是扫描器，是叙事生成机。

一句话：**工具的 edge 是机械纪律一致地施加于全量候选，而非对某家公司的叙事综合。** 本仓库里的每个工具、每个不变量、每条硬规则，都源于四条原则——改根因（不打补丁）、Hybrid 而非 thin（数据层有其存在价值）、纪律即护城河、`reference/` 单一真相源。

📜 **[阅读完整设计哲学 → PHILOSOPHY.md](PHILOSOPHY.md)**

---

## 它是什么（不是什么）

给定一个投资主题或一个 ticker，skill 自 SEC 申报全库枚举候选，施加机械避雷硬规则，以强制反方为前提做可证伪的深度尽调，并对幸存候选排序。逐步拆解：

0. **开运行批次**（`new_run.py`）：每次运行写入 `reports/smallcap/<日期>_<label>/`，附 `_run.json` manifest（skill git commit + 估值 config 快照），便于按版本对比。`export SMALLCAP_RUN=$(python tools/new_run.py --label <主题>)`。

1. **枚举 SEC 全库**：用 EDGAR 全文检索（FTS），并 UNION 一个 **SIC 反向召回底**（`discover.py` + `filter_by_sic.py`）——对有专属 SIC 码的主题,枚举该 SIC 下全部注册人,避免漏掉低关键词密度的真实成员。市值用 fallback 链解析（yfinance 为空时用 SEC 股数×价格）；仍无法定价的归 `band="unknown"` 流过,而非静默丢弃。

2. **两阶段精度门（强制）**：门 1（`filter_by_sic.py`）：基于 SIC 行业码粗排除明显无关行业。门 2（LLM）：读每家公司 10-K 业务描述，判 `pure_play / partial / misrecall`。典型失败案例：用 `refractory`（难治性）作为铁路车厢隔热主题关键词，FTS 拉回整个肿瘤 biotech 板块，零家铁路公司。召回用 `recall@gold`（对照手工真实成员清单）**度量**,而非假设。

3. **机械避雷**（`cheap_pass.py`）：直接读 SEC 申报的硬红线——持续经营审计段、死亡螺旋可转债、内控重大缺陷、magnitude 级客户/政府单一项目集中度。触发的公司不进入判断,无论叙事质量如何。

4. **取数**（`deepdive_data.py`）：XBRL 财务序列（含 EBIT 概念级联、债务与股数 fallback）、Form 4 内部人交易、货架/ATM 状态、稀释历史、重大事件时间线。数据完整性守卫：债务截断、错误实体、低营收巨亏比、以及**二次源交叉校验**（SEC vs yfinance，>2.5× 分歧即标记并阻断 BUY）。

5. **估值 + 机械 `buy_eligible` 门**（`valuation.py`）：反向 DCF（标准化 FCF）、EV/EBITDA 倍数、周期底部 EBITDA 标准化、重资产 NAV 路径。买入要求 `mos_basis∈{fcf_cap,nav}` 且 安全边际 ≥ 30% 且 **`buy_eligible == true`** 且 零 kill-flag 且 无 T3 核心论据。`buy_eligible` 与入全部守卫——极端 MoS、大盘上限、FCF 可持续性、金融-SIC/保险排除、债务截断、二次源分歧、集中度 kill,以及 **V 形价值陷阱否决**（`fundamental_decline_flag` 单调下滑 + `peak_contamination_flag` 谷→峰→回落）。催化剂修正当前冻结为 WATCH（待机制校准）。

6. **强制反方判断**：评分前先锚定基准概率，对每个候选强制反方 WebSearch，7 维评分卡配硬上限规则。证据按 Tier 标注（T1 第一方 SEC 申报 / T2 独立第三方 / T3 公司自述）；T3 证据不得作为买入支撑。

7. **收尾 + 排序**（`finalize_run.py`、`make_report.py`、`rank.py`）：确定性逐票报告,每个评级下附数据质量**信任 banner**,自动生成 verdict 喂入 track-forward,并产出 `RANKING.md`（漏斗计数、淘汰原因、数据盲区）。

8. **前向校准**（`track_forward.py`）：verdict 记入 `metrics/verdicts.jsonl`,到期对 IWM 做 Brier 评分,含 de-risk 指标（避免暴雷/下行捕获）。

9. **诊断信号——防火墙隔离**（`signals.py`）：严格诊断的侧信道,度量"延迟信息扩散"立论——**价格背离**（基本面轨迹 vs 滚动价格回报 → `unpriced_improvement` / `melting_ice_cube_priced` / `aligned`）与**持仓**（13D/13G + 做空)。它**永不**触碰 `buy_eligible` 或买入决策,仅记录供未来 per-signal 校准。

**它不做什么：**

- 多因子/量化选股或回测——实证证明扣除交易成本后因子 alpha 消失，这个决策空间不进本工具。
- 交易信号、执行或组合管理。
- 实时行情——所有数据来自 SEC 申报，典型延迟 1–4 天。
- 大盘/卖方覆盖——工具针对无或极少分析师覆盖的小盘/微盘股校准。
- 自动买入建议——每份输出以"值得人工尽调"结尾，不以"买入"结尾。

### 留出集验证（2026-06）

一个 25 格、无幸存者偏差的 point-in-time 回测（5 主题 × 5 个 as-of 日期 2020–2024，12 个月持有期）
在留出数据上检验了 skill 的主张。诚实结论——详见
[`docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md`](docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md)：

- **无持久 alpha。** 便宜度（安全边际 MoS）在样本内跑赢市场，但那是 2020–21 后疫情反弹的 regime 假象，
  在留出集上消失（holdout permutation p=0.72）。**工具无法选出跑赢者，也不声称能**——这正是它从不发出"买入"的原因。
- **真实的避崩盘 edge**（它的本职）。经 OOS 验证的 **CORE-4 困境 kill-flag**（经营现金流为负、经营亏损、
  累计赤字、Altman Z″ < 1.1）把困境股打入 AVOID：top-quintile 崩盘 **lift 2.56×**、recall 62%，
  ticker 聚类 bootstrap 对 lift 的 95% CI = **[1.73, 3.00]**（P(lift≤1)=0）。0-BUY 的扫描结果依然有效——
  价值在于你**没有**踩到的雷。

---

## 安装

```
/plugin install github:DaizeDong/small-cap-deepdive
```

或手动克隆：

```bash
git clone https://github.com/DaizeDong/small-cap-deepdive.git ~/.claude/plugins/small-cap-deepdive
```

然后安装取数层依赖并一次性配置：

```bash
cd ~/.claude/plugins/small-cap-deepdive
pip install -r tools/requirements.txt
cp reference/config.example.json reference/config.json
```

打开 `config.json`，将 `"sec_user_agent"` 设为你的真实姓名和邮箱：

```json
"sec_user_agent": "张三 zhangsan@example.com"
```

这是唯一必填字段。EDGAR 要求每次请求带有效 `User-Agent` 头（SEC 政策），缺失或使用假值会导致 `efts.sec.gov` 返回 403。

若不走 `/plugin install`，也可建立 junction/symlink 部署为 Claude Code skill：

```bash
# Windows（以管理员身份运行）
cmd /c mklink /J "%USERPROFILE%\.claude\skills\small-cap-deepdive" "skills\small-cap-deepdive"

# macOS / Linux
ln -s "$(pwd)" "$HOME/.claude/skills/small-cap-deepdive"
```

---

## 快速开始

> **每种模式先开运行批次**：`export SMALLCAP_RUN=$(python tools/new_run.py --label <名称>)` 把所有产物路由到 `reports/smallcap/<日期>_<名称>/`,附 `_run.json`(skill commit + config),保证可复现、可跨版本对比。未设则平铺(向后兼容)。

共有四种入口模式。

### 1. 主题跑——全库筛选

获取某主题的小盘纯玩家排名：

```
/small-cap-deepdive theme "铁路车厢租赁"
/small-cap-deepdive theme "railcar leasing"
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
python tools/rank.py
python tools/rank.py --slug railcar
python tools/rank.py --input reports/railcar_scores/
```

完整步骤：**[runbooks/batch-rank.md](runbooks/batch-rank.md)**

预计 token 预算：零——纯确定性计算，无 LLM 调用。

### 4. 事件驱动发现——分拆或内部人集群

用结构性催化剂（强制交易）而非主题关键词来发现被误定价的小盘股：

```bash
# 枚举近期分拆注册（Form 10-12B）
python tools/discover_events.py --spinoffs

# 枚举集群公开市场内部人买入（openinsider）
python tools/discover_events.py --insider-clusters
```

分拆催化剂：母公司的被动指数基金持有人被迫卖出子公司股票（不在指数范围内），
产生短暂供给过剩、无自然接盘者。

内部人集群催化剂：多名内部人在公开市场用个人资金买入，是可获取的最硬管理层
信心信号（Form 4，公开市场现金购买，不含期权行权）。

无需主题适配门——表单类型枚举本身即为精确过滤器。Kill-flag 扫描仍然强制执行
（`cheap_pass.py --universe <candidates_event_*.json>`）。未上市的分拆子公司（暂无
ticker）通过 CIK 处理，归入 `band="unknown"` 队列。

预计 token 预算：含全量尽调约 30 万 token。

---

## 如何触发

任意模式用 slash 命令，例如 `/small-cap-deepdive theme "铁路车厢租赁"` 或
`/small-cap-deepdive ticker EGAN`。或在任何 Claude Code 会话里用自然语言触发：

```
对"铁路车厢租赁"主题跑 small-cap-deepdive
用 small-cap-deepdive 把 EGAN 当小盘股深挖
对"工业水处理"主题筛 SEC 小盘股全库
```

skill 触发于小盘/微盘价值研究、主题选股、单公司深度尽调。它**不**触发于大盘/卖方覆盖、
多因子/量化选股、交易信号或执行。

---

## 示例输出

每个候选机械化评级。评分速查：

| 分数 | 含义 | 行动 |
|---|---|---|
| 4–5 | 通过全部门，真实主题敞口，无结构性红线 | 值得完整人工尽调 |
| 3 | 边界——某一维度偏弱 | 读维度详情后再决定 |
| 1–2 | 硬上限规则生效 | 存在已命名的结构性问题；在解决前不应投资 |
| 已淘汰 | cheap_pass 触发 kill-flag | 停止——不必重新审查 |

评级是机械的：`rating = f(MoS / NAV-MoS, kill-flags, 硬上限, buy_eligible)`。7 维评分卡是诊断性 `/35` 汇总（无隐藏权重）,不是评级驱动;硬上限规则凌驾于叙事质量之上。完整评分卡：`reference/judgment-rubric.md`。

主题跑收尾产出确定性逐票报告，外加 `RANKING.md`（漏斗计数、淘汰原因、数据盲区）。

### 架构

```
取数层（确定性 Python，只摆数据，永不做投资判断）
  tools/_common.py       — 配置、EDGAR session、per-tool sleep + http_get 重试退避、批次路由
  tools/new_run.py       — 开时间戳运行批次 + _run.json manifest
  tools/discover.py      — EDGAR FTS 枚举 + SIC 反向召回 + 市值 fallback
  tools/filter_by_sic.py — 门 1：SIC 粗排除 + SIC 反向召回底
  tools/cheap_pass.py    — 机械避雷硬红线（含集中度）
  tools/deepdive_data.py — XBRL + Form 4 + 货架状态 + 数据完整性守卫 + 二次源校验
  tools/valuation.py     — 反向 DCF / NAV / EV-EBITDA + buy_eligible 机械门
  tools/discover_events.py — 事件驱动发现（分拆 / 内部人集群）
  tools/finalize_run.py  — 确定性收尾（报告 + verdict + RANKING）
  tools/make_report.py   — 确定性报告脚手架 + 数据质量信任 banner
  tools/rank.py          — 确定性评分与排序
  tools/track_forward.py — verdict 日志、对 IWM Brier、de-risk 指标、recall@gold
  tools/run_theme.py     — 主题端到端驱动

诊断侧信道（防火墙隔离——只记录，永不驱动 BUY）
  tools/signals.py       — 价格背离（P16）+ 持仓（P17）；度量扩散立论

判断层（LLM，只读 JSON 做判断，永不计算财务数据）
  SKILL.md         — 编排 + 世界观 + 硬规则
  reference/*.md   — 方法论不变量（单一真相源）
  workflows/theme-fit-gate.js  — 可选：门 2 并行加速
  workflows/deepdive-fanout.js — 可选：尽调并行加速
```

**两条硬边界。**（1）`tools/*.py` 只出数、不做投资判断；判断层只读 JSON、不算财务。（2）诊断 `signals` 层被防火墙隔离——`valuation.py` / `buy_eligible` / 买入触发器对任何 signal **零引用**（加/不加 signals,buy_eligible 字节相同）。取数/判断分工经两轮生产 bug 验证(bug 全在取数层,被边界拦住);signals 防火墙每轮 grep 校验。

---

## 局限

**依赖。** 无专有依赖，核心数据层无需 API key。

| 包 | 许可 | 用途 |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | EDGAR FTS、XBRL 解析、Form 4 检索 |
| yfinance | Apache 2.0 | 市值/股价便利层 |
| pandas | BSD | 数据处理 |
| requests | Apache 2.0 | 带速率纪律的 HTTP |

**market-intel（可选只读复用）：** 若已安装 `market-intel` skill，判断层会读取其源目录来路由定性检索（X 舆情、行业新闻、竞品网络存在感）到最优 MCP 工具。market-intel 不会在运行时被当作 skill 调用——只读取 catalog 作为文档。完整的防递归设计见 `reference/data-sources.md §market-intel`。

**openinsider 脆弱性：** 默认 `insider_source` 配置使用 `openinsider.com` 解析 Form 4 买卖方向。该第三方服务无明确的自动访问条款。工具在 openinsider 不可用时自动回退到直接 EDGAR Form 4 解析，并在报告中标注数据来源。如需从一开始就去除 openinsider 依赖，可设 `"insider_source": "edgar"`——但**注意：此模式为路线图存根，尚未实现**（设置后返回 `available: false`；已测试的默认为 openinsider）。详见 `reference/data-sources.md`。

**workflow .js 文件为可选项：** `workflows/theme-fit-gate.js` 和 `workflows/deepdive-fanout.js` 在 Claude Code 会话中有 Workflow 工具时可加速并行步骤。它们不是必要依赖——`SKILL.md` 中的自然语言编排是主路径，任意 Claude Code 会话均可运行。

**X 舆情路由：** 需要某只票的 X/Twitter 舆情时，若已通过 market-intel 配置文件配置了 twitterapi.io key，则走 resale 路由（供应商账号池+代理，用户账号零风险）；不可用时回退到搜索引擎索引 X 内容。永久排除用户自己账号的登录路由——存在账号封禁风险。

---

## 语言

English（[`README.md`](README.md)，权威版本）· 中文（`README_CN.md`）

---

## 路线图 · 贡献 · 许可

见 [ROADMAP.md](ROADMAP.md) · [PHILOSOPHY.md](PHILOSOPHY.md) · [CHANGELOG.md](CHANGELOG.md) · [LICENSE](LICENSE)（MIT）。

贡献：架构不变量见 `docs/` 设计规范。核心不变量是数据/判断边界：数据层（`tools/*.py`）永不产生投资判断；判断层永不计算财务。任何模糊这条边界的改动，需在 [PHILOSOPHY.md](PHILOSOPHY.md) 给出显式理由。
