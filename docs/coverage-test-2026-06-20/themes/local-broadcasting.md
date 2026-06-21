# Coverage Test — Theme: local-broadcasting

- **Slug:** `local-broadcasting`
- **Sector:** CommSvcs
- **Keywords:** `broadcasting, local television, radio station`
- **Skill version:** small-cap-deepdive v0.3.0 (commit `f12fef5`, run flagged dirty=true)
- **Run batch:** `reports/smallcap/2026-06-21_cov-local-broadcasting/`
- **Code-path focus:** declining sector -> V-shape / peak-contamination veto
- **Date:** 2026-06-21

---

## 1. Funnel

| Stage | Count |
|---|---|
| Raw FTS universe (discover, small-cap <=$2.0B) | 102 |
| cheap_pass survivors (no hard going-concern/death-spiral kill) | 58 |
| SIC gate (keep=36, review=22 -> all forwarded to LLM) | 58 |
| Deep band (band="deep") | 45 |
| **LLM theme-fit survivors (deep-dived)** | **9** |
| Gate-2 misrecall (resolved, not deep-dived) | 36 |
| Mechanical BUY (rule-clean) | **0** |
| BUY surviving adversarial verification | **0** |

watch-band (>$2.0B, out of small-cap scope): 12 names (DJT, IAC, JOYY, LBTYA, GHC, TDS, etc.) — not deep-dived.

### SIC recall floor — NOT available for this theme
`filter_by_sic.THEME_SIC` has **no entry** for local-broadcasting. The dedicated broadcasting SICs
(4832 radio, 4833 TV) are not mapped, so **no SIC reverse-recall floor fired** — recall rested on FTS
+ mktcap-fallback alone. This is an honest coverage gap: a registrant with a broadcasting SIC that
never tripped the FTS keywords would be missed. (Contrast: water-utilities / railcar / gaming have
floors; this theme does not.) Despite the missing floor, all the canonical US small-cap
broadcasters (SGA, TSQ, SSP, GTN, IHRT, EVC, SBGI) were recalled via FTS.

---

## 2. LLM theme-fit gate (membership judged from blurbs)

**Pure-play local broadcasters (7):** SGA (Saga, radio), TSQ (Townsquare, sub-top-50 radio),
SSP (E.W. Scripps, 60+ local TV stations), GTN (Gray Media, local TV), IHRT (iHeartMedia, radio/audio),
EVC (Entravision, Spanish-language local TV/radio), SBGI (Sinclair, local TV group).

**Partial (2):** NMAX (Newsmax — national cable news + broadcasting subsidiary, not "local"),
TV (Grupo Televisa — Mexican national broadcaster, foreign 20-F).

**Dropped as misrecall (36 deep-band):** Chinese internet/streaming/social (SOHU, WB, HUYA, MOMO,
XNET, IQ, SOGP, NCTY, CHR, SY, GOTU, NAMI, ZEPP, TKLF, GETY); cable-network programmers/telecom
(AMCX, LILA, LBTYA, STRZ); OOH/billboards (CCO); BDCs (WHF, PFLT, CGBD, BBDC, OCSL); ETFs (BRRR);
gaming/entertainment venues (BALY, LUCK); REIT (ESRT); electronics/tech (UEIC, KLTR, XPER, IZEA);
holding co (CNNE); crypto (HKD); printing (TGE).

---

## 3. Ranked shortlist (RANKING.md)

| Rank | Ticker | Rating | Conf | mos_basis | MoS | buy_eligible | Kill-flags fired |
|---|---|---|---|---|---|---|---|
| 1 | NMAX | 观察 watch | 3 | fcf_cap | null | False | cross_source_mismatch |
| 2 | TV | 观察 watch | 2 | fcf_cap | null | **True** | (none — but no numeric MoS) |
| 3 (sunk) | EVC | 避开 avoid | 4 | fcf_cap | -65.5% | False | fundamental_decline, peak_contamination |
| 4 (sunk) | GTN | 避开 avoid | 4 | fcf_cap | -835% | False | extreme_mos, fcf_sustainability, peak_contamination |
| 5 (sunk) | IHRT | 避开 avoid | 4 | nav | null (-100%) | False | peak_contamination, fcf_cap_unsuitable(debt>0.62) |
| 6 (sunk) | SBGI | 避开 avoid | 4 | nav | null (-100%) | False | debt_truncation, fundamental_decline, peak_contamination, cross_source_mismatch |
| 7 (sunk) | SGA | 避开 avoid | 4 | fcf_cap | +80.1% | False | fundamental_decline, peak_contamination |
| 8 (sunk) | SSP | 避开 avoid | 4 | fcf_cap | -549% | False | extreme_mos, fcf_sustainability, fundamental_decline, peak_contamination |
| 9 (sunk) | TSQ | 避开 avoid | 4 | nav | null (-100%) | False | financial_sic_forced, insurance_concepts, peak_contamination |

