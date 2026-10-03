# Runbook: Theme Run

> Entry mode 1, `theme <主题>`. Use when you have an investment theme and want a ranked
> shortlist of small-cap pure-plays from the full SEC-filing universe.

---

## Prerequisites

Complete this once before any run:

```bash
pip install -r tools/requirements.txt
gh repo create small-cap-deepdive-config --private
gh repo clone small-cap-deepdive-config "$HOME/.small-cap-deepdive-config"
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
```

Open `~/.small-cap-deepdive-config/config.json` (the private config dir, never the repo) and set
`"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "AcmeCorp user1@example.com"
```

EDGAR requires a valid `User-Agent` header on every request. Omission causes 403 errors.
This is the only required field, all other keys have defaults.

---

Keep config, observations and reports committed and pushed in this PRIVATE companion. The identity shown here is synthetic; replace it privately before live SEC use. Run `python scripts/verify_config.py --json` before starting.

## Open a run batch (do this at the start of every run)

```bash
SMALLCAP_RUN="$(python tools/new_run.py --label "Synthetic research")" || exit 1
export SMALLCAP_RUN
REPORTS_ROOT="$(python -c 'import sys; sys.path.insert(0, "tools"); from _common import reports_dir; print(reports_dir())')" || exit 1
export REPORTS_ROOT
```

All outputs land in the absolute PRIVATE `$REPORTS_ROOT` directory with a `_run.json` manifest. Before handing paths to another agent, expand `REPORTS_ROOT` to its actual value. With no active run, the runtime uses the unbatched private reports root.

---

## Recommended: One-Command Theme Run

The mechanical pipeline runs FTS discovery → cheap-pass → SIC review. `run_theme.py`
does not request `--sic-reverse`. For a configured SIC union, run Steps 1 to 3 separately
and add `--sic-reverse` to the `discover.py` command in Step 1.

```bash
python tools/run_theme.py --theme "railcar,railcar leasing" --slug railcar
```

This runs Steps 1 to 3 below automatically and prints the "Next steps" handoff.
Use `--micro` flag to apply the micro-cap ($500M) ceiling instead of the default small-cap ($2B).

---

## Step 1, Universe Enumeration

```bash
python tools/discover.py --theme "railcar leasing" --out-slug railcar
```

Output: `${REPORTS_ROOT}/universe_railcar_<date>.csv`

Expected output:

```
[1/3] SEC FTS 召回 (主题: ['railcar leasing'], forms: 10-K,10-Q)...
  'railcar leasing': 214 家
  去重后 187 家
[2/3] yfinance 补市值+流动性...
[3/3] 过滤去噪...

=== 发现结果 ===
总召回 187 家 | 小盘候选 42 家 (市值<$2.0B, 已剔SPAC/低流动性)
...
清单: ${REPORTS_ROOT}/universe_railcar_<date>.csv
```

**What to expect:** Over-recall is intentional. 150 to 300 candidates for a niche theme;
500+ for a broad theme like "AI infrastructure". The precision gate below clears the field.

**Token magnitude:** Negligible, pure HTTP to `efts.sec.gov`, no LLM calls.

**If zero hits:** FTS keyword is too restrictive. Try shorter terms (`railcar` instead of
`railcar leasing`), or two separate runs on each word, then union the results.

---

## Step 2, Mechanical De-Risk (cheap_pass)

```bash
python tools/cheap_pass.py --universe "${REPORTS_ROOT}/universe_railcar_<date>.csv" \
  --out-slug railcar
```

Output: `${REPORTS_ROOT}/cheappass_railcar_<date>.csv`

Expected output:

```
对 42 家小盘候选做机械体检...
...
=== Cheap pass 结果 ===
体检 42 家 | 淘汰 8 家 | 幸存 34 家
...
清单: ${REPORTS_ROOT}/cheappass_railcar_<date>.csv
```

**What it checks (hard kill-flags):**

| Flag | Trigger | Action |
|---|---|---|
| Going concern | Connected current affirmative substantial-doubt / going-concern assertion in the selected annual filing | Eliminate when the contextual flag is true |
| Death spiral | Variable-rate convertible in most recent filings | Eliminate if killflag_count >= 2; a lone flag blocks BUY but remains for review |
| Material weakness | Current unresolved ICFR material-weakness assertion | Eliminate if killflag_count >= 2 |

Annual filing retrieval tries 10-K, then 20-F, then 40-F, excluding amendments. Bare
phrase co-occurrence is insufficient: inspect the parser's negated, remediated, historical,
conditional and ambiguous states. Missing sources or unresolved evidence remain unknown;
verify filing identity and source completion before treating a screen as complete.

**Do not deepdive eliminated candidates.** The kill-flag verdict stands.

**Token magnitude:** Negligible for deterministic guards.

---

## Step 3, Gate 1: SIC Coarse Review

After cheap-pass, Gate 1 is applied automatically by `run_theme.py` (via `filter_by_sic.sic_classify`).
`filter_by_sic.py` is a library module, not a standalone pipeline step; its only CLI is
`--selftest`.

To verify the SIC logic:

```bash
python tools/filter_by_sic.py --selftest
```

**What it does:** tags each survivor with a `sic_tier`. **It drops nothing.** A SIC in
`sic_hard_exclude` yields `sic_tier="review"`, and a `review` company still goes to Gate 2, the
tier is a hint about how suspicious the SIC is, not a verdict. Everything else yields
`sic_tier="keep"`. Companies with no SIC on file are kept. The third value, `drop`, is reserved and
never returned, so Gate 2 is the only place a company leaves the funnel for theme-fit reasons.

