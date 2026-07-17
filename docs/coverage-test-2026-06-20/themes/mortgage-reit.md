# Coverage Test, Theme: mortgage-reit (Financials)

**Skill version:** small-cap-deepdive v0.3.0 @ `f12fef5` (run manifest records `skill_dirty: true`, working tree had uncommitted changes at run time; no tool source was edited by this agent).
**Run batch:** `reports/smallcap/2026-06-21_cov-mortgage-reit/`
**Theme keywords:** `mortgage REIT, mortgage-backed securities, real estate finance`
**Code-path focus:** financial-SIC → NAV routing; `book != liquidation` guards.
**Date:** 2026-06-21 (run executed under batch label `cov-mortgage-reit`).
**Status:** RESEARCH OUTPUT, landmine scanner, not a buy list.

---

## 1. Headline

**Zero clean BUYs. Expected and correct.** This is the canonical stress case for the
financial-SIC code path: every genuine mortgage REIT is SIC 6798 (prefix 67), which
`valuation.py` forces to `mos_basis = nav` and `buy_eligible = false` via
`financial_sic_forced_unsuitable`. No FCF-cap BUY is structurally reachable for a true
mREIT, and the one name that escaped the financial-SIC prefix (KW, SIC 6500) trades
*above* tangible book (NAV MoS −21.4%), failing the MoS ≥ 30 threshold. The pipeline
behaved exactly as the v0.3.0 guards intend.

---

## 2. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw recall (deduped) | 92 | 3 keywords; `mortgage REIT`=48 + MBS + real estate finance, deduped to 92 |
| SIC reverse-recall floor | n/a | `mortgage-reit` has **no `THEME_SIC` entry** → floor is a no-op (FTS-only recall) |
| Market-cap band split | 54 deep / 14 watch | deep = mktcap < $2.0B; watch = $2.0 to 5.0B |
| cheap_pass survivors | 48 | 0 hard kill-flags (going-concern / death-spiral / material-weakness); banks+insurers survive cheap_pass |
| SIC Gate-1 | 48 (1 keep, 47 review) | almost all are financial SIC → "review" tier → passed to LLM gate (not auto-dropped) |
| Deep-band candidates | 35 | the 35 with band=deep |
| **Gate-2 LLM theme-fit (my call)** | **22 pass / 13 misrecall** | 20 pure_play + 2 partial; 13 misrecall (8 banks, 4 insurers, 1 asset-manager) |
| Deep-dived (deepdive + valuation + report) | 22 | every Gate-2 survivor; **0 ERROR files**, 0 missing |
| **Clean mechanical BUYs** | **0** |, |

`finalize_run` reconciliation: `deep-band candidates: 35, reports: 22, gate2-misrecall (resolved): 13, missing: 0`.

### Gate-2 theme-fit decisions (all 35 deep-band)

**pure_play (20)**, core mortgage/RE-credit balance sheets:
SEVN, REFI, CMTG, BRSP, ARI, FBRT, GPMT, CHMI, EARN, NREF, KREF, IVR, MITN, TWO, ORC, ACRE, EFC, CIM, RPT, ADAM.

**partial (2)**, real-estate-related but not pure mortgage credit:
NXDT (NexPoint Diversified RET, diversified RE, not pure mortgage), KW (Kennedy-Wilson, RE equity investor + investment manager with some debt).

**misrecall (13, dropped before deep-dive):**
- Deposit-taking banks (8): GCBC, NFBK, INBK, FBIZ, FISI, FMCB, NPB, EQBK, these hit the keyword via mortgage-lending language but are bank holding companies, not mREITs.
- Insurers (4): BOW, SAFT, AMSF, GBLI, specialty/workers-comp/P&C carriers (SIC 6331); off-theme.
- Asset manager (1): RMR (SIC 8742), manages REITs but is itself a management company, not a RE-finance balance sheet.

The canonical FTS over-recall pattern held: banks and insurers tripped the keywords ("mortgage", "real estate finance") but are structurally outside the theme. The SIC Gate-1 sent them to "review" (correct, it does not auto-drop financial SICs because the theme *is* financial); Gate-2 LLM judgment removed them.

---

## 3. MoS-basis distribution

