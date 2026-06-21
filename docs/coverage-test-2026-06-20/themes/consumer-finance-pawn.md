# Coverage Test — Theme: consumer-finance-pawn

- **Slug:** `consumer-finance-pawn`
- **Sector:** Financials
- **Keywords (FTS):** `consumer finance, pawn, installment lending`
- **Code-path focus:** financial / regulatory (financial-SIC FCF-unsuitable guard, insurance-concept exclusion, cross-source mismatch, debt-truncation)
- **Skill version:** v0.3.0 @ commit `f12fef5` (run manifest `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-consumer-finance-pawn/`
- **Date:** 2026-06-21
- **Verdict (one line):** Clean scanner pass — the financial-SIC universe is large and theme-rich, every clean lender is correctly routed to NAV (FCF model is unsuitable for balance-sheet lenders), and **zero names clear the BUY bar.** This is the intended behavior for a Financials theme; the guards did their job.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw FTS universe (efts.sec.gov) | **277** | 3 keywords UNIONed; no SIC reverse-recall floor exists for this theme (FTS-only). |
| ↳ deep band (mktcap < $2.0B) | 105 | |
| ↳ watch band ($2.0–5.0B) | 22 | theme-fit only, no deep-dive (band rule) |
| ↳ large (> $5.0B) | 38 | dropped by cap |
| ↳ unknown (unpriced) | 112 | flowed through as `band=unknown` (not silently dropped) |
| cheap_pass health check (priced small-caps) | 107 | mechanical kill-flag scan |
| ↳ cheap_pass survivors | 94 | 13 killed (going-concern / death-spiral / ICFR≥2) |
| SIC Gate 1 | 94 | keep=15, review=79 → all forwarded to LLM Gate 2 |
| **candidates JSON (deep-band)** | **73** | (+21 watch-band = 94 total rows) |
| **Gate 2 LLM theme-fit (deep-band)** | 73 → **20 survivors** | 10 pure_play + 10 partial; **53 misrecalls dropped** |
| **Deep-dived (every survivor)** | **20 / 20** | 0 ERROR files; full data + valuation on all |
| **BUY-eligible & clean (MoS≥30, basis∈{fcf,nav}, 0 kill-flags)** | **0** | — |
| **BUYs surviving adversarial review** | **0** | — |

Funnel triple: raw **277** → deepdived **20** → survivors (clean BUY) **0**.

> RANKING.md prints its own internal funnel ("114 → 93 → 21 → 20") computed from the candidates+watch rows; the canonical theme funnel is the table above. Minor off-by-one in the RANKING header (21 vs 20 deep-dives) is a cosmetic count in the deterministic scaffolder, not a data error — exactly 20 deepdive JSONs and 20 reports exist.

### Gate 2 — why 53 were dropped
The keyword `consumer finance` appears in essentially **every U.S. bank holding company 10-K** (it is regulatory boilerplate). The dominant misrecall cohort was **38 community/commercial bank holding companies** (SIC 6021/6022/6029/6035) — depository institutions, not consumer-finance/pawn pure-plays. The rest were BDCs (commercial credit, not consumer), mortgage REITs, fintech adtech/lead-gen (NerdWallet, MediaAlpha), and one optics company (Semilux, SIC 3674). This is the canonical FTS-sweep failure mode and the LLM gate is exactly what contains it.

---

## 2. Ranked shortlist (20 deep-dived theme members)

All 20 are correctly-classified theme members; none is a BUY. Ranked by mechanical cleanliness then valuation basis.

| # | Ticker | Class | SIC | MktCap | Basis | MoS | buy_eligible | kill-flags | Rating | Why not a BUY |
|--:|---|---|---|---:|---|---:|:--:|--:|---|---|
| 1 | **PRG** | pure_play | 7359 | $1.54B | fcf_cap | **19.6%** | **true** | 0 | 观察 | Mechanically clean, but MoS 19.6% < 30% floor. The single closest name. |
| 2 | EZPW | pure_play | 5900 | $1.95B | fcf_cap | -0.7% | false | 0 | 避开 | `fcf_sustainability_uncertain` (no capex → OCF proxy); MoS negative. |
| 3 | CPSS | pure_play | 6199 | $0.21B | nav | n/a | false | 0 | 避开 | financial-SIC FCF-unsuitable + debt-truncation + cross-source mismatch. |
| 4 | CRMT | pure_play | 5500 | $0.02B | nav | n/a | false | 1 | 避开 | extreme_mos (NAV MoS +1733%, debt-truncation artifact). |
| 5 | MFIN | pure_play | 6199 | $0.22B | nav | n/a | false | 0 | 避开 | financial-SIC + cross-source mismatch; rev extracted as $0. |
| 6 | OPRT | pure_play | 6199 | $0.24B | nav | -? | false | 0 | 避开 | financial-SIC + cross-source mismatch (rev SEC 19.5M vs yf 727.5M, 37x). |
| 7 | RM | pure_play | 6141 | $0.34B | nav | -12.7% | false | 0 | 避开 | financial-SIC + **insurance_concepts_present** (credit-insurance lender). |
| 8 | UPBD | pure_play | 7359 | $1.07B | nav | -? | false | 0 | 避开 | cross-source mismatch (total_debt SEC 191.8M vs yf 1728M, 9x). |
| 9 | WRLD | pure_play | 6141 | $0.83B | nav | -? | false | 0 | 避开 | financial-SIC + cross-source mismatch (rev SEC 175.9M vs yf 584.8M, 3.3x). |
| 10 | OPFI | pure_play | 6199 | $1.21B | nav | -? | false | 1 | 避开 | financial-SIC + cross-source mismatch; rev $0 extraction. |
| 11 | PRAA | partial | 6153 | $0.57B | nav | -? | false | 0 | 避开 | financial-SIC FCF-unsuitable (debt buyer). |
| 12 | ECPG | partial | 6153 | $1.78B | nav | -79.4% | false | 0 | 避开 | financial-SIC + **fundamental_decline_flag** + debt-truncation + cross-source. |
| 13 | LPRO | partial | 6141 | $0.37B | nav | -? | false | 0 | 避开 | financial-SIC FCF-unsuitable. |
| 14 | PGY | partial | 6199 | $1.29B | nav | -? | false | 0 | 避开 | financial-SIC + debt-truncation + cross-source mismatch. |
| 15 | LSAK | partial | 6099 | $0.39B | nav | -100% | false | 1 | 避开 | financial-SIC + insurance_concepts + **peak_contamination_flag**. |
| 16 | JFIN | partial | 6199 | $0.21B | nav | n/a | false | 0 | 避开 | extreme_mos + financial-SIC + cross-source (China VIE ADR). |
| 17 | LX | partial | 6199 | $0.33B | nav | n/a | false | 0 | 避开 | extreme_mos + financial-SIC + cross-source (China VIE ADR). |
| 18 | FINV | partial | 6163 | $1.10B | nav | -? | false | 0 | 避开 | financial-SIC + cross-source (China VIE ADR). |
| 19 | QFIN | partial | 6199 | $1.85B | nav | -? | false | 0 | 避开 | financial-SIC + cross-source (China VIE ADR). |
| 20 | XYF | partial | 6199 | $0.19B | nav | n/a | false | 1 | 避开 | extreme_mos + financial-SIC + cross-source (China VIE ADR). |

`-?` = NAV MoS computed but negative/uninformative under the artifact-laden balance sheet; not load-bearing once `buy_eligible=false`.

---

## 3. BUY analysis — 0 mechanical BUYs (honest zero)

**No name satisfies the BUY rule:** `mos_basis∈{fcf_cap,nav}` AND numeric MoS ≥ 30 AND `buy_eligible==true` AND 0 kill-flags.

The only `buy_eligible==true` name with 0 kill-flags is **PRG (PROG Holdings / Progressive Leasing)**:
- basis = `fcf_cap`, normalized FCF ≈ $325M, FCF yield 21%, reverse-DCF implied growth -11% (i.e. market prices in decline).
- Conservative intrinsic band $1.84B–$2.74B equity vs $1.54B market cap.
- **MoS = 19.6%** (computed conservatively off the LOW end of the band: (1.84B − 1.54B)/1.54B). Off the band midpoint it would be ~33%, but the skill deliberately uses the low end. **19.6% < 30% → no BUY.** Correctly rated 观察 (WATCH).

This is a textbook "scanner says nothing clean enough" result. Zero buys is a feature: the consumer-finance/pawn small-cap universe at these prices does not contain a name that is both (a) valuable on a methodology the skill trusts for the business model and (b) cheap enough by ≥30%.

### Adversarial check on the lone near-miss (PRG)
*Is PRG a real opportunity the MoS floor is hiding, or a data/model artifact?* — Neither produces a BUY, but for completeness: PRG's FCF is real and large (lease-to-own throws off cash), and the only data-quality note is `ebitda_series_partial_entries:4` (benign). It is **not** an artifact — it is a genuine but only-modestly-cheap name (reverse-DCF says the market already prices in an -11% decline). The 19.6% MoS is honest. A skeptical PM would file it as a watchlist name, not a buy. **Adversarial verdict: legitimately not-a-BUY; correctly held below the bar. No artifact rescue warranted.**

---

## 4. Which code-paths fired (financial/regulatory focus — the point of this theme)

This theme is a stress-test of the v0.3.0 Financials guards, and they fired exactly as designed:

| Guard | Fired on | Effect |
|---|---|---|
| **financial_sic_fcf_unsuitable** | 16 / 20 (all SIC 6141/6153/6163/6199/6099) | Forces `mos_basis=nav`, blocks FCF-cap BUY. The core consumer-finance guard. |
| **cross_source_mismatch** (SEC vs yfinance >2.5×) | 12 / 20 | Blocks BUY. yfinance reports balance-sheet gross receivables/debt for lenders that diverge wildly from SEC revenue XBRL (e.g. OPRT rev 19.5M vs 727.5M = 37×). |
| **insurance_concepts_present** | RM, LSAK | Blocks BUY (credit-insurance attached to lending). |
| **debt_truncation_suspected** | CPSS, CRMT, ECPG, PGY | Reported total_debt ≈ 0 vs implied (liab−equity) hundreds of M → blocks. |
| **extreme_mos_review_required** | CRMT, JFIN, LX, XYF | NAV MoS > 100% (artifact of debt-truncation / VIE balance sheets) → blocks. |
| **fundamental_decline_flag** (V-shape veto) | ECPG | Monotone fundamental decline → blocks. |
| **peak_contamination_flag** (V-shape veto) | LSAK | Trough→peak→rollover contamination → blocks. |
| going_concern / death_spiral / ICFR≥2 (cheap_pass) | 13 names killed pre-deepdive | Eliminated before judgment. |

**Not fired** (no eligible target): large_cap_out_of_scope (cap pre-filtered), concentration_kill, low_revenue_loss_extreme. The financial-SIC + cross-source pair alone is sufficient to block the entire clean-lender cohort, which is the correct conservative stance for balance-sheet financials.

---

## 5. Data-quality issues observed

1. **XBRL revenue extraction returns $0 / near-$0 for several lenders** (MFIN $0, OPFI $0, OPRT $20M). Finance companies report under interest-income/revenue concepts the XBRL cascade does not always map. This is *contained* — it forces NAV basis and trips cross-source mismatch, both of which block BUY. No false BUY leaked.
2. **yfinance vs SEC gross disagreement is the norm, not the exception, for lenders** (12/20). yfinance surfaces balance-sheet aggregates (gross loan book, total debt) that are 3–37× the SEC revenue line. The 2.5× cross-source guard correctly treats this as untrustworthy and blocks. This is the single most-fired data guard in the theme.
3. **debt_truncation on 4 names** — `total_debt` reported as ~0 against an implied debt of hundreds of millions; a known XBRL tagging gap for finance issuers. Correctly flagged.
4. **Report scaffolder displays MoS as a raw fraction** — PRG's `mos_pct: 0.2` in the rating contract is the rounded fraction 0.1956 (= 19.6%), not 0.2%. Cosmetic display nuance; the BUY rule consumes the fraction against the 0.30 threshold correctly.
5. **No SIC reverse-recall floor for this theme** — consumer-finance/pawn has no entry in `THEME_SIC`, so recall is FTS-only. SIC 6141 (personal credit) and 5932 (pawn/used-merchandise) would be natural recall floors if this theme were promoted to a tracked cohort. The known pawn pure-play **FirstCash (FCFS)** did not appear in the deep band — it is a >$2B-cap name (watch/large band), so its absence from the BUY shortlist is the cap rule, not a recall leak.

---

## 6. recall@gold

**n/a.** `consumer-finance-pawn` has no hand-built gold list in `THEME_GOLD` (only deathcare, water-utilities, railcar-leasing, regional-gaming are seeded). `track_forward.py --recall-gold ... --theme consumer-finance-pawn` returns *"no gold list for theme — not measurable."* Recall cannot be quantified for this theme this run.

---

## 7. Market-intel / T2 analyst context (does NOT drive buy_eligible)

- **TrendsMCP:** quota exhausted for the day (5/5 daily, 100/100 monthly) — no search-volume series retrievable this run.
- **Sector macro (T2 web, 2026):** U.S. consumer credit is on a **"K-shaped"** path — prime resilient, **subprime stressed**. Unsecured personal-loan balances hit a record **$277B (Q1 2026)**; FinTech lenders now originate **42%** of personal loans. Personal-loan delinquency rose to **3.99% (Q4 2025)**, the largest YoY jump since early 2023, with the sharpest rise in subprime. The **Sept 2025 Tricolor collapse** (subprime auto lender/retailer) rattled the sector and has banks reassessing subprime-auto exposure — directly relevant to CPSS, CRMT, and the auto-adjacent names. Pawn (EZPW) is structurally **counter-cyclical** — credit tightening elsewhere pushes marginal borrowers to pawn collateral lending.
- **Read-through:** the macro backdrop is "higher-risk but manageable, execution-quality decisive." This *supports* the skill's conservatism — a NAV-only, cross-source-skeptical stance on subprime lenders is appropriate when subprime delinquency is rising and a recent peer (Tricolor) just failed. None of this changes a single `buy_eligible`; it is recorded as analyst color only.

Sources: [TransUnion K-shaped Q1 2026](https://newsroom.transunion.com/k-shaped-q1-2026-ciir/) · [Morgan Stanley consumer credit](https://www.morganstanley.com/insights/articles/consumer-credit-trends-mixed-signals) · [BadCredit.org $276B subprime wave](https://www.badcredit.org/news/fintechs-ride-276b-subprime-wave-as-delinquencies-tick-up/) · [VantageScore CreditGauge Jan 2026](https://vantagescore.com/resources/knowledge-center/press_releases/vantagescore-creditgauge-january-2026-mortgage-delinquencies-rise-as-early-stage-credit-stress-broadens-across-borrowers)

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** This run is a clean, defensible scanner pass:
- The theme is genuinely populated (20 real consumer-finance/pawn/installment members deep-dived, 0 ERROR files).
- Gate 2 correctly stripped 53 bank-holding-company misrecalls — the FTS-sweep failure mode was contained.
- Every clean lender was routed to NAV (FCF is the wrong lens for a balance-sheet lender) and then blocked by financial-SIC + cross-source guards. **Zero false BUYs leaked** despite pervasive XBRL revenue-extraction problems — the data-quality guards earned their keep here.
- The honest answer is **0 BUYs**, with PRG as a documented near-miss watchlist name (19.6% MoS, mechanically clean).

A PM can trust the elimination: the names that fell out are out for legible reasons (depository misrecall, financial-SIC, cross-source untrustworthy data, V-shape value-trap). The one residual action item is operational, not a buy: **promote consumer-finance-pawn to a tracked cohort with SIC floors (6141 personal credit, 5932 pawn) and a gold list** so recall becomes measurable and pawn pure-plays like FCFS are deliberately bracketed by cap band.