**Token magnitude:** Negligible, deterministic lookup against SEC company data.

---

## Step 4, Gate 2: Bound Theme-Fit Request

Use the `gate2_request.json` emitted by `run_theme.py`. For an existing candidate artifact
that has no request yet, prepare it once:

```bash
python tools/run_theme.py --prepare-gate2 "${REPORTS_ROOT}/candidates_railcar.json"
```

Pass the parsed request JSON as `args` to `workflows/theme-fit-gate.js` through the configured
Workflow host. The host supplies `agent`, `parallel` and `phase` and uses the installed
`llmcall` routing. This file is a host workflow, so a direct Node invocation is not a valid
entry point. Preserve the host's complete result as `gate2_host_result.json` in the private run.

```bash
python tools/run_theme.py --gate2-request "${REPORTS_ROOT}/gate2_request.json" --gate2-result "${REPORTS_ROOT}/gate2_host_result.json"
```

Ingestion validates the request binding and every candidate identity, then writes
`gate2_results.json`, `candidates_gate2_survivors.json` and their stage receipts. Retain
those files together. A hand-written classification list cannot replace this contract.
An unavailable host or incomplete result remains an unfinished stage; record that boundary.

## Step 5, Pull Data for the Validated Survivors

```bash
python tools/deepdive_data.py --candidates "${REPORTS_ROOT}/candidates_gate2_survivors.json"
```

Use the ingested survivor artifact, including its receipt. The original pre-Gate-2 candidate
list cannot prove theme-fit completion. Keep every per-candidate outcome and the batch
data-results artifact; inspect the reported completion status before claiming coverage.

## Step 6, Bound Deep-Dive Judgment

Prepare the request from the same survivor artifact, with an explicit decision date:

```bash
python tools/deepdive_data.py --prepare-fanout "${REPORTS_ROOT}/candidates_gate2_survivors.json" --verdict-date 2000-01-01
```

The date above is synthetic; supply the intended decision date for a real private run.
Pass the resulting `deepdive_request.json` as `args` to `workflows/deepdive-fanout.js`
through the configured Workflow host. The request binds candidate and data artifacts.
The host's per-candidate valuation call is
`python tools/deepdive_data.py --valuation-request <original_request_json> --input-index <original_index>`.
Preserve the original index and the independent artifact at the request's bound `valuation_path`.
The sealed data input stays unchanged; do not use `valuation.py --json` to merge a valuation into it.

Save the complete host response as `deepdive_host_result.json`, then ingest it:

```bash
python tools/deepdive_data.py --fanout-request "${REPORTS_ROOT}/deepdive_request.json" --fanout-result "${REPORTS_ROOT}/deepdive_host_result.json"
```

Ingestion validates identities, valuation evidence and report fields before writing reports
and `deepdive_fanout_results.json` with their receipts. New work must use fresh output paths.
Do not replace a partial status with a hand-written success receipt. The documented
request/response contract is statically checked; it does not establish a successful host run.

---

## Step 7, Rank

```bash
python tools/rank.py --slug railcar
```

Expected output: `${REPORTS_ROOT}/RANKING.md`

**Token magnitude:** Negligible, deterministic sort + Markdown table generation.

---

## Total Run Summary

| Phase | Time | Tokens | Cost (est.) |
|---|---|---|---|
| discover + SIC filter | 3 to 8 min | ~0 LLM | $0.00 |
| theme-fit gate (Gate 2) | 15 to 40 min | ~40k | ~$0.05 |
| cheap_pass (deterministic) | 8 to 25 min | ~0 LLM | $0.00 |
| deepdive_data pull | 10 to 30 min | ~0 LLM | $0.00 |
| deep-dive judgment | 20 to 60 min | ~200k | ~$0.20 |
| rank | <1 min | ~0 LLM | $0.00 |
| **Total** | **~1 to 3 hr** | **~240k** | **~$0.25** |

Costs shown at Claude Sonnet input-token pricing. Actual cost depends on candidate count
and filing length. Large themes (500+ raw candidates) scale linearly with Gate 2 + judgment.

---

## Interpreting the Output

- **Score 4 to 5:** Survived all gates, real theme exposure, no structural red flags. Merits full
  human diligence, this is the output the tool is designed to surface.
- **Score 3:** Borderline. Check dimension breakdown; often one weak dimension (e.g., insider
  selling) dragging an otherwise solid profile.
- **Score 1 to 2:** Hard-rule ceiling applied (dilution, weakness, weak fundamentals). Do not buy
  without understanding and explicitly accepting the specific flag.
- **An empty result is coverage-limited.** Zero score-4+ candidates describes the observed
  screen under its policy. Report retrieval gaps, missing work and abstentions. It does not
  establish that the theme has no clean beneficiaries or investment opportunities.

---

## Troubleshooting

**EDGAR 403 error:** `sec_user_agent` in `~/.small-cap-deepdive-config/config.json` (private config dir) is missing or malformed. Must be
`"Name email@domain.com"` format.

**Zero FTS hits:** Keyword too specific. Try the single most distinctive word of the theme.

**Gate 2 stalls:** LLM hitting rate limit or filing not available in EDGAR FTS. The workflow
runner retries with exponential backoff; natural-language path: skip that ticker and note in
coverage gaps.

**deepdive_data partial XBRL:** Common for micro-caps. The tool logs which concepts are missing;
judgment rubric Dimension 1 confidence auto-caps at 40% when revenue or OCF is unavailable.
