# Coverage Test — Insurance Brokers (Financials)

- **Slug**: `insurance-brokers`
- **Sector**: Financials
- **Keywords**: `insurance brokerage`, `benefits broker`
- **Skill version**: v0.3.0 (commit `f12fef5`)
- **Run batch**: `reports/smallcap/2026-06-21_cov-insurance-brokers/`
- **Date (time-locked)**: 2026-06-21
- **Code-path focus**: financial-SIC / fee-model guard
- **Headline result**: **0 BUYs** — and that is the *correct* outcome. This theme is a
  deliberate stress test of the financial-SIC firewall, which is designed to refuse the
  FCF-cap valuation model for commission/float businesses. Every true insurance broker is
  SIC 6411 (or an adjacent 60-67 financial code) and is therefore structurally routed away
  from a tradeable FCF-cap BUY by design.

> **Research output, not investment advice.** This is a landmine-scanner pass: its value here
> is in what it eliminates and in confirming the guards fire as specified, not in surfacing a buy.

---

## 1. Funnel

| Stage | Count | Note |
|---|---:|---|
| Raw universe (discover, FTS + mktcap filter) | 221 | SEC EDGAR full-text recall on the two keywords |
| Cheap-pass input (small-cap cap, top 100) | 100 | mktcap <= $2.0B band cut |
| Candidates after cheap-pass + SIC gate | 78 | health-check survivors; SIC-tier review=67, keep=11 |
| Deep band (band="deep") | 59 | the names that earned a full deep-dive slot |
| LLM theme-fit survivors (Gate 2) | 12 | I judged true membership from blurbs; 47 dropped as misrecall |
| Deep-dived (deepdive_data + valuation) | 12 | EVERY survivor — no sampling; 0 ERROR files |
| **Mechanical BUYs** | **0** | all 12 buy_eligible=false |
| **Clean BUYs (post-adversarial)** | **0** | n/a — nothing to verify |

**No recall floor for this theme.** Insurance-broker SIC 6411 is in `sic_hard_exclude`, NOT in
`THEME_SIC`, so discover ran FTS-only (no SIC reverse-recall union). This is intentional: the
financial sector is a coarse-exclude, and the LLM Gate-2 pass is what recovers the true members
from the FTS hits. There is also **no recall@gold gold list** for insurance-brokers (only
water-utilities / railcar-leasing / regional-gaming / deathcare have one), so recall@gold = **n/a**.

### Gate-2 theme-fit reasoning (the 59 -> 12 cut)

The deep band was dominated by **misrecalls** that an FTS keyword pass cannot avoid:
- **24x SIC-60 banks** (CBFV, OPBK, BRBS, GCBC, NFBK, UVSP, TMP, SBSI, FMBH, TFIN, SRCE, AMTB,
  EQBK, PBHC, ...) — they mention "insurance products" because they cross-sell agency services,
  but they are deposit-taking banks, not brokers. **Dropped.**
- **Underwriters/carriers** (JRVR, KINS, ROOT, HIPO, KFS — SIC 6331) — they *bear* risk; a broker
  *distributes* it. The theme is distribution, not underwriting. **Dropped.**
- **Lenders / asset managers / unrelated** (FINV, XYF, TREE-adjacent lenders, VINP, BBDC, KARO,
  CCS, GNE, IOTR, ZEPP, IDT, FPI, SY, BOC, SDA, PICS, AGBK). **Dropped.**

Retained as genuine insurance distribution (fee/commission model = the true theme):
- **Pure-play (9)**: EHTH, HIT, TWFG, WDH, BWIN, GSHD, AIFU, YB, LIFE — all SIC 6411.
- **Partial (3)**: CBZ (benefits-brokerage segment inside a diversified services firm),
  TREE (insurance comparison vertical, SIC 6163 loan-brokers), NRDS (insurance vertical, SIC 7374).

---

## 2. Ranked shortlist (all 12 sink — AVOID)

`rank.py` sinks every name to the bottom because all carry rating=AVOID. There is no
watch/buy tier. Ordering below is by the mechanical routing story, not by attractiveness.

