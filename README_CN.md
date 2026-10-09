# small-cap-deepdive

基于 SEC 申报研究美国小盘股和微盘股：按主题或事件发现候选，筛查财务及披露风险，生成供人工尽调使用的公司报告。

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![避雷扫描器](https://img.shields.io/badge/%E9%81%BF%E9%9B%B7-%E6%89%AB%E6%8F%8F%E5%99%A8-green?style=flat)](#设计理念)
[![依赖](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![语言](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-EN%20%2F%20CN-blue?style=flat)](#语言)
[![Roadmap](https://img.shields.io/badge/Roadmap-v0.3.3-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## 设计理念

缺少分析师覆盖本身不能证明价格被低估。这里的研究假设是：基本面变化可能尚未充分反映在价格中。
工具对每个已纳入候选采用相同的申报检查和反方检索流程，使筛选有可追溯的证据。
理论依据和实证文献说明见[认知先验](reference/cognitive-priors.md)。

保守规则也有代价：经营正常的公司可能因证据缺失或口径不兼容而无法获得评级。
计算前必须核对日期、财务期间、单位和来源。排名靠前表示值得人工尽调，投资优势仍需单独验证。
没有候选达到 4 分时，应同时报告已观察的候选范围、未完成工作和覆盖限制；空名单不能证明
该主题没有合适公司或投资机会，也不能证明市场有效。

[PHILOSOPHY.md](PHILOSOPHY.md) 说明四项设计原则：分离取数和判断、保留确定性的申报处理工具、
一致执行筛选规则，以及由参考文档统一维护方法规范。

---

## 它是什么（不是什么）

入口包括主题、公司代码、事件路线和既有评分报告。主要步骤如下：

| 步骤 | 行为与详细规范 |
|---|---|
| 创建批次 | `new_run.py` 在 PRIVATE 伴生仓创建报告批次；`_run.json` 记录源码版本和估值配置快照。见[快速开始](#快速开始)。 |
| 主题发现 | EDGAR FTS 可按需合并 `discover.py --sic-reverse` 结果；无法定价的候选保留为 `band="unknown"`。检索范围和完成状态见[发现流程](reference/discovery-engine.md)。 |
| 机械筛查 | `cheap_pass.py` 检查持续经营、死亡螺旋可转债、内控重大缺陷和集中度；按 `rejected` 判定准入。单一标记可能不淘汰公司，但仍会阻止 BUY。 |
| 主题复核 | 仅主题入口依次执行 SIC 复核和绑定请求的 LLM 业务复核。SIC 两层均保留候选；只有 `misrecall` 因主题不符而淘汰。 |
| 财务取数 | `deepdive_data.py` 获取 XBRL、内部人交易及披露事件，核对债务、实体、期间和来源。见[机械检查](reference/mechanical-checks.md)及[数据来源](reference/data-sources.md)。 |
| 估值 | 按证据选择反向 DCF、EV/EBITDA、周期标准化或 NAV。BUY 要求 `mos_basis∈{fcf_cap,nav}`、有效安全边际 ≥ 30%、`buy_eligible == true`、零 kill-flag 且无 T3 核心论据。催化剂免除 MoS 门槛的规则仍冻结。见[估值规范](reference/valuation.md)。 |
| 判断和报告 | [评分规范](reference/judgment-rubric.md) 要求基准概率、反方检索、证据分级和七维评分。报告保留数据质量与未完成工作，可按需排序。 |
| 前向跟踪 | `track_forward.py` 在 PRIVATE `data/metrics/` 记录判断，到期对 IWM 计算 Brier 和风险筛查指标。见[跟踪规范](reference/track-forward.md)。 |
| 诊断信号 | `signals.py` 记录价格背离和持仓信息，供后续校准；诊断字段不影响 BUY 资格。见[数据来源](reference/data-sources.md)。 |

工具面向缺少分析师覆盖的公司，不提供因子或量化选股、交易执行、组合管理、大盘股覆盖或自动投资决策。
申报数据并非实时数据，典型延迟为 1 到 4 天；行情等辅助来源各有可用性限制。
报告供人工判断使用。历史研究脚本见[文档索引](docs/README.md)，其存在不代表已验证因子策略。

### 证据与评估

真实运行记录和研究报告保存在已初始化、纳入版本管理的 PRIVATE 伴生仓。
公开工具只提供通用方法和生成的合成样例。[证据状态](docs/evidence-status.md)
区分源码审查、合成检查、当前执行和历史研究各自能说明什么。

CORE-4 是四个二元困境指标之和，取值为 0 到 4。固定分数门槛、逐年排序和
训练集/测试集逻辑回归属于不同的评估方法。绩效结论需要有日期的资格证据、
完整范围和数据来源，以及重新执行的评估。没有 BUY 输出不能证明市场有效或没有投资机会。

---

## 研究流程

<p align="center">
  <a href="docs/diagrams/workflow-cn.png">
    <img width="760" src="docs/diagrams/workflow-cn.png" alt="研究流程：筛查主题、公司或事件候选；主题专用检查后进入尽调；报告直接交付或按需排序。">
  </a>
</p>

[DOT 源码](docs/diagrams/workflow-cn.dot) · [绘图脚本](docs/diagrams/render.py)

只有 `theme` 经过 SIC 与主题契合度复核；SIC 的 `keep`、`review` 两层均保留候选。
主题契合度只淘汰 `misrecall`。
机械筛查以 `cheap_pass` 返回的 `rejected` 为准：单一风险标记不必然淘汰公司。

单公司报告可直接交付；排序按需进行，也可读取既有评级报告。两种输出都供人工尽调使用。

尽调仍须满足相应的准入、市值分层和步骤完成检查；未完成工作会保留在报告中。
诊断 `signals` 仅供研究参考，不设置 BUY 资格，也不执行交易。
详细步骤见[入口流程](SKILL.md#four-entry-workflows)。

## 安装

```
/plugin install github:DaizeDong/small-cap-deepdive
```

或手动克隆：

```bash
git clone --recurse-submodules https://github.com/DaizeDong/small-cap-deepdive.git ~/.claude/plugins/small-cap-deepdive
```

然后安装取数层依赖并一次性配置：

```bash
cd ~/.claude/plugins/small-cap-deepdive
pip install -r tools/requirements.txt
gh repo create small-cap-deepdive-config --private --add-readme
gh repo clone small-cap-deepdive-config ~/.small-cap-deepdive-config
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
```

打开 `~/.small-cap-deepdive-config/config.json`，将 `"sec_user_agent"` 设为你的真实姓名和邮箱：

```json
"sec_user_agent": "AcmeCorp user1@example.com"
```

这是唯一必填字段。EDGAR 要求每次请求带有效 `User-Agent` 头（SEC 政策），缺失或使用假值会导致 `efts.sec.gov` 返回 403。

注意 config 位于**仓库之外**，这是刻意的：`sec_user_agent` 是你的真实姓名和邮箱，而这是一个公开仓库。
仓内已不存在任何 config 位置，工具也会拒绝在仓内创建。

若不走 `/plugin install`，也可建立 junction/symlink 部署为 Claude Code skill：

```powershell
# 在克隆目录内运行，普通用户 PowerShell 即可，无需管理员权限。
$repoRoot = (Resolve-Path -LiteralPath (git rev-parse --show-toplevel)).Path
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'SKILL.md'))) { throw 'SKILL.md missing' }
$skillAlias = Join-Path $env:USERPROFILE '.claude/skills/small-cap-deepdive'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $skillAlias) | Out-Null
New-Item -ItemType Junction -Path $skillAlias -Target $repoRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $skillAlias 'SKILL.md'))) { throw 'Skill alias failed' }
```

```bash
# macOS / Linux，在克隆目录内运行
repo_root="$(git rev-parse --show-toplevel)"
test -f "$repo_root/SKILL.md" || exit 1
mkdir -p "$HOME/.claude/skills"
skill_alias="$HOME/.claude/skills/small-cap-deepdive"
ln -s "$repo_root" "$skill_alias"
test -f "$skill_alias/SKILL.md" || exit 1
```

---

## 配置

[CONFIG.md](CONFIG.md) 统一定义字段、DATA/CONFIG 选择顺序、目标验证、配置切换和保留规则。
配置、报告和跟踪共用已核验的 PRIVATE 伴生仓。每套备用配置必须选择独立 Git 工作树的根目录，
不接受嵌套 profile；缺少配置或无法证明私有可见性时停止写入。

初始化后，在私有配置中填写 `sec_user_agent`，再运行：

```bash
python scripts/verify_config.py --json
```

身份为空或仍为示例时返回 NOT READY。doctor 检查本地配置、目标证明和依赖；SEC、行情与模型
服务是否可用需要另行实测。配置和运行 DATA 在 PRIVATE 伴生仓提交并推送。超过 64 MiB 的存储
检查阈值时须审查文件依赖，不能为达标删除受保护记录。详见[保留规则](CONFIG.md#companion-storage-and-retention)。

---

## 快速开始

先用 `python tools/new_run.py --label <名称> [--input-hash <SHA256>]` 创建批次，将输出的名称设为 `SMALLCAP_RUN`。每次调用都在私有报告根目录下创建独立目录，名称包含日期、编码后的标签和随机标识；同名调用也不会覆盖旧批次。未设置 `SMALLCAP_RUN` 时，报告直接写入该根目录。

恢复批次需显式传入 `--resume <RUN_ID> --input-hash <SHA256>`。工具会先核对清单中的输入哈希、目录名称和报告根目录；不匹配时退出，不改动已有文件。新批次未传哈希时，会对标签、备注和非敏感估值配置快照的规范 JSON 计算 SHA256，具体格式见 `tools/new_run.py`。

输出目标和 SSH 远端验证见 [CONFIG.md](CONFIG.md#secrets--pii-mode-b-e6)。

共有四种入口模式。

### 1. 主题跑，全库筛选

获取某主题的小盘纯玩家排名：

```
/small-cap-deepdive theme "铁路车厢租赁"
/small-cap-deepdive theme "railcar leasing"
```

完整步骤：**[runbooks/theme-run.md](runbooks/theme-run.md)**

预计 token 预算：~30 万 token，约 $0.30，小众主题约 1 to 3 小时。

### 2. 单只票深度尽调

对已知公司做严格的可证伪报告：

```
/small-cap-deepdive ticker <ticker>
/small-cap-deepdive ticker <ticker> --theme "合规行业 SaaS"
```

完整步骤：**[runbooks/single-deepdive.md](runbooks/single-deepdive.md)**

预计 token 预算：~1 to 1.5 万 token，<$0.02。

### 3. 批量重排已有评分

不重跑发现和尽调，重新排序既有评分报告：

```bash
python tools/rank.py --output RANKING-rerun-01.md
python tools/rank.py --slug railcar --output RANKING-railcar-rerun-01.md
python tools/rank.py --input "<private-companion>/reports/smallcap/<run>" --output RANKING-rerun-02.md
```

每次重排都要选一个尚不存在的输出文件名；工具会保留已有的排序文件。

默认读取已配置 PRIVATE 伴生仓中当前批次的已有报告；重排不会创建研究批次。
显式输入须指向已有报告目录的绝对路径。写入前按
[CONFIG.md](CONFIG.md#secrets--pii-mode-b-e6) 检查本地 PRIVATE 可见性记录，拒绝文件系统别名。

完整步骤：**[runbooks/batch-rank.md](runbooks/batch-rank.md)**

预计 token 预算：零，纯确定性计算，无 LLM 调用。

### 4. 事件驱动发现，分拆或内部人集群

用结构性催化剂（强制交易）而非主题关键词来发现被误定价的小盘股：

```bash
# 枚举近期分拆注册（Form 10-12B）
python tools/discover_events.py --spinoffs

# 枚举集群公开市场内部人买入（openinsider）
python tools/discover_events.py --insider-clusters
```

这些路线按强制交易或内部人信心事件发现候选。机制和来源限制见
[事件发现规范](reference/event-driven.md)。事件入口跳过主题契合度检查，但仍须验证来源并执行
`cheap_pass.py --universe <candidates_event_*.json>`。尚无 ticker 的分拆候选通过 CIK 处理，
保留在 `band="unknown"` 队列。

预计 token 预算：含全量尽调约 30 万 token。

---

## 如何触发

任意模式用 slash 命令，例如 `/small-cap-deepdive theme "铁路车厢租赁"` 或
`/small-cap-deepdive ticker <ticker>`。或在任何 Claude Code 会话里用自然语言触发：

```
对"铁路车厢租赁"主题跑 small-cap-deepdive
用 small-cap-deepdive 把 <ticker> 当小盘股深挖
对"工业水处理"主题筛 SEC 小盘股全库
```

skill 触发于小盘/微盘价值研究、主题选股、单公司深度尽调。它**不**触发于大盘/卖方覆盖、
多因子/量化选股、交易信号或执行。

---

## 示例输出

每个候选机械化评级。评分速查：

| 分数 | 含义 | 行动 |
|---|---|---|
| 4 to 5 | 通过全部门，真实主题敞口，无结构性红线 | 值得完整人工尽调 |
| 3 | 边界，某一维度偏弱 | 读维度详情后再决定 |
| 1 to 2 | 硬上限规则生效 | 存在已命名的结构性问题；在解决前不应投资 |
| 已淘汰 | cheap_pass 返回 `rejected=true` | 停止，不必重新审查 |

评级是机械的：`rating = f(MoS / NAV-MoS, kill-flags, 硬上限, buy_eligible)`。7 维评分卡是诊断性 `/35` 汇总（无隐藏权重）,不是评级驱动；硬上限规则凌驾于叙事质量之上。完整评分卡：`reference/judgment-rubric.md`。

主题跑收尾产出确定性逐票报告，外加 `RANKING.md`（漏斗计数、淘汰原因、数据盲区）。

### 架构

```
取数层（确定性 Python，只摆数据，永不做投资判断）
  tools/_common.py       — 配置、EDGAR session、per-tool sleep + http_get 重试退避、批次路由
  tools/new_run.py       — 开时间戳运行批次 + _run.json manifest
  tools/discover.py      — EDGAR FTS 枚举 + SIC 反向召回 + 市值 fallback
  tools/filter_by_sic.py — 门 1：SIC 复核层 + SIC 反向召回底（库模块；CLI 只有 --selftest）
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
  workflows/theme-fit-gate.js  — 主题门 2 必须使用的 host 工作流
  workflows/deepdive-fanout.js — 主题运行必需，单票尽调可选
```

确定性取数层提供财务数据和资格检查；判断层读取这些结果并应用评分规范，不自行计算财务。
诊断 `signals` 不进入 `valuation.py`、`buy_eligible` 或 BUY 触发条件。
设计依据和历史开发背景见 [PHILOSOPHY.md](PHILOSOPHY.md)。

---

## 局限

**依赖。** 无专有依赖，核心数据层无需 API key。

| 包 | 许可 | 用途 |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | EDGAR FTS、XBRL 解析、Form 4 检索 |
| yfinance | Apache 2.0 | 市值/股价便利层 |
| pandas | BSD | 数据处理 |
| requests | Apache 2.0 | 带速率纪律的 HTTP |

**market-intel（可选只读复用）：** 若已安装 `market-intel` skill，判断层会读取其源目录来路由定性检索（X 舆情、行业新闻、竞品网络存在感）到最优 MCP 工具。market-intel 不会在运行时被当作 skill 调用，只读取 catalog 作为文档。完整的防递归设计见 `reference/data-sources.md §market-intel`。

**OpenInsider 可用性：** 默认路径解析 OpenInsider 提供的 Form 4 买卖信息。获取或解析失败时，输出保留不可用状态；当前没有自动切换到 EDGAR Form 4 的实现。配置 `"insider_source": "edgar"` 选择的是尚未实现的路径，会返回 `available: false`。报告不能把不可用的数据写成零交易。详见 `reference/data-sources.md`。

**Workflow host 要求：** `workflows/theme-fit-gate.js` 和 `workflows/deepdive-fanout.js` 需要通过已配置的 Workflow host 处理绑定请求。自然语言编排可以准备请求，但只有导入对应的 host 结果后，该阶段才算完成。这两个 JavaScript 文件不能直接用 Node 运行。

**X 舆情路由：** 需要某只票的 X/Twitter 舆情时，若已通过 market-intel 配置文件配置了 twitterapi.io key，则使用该 resale API；不可用时回退到搜索引擎索引 X 内容。永久排除用户自己账号的登录路由，存在账号封禁风险。

---

## 语言

English（[`README.md`](README.md)，权威版本）· 中文（`README_CN.md`）

---

## 路线图 · 贡献 · 许可

见 [ROADMAP.md](ROADMAP.md) · [PHILOSOPHY.md](PHILOSOPHY.md) · [CHANGELOG.md](CHANGELOG.md) · [LICENSE](LICENSE)（MIT）。

贡献：架构约束见 [PHILOSOPHY.md](PHILOSOPHY.md) 和[文档索引](docs/README.md)。核心不变量是数据/判断边界：数据层（`tools/*.py`）永不产生投资判断；判断层永不计算财务。任何模糊这条边界的改动，需在 [PHILOSOPHY.md](PHILOSOPHY.md) 给出显式理由。
