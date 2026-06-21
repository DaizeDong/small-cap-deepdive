# Coverage Test — Building Products / HVAC / Insulation

**Theme slug:** `building-products-hvac` · **Sector:** Industrials · **Keywords:** building products, HVAC, insulation
**Code-path focus:** housing-cyclical
**Skill version:** v0.3.0 (commit f12fef5) · **Run batch:** `2026-06-21_cov-building-products-hvac` · **Run date:** 2026-06-21

> **Research output, not investment advice.** This is a landmine-scanner: it tells you what to *eliminate* and what survived
> mechanical de-risking. A surviving name is a candidate for human DD, never a buy signal.
> **Headline result: 0 mechanical BUYs.** No name cleared the BUY rule (mos_basis ∈ {fcf_cap, nav} AND numeric MoS ≥ 0.30 AND
> buy_eligible == true AND zero kill-flags).

---

## 1. Funnel

| Stage | Count | Note |
|---|---:|---|
| Raw discover (FTS + mktcap filter) | — | EDGAR full-text over-recall; FTS-only (no SIC recall floor exists for this theme) |
| Small-cap cheap-pass input | 45 | after market-cap band tag (deep ≤ $2.0B; watch $2.0–5.0B) |
| Cheap-pass survivors (no hard kill-flag) | 35 | 10 eliminated on going-concern / death-spiral / material-weakness |
| After SIC Gate-1 | 35 | keep=34, review=1 (ENTA, SIC 2834 pharma — correctly flagged) |
| **Deep band (band="deep", ≤ $2.0B)** | **25** | the deep-dive-eligible universe |
| Watch band (band="watch", $2.0–5.0B) | 10 | surfaced for human review only, not deep-dived |
| **Gate-2 theme-fit survivors (deep-dived)** | **10** | 15 deep-band names dropped as misrecalls |
| Valuation + BUY-rule applied | 10 | all 10 valued (--json + --ticker), 0 deepdive ERROR files |
| **Mechanical BUYs (clean)** | **0** | — |

**SIC recall floor:** none. `building-products-hvac` is not in `filter_by_sic.THEME_SIC` (only water-utilities, railcar-leasing,
regional-gaming, deathcare have floors), so the P8 reverse-recall channel was a no-op and recall was FTS-only. This is correct
behavior, not a gap — there is no single dedicated SIC for "building products / HVAC."

**recall@gold:** **n/a** — no gold list exists for this theme (`track_forward.py --recall-gold` returns "not measurable").

---

## 2. Gate-2 theme-fit (LLM judgment from Item-1 blurbs)

**Dropped as misrecalls (15):** the FTS keyword "building products" recalled a large cohort of entities that merely *hold* or
*mention* building-products companies, not operate as them:

- **10 BDCs / closed-end investment companies** (SIC nan): BCIC, WHF, NMFC, SLRC, FDUS, PFLT, MFIC, KBDC, OCSL, GSBD —
  pure financial entities; keyword fired on portfolio-company descriptions.
- **ENTA** — biotech (HCV protease inhibitors). **SND** — frac/industrial sand for oil & gas. **FWRD** — asset-light trucking.
  **OLPX** — haircare/beauty. **UPBD** — rent-to-own consumer fintech.

**Retained for deep-dive (10):** APOG, ASTE, BOOM, BXC, BZH, CMT, HOV, IIIN, NX, TRS — split pure-play vs partial:

| Ticker | Class | Why in theme |
|---|---|---|
| NX (Quanex) | pure_play | insulating glass spacers, window/door seals, vinyl profiles — literally insulation + building products |
| APOG (Apogee) | pure_play | architectural building products (curtainwall/window/storefront systems) |
| BXC (BlueLinx) | pure_play | wholesale distributor of residential/commercial building products |
| IIIN (Insteel) | pure_play | steel wire reinforcing for concrete construction |
| BOOM (DMC Global) | partial | Arcadia segment = architectural building products; 2 other segments are energy |
| CMT (Core Molding) | partial | building products one of several molded-product end markets (mostly trucks) |
| ASTE (Astec) | partial | road-building / construction equipment (housing-cyclical adjacent) |
| TRS (TriMas) | partial | diversified industrial; some building/plumbing-products lineage |
| BZH (Beazer) | partial | homebuilder — housing-cyclical, not a products maker |
| HOV (Hovnanian) | partial | homebuilder — same |

---

