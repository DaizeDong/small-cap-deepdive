# Coverage Test — Theme: Waste Management / Recycling / Environmental Services

- **Run batch:** `2026-06-21_cov-waste-recycling`
- **Skill version:** v0.3.0 (commit `f12fef5`, dirty=true)
- **Slug:** `waste-recycling` (discover out-slug `waste_recycling`)
- **Sector:** Industrials
- **Keywords (FTS):** `waste management, recycling, environmental services`
- **Code-path focus:** defensive / clean-FCF candidate
- **Date:** 2026-06-21
- **Verdict in one line:** **0 BUY.** The clean-industrial-beneficiary slot for this theme in the
  micro/small-cap universe is empty right now. The scanner did its job: it surfaced 5 genuine
  theme members and correctly sank every one of them on mechanical grounds (negative/unavailable
  normalized FCF, extreme negative MoS, pre-revenue, or a financial-SIC misfire).

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw hits (3 keywords, deduped) | 656 | `waste management` 331 + `recycling` 266 + `environmental services` 176 |
| Priced + banded | 656 | deep band (<$2.0B) 46, watch band ($2–5B) 12 |
| Small-cap into cheap_pass | 41 | deep + part of watch within cap logic |
| cheap_pass survivors | 25 | 16 eliminated (kill-flag ≥3 or too cheap/no financials) |
| SIC gate (Gate 1) | 25 | keep=20, review=5 (forwarded to LLM gate, not dropped) |
| **LLM theme-fit survivors (deep-band, true members)** | **5** | OPAL, TOPP, ADUR, WBI, BBCP |
| Deep-dived | 5 | every theme-fit deep-band survivor — no sampling |
| **Mechanical BUY** | **0** | none cleared `buy_eligible ∧ MoS≥30 ∧ 0 kill-flags ∧ mos_basis∈{fcf_cap,nav}` |
| BUY after adversarial verification | 0 | nothing to confirm |

**Funnel object:** raw=656, deepdived=5, survivors=5.