| Ticker | Theme-fit | SIC | Mktcap | MoS basis | Active MoS | buy_eligible | Primary block |
|---|---|---|---:|---|---:|---|---|
| EHTH | pure_play | 6411 | $52M | nav | **+7.8%** | false | extreme_mos + financial_sic |
| WDH | pure_play | 6411 | $446M | nav | +0.3% | false | financial_sic + cross_source_mismatch |
| HIT | pure_play | 6411 | $71M | nav | -0.8% | false | financial_sic |
| TWFG | pure_play | 6411 | $282M | nav | -0.8% | false | financial_sic |
| NRDS | partial | 7374 | $551M | nav | -71% | false | cross_source_mismatch |
| LIFE | pure_play | 6411 | $1528M | nav | -77% | false | financial_sic + wrong_entity + cross_source |
| AIFU | pure_play | 6411 | $292M | nav | -98% | false | financial_sic + cross_source_mismatch |
| TREE | partial | 6163 | $545M | nav | -100% | false | financial_sic |
| GSHD | pure_play | 6411 | $1313M | nav | -100% | false | financial_sic |
| BWIN | pure_play | 6411 | $1973M | nav | -100% | false | financial_sic + insurance_concepts + debt_trunc + cross_source |
| CBZ | partial | 7389 | $1668M | **fcf_cap** | -120.6% | false | extreme_mos_review_required |
| YB | pure_play | 6411 | $699M | **abstain** | null | false | financial_sic + cross_source + conc_unquantified |

**mos_basis distribution: nav=10, fcf_cap=1, abstain=1.**

---

## 3. BUY analysis — honest 0-BUY

No name satisfies the v0.3.0 BUY rule
(`mos_basis in {fcf_cap,nav}` AND `numeric MoS>=30` AND `buy_eligible==true` AND zero kill-flags).

- **9 of 12 are blocked at the source** by `financial_sic_forced_unsuitable` (SIC prefix 60-67).
  Insurance brokers earn commissions/contingent fees on premium flow they do not retain on
  balance sheet; tangible equity is thin and FCF is lumpy/contract-driven. The FCF-cap model
  is the wrong lens, so it is refused and the name routes to NAV. The NAV bands then collapse to
  ~0 or deeply negative (the capital-light fee-business signature), which is *abstain by
  construction* — not a missed cheap stock.
- **The single fcf_cap survivor, CBZ** (SIC 7389, non-financial), reached the FCF-cap path and
  printed MoS = **-120.6%** — i.e. the market price sits far above its conservative FCF-cap
  intrinsic band. `extreme_mos_review_required` fired. Not cheap on its own model.
- **NRDS** (SIC 7374, non-financial) was not caught by the financial-SIC guard, but
  `cross_source_mismatch` (SEC vs market-data disagreement) blocked it on data integrity.
- **No name had a numeric MoS >= 30** on either basis. The closest positive was EHTH at +7.8%
  NAV — a quarter of the threshold and itself gated.

### Adversarial check on the strongest near-miss (EHTH)

EHTH is the only name with a positive margin (NAV +7.8%). Is the elimination a model artifact
hiding a real opportunity? **No.** (a) +7.8% is far below the 30% bar; (b) eHealth is a
commission-recognition business whose "book value" is dominated by deferred Medicare commission
receivables — a NAV anchor is not a defensible intrinsic value for it, so the small positive is
not economically meaningful; (c) the `extreme_mos_review_required` flag indicates the underlying
band is degenerate. Verdict: **correct elimination, no artifact.** No mechanical BUY survived to
require fuller adversarial work.

---

## 4. Code-paths exercised (the point of this test)