## 3. Code-paths fired (housing-cyclical focus)

- **Cyclical normalization** (`cyclical=True`, 5-yr EBITDA-CV normalization): fired on **9 of 10** survivors (all except CMT,
  cv=0.145 < 0.25 threshold → treated as non-cyclical). This is the housing-cyclical core path: BOOM cv=1.92, NX cv=1.56,
  ASTE cv=1.01, IIIN cv=0.70 — high CV correctly drives normalized-earnings valuation rather than trailing.
- **FCF-cap vs NAV basis routing:** `fcf_cap_model_unsuitable=True` (asset-heavy / homebuilder inventory) routed BZH, NX, TRS,
  IIIN, ASTE to **NAV basis**; BOOM, APOG, BXC, CMT, HOV stayed on **FCF-cap**. Basis split = 5 fcf_cap / 5 nav.
- **v0.3.0 buy_eligible guards that fired** (all firewalled from signals side-channel; signals emitted nothing here):
  - `cross_source_mismatch` — **NX** (SEC debt 142.5M vs yfinance 889.3M, 6.2x), **CMT** (SEC rev 74.7M vs yf 270.9M, 3.6x)
  - `financial_sic_forced_unsuitable` + `insurance_concepts_present` — **ASTE** (see §5: spurious-reason mis-fire)
  - `fundamental_decline_flag` — **BXC**, **IIIN**
  - `extreme_mos_review_required` (MoS > 100%) + `fcf_sustainability_uncertain` — **BXC**
  - `debt_truncation_suspected` — **IIIN** (debt_for_nav = $5.4M, implausibly low)
- **Not fired (clean):** peak_contamination / V-shape, concentration kill, large-cap, low_revenue_loss_extreme, wrong-entity.

---

## 4. Ranked shortlist

From `RANKING.md`. AVOID / kill-flag-heavy names sink to the bottom.

| Rank | Ticker | Rating | Basis | Operative MoS | buy_eligible | Blockers |
|---:|---|---|---|---:|---|---|
| 1 | APOG | 观察 WATCH | fcf_cap | −30.7% | true | none (MoS negative) |
| 2 | BOOM | 观察 WATCH | fcf_cap | **+24.8%** | true | none — **closest to BUY**, MoS < 30 |
| 3 | BZH | 观察 WATCH | nav | **+25.5%** | true | none — **2nd closest**, MoS < 30 |
| 4 | HOV | 观察 WATCH | fcf_cap | −0.4% | true | none (MoS ~0) |
| 5 | TRS | 观察 WATCH | nav | −45.0% | true | none (MoS negative) |
| 6 ⬇ | ASTE | 避开 AVOID | nav | −75.5% | false | financial_sic_forced_unsuitable, insurance_concepts_present |
| 7 ⬇ | BXC | 避开 AVOID | fcf_cap | +221.9% | false | extreme_mos_review, fcf_sustainability_uncertain, fundamental_decline |
| 8 ⬇ | CMT | 避开 AVOID | fcf_cap | −90.1% | false | cross_source_mismatch |
| 9 ⬇ | IIIN | 避开 AVOID | nav | −56.0% | false | debt_truncation_suspected, fundamental_decline |
| 10 ⬇ | NX | 避开 AVOID | nav | −53.6% | false | cross_source_mismatch |

---

## 5. BUYs and adversarial verification

**0 mechanical BUYs.** No adversarial-BUY verdict required. Two near-misses were adversarially examined anyway:

- **BOOM (DMC Global), fcf_cap MoS +24.8%, buy_eligible, zero flags — fell ~5pp short of 30%.**
  Adversarial check: this is a *real* gap, not a data artifact — but the name is fragile. cv_ebitda=1.92 (extremely cyclical),
  TTM net income **negative (−$14M)**, normalized FCF only $24M against a $144M cap. The FCF-cap MoS rests entirely on the
  5-yr normalized number; with earnings currently negative, the normalization is doing heavy lifting. The 30% gate correctly
  withholds BUY. Verdict: legitimately WATCH, not a model error — the skill was right to *not* round it up.
- **BZH (Beazer), nav MoS +25.5%, buy_eligible, zero flags — ~4.5pp short.**
  Adversarial check: NAV path on a homebuilder = tangible equity $1.16B vs $1.55B debt vs $739M cap. The +25% discount-to-NAV
  is real but homebuilder book value is land-inventory-heavy and marks at cost; in a housing downturn that NAV is the *first*
  thing to impair. A 25% discount is thin compensation for that left-tail. Verdict: WATCH is the honest call.