### Why this theme is a low-precision FTS magnet
The three keywords are generic and pervade 10-K boilerplate. The 46-name deep band was dominated by
**precious-metals / base-metals miners** (AUMN, NAMM, SCZM, NEWP, ODV, MTAL, ASM, DRD, NG — "environmental
services" / "recycling" appear in their reclamation and tailings disclosures), plus medical devices
(OFIX, MDXG), fintech (LSAK), an industrial REIT (MDV), aviation real estate (SKYH), TiO2 chemicals
(TROX), fertilizer (IPI), oilfield services (RES), uniforms (UNF), and garden/pet (CENT). The LLM
theme-fit gate (Gate 2) is what carries recall precision here — there is **no SIC recall floor for this
theme** (see §5), so FTS + market-cap fallback is the only recall channel and Gate 2 is the only
precision channel.

---

## 2. Theme-fit gate (LLM, Gate 2) — judgments from 10-K blurbs

**Kept as true / borderline members (deep-dived):**

| Ticker | Name | SIC | Membership | Rationale |
|---|---|---|---|---|
| OPAL | OPAL Fuels | 4932 | pure/partial | Captures landfill + dairy biogas → renewable natural gas (RNG); core waste-stream methane monetization. Genuine waste-to-energy / environmental services. |
| TOPP | Toppoint Holdings | 4210 | partial | Truckload logistics for the **recycling export supply chain** (waste paper, scrap metal). Recycling-adjacent logistics. |
| ADUR | Aduro Clean Technologies | 2800 | partial | Hydrochemolytic chemical recycling of waste plastics (PE/PP/PS) + crude upgrading. Genuine recycling tech — but pre-revenue (see §4). |
| WBI | WaterBridge Infrastructure | 1389 | borderline | Oilfield **produced-water gathering/disposal** for the Permian. "Environmental services" adjacency, but really E&P-midstream water. Kept to avoid under-recall. |
| BBCP | Concrete Pumping Holdings | 1700 | borderline | Predominantly concrete pumping; has an Eco-Pan **concrete-washout waste-management** segment. Kept on the strength of that segment. |

**Excluded as misrecall (off-theme; not deep-dived):** MDV (REIT), OFIX/MDXG (medical), RES (oilfield
svcs), LSAK (fintech), SKYH (aviation RE), TROX (TiO2), MTAL/SCZM/NEWP/ODV/NAMM (mining), IPI
(fertilizer), and the watch band CTOS/CENT/UNF/DRD/EFXT/CDLR/CSAN.

---

## 3. Ranked shortlist (RANKING.md)

| Rank | Ticker | Rating | Conf | mos_basis | MoS | buy_eligible | kill-flags |
|---|---|---|---|---|---|---|---|
| 1 | OPAL | 观察 WATCH | 60 | fcf_cap | null | true | 0 |
| 2 ⬇ | ADUR | 避开 AVOID | 55 | fcf_cap | null | true | 0 |
| 3 ⬇ | WBI | 避开 AVOID | 50 | fcf_cap | -140.5% | false | 0 |
| 4 ⬇ | BBCP | 避开 AVOID | 45 | fcf_cap | -141.6% | false | 1 |
| 5 ⬇ | TOPP | 避开 AVOID | 45 | nav | -78.7% | false | 1 |

mos_basis distribution: **fcf_cap=4, nav=1, abstain=0.**

---

## 4. BUY rule application — honest 0-BUY

BUY requires: `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30` AND `buy_eligible == true` AND
zero kill-flags. No candidate satisfied all four.

- **OPAL** — `buy_eligible=true`, kill-flags=0, mos_basis=fcf_cap. **Fails on MoS:** normalized FCF is
  **negative** (-$86M; norm. EBITDA $23M but FCF yield -10.5%), so the fcf_cap intrinsic band is
  `unavailable` → `MoS = null` (not ≥30). EV/EBITDA 17.5x is not cheap. Lumpy-OCF flagged
  (peak OCF $38.3M > 2× median $15.0M) — normalization is suspect. Correctly **WATCH**, not BUY.
- **ADUR** — `buy_eligible=true`, kill-flags=0, mos_basis=fcf_cap. **Fails on MoS:** company is
  **pre-revenue / development-stage** (XBRL revenue $0; FY25 actual ~$231K, net loss ~$12M). No
  EBITDA, no FCF → intrinsic band unavailable → `MoS = null`. `buy_eligible` only stayed true because
  there are no financials for the FCF-sustainability / decline guards to bite. A $529M cap on ~zero
  revenue is a venture bet, not a clean-FCF buy. Correctly **AVOID**.
- **WBI** — **`buy_eligible=false`**: `extreme_mos_review_required` (MoS -140.5%) + `fcf_sustainability_uncertain`
  (FCF is an OCF proxy on a capital-intensive book, assets/rev = 7.1×; no capex available). Newly
  IPO'd (Sep-2025), 3-yr-insufficient normalization. Not a BUY.
- **BBCP** — **`buy_eligible=false`**: `extreme_mos_review_required` (MoS -141.6%); kill-flag=1; P/E 86x.
  Intrinsic FCF band is negative. Not a BUY.
- **TOPP** — **`buy_eligible=false`**: `financial_sic_forced_unsuitable` + `insurance_concepts_present`
  (the FCF model was forced unsuitable; NAV path used). NAV MoS -78.7% (market cap $28M >> tangible
  equity $8M). Micro-cap, burning cash (OCF -$1.8M). Not a BUY. **Note:** the financial-SIC / insurance
  trigger here is a *false-positive flavor* — TOPP is a trucking company (SIC 4210), and the XBRL
  concept `PremiumsEarnedNet` was almost certainly an insurance-receivable/insurance-expense line, not
  an insurer's premium revenue. This did not change the outcome (NAV MoS was already deeply negative),
  but it is a data-quality artifact worth logging (see §7).

**There are no BUYs to adversarially defend.** For completeness, the two closest-to-buy names
(OPAL, ADUR — both `buy_eligible=true`) were *correctly* withheld by the MoS gate because neither
produces a positive normalized FCF intrinsic band. That is the guard working as designed: a
`buy_eligible=true` company with `MoS=null` is **not** a BUY. No data/model artifact manufactured a
false BUY in this theme.

**n_buy_clean = 0.**

---

## 5. Code-paths exercised

- `new_run.py` — opened run batch + manifest (commit/config snapshot).
- `run_theme.py` → `discover.py` — FTS recall (656), yfinance market-cap with **SEC shares×price
  fallback** and `band=unknown` passthrough (ESGL/POAI/SRCL/SGD/ALE 404'd on yfinance and were
  handled, not silently dropped).
- **SIC recall floor: NOT fired** — `waste-recycling` is **not in `THEME_SIC`** (only deathcare /
  water-utilities / railcar-leasing / regional-gaming have floors). Recall here = FTS + mktcap fallback
  only. This is a known coverage gap for this theme (refuse-systems SIC 4953 / scrap SIC 5093 are not
  seeded).
- `cheap_pass.py` — mechanical kill-flags; 16 eliminations incl. going-concern / death-spiral
  (SMTK kf3, SCWO kf3, RETO kf2, AQMS kf2, BLNK kf2).
- `filter_by_sic.py` (Gate 1) — tri-state: keep=20, **review=5** (financial/medical/REIT SICs forwarded
  to LLM, not auto-dropped — the review path was exercised: MDV 6798, OFIX/MDXG 3841, LSAK 6099, SKYH 6500).
- LLM theme-fit gate (Gate 2) — 5 of 20+ deep-band names judged true members; the mining/medical/fintech
  swarm filtered out by blurb.
- `deepdive_data.py` — 5/5 clean pulls, **0 `*_ERROR.json`**. Exercised: EBIT concept cascade
  (`OperatingIncomeLoss`), OCF-proxy-for-FCF (ADUR/WBI: capex unavailable), Form-4 insider (OPAL
  net_buy 18/0, WBI net_buy 6/0), 40-F path (ADUR), customer-concentration text flag.
- `valuation.py` — exercised fcf_cap (4) and NAV (1) paths; **buy_eligible guards fired:**
  `extreme_mos_review_required` (WBI, BBCP), `fcf_sustainability_uncertain` (WBI),
  `financial_sic_forced_unsuitable` + `insurance_concepts_present` (TOPP), `intrinsic_band_unavailable`
  → MoS null (OPAL, ADUR), cyclical CV / trailing-5yr normalization, lumpy-OCF normalization-suspect
  (OPAL, WBI).
- `signals.py` (diagnostic, **firewalled**) — emitted in each report's T2 section (e.g. OPAL
  `divergence_label=unpriced_improvement`, 6m -11.4% / 12m -43.3%). **Did not touch any buy_eligible
  or rating** — confirmed by inspecting the firewall banner and the valuation blocks.
