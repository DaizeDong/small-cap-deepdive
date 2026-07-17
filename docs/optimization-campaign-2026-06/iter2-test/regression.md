# iter2 Regression, V-shape veto (P-A) + label fix (P-B)

Run batch: `2026-06-20_iter2-regression`
Code under test: commit `2599d66` (adds `peak_contamination_flag` V-shape veto, `low_revenue_loss_ratio` label, hygiene).
Method: targeted (no theme screen). For each ticker: `deepdive_data --ticker` then `valuation --json --ticker [--mktcap]`. FULL, every ticker deep-dived + valuated; no ERROR.json produced (all 4 clean).

mktcap overrides used: NRP $1.34B, INVA $1.66B, SIGA $310M. EU used live yfinance (no override).

## iter2 BUY rule applied
BUY := `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30%` AND `buy_eligible == true` AND zero kill-flags AND `not peak_contamination_flag`.
(`buy_eligible` itself now also requires `not peak_contamination_flag`.)

## Before / After

"Before" = behaviour of the codebase **prior to P-A** (`peak_contamination_flag` did not exist; the V-shape value trap fell through because `fundamental_decline_flag` is gated on `rev_slope_sign < 0`, and a trough→peak→rollover has whole-window slope = +1). "After" = observed under `2599d66`.

| Ticker | contam_ratio | rev_slope | below_avg | latest_NI | fund_decline_flag | peak_contam_flag (BEFORE→AFTER) | buy_eligible (BEFORE→AFTER) | MoS / basis | BUY (BEFORE→AFTER) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **NRP** | 0.7445 | +1 | True | -$84.8M | False | (n/a) → **True** | True → **False** | 36.4% / fcf_cap | **BUY → 避开** | ✅ V-shape trap killed |
| **INVA** | 0.9015 | +1 | True | (NI N/A, +) | False | False → False | True → **True** | 30.2% / fcf_cap | (clean) → **买入 BUY** | ✅ clean grower NOT over-blocked |
| **EU** | 0.8808 | +1 | **False** | loss | False | False → **False** | True → True | null / fcf_cap | not-BUY → 观察 | ✅ genuine trough-recovery NOT over-vetoed |
| **SIGA** | 0.9051 | -1 | True | +$23M | **True** | False → False | False → **False** | null (use nav) / nav | 避开 → 避开 | ✅ still double-blocked |

### Why each lands where it does (after)
- **NRP**, `contamination_ratio 0.7445 < 0.8` AND `latest_below_avg` AND `latest_NI = -$84.8M < 0` ⇒ `peak_contamination_flag = True`. `fundamental_decline_flag` stays **False** (slope = +1, so the OLD veto misses it entirely). P-A is the only thing catching it. `buy_eligible → False (reasons=['peak_contamination_flag'])`. Without P-A this name was a 36.4%-MoS mechanical BUY, exactly the melting-ice-cube it now rejects.
- **INVA**, `peak_contam False` (loss-making test fails / contam 0.90 ≥ 0.8), `fund_decline False`, zero kill-flags, `buy_eligible True`, MoS 30.2% ≥ 30, basis fcf_cap ⇒ **买入**. The new veto did NOT touch the clean grower.
- **EU**, `latest_below_avg = False` (genuine trough-RECOVERY: latest base is at/above trailing avg), so `peak_contamination_flag = False` even though contam 0.88 < 1. This is the key guard against the veto being too aggressive: a real recovery is not punished. `buy_eligible True`, but MoS is **null** (`intrinsic_band_unavailable`: normalized FCF non-positive) so the BUY threshold can't be met ⇒ 观察, on fundamentals not on the veto.
- **SIGA**, double-blocked exactly as expected: `concentration_kill` (top customer 75.0%, BARDA) **AND** `fundamental_decline_flag` (slope -1, contam 0.9051, below_avg). `buy_eligible → False (reasons=['concentration_kill','fundamental_decline_flag'])`. fcf_cap model blocked (data-quality guard) → routes to NAV, NAV MoS negative.

## Confirmations vs spec, all 4 PASS
1. NRP `peak_contamination_flag = True` → `buy_eligible = False` (V-shape trap killed). ✅
2. INVA `buy_eligible = True` (clean grower NOT over-blocked). ✅
3. EU `peak_contamination_flag = False` (genuine trough-recovery NOT over-vetoed, guard against the veto being too aggressive holds). ✅
4. SIGA still double-blocked (`concentration_kill` + `fundamental_decline_flag`). ✅

## Surprises / notes
- **No BUY-count blow-up:** P-A removes NRP from BUY without dragging in INVA (still BUY), the veto is surgical, not a blanket loss-making screen. EU's exclusion is driven by null MoS, NOT by the new veto, which is the desired separation of concerns.
- **`peak_contamination_flag` is a buy_eligible veto, NOT counted in the ranking "kill-flag" column.** In `RANKING.md` NRP shows `kill-flag = 0` yet is sunk to 避开 (via rating, not kill-count). This is internally consistent (the flag flips `buy_eligible`/rating rather than incrementing the kill-flag tally) but is worth flagging: a reader scanning only the kill-flag column would not see why NRP is rejected. The reason surfaces in the valuation block (`reasons=['peak_contamination_flag']`) and data_quality (`peak_contamination_veto:...`).
- **EU `low_revenue_loss_ratio = False`** despite being an early-stage uranium developer with a large loss vs $43M revenue, the P-B label did not fire here (rev not tiny enough relative to the loss to trip the ratio). Not a spec requirement for EU; noted for completeness. P-B's own selftest (URG-like tiny-rev + large-loss) passes in-tree.
- INVA OCF/NI internal-trade series came back as `[]` (no insider transactions parsed), does not affect the trajectory flags or buy_eligible; net_sell label derived from the available filings.

## Artifacts
- `reports/smallcap/2026-06-20_iter2-regression/deepdive_{NRP,INVA,EU,SIGA}_2026-06-20.json`
- `reports/smallcap/2026-06-20_iter2-regression/valuation_{NRP,INVA,EU,SIGA}_2026-06-20.json`
- `reports/smallcap/2026-06-20_iter2-regression/report_{...}.md`, `deepdive_verdicts.json`, `RANKING.md`