| Guard / path | Fired on | Verdict |
|---|---|---|
| `financial_sic_forced_unsuitable` (SIC 60-67 -> NAV) | EHTH, HIT, TWFG, WDH, BWIN, GSHD, AIFU, YB, LIFE, TREE (10) | **Primary path — worked as designed.** This is the headline of the test. |
| `insurance_concepts_present` (A3 holdco guard) | BWIN | Worked — flags an insurance-bearing holdco even where top-level SIC would not. |
| `cross_source_mismatch` (data-integrity) | WDH, BWIN, AIFU, YB, LIFE, NRDS (6) | Worked — independent of the SIC guard; caught NRDS where SIC did not. |
| `extreme_mos_review_required` | EHTH, CBZ (2) | Worked — gated a degenerate NAV band and a -120% FCF-cap band. |
| `debt_truncation_suspected` | BWIN | Worked. |
| `wrong_entity_suspected` | LIFE | Worked. |
| `concentration_unquantified` (dq) | YB, LIFE | Worked — contributed to YB abstain routing. |
| NAV path routing / abstain / fcf_cap split | 10 / 1 / 1 | Three-way routing exercised end-to-end. |
| Signals side-channel | auto-emitted | Firewalled — did NOT influence any buy_eligible (there were none). |

Every guard in the financial-SIC / fee-model cluster fired and was observable. The theme is a
clean positive for the firewall: 9 genuine insurance brokers, all correctly refused an FCF-cap
BUY without a single false BUY leaking through.

---

## 5. Data-quality issues

- **`market_cap`/`sic` not surfaced in the deepdive top-level JSON** (None there); the authoritative
  values live in the valuation block (`market_cap`, `sic_used`). Cosmetic, not blocking.
- **6/12 tripped `cross_source_mismatch`** — a high rate. Several are ADR/foreign-private-issuer
  20-F filers (WDH, AIFU, YB China; BWIN Up-C) where SEC XBRL vs market-data share counts diverge.
  Correct conservative behavior, but worth noting the theme is FPI-heavy.
- **YB returned ~$0 revenue/NI/OCF in rank.py** (XBRL normalized FCF unavailable) -> abstain. A
  genuine data gap for a recent Chinese IPO, handled by routing to abstain rather than a bad number.
- **LIFE blurb was empty** in the candidates JSON; theme-fit relied on SIC 6411 + known identity
  (Ethos life-insurance distribution). Low-confidence membership input, but the name was AVOID
  regardless.
- **TrendsMCP unavailable** (daily+monthly quota exhausted) and **no cached market-intel** entry for
  this theme, so the T2 enrichment layer is thin this run. Non-blocking — T2 never drives
  buy_eligible.

---

## 6. Market-intel / T2 analyst context (non-load-bearing)

TrendsMCP was rate-limited out and market-intel had no cached insurance-broker dossier, so this
is analyst domain context only, explicitly NOT an input to any verdict:

- The insurance-brokerage industry is a structurally attractive, recurring-revenue, capital-light
  fee model — which is precisely *why* the FCF-cap-vs-NAV tension exists. The public large-caps
  (MMC, AON, AJG, BRO, WTW) trade at premium FCF multiples; the small-caps that screened here are
  mostly (i) early/loss-making insurtech distributors (HIT, WDH, YB, AIFU, ROOT-adjacent), or
  (ii) high-multiple franchised growth names (GSHD, BWIN, TWFG). Neither cohort is a deep-value
  setup, consistent with the 0-BUY mechanical result.
- The theme is "hot-ish" (insurtech distribution had an IPO wave); per the skill's world-view #2,
  a branded/hyped theme is the casino, not the edge — alpha here would require a delayed-information
  fundamental change at a single name, which none surfaced.

---

## 7. Skeptical-PM usable verdict

**Usable = TRUE (as a firewall validation), NOT usable as a buy list.**

A skeptical PM gets exactly what this skill promises: a complete, no-sampling sweep of the small-cap
insurance-distribution universe that (a) correctly separated 12 genuine members from 47 bank/
underwriter/lender misrecalls, and (b) refused to emit a single FCF-cap BUY on a commission/float
business — the specific failure mode the financial-SIC guard exists to prevent. There is no
tradeable idea here, and the skill says so plainly. That honest 0-BUY, with every guard observable
and zero crashes, is the correct and useful answer for this theme.