Neither would become a clean BUY even if it crossed 30% without re-checking inventory marks — consistent with the skill's
"neglect ≠ undervalued, hot theme = casino" priors.

---

## 6. Data-quality issues

1. **ASTE guard mis-fire (false-positive reason, conservative outcome).** `financial_sic_forced_unsuitable` and
   `insurance_concepts_present` fired on **Astec Industries**, a construction-machinery maker (SIC 3531) — not a financial or
   insurer. The block is *directionally safe* (ASTE's normalized FCF is negative and NAV MoS is −75%, so it deserved AVOID
   anyway), but the **reason strings are spurious**. Likely an Item-1/risk-factor keyword hit ("insurance") + an SIC-prefix
   collision. Flag for guard-precision review: a future genuinely-cheap industrial could be blocked for the wrong reason.
2. **Cross-source debt/revenue disagreement (NX, CMT).** SEC vs yfinance gross mismatch (NX debt 6.2x, CMT revenue 3.6x).
   These correctly blocked BUY, but they also mean the *displayed* valuation for these two is unreliable until reconciled.
   NX's NAV uses SEC debt $142.5M (the low figure); if yfinance's $889M is right, NAV would be far worse — the block is the
   right call.
3. **IIIN debt_truncation_suspected** — debt_for_nav = $5.4M is implausibly low for a $565M steel manufacturer; NAV is
   untrustworthy and correctly blocked.
4. **BXC extreme MoS +221.9%** — far outside plausible range, auto-flagged extreme_mos_review + fcf_sustainability_uncertain;
   a textbook normalization artifact, correctly quarantined.
5. **TRS growth +289%** (in RANKING table) — a base-effect artifact off a low prior-year net income; does not affect the NAV
   basis used for its verdict.
6. **Market-cap source = yfinance for all 10** (no SEC cross-confirm of cap itself) — standard for the layer, noted.

---

## 7. Market-intel / Trends context (T2 — analyst color only, does NOT drive buy_eligible)

- **HVAC** (Google search): **+23.8% YoY**, +9.9% over trailing 3M; absolute volume ~1.06M/mo, rising. Strong demand momentum.
- **home insulation** (Google search): **+36.8% YoY**. Decarbonization / efficiency-retrofit tailwind is visible in search.

Interpretation: the *demand theme* is genuinely hot — which, per the skill's worldview (#2, hot theme = casino), is exactly the
condition under which the valuations should look full. They do: 9 of 10 cyclicals show negative or sub-30% MoS. The one cohort
with positive MoS (BOOM, BZH) carries elevated cyclicality / inventory-mark risk that the 30% gate is calibrated to demand
compensation for. The T2 tailwind reinforces, rather than contradicts, the 0-BUY result: strong demand ≠ a margin of safety.

---

## 8. Skeptical-PM usable verdict

**Usable: YES (as a clean negative + a watchlist).** A skeptical PM gets exactly what this skill is built to deliver:

- A defensible, fully-covered **0-BUY** on a fashionable theme, with every elimination reasoned (10 hard kill-flags, 15
  theme misrecalls, 10 valuation blocks/short-falls).
- A short **WATCH list** (BOOM, BZH at ~25% NAV/FCF discount) flagged with the *specific* reason each isn't a BUY yet
  (cyclical-trough earnings; land-inventory NAV fragility) — that is actionable for monitoring a future entry.
- Honest data-quality disclosure (ASTE guard mis-fire; NX/CMT/IIIN source mismatches) so the PM knows which numbers to
  re-pull before trusting them.

What it is NOT: it does not surface a hidden gem here, because there isn't one at current prices. The correct skeptical use is
"shelf the theme, re-run if the cyclical rolls over and BOOM/BZH cross 30% with inventory marks verified."

---

## Appendix — artifacts

- Run dir: `reports/smallcap/2026-06-21_cov-building-products-hvac/`
- `RANKING.md`, `deepdive_verdicts.json`, `candidates_building_products_hvac.json`, `candidates_gate2_survivors.json`
- Per-ticker: `deepdive_<T>_2026-06-21.json`, `valuation_<T>_2026-06-21.json`, `report_<T>.md` (10 each)
- 0 `deepdive_*_ERROR.json` files (no crashes).
