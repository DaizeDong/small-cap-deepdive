# Runbook: Single-Ticker Deep-Dive

> Entry mode 2, `ticker <代码> [--theme X]`. Use when you have a specific company and want
> a rigorous, falsifiable deep-dive report without running a full theme screen.

This is the highest-frequency entry point. You know the ticker; you want to know if it is worth
owning. The tool mechanically eliminates it if it fails the kill-flags, and gives you a
scored report if it survives.

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

Set `"sec_user_agent"` to `"AcmeCorp user1@example.com"` in that file (the private config dir,
never the repo, your identity is yours, and an in-tree copy is a leak waiting to be committed).
EDGAR blocks requests with a missing or obviously fake User-Agent.

Keep config, observations and reports committed and pushed in this PRIVATE companion. The identity shown here is synthetic; replace it privately before live SEC use. Run `python scripts/verify_config.py --json` before starting.

Then open a run batch (start of every run) so outputs stay grouped and version-comparable:

```bash
SMALLCAP_RUN="$(python tools/new_run.py --label "Synthetic research")" || exit 1
export SMALLCAP_RUN
REPORTS_ROOT="$(python -c 'import sys; sys.path.insert(0, "tools"); from _common import reports_dir; print(reports_dir())')" || exit 1
export REPORTS_ROOT
```

Outputs land in the absolute PRIVATE `$REPORTS_ROOT` directory with a `_run.json` manifest. Before handing paths to another agent, expand `REPORTS_ROOT` to its actual value. With no active run, the runtime uses the unbatched private reports root.

---

## Step 1, Mechanical De-Risk First

Always run `cheap_pass` before any qualitative work. If the company fails a hard kill-flag,
stop, do not spend judgment budget on a structurally disqualified candidate.

```bash
python tools/cheap_pass.py --universe "<validated-universe.csv>"
```

The cheap_pass selftest includes live EDGAR acquisition and issuer-based checks.
It requires network access and an initialized private configuration; it is not an offline
synthetic check. Its output covers only the requests and assertions actually completed:

```bash
python tools/cheap_pass.py --selftest
```

Read the returned source-completion status, filing identity and individual disclosure
findings before interpreting admission. A clean observed filing and an unavailable filing are
different outcomes. The presence of a kill flag must be traced to the current source evidence;
an empty result or transport failure cannot establish that no flag exists.

**If eliminated:** Report the kill-flag and stop. The hard-rule is not an invitation to
argue, it is a floor. The outcome base rate for companies with an auditor going-concern
opinion is unknown here. Any empirical estimate requires a traceable study with a matching
population, outcome definition and observation window; missing evidence does not relax the
kill-flag exclusion policy.

**Token magnitude:** Negligible, deterministic EDGAR filing fetch and parse, no LLM calls.
Runtime: 30 to 90 seconds.

---

## Step 2, Standalone Data Pull

Supply both the ticker and the verified CIK. This synthetic identity illustrates the CLI:

```bash
python tools/deepdive_data.py --ticker SYNTA --cik 0000000123
```

Use the artifact path printed by the command. Standalone input has no bound upstream
candidate receipt, so the artifact retains `unbound_single_input` and may exit 2 even when
individual acquisitions succeed. It is a diagnostic data pull, not proof of a completed
theme pipeline. Keep source failures and missing financial or filing inputs visible.

For a single company that already belongs to a validated Gate-2 survivor artifact, use
`--candidates <survivors.json>` and the prepare/host/ingest sequence in
[theme-run.md](theme-run.md). A one-row raw JSON array is not a Workflow request.

---

## Step 3, Judgment Pass

Give the agent the verified issuer identity, selected artifact path and optional theme
context. Require it to read `reference/cognitive-priors.md`, identify any applicable evidence,
perform a disconfirmation search and report filing dates and missing sources.

Apply the seven-dimension scorecard and the rating rules to that bound evidence. The report
must contain dimension scores, evidence tiers, kill-flag details, falsifiable counterarguments
and unresolved gaps. Save the filled report in the configured PRIVATE companion.

**Optional Workflow host:** use a bound survivor artifact to prepare
`deepdive_request.json` with `--prepare-fanout` and an explicit `--verdict-date`.
Pass that request to the configured host, save its full response, then validate it with
`--fanout-request` and `--fanout-result`. See [theme-run.md](theme-run.md) for the exact
commands. The workflow depends on host-provided functions; a direct Node invocation or
raw candidate array does not implement the contract. Host execution remains unverified
until an actual result and its ingestion receipt have been checked.

**Token magnitude:** ~8k to 15k tokens per company.

Cost: <$0.02 per company at Sonnet pricing.

---

## Step 4, Reading the Output

Use the report structure in `reference/judgment-rubric.md`. Every filled report is private
DATA. The public runbook describes the required fields without a completed company report.

| Section | Required content |
|---|---|
| Identity and decision | Ticker, timestamp, rating, confidence and holding horizon |
| Thesis and reference class | Falsifiable thesis; matching base-rate evidence or an explicit unknown |
| Scorecard | Seven dimension scores with evidence tiers and concise cited reasons |
| Bull and bear cases | Claims, disconfirming observations and conditions that would change each claim |
| Pre-mortem | Plausible failure mechanism with stated assumptions |
| Kill flags | Each flag, current source evidence and unresolved review items |
| Valuation | Active basis, intrinsic band, margin-of-safety denominator and missing evidence |
| Monitoring | Dated events and measurable conditions to revisit the thesis |
| Coverage gaps | Unavailable sources, unsupported fields and incomplete observation windows |

Do not infer that an absent flag means a source was successfully examined. Read the source
completion and review evidence alongside the rating.

---

## Interpreting the Score

**Score 4 to 5:** No structural red flags. Real business, real cash flow, insider alignment.
This is what the tool exists to surface, a candidate worth actual human research time.

**Score 3:** Borderline. One dimension is weak. Read the specific dimension note to decide
if the weakness is temporary or structural. Do not infer "buy" from a 3.0 score.

**Score 1 to 2:** Hard-rule ceiling in effect. A specific structural problem is capping the
score. The report names it. Do not invest without independently resolving the named issue.

**0 or eliminated:** The kill-flag fired in Step 1. Stop. Do not re-examine.

---

## Common Patterns

**"The financials look great but the score is a 2"**

Check Dimension 4 (management) and the kill-flag detail. A heavy net-sell pattern
concurrent with secondary offerings is a hard cap, regardless of reported financial quality.

**"The company just reported great earnings but cheap_pass flagged going concern"**

Read the selected annual filing and the parser's evidence, polarity and status. Annual
retrieval tries 10-K, then 20-F, then 40-F, excluding amendments. A connected current
affirmative assertion can set the flag; negation, remediation, historical or ambiguous
language require their own interpretation. Missing filing text or unresolved evidence
remains unknown and cannot establish a clear result. Check source completion before judgment.

---

## Troubleshooting

**EDGAR 403:** Set `sec_user_agent` to `"AcmeCorp user1@example.com"` in `~/.small-cap-deepdive-config/config.json` (the private config dir, never the repo).

**CIK unresolved:** Verify the ticker and CIK against a current issuer-identity source and
retain the returned identity evidence. An unresolved or conflicting mapping remains unavailable.

**OpenInsider timeout:** The observation remains unavailable with a reason. Automatic
EDGAR Form 4 parsing is not implemented; the EDGAR mode is an unavailable stub. Any direct
filing verification is separate work and must retain its own evidence.