---

## 4. BUY rule outcome — ZERO clean BUYs

BUY requires: `mos_basis in {fcf_cap, nav}` AND numeric `MoS >= 30` AND `buy_eligible == true` AND zero kill-flags.

**No candidate satisfies all four.** Two near-misses are instructive:

### SGA (Saga) — the headline trap (+80.1% MoS, but vetoed)
SGA's fcf_cap MoS is **+80.1%** — well above the 30% bar — and mos_basis is fcf_cap (eligible basis).
But `buy_eligible = False`, vetoed by **fundamental_decline_flag + peak_contamination_flag**.
Revenue series (FY, $M): 2023:115.5 -> 2024Q-mix -> **2024:112.9 -> 2025:107.1** (note the even-year
political-ad bump in the 2024 line and the 2025 decline). Latest net income **-$7.9M**, latest year
below the cyclical average (contamination_ratio 0.386). The +80% MoS is an artifact of normalizing
FCF across an even-year (election advertising) peak — exactly the V-shape the v0.3.0 veto is built to
catch. **Correctly blocked.**

### TV (Grupo Televisa) — buy_eligible but no numeric MoS
TV is the only name with `buy_eligible = True` and an empty `buy_ineligible_reasons` list. But its
`margin_of_safety_pct = None` (mos_null_reason: `intrinsic_band_unavailable`) — as a foreign 20-F
filer, cash / debt / shares / dep&amort / capex are all unavailable in XBRL, so no intrinsic band can
be built. It passes `buy_eligible` only because the financial-data-dependent guards (decline,
contamination, extreme-MoS) **cannot evaluate without data** — a silent buy_eligible=True that the
NEW BUY rule's "**numeric MoS >= 30**" clause correctly catches. **NOT a BUY** (and would be a data
artifact if it were). This is a clean demonstration that the numeric-MoS gate is load-bearing on top
of buy_eligible.

---

## 5. Code-paths exercised (the focus of this test)

- **`fundamental_decline_veto`** — fired on SGA, SSP, EVC, SBGI (rev_slope_sign=-1, latest below avg).
- **`peak_contamination_veto`** — fired on **8 of 9** (all except TV, which has no series at all).
  This is the core V-shape / even-year-peak detector and it dominated this declining-cyclical theme.
- **`extreme_mos_review_required`** — GTN (-835%), SSP (-549%): reverse-DCF implies the market is
  pricing in steep decline; the absurd negative MoS is flagged not trusted.
- **`fcf_cap_model_unsuitable` (debt>0.62 of assets)** — IHRT (debt/assets=1.03) -> routed to NAV.
- **`debt_truncation_suspected` + `cross_source_mismatch`** — SBGI (SEC total_debt=$22M vs implied
  $4.9B / yfinance $4.5B; 205x gap) -> NAV basis, flagged.
- **`cross_source_mismatch`** — NMAX (SEC $119M vs yfinance $8.3M debt, 14x).
- **`financial_sic_forced_unsuitable` + `insurance_concepts_present`** — TSQ (DeferredPolicyAcquisitionCosts
  concept present -> fcf_cap unsuitable -> NAV).
- **`intrinsic_band_null` / numeric-MoS gate** — TV (foreign filer, no financials).
- **NAV fallback** — TSQ, IHRT, SBGI all routed fcf_cap -> nav; all returned nav MoS = -100%.

Every one of the v0.3.0 guards named in the BUY rule was exercised by at least one candidate. The
declining-sector / peak-veto path is the dominant story: the whole sub-industry rides the 2-year
US political-advertising cycle (even-year revenue/EBITDA peaks, odd-year troughs), every name's
latest FY sits below its 5-year normalized average, and the veto fired across the board.