| mos_basis | count | meaning |
|---|---|---|
| `nav` | 22 | **100% of deep-dived names**, every true mREIT + the 2 partials routed to NAV |
| `fcf_cap` | 0 | none, financial-SIC + leverage guards block the FCF model entirely |
| `abstain` | 0 | every name had book equity available, so NAV (not abstain) was reachable |

This is the defining result for the code-path under test: **the financial sector never reaches the FCF-cap model.** SIC prefix 67 (REIT/holdco) forces `_financial_sic_forced_unsuitable = True`, which sets `mos_basis = nav` whenever equity is available.

---

## 4. The BUY rule, applied to all 22

BUY requires: `mos_basis ∈ {fcf_cap, nav}` AND numeric active-MoS ≥ 30 AND `buy_eligible == true` AND zero kill-flags.

| ticker | NAV MoS | buy_eligible | kill-flags | buy_ineligible_reasons | BUY? |
|---|---:|---|---:|---|---|
| GPMT | +587.7% | false | 0 | extreme_mos_review, financial_sic, peak_contamination | no |
| CMTG | +413.4% | false | 0 | extreme_mos_review | no |
| NXDT | +130.4% | false | 0 | extreme_mos_review, financial_sic | no |
| CHMI | +110.2% | false | 0 | extreme_mos_review, financial_sic, cross_source_mismatch | no |
| RPT | +105.2% | false | 0 | extreme_mos_review, financial_sic | no |
| KREF | +93.1% | false | 0 | financial_sic, peak_contamination | no |
| CIM | +77.4% | false | 0 | financial_sic, debt_truncation, cross_source_mismatch | no |
| ACRE | +53.7% | false | 0 | financial_sic, fundamental_decline, peak_contamination | no |
| TWO | +51.9% | false | 0 | financial_sic, peak_contamination | no |
| FBRT | +46.3% | false | 0 | financial_sic, debt_truncation, cross_source_mismatch | no |
| SEVN | +41.2% | false | 0 | financial_sic | no |
| ADAM | +39.8% | false | 0 | financial_sic, debt_truncation, cross_source_mismatch | no |
| EARN | +10.8% | false | 0 | financial_sic | no |
| ARI | +2.2% | false | 0 | financial_sic, fundamental_decline, cross_source_mismatch | no |
| BRSP | +1.7% | false | 0 | financial_sic | no |
| REFI | −0.5% | false | 0 | financial_sic, cross_source_mismatch | no |
| EFC | −8.9% | false | 0 | debt_truncation_suspected | no |
| IVR | −10.8% | false | 0 | financial_sic, cross_source_mismatch | no |
| ORC | −17.2% | false | 0 | financial_sic | no |
| **KW** | **−21.4%** | **true** | 0 | (none) | **no, fails MoS ≥ 30** |
| MITN | −46.1% | false | 0 | financial_sic, debt_truncation | no |
| NREF | −68.6% | false | 0 | financial_sic, cross_source_mismatch | no |

**Result: 0 clean BUYs.**

The names with the *largest* apparent NAV MoS (GPMT +588%, CMTG +413%, NXDT +130%, CHMI +110%, RPT +105%) are precisely the ones the defense-in-depth catches, every one carries `extreme_mos_review_required` (|MoS| > 100%) and/or `cross_source_mismatch`/`debt_truncation_suspected`. A +588% "margin of safety" is never real cheapness; it is a corrupted book/debt denominator. The guards are doing their job.

---

## 5. Code-paths exercised

