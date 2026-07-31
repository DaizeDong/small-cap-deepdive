# Documentation index

The methodology lives in [`../SKILL.md`](../SKILL.md) and [`../reference/`](../reference) (the
single source of truth). **This folder is dated evidence: append-only by design.** Each subtree is
the raw output of one study, kept because two shipped guards and one shipped kill-flag rest on it,
and because a claim with no reproducible evidence behind it is a claim this repo does not make.
None of it is loaded into agent context during a run, so it costs nothing to keep.

Four subtrees, newest first. Every tracked file is indexed below.

---

## Backtest, 2026-06 (v0.3.3), the out-of-sample study

[`backtest-2026-06/`](backtest-2026-06) The 25-cell survivorship-safe point-in-time backtest
(5 themes × 5 as-of dates 2020 to 2024, 12mo horizon) that produced both the honest negative
(no durable alpha) and the CORE-4 distress kill-flag.

- **[`ROOT_CAUSE_AND_DERISK_EDGE.md`](backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md)**, start
  here: why the decision layer threw away a usable signal, why the Margin-of-Safety edge does not
  generalize, and the cluster-robust de-risk edge that does. Includes the adversarial review and
  the caveats it forced.
- [`spec.md`](backtest-2026-06/spec.md), the study design.
- [`_aggregate.md`](backtest-2026-06/_aggregate.md), pooled cell-level results.
- Reproduction scripts: [`distress_features_fast.py`](backtest-2026-06/distress_features_fast.py)
  (build / validate the PIT feature set),
  [`distress_features_extract.py`](backtest-2026-06/distress_features_extract.py) (the slower
  extractor it replaced), [`distress_oos_validate2.py`](backtest-2026-06/distress_oos_validate2.py)
  (the cluster-robust OOS verdict),
  [`distress_oos_validate.py`](backtest-2026-06/distress_oos_validate.py) (the earlier, superseded
  validator), [`significance_test.py`](backtest-2026-06/significance_test.py) (permutation tests on
  the alpha claim).
- `distress_features.json` and the `_*.log` / `_before_blowup_avoid.json` files are the study's raw
  data artifacts. Caveat carried in the write-up: the JSON stores `{end, val}` only, so PIT
  correctness is inherited from the validated `_deepdive_concepts` code path, not self-audited from
  the artifact.

## Coverage test, 2026-06-20 (drove v0.3.1), 53 themes

[`coverage-test-2026-06-20/`](coverage-test-2026-06-20) One run per theme across all GICS sectors
plus niche. It confirmed 0 false BUYs leaked and found the degenerate-base hole and the debt
truncation bug that v0.3.1 fixed.

- **[`_aggregate.md`](coverage-test-2026-06-20/_aggregate.md)**, start here: the cross-theme roll-up
  and the numbered defect list v0.3.1 works through.