---

## 6. Adversarial verification

No mechanical BUY exists, so there is no BUY to adversarially defend. The adversarial question is
instead inverted: **did the vetoes wrongly suppress a real opportunity?** Spot-check on SGA (the only
name with a large positive MoS): the +80% MoS is built on trailing-5yr-average FCF that includes a
2024 even-year advertising peak; 2025 revenue and net income are both below trend and net income is
negative. A skeptical PM would not pay for a "margin of safety" that depends on the next election
cycle re-inflating ad revenue. The veto is **correct, not a false negative**. The structural
trajectory (cord-cutting, secular ad-dollar migration to digital/streaming, retransmission plateau)
corroborates the mechanical decline flags. Verdict: **the 0-BUY outcome is honest, not over-conservative.**

---

## 7. Data-quality issues

- **No SIC recall floor** for broadcasting (THEME_SIC lacks 4832/4833) — recall floor absent;
  FTS-only recall. Canonical names still caught, but the floor guarantee is missing for this theme.
- **Foreign-filer data gaps (20-F):** TV (Televisa) has essentially no usable XBRL financials
  (cash/debt/shares/capex all null) -> intrinsic band unavailable -> buy_eligible=True with null MoS.
  Many Chinese 20-F misrecalls had table-of-contents-only blurbs (low blurb signal; SIC + name
  carried the theme-fit judgment).
- **Cross-source debt disagreement:** SBGI (205x) and NMAX (14x) SEC-vs-yfinance total_debt
  mismatches -> correctly flagged `cross_source_mismatch`, NAV/route adjustments applied.
- **Debt truncation:** SBGI reported total_debt $22M vs implied $4.9B — a classic XBRL tag-scope
  truncation, caught.
- **Negative-net-income everywhere:** all 9 have non-positive latest net income -> PE null; this is
  the sector's reality (heavy D&A + interest on leveraged broadcast roll-ups), not a data bug.

---

## 8. recall@gold

**n/a** — local-broadcasting is not in `track_forward.THEME_GOLD` (the gold lists are deathcare,
water-utilities, railcar-leasing, regional-gaming). `track_forward.py --recall-gold` returned
"no gold list for theme 'local-broadcasting' — not measurable." No recall metric recorded.

---

## 9. T2 analyst context (market-intel / Trends — NON-binding, does NOT drive buy_eligible)

TrendsMCP quota was exhausted for the day (5/5 daily, 100/100 monthly) so no live trend pull was
attached. Structural T2 context (analyst knowledge, not a model input): US local broadcasting is a
**secularly declining, politically-cyclical** sub-industry. Linear-TV and terrestrial-radio audiences
erode to streaming/podcasts/digital; the one structural support — retransmission consent fees and
even-year political ad surges — is plateauing as cord-cutting shrinks the subscriber base that pays
retrans. This is precisely the regime where a naive trailing-average DCF manufactures phantom margins
of safety off the last election peak. The skill's peak-contamination veto is the correct response and
its 0-BUY output is consistent with the sector reality. **This paragraph is firewalled from the BUY
logic — it informed none of the mechanical verdicts.**

---

## 10. Skeptical-PM usable verdict

**USABLE — yes.** The run is a clean negative: from a 102-name FTS over-recall it isolated the 9
genuine US/foreign small-cap broadcasters, correctly dropped 36 misrecalls (Chinese internet, BDCs,
ETFs, OOH, cable programmers), and returned **zero BUYs** with every rejection traceable to a named,
sector-appropriate veto. The two near-misses (SGA's vetoed +80% MoS; TV's buy_eligible-but-null-MoS)
both demonstrate the v0.3.0 guards working as designed against exactly the failure mode this theme
was chosen to stress (declining-sector V-shape / peak contamination). A PM gets an accurate "nothing
to buy here, and here is the mechanical reason for each name" — which is the skill's intended landmine-
scanner output, not a buy list.

The one caveat to flag upward: **no SIC recall floor exists for broadcasting**, so completeness rests
on FTS keywords; adding 4832/4833 to THEME_SIC would harden recall for future runs.