- `make_report.py` — 5 deterministic report scaffolds + trust banners.
- `finalize_run.py --allow-missing` — emitted 5 verdicts, rebuilt RANKING. (Warning about "18 deep-band
  missing reports" is expected: only theme-fit survivors get deep-dived; the off-theme miners/medical
  names are intentionally not deep-dived. The 5 slug-named reports were parsed correctly.)
- `rank.py` — RANKING.md with funnel + sink logic (4 AVOIDs sunk).
- `track_forward.py --recall-gold` — ran; returned **"no gold list for theme 'waste-recycling' → not
  measurable."**

---

## 6. recall@gold

**n/a — not measurable.** `waste-recycling` has no gold cohort in `track_forward.THEME_GOLD`
(only deathcare, water-utilities, railcar-leasing, regional-gaming are seeded). The
`--recall-gold` call returned "no gold list … not measurable."

---

## 7. Data-quality issues observed

- **No SIC recall floor for this theme** — the dedicated refuse/recycling SICs (4953 refuse systems,
  5093 scrap & waste materials) are not in `THEME_SIC`, so a low-keyword-density true member living in
  those SICs would be invisible to this run. Recall rests entirely on FTS + Gate 2. (Coverage gap, not
  a bug in this run.)
- **TOPP financial-SIC false-positive flavor** — `insurance_concepts_present` (`PremiumsEarnedNet`)
  fired on a trucking company. Outcome unchanged (NAV MoS already -78.7%) but the trigger is a
  mis-mapped XBRL concept, not a real insurer. Worth a guard refinement.