1. **financial-SIC NAV routing (the focus path), FIRED on 20/22.** SIC prefix 67 (6798) → `_financial_sic_forced_unsuitable` → `mos_basis = nav`, `buy_eligible = false`, reason `financial_sic_forced_unsuitable`. This is the dominant path and it fired on every SIC-6798 mREIT.
2. **`book != liquidation` discipline.** The NAV path computes tangible equity and bands it at 0.80 to 1.05×, then applies a 0.6 conviction multiplier (per rubric), explicitly because book value of a levered MBS/repo portfolio is *not* liquidation value. No mREIT can BUY off book.
3. **extreme_mos_review_required (|MoS| > 100%), FIRED on 5** (GPMT, CMTG, NXDT, CHMI, RPT). Backstop G1 caught the data-pathology tail.
4. **cross_source_mismatch (P7, yfinance vs SEC), FIRED on 7** (CHMI, CIM, FBRT, ARI, REFI, IVR, NREF, ADAM). The SEC-XBRL `total_debt` for mREITs systematically *under-captures* repo financing: CIM SEC $252M vs yf $12,734M (50.5×); ADAM $669M vs $11,155M (16.7×); ARI $773M vs $8,158M (10.5×). The first independent-feed gate, working as designed on a sector where single-source XBRL debt is unreliable.
5. **debt_truncation_suspected, FIRED on 5** (ADAM, CIM, FBRT, MITN, EFC). Internal-consistency check (reported debt vs liabilities−equity); ADAM reported $669.5M vs implied $9,876M (ratio 0.07).
6. **peak_contamination_flag (V-shape veto, P-A), FIRED on 4** (GPMT, KREF, ACRE, TWO). Trough→peak→rollover with latest net income < 0.
7. **fundamental_decline_flag (P6), FIRED on 2** (ACRE, ARI).
8. **financial-SIC hole at SIC 65xx, backstopped.** EFC and KW are SIC 6500 (real estate, *not* prefix 60/61/63/64/67), so `financial_sic` did **not** fire on them. EFC was nonetheless routed to NAV and gated by `debt_truncation_suspected` (debt/assets > 0.62 → fcf_cap_model_unsuitable). KW alone slipped every gate (`buy_eligible = true`), and was then stopped only by the MoS threshold (−21.4%). **This is a coverage observation worth flagging: the financial-SIC list excludes 65xx, so an mREIT-adjacent name registered under 6500 relies entirely on the leverage / data-integrity backstops, not the SIC gate.** Here the backstops held, but a 65xx name with low leverage and clean cross-source data could reach a BUY on the FCF path, appropriate for an equity-RE operator like KW, less so if a true mortgage lender ever registers under 6500.
9. **SIC reverse-recall floor, NOT exercised** (no `THEME_SIC['mortgage-reit']`). Recall rested on FTS alone. See data-quality note below.

---

## 6. Adversarial verification

There were **0 mechanical BUYs**, so there is nothing to adversarially confirm or reject, the honest outcome is a clean 0-BUY.

The one name worth a forced second look is the sole `buy_eligible == true`, **KW (Kennedy-Wilson)**: had its NAV MoS been ≥ 30 it would have been a mechanical BUY. Adversarial read: KW is a real-estate *equity* investor + investment manager, not a mortgage REIT, it is a Gate-2 *partial*, not a pure-play. Its `buy_eligible = true` is only because SIC 6500 dodged the financial-SIC prefix. Its NAV MoS is **−21.4%** (price above tangible book), so it is not cheap on the NAV basis the tool routed it to, and book value for a manager + carried-interest business understates intangible franchise value anyway. **Verdict: not an opportunity surfaced by this run; correctly a non-BUY.** No artifact slipped through.

`n_buy_clean = 0`.

---

## 7. Data-quality issues

1. **Systematic SEC-XBRL debt under-capture for mREITs.** Repo / secured-borrowing leverage is tagged inconsistently in XBRL; the SEC arm captured only a small notes/debt concept on many names, producing 8.8×,50.5× disagreements vs yfinance. P7 `cross_source_mismatch` caught the worst 7. **Consequence: NAV MoS for the whole sector is built on an unreliable debt denominator and must not be trusted as cheapness**, which is exactly why every NAV name is non-BUY and carries the 0.6 conviction haircut.
2. **`form_used = null` on every deepdive.** The provenance tag did not populate for any name in this run (all 22). Minor (it is advisory), but worth noting for v0.3.0, the filing-form provenance field is empty across the board for this theme.
3. **No SIC reverse-recall floor for `mortgage-reit`.** Recall is FTS-only. Mortgage REITs have a dedicated SIC (6798); adding `"mortgage-reit": ["6798"]` to `THEME_SIC` would give this theme a recall floor and let an mREIT with weak keyword density be backstopped. Today, a true 6798 mREIT that FTS missed would be silently lost. (FTS did not appear to hit the 1000-cap here, 92 deduped hits, so recall is probably acceptable, but it is unfloored by construction.)
4. **`ADAM` (Adamas Trust) revenue = $0M with $149M net income / $134M OCF.** Classic mREIT presentation (interest income not tagged as "revenue"); the loss-ratio guards are not tripped (no revenue), and NAV routing handles it, but the financial series is thin for a clean read.
5. **No recall@gold**, `mortgage-reit` is not in `THEME_GOLD`, so discovery recall could not be measured against a curated list (n/a, not a failure).