- [`spec.md`](coverage-test-2026-06-20/spec.md), the test design and per-theme protocol.
- [`themes/`](coverage-test-2026-06-20/themes), 53 per-theme reports, one file per theme. These are
  the primary evidence for the recall floors and precision guards added in v0.3.1; read the one
  matching your theme before assuming a gate behaves generically. Index:
  [adtech](coverage-test-2026-06-20/themes/adtech.md) ·
  [animal-health](coverage-test-2026-06-20/themes/animal-health.md) ·
  [asset-managers](coverage-test-2026-06-20/themes/asset-managers.md) ·
  [auto-parts-dealers](coverage-test-2026-06-20/themes/auto-parts-dealers.md) ·
  [bdc](coverage-test-2026-06-20/themes/bdc.md) ·
  [beverages](coverage-test-2026-06-20/themes/beverages.md) ·
  [biotech-clinical](coverage-test-2026-06-20/themes/biotech-clinical.md) ·
  [building-products-hvac](coverage-test-2026-06-20/themes/building-products-hvac.md) ·
  [cannabis](coverage-test-2026-06-20/themes/cannabis.md) ·
  [cdmo-cro](coverage-test-2026-06-20/themes/cdmo-cro.md) ·
  [coal-metcoal](coverage-test-2026-06-20/themes/coal-metcoal.md) ·
  [consumer-finance-pawn](coverage-test-2026-06-20/themes/consumer-finance-pawn.md) ·
  [cybersecurity](coverage-test-2026-06-20/themes/cybersecurity.md) ·
  [deathcare](coverage-test-2026-06-20/themes/deathcare.md) ·
  [diagnostics](coverage-test-2026-06-20/themes/diagnostics.md) ·
  [enterprise-saas](coverage-test-2026-06-20/themes/enterprise-saas.md) ·
  [farmland-timber-reit](coverage-test-2026-06-20/themes/farmland-timber-reit.md) ·
  [for-profit-education](coverage-test-2026-06-20/themes/for-profit-education.md) ·
  [gold-silver-miners](coverage-test-2026-06-20/themes/gold-silver-miners.md) ·
  [healthcare-services](coverage-test-2026-06-20/themes/healthcare-services.md) ·
  [homebuilders-land](coverage-test-2026-06-20/themes/homebuilders-land.md) ·
  [household-personal](coverage-test-2026-06-20/themes/household-personal.md) ·
  [industrial-distribution](coverage-test-2026-06-20/themes/industrial-distribution.md) ·
  [insurance-brokers](coverage-test-2026-06-20/themes/insurance-brokers.md) ·
  [ipp-renewables](coverage-test-2026-06-20/themes/ipp-renewables.md) ·
  [it-services](coverage-test-2026-06-20/themes/it-services.md) ·
  [lithium-battery-materials](coverage-test-2026-06-20/themes/lithium-battery-materials.md) ·
  [local-broadcasting](coverage-test-2026-06-20/themes/local-broadcasting.md) ·
  [logistics-3pl](coverage-test-2026-06-20/themes/logistics-3pl.md) ·
  [machinery](coverage-test-2026-06-20/themes/machinery.md) ·
  [medtech-devices](coverage-test-2026-06-20/themes/medtech-devices.md) ·
  [midstream-mlp](coverage-test-2026-06-20/themes/midstream-mlp.md) ·
  [mortgage-reit](coverage-test-2026-06-20/themes/mortgage-reit.md) ·
  [niche-reits](coverage-test-2026-06-20/themes/niche-reits.md) ·
  [oilsvc](coverage-test-2026-06-20/themes/oilsvc.md) ·
  [quantum-computing](coverage-test-2026-06-20/themes/quantum-computing.md) ·
  [railcar-leasing](coverage-test-2026-06-20/themes/railcar-leasing.md) ·
  [rare-earths](coverage-test-2026-06-20/themes/rare-earths.md) ·
  [refiners](coverage-test-2026-06-20/themes/refiners.md) ·
  [regbank](coverage-test-2026-06-20/themes/regbank.md) ·
  [regional-gaming](coverage-test-2026-06-20/themes/regional-gaming.md) ·
  [restaurants](coverage-test-2026-06-20/themes/restaurants.md) ·
  [rural-telecom-fiber](coverage-test-2026-06-20/themes/rural-telecom-fiber.md) ·
  [semicap-equipment](coverage-test-2026-06-20/themes/semicap-equipment.md) ·
  [semiconductors](coverage-test-2026-06-20/themes/semiconductors.md) ·
  [spac-derived-micro](coverage-test-2026-06-20/themes/spac-derived-micro.md) ·
  [space-economy](coverage-test-2026-06-20/themes/space-economy.md) ·
  [specialty-retail](coverage-test-2026-06-20/themes/specialty-retail.md) ·
  [steel-fab](coverage-test-2026-06-20/themes/steel-fab.md) ·
  [timber-forest](coverage-test-2026-06-20/themes/timber-forest.md) ·
  [tobacco-alternatives](coverage-test-2026-06-20/themes/tobacco-alternatives.md) ·
  [waste-recycling](coverage-test-2026-06-20/themes/waste-recycling.md) ·
  [water-utilities](coverage-test-2026-06-20/themes/water-utilities.md)

## Optimization campaign, 2026-06 (v0.3.0)

[`optimization-campaign-2026-06/`](optimization-campaign-2026-06) The 5-iteration, subagent-driven,
test-driven campaign that turned a value-trap generator into a calibrated landmine scanner.

- **[`2026-06-20-campaign-final-report.md`](optimization-campaign-2026-06/2026-06-20-campaign-final-report.md)**,
  start here: the 5-iteration summary, all four original diagnoses closed, and the forward roadmap.
- [`2026-06-20-smallcap-optimization-design.md`](optimization-campaign-2026-06/2026-06-20-smallcap-optimization-design.md),
  the design and the single human approval gate.
- [`2026-06-20-optimization-campaign-progress.md`](optimization-campaign-2026-06/2026-06-20-optimization-campaign-progress.md),
  per-iteration progress tracker.
- [`iter1-test/`](optimization-campaign-2026-06/iter1-test):
  [`_assessment.md`](optimization-campaign-2026-06/iter1-test/_assessment.md) (the real-world-usable
  verdict) ·
  [`new-royalty-streaming.md`](optimization-campaign-2026-06/iter1-test/new-royalty-streaming.md) ·
  [`new-uranium-miners.md`](optimization-campaign-2026-06/iter1-test/new-uranium-miners.md) ·
  [`old-recall-p5.md`](optimization-campaign-2026-06/iter1-test/old-recall-p5.md).
- [`iter2-test/`](optimization-campaign-2026-06/iter2-test):
  [`_assessment.md`](optimization-campaign-2026-06/iter2-test/_assessment.md) ·
  [`regression.md`](optimization-campaign-2026-06/iter2-test/regression.md) (the TUSK / SIGA / NRP
  regression set) · [`ai-dc-power.md`](optimization-campaign-2026-06/iter2-test/ai-dc-power.md) ·
  [`defense-drones.md`](optimization-campaign-2026-06/iter2-test/defense-drones.md) ·
  [`glp1-supply.md`](optimization-campaign-2026-06/iter2-test/glp1-supply.md) ·
  [`title-insurance.md`](optimization-campaign-2026-06/iter2-test/title-insurance.md).

## Validation campaign, 2026-06-19 (drove v0.2.1)

- [`2026-06-19-validation-report.md`](2026-06-19-validation-report.md), the 21-subagent campaign
  (8 themes + 3 trigger-diagnostics + 3 event-driven + 4 robustness + 2 precision + synthesis).
  Finding: the BUY trigger is reachable, not logically dead, but on real data every BUY was a
  data-layer false positive. These are the findings the v0.2.1 guards answer.