- **OCF-proxy-for-FCF on capital-intensive names** — WBI and ADUR have no capex in XBRL, so FCF =
  OCF proxy. For WBI (assets/rev 7.1×) this is explicitly flagged `fcf_sustainability_uncertain` and
  blocks BUY — correct behavior, but the proxy inflates apparent FCF.
- **Lumpy-OCF normalization suspect** — OPAL (peak $38.3M > 2× median $15.0M) and WBI (peak $159.7M >
  2× median $61.2M). Trailing-5yr-avg normalization is fragile for these; flagged in trust banners.
- **Concentration text-flag without magnitude** — OPAL/WBI/BBCP/TOPP all show
  `concentration_unquantified:text_flag_true_but_xbrl_magnitude_null` (customer ≥10% mentioned in text
  but no XBRL magnitude). Did not drive any decision.
- **Pricing 404s handled** — ESGL/POAI/SRCL/SGD/ALE failed yfinance; passed through via fallback /
  band=unknown rather than being dropped.
- **ADUR XBRL revenue = $0** while the actual FY25 revenue is ~$231K (40-F filer, sparse tagging).
  Pre-revenue conclusion is robust either way.

---

## 8. Market-intel / TrendsMCP context (T2 — labeled, does NOT drive buy_eligible)

- **Plastic recycling** (Google search interest): **+32.6% YoY** (value 43→57; volume 10.3k→13.7k),
  but **-10.9% over the last 6M** — secular interest up, near-term attention cooling. Relevant T2
  backdrop for ADUR's chemical-recycling thesis; does not change its pre-revenue mechanical AVOID.
- **Renewable natural gas** (Google search interest): **-7.4% YoY** (value 27→25) — muted mainstream
  attention, consistent with OPAL's -43% trailing-12M price and the WATCH (not BUY) call.
- These are between-filings T2 signals only; per the firewall, none of this entered `buy_eligible` or
  the rating.

---

## 9. Skeptical-PM usable verdict

**Usable: YES.** This is a textbook correct "nothing found" result. The theme is a low-precision FTS
magnet (656 raw → mining/medical/fintech swarm), and the tool (a) recalled the genuine members via the
LLM gate despite having no SIC floor, (b) deep-dived all 5 with zero crashes, and (c) sank every one on
defensible mechanical grounds — negative/unavailable normalized FCF (OPAL), pre-revenue (ADUR), extreme
negative MoS on capital-intensive water/concrete (WBI, BBCP), and a financial-SIC + deeply-negative-NAV
micro-cap (TOPP). **No false BUY was produced; no candidate was silently skipped.** A PM gets an honest
0-BUY plus one name (OPAL) worth a watch-list slot for when/if RNG economics and FCF turn positive.

The one caveat a PM should note: the **absent SIC recall floor** means a quiet, profitable
refuse-hauler in SIC 4953 with thin keyword density could be missed. For a production run of this
theme, seeding `THEME_SIC["waste-recycling"] = ["4953", "5093"]` (plus a recall@gold cohort, e.g.
WM, RSG, WCN, GFL, CWST, MEG, PCT) would let recall be measured rather than assumed.