---

## 8. recall@gold

**n/a.** `mortgage-reit` has no `THEME_GOLD` entry (the gold cohorts are deathcare, water-utilities, railcar-leasing, regional-gaming). `track_forward --recall-gold` is a no-op for this theme. No discovery-floor number to report.

---

## 9. T2 diagnostic / market-intel context (context only, NOT used in any rating)

TrendsMCP was rate-exhausted at run time (0 requests remaining); substituted a labeled web search.

- **The mortgage-REIT theme is a hot, branded-ETF theme (REM ETF).** Per the world-view "hot themes = casino," alpha in a branded-ETF theme is largely captured; the skill's job here is to separate true balance sheets from concept-players, which Gate-2 did (13 misrecalls dropped).
- **Sector setup 2026: cautiously optimistic.** Anticipated Fed cuts, a steepening curve (supportive of net interest margin), healing CRE credit (KBW estimates ~81% of losses already recognized), and **persistent book-value discounts** that could narrow. Commercial mREITs (BXMT/STWD/Apollo) carry the strongest discount-and-recovery story; small-cap residential/agency names are more idiosyncratic and rate-volatility-sensitive.
- **Key takeaway for this run:** the "many mREITs trade below book" narrative is the market's own framing, but the tool's NAV path deliberately does *not* treat book as liquidation value for a levered repo portfolio, and the P7/debt-truncation guards show the book/debt inputs themselves are unreliable in single-source XBRL. The T2 "discount to book" story is exactly the value-trap the NAV haircut + extreme-MoS backstop are built to resist. This context **did not and must not** influence any `buy_eligible` decision.

Sources:
- [Nareit, Brighter Outlook for Commercial mREITs](https://www.reit.com/news/articles/brighter-outlook-for-commercial-mreits-as-recent-challenges-begin-to-fade)
- [Cohen & Steers, 2026 real estate outlook](https://www.cohenandsteers.com/insights/three-data-points-driving-our-2026-real-estate-outlook/)
- [Money for the Rest of Us, Mortgage REIT Investing guide](https://moneyfortherestofus.com/mortgage-reit-investing/)
- [Motley Fool, Mortgage REIT sector](https://www.fool.com/investing/stock-market/market-sectors/real-estate-investing/reit/mortgage-reit/)
- [U.S. News, Best REIT ETFs 2026](https://money.usnews.com/investing/articles/best-reit-etfs-to-buy-now)

---

## 10. Skeptical-PM usable verdict

**Usable: YES.** A skeptical PM gets exactly the right answer with zero spurious BUYs:

- The financial-SIC NAV path fired on 20/22 and routed the entire sector away from the FCF model, no mortgage REIT was ever allowed to "look cheap" on an inappropriate FCF basis.
- The `book != liquidation` discipline (NAV band + 0.6 haircut + extreme-MoS backstop + P7 cross-source) correctly neutralized the eye-catching +100%-to-+588% "NAV margins of safety" that are pure data pathology (under-captured repo debt).
- Gate-2 cleanly stripped 13 banks/insurers/managers that the keyword over-recall swept in.
- The one `buy_eligible` escapee (KW, SIC 6500) was caught by the MoS threshold, not luck.

The run produced a defensible, fully-covered 0-BUY shortlist with every name's non-BUY reason auditable. The two improvement notes a PM would want fed back: (a) add `6798` to `THEME_SIC` so this theme has a recall floor; (b) consider widening the financial-SIC list (or insurance-style routing) to SIC 65xx mortgage lenders, since the 6500 hole currently relies entirely on leverage/data-integrity backstops.

**Hotness:** hot (branded-ETF theme, REM). **Sector:** Financials. **Clean BUYs:** 0.
