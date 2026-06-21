# v0.3.0 Full-Coverage Test — Spec (2026-06-20)

> Exhaustive, quality-first test of small-cap-deepdive **v0.3.0** (`764e554`) across every GICS
> sector + niche/weird pockets (hot → cold). Dual lens: **robustness** (does every code path behave
> correctly everywhere; zero false BUYs; correct routing; decision-ready reports) **and alpha** (any
> clean BUY market-wide, adversarially verified). Full data — no sampling; retries not skips;
> synchronous theme completion (the iter2 fix). EDGAR rate-limit is the binding constraint, so themes
> run in **throttled waves of ~5**, not all at once.

## Scale & cost (approved: tier C exhaustive)
- ~48 new themes + 3 regression anchors + 3 newly-built `recall@gold` gold lists.
- ~10–12M output tokens (±50%), ~14–20h wall-clock (EDGAR-bound), background + resumable.
- Per theme ≈ 200–250k tokens, ~40–75 min; ~5 concurrent → ~10 waves.

## Pre-step (controller, before launch): build 3 new gold lists
Add to `tools/track_forward.py` `THEME_GOLD` + `tools/filter_by_sic.py` theme→SIC map, with selftest:
- **water-utilities** (SIC 4941): YORW, ARTNA, MSEX, GWRS, CWCO, PCYO, SJW, CWT, AWR
- **railcar-leasing** (SIC 4741/6726): GATX, TRN, GBX, WAB, RAIL
- **regional-gaming** (SIC 7990/7011): BYD, RRR, MCRI, GDEN, CNTY, FLL, ELYS, ACEL
(These make recall a measured floor on 4 themes total incl. deathcare.)

## Theme list (~48 new, by GICS sector)
Tags: 🔥hot ⚪mid 🧊cold. Code-path = the v0.3.0 mechanism each is chosen to stress.

### Energy
| slug | keywords | tag | code-path |
|---|---|---|---|
| coal-metcoal | coal, metallurgical coal, thermal coal | 🧊 | cyclical normalization, going-concern |
| midstream-mlp | midstream, pipeline, gathering processing | ⚪ | MLP distributions, financial-ish routing |
| refiners | petroleum refining, fuel distribution | ⚪ | cyclical, thin margins |

### Materials
| gold-silver-miners | gold mining, silver mining, precious metals | ⚪ | foreign/IFRS, pre-revenue, low_revenue_loss |
| lithium-battery-materials | lithium, battery materials, cathode anode | 🔥 | pre-rev, peak_contamination (post-boom rollover) |
| rare-earths | rare earth, critical minerals, permanent magnets | 🔥 | pre-rev, concentration (single offtake) |
| timber-forest | timber, forest products, lumber | 🧊 | REIT/NAV overlap, cyclical |
| steel-fab | steel, steelmaking, metal fabrication | ⚪ | cyclical normalization |

### Industrials
| waste-recycling | waste management, recycling, environmental services | 🧊 | defensive, stable-FCF (clean BUY candidate) |
| building-products-hvac | building products, HVAC, insulation | ⚪ | housing cyclical |
| machinery | industrial machinery, capital equipment | ⚪ | cyclical, EBIT cascade |
| railcar-leasing★ | railcar, equipment leasing, rolling stock | ⚪ | asset-heavy NAV routing |
| industrial-distribution | industrial distribution, MRO supply | ⚪ | working-capital, mid |
| logistics-3pl | logistics, third-party logistics, supply chain | ⚪ | asset-light vs asset-heavy |

### Information Technology
| semiconductors | semiconductor, chip design, fabless | 🔥 | cyclical, growth-vs-V-shape veto |
| semicap-equipment | semiconductor equipment, wafer fab tools | 🔥 | cyclical peak/trough |
| cybersecurity | cybersecurity, network security, endpoint | 🔥 | SaaS, OCF-proxy, growth |
| enterprise-saas | enterprise software, SaaS, cloud platform | ⚪ | V-shape veto on decelerators |
| quantum-computing | quantum computing, quantum hardware | 🔥 | pre-rev abstain, low_revenue_loss |
| it-services | IT services, managed services, consulting | 🧊 | mature, clean-FCF candidate |

### Health Care
| biotech-clinical | clinical stage biotech, drug development | 🔥 | pre-rev binary, going-concern, abstain discipline |
| medtech-devices | medical devices, surgical instruments | ⚪ | mid, EBIT cascade |
| cdmo-cro | contract drug manufacturing, CDMO, CRO | ⚪ | customer concentration kill |
| diagnostics | diagnostics, clinical testing, molecular | ⚪ | growth, reimbursement risk |
| healthcare-services | healthcare services, clinics, physician practice | 🧊 | leverage, roll-up debt |
| animal-health | animal health, veterinary, pet care | ⚪ | niche, mid |

### Financials (stress financial-SIC / BDC / NAV exclusion — expect mostly nav/abstain)
| bdc | business development company, middle market lending | ⚪ | BDC fallback (no-SIC) routing |
| mortgage-reit | mortgage REIT, MBS, real estate finance | ⚪ | financial-SIC nav, book≠liquidation |
| insurance-brokers | insurance brokerage, benefits broker | ⚪ | financial-SIC, fee model |
| consumer-finance-pawn | consumer finance, pawn, installment lending | 🧊 | financial, regulatory |
| asset-managers | asset management, investment manager | ⚪ | financial, AUM-fee |

### Consumer Discretionary
| restaurants | restaurant chains, quick service, casual dining | ⚪ | unit economics, lease-heavy |
| specialty-retail | specialty retail, retail stores | ⚪ | cyclical, lease-heavy |
| regional-gaming★ | casino, gaming, regional gaming | 🧊 | debt/lease-heavy, cyclical |
| homebuilders-land | homebuilder, residential construction, land | ⚪ | cyclical, inventory/NAV |
| auto-parts-dealers | auto parts, automotive aftermarket, dealerships | ⚪ | cyclical, floorplan debt |

### Consumer Staples
| beverages | beverages, non-alcoholic, craft beverage | ⚪ | mature, brand |
| household-personal | household products, personal care | 🧊 | mature, low-growth |
| tobacco-alternatives | tobacco, nicotine, vaping alternatives | 🧊 | declining, high-FCF (clean-BUY candidate) |

### Communication Services
| rural-telecom-fiber | rural telecom, fiber broadband, local exchange | 🧊 | capital-intensive, debt |
| local-broadcasting | broadcasting, local television, radio | 🧊 | **declining → V-shape/peak veto stress** |
| adtech | advertising technology, digital advertising | ⚪ | growth, cyclical ad spend |

### Utilities
| water-utilities★ | water utility, water infrastructure | 🧊 | regulated, dividend total-return |
| ipp-renewables | independent power, renewable generation | 🔥 | capital-intensive, project finance |

### Real Estate (stress REIT/financial path)
| niche-reits | data center REIT, cell tower REIT, specialty REIT | 🔥 | REIT routing, FFO not FCF |
| farmland-timber-reit | farmland REIT, timber REIT, agricultural land | 🧊 | NAV, niche REIT |

### Cross / weird (stress + diversity)
| cannabis | cannabis, marijuana, hemp | 🧊 | regulatory limbo, going-concern, dilution |
| space-economy | space, satellite, launch services | 🔥 | pre-rev, de-SPAC, low_revenue_loss |
| spac-derived-micro | de-SPAC, special purpose acquisition company | 🧊 | **cross-source / wrong-entity / data-quality stress** |
| for-profit-education | for-profit education, career training, online learning | 🧊 | regulatory, declining |

★ = has a `recall@gold` gold list (measured recall floor).

## Regression anchors (3, re-run under v0.3.0 for consistency)
- **oilsvc** (cyclical, vs iter), **regbank** (financial-SIC + P5 recall), **deathcare** (recall@gold baseline 100%).

## Per-theme execution (each agent, SYNCHRONOUS — the iter2 fix)
1. `export SMALLCAP_RUN=$(python tools/new_run.py --label cov-<slug>)`.
2. Full pipeline: `run_theme` (discover + SIC-reverse-recall + mktcap-fallback → cheap_pass → SIC gate) → LLM theme-fit → deep-dive **every** deep-band survivor (`deepdive_data` + `valuation`, both `--json` and `--ticker`/`--mktcap`) → `buy_eligible` BUY rule → `finalize_run` (reports + verdicts + RANKING + trust banner) → `rank`.
3. `recall@gold` if a gold list exists; `signals` diagnostic is emitted (firewalled — never affects BUY).
4. Independent report → `docs/coverage-test-2026-06-20/themes/<slug>.md`.
5. Structured return: `{sector, slug, hotness, code_paths_exercised[], funnel, mos_basis_dist, buys[{ticker,mos,buy_ineligible_reasons,adversarial_verdict}], data_quality_issues[], recall_at_gold, usable_verdict}`.

## Quality rules (non-negotiable)
Full data (deep-dive every survivor, no sampling); retries on rate-limit, never silent skip (deepdive writes `*_ERROR.json` on crash); synchronous completion (no "still running" returns); finalize_run determinism.

## Aggregation (final synthesis agent → `docs/coverage-test-2026-06-20/_aggregate.md`)
1. **Code-path coverage matrix** — each v0.3.0 path (financial-SIC/BDC, foreign-IFRS, pre-rev abstain, cyclical, concentration kill, V-shape/peak veto, REIT/NAV, cross-source, low-rev-loss, EBIT cascade, recall floor) × did it fire correctly, where, any misbehavior.
2. **Clean-BUY list** — every market-wide BUY that survived adversarial verification (expected: very few; 0-BUY is the common honest output).
3. **recall@gold** results across the 4 gold-list themes.
4. **Data-quality issues found** → prioritized **v0.3.1 backlog** (this is the test's main yield).
5. **Overall verdict** on v0.3.0 cross-sector robustness.

## Execution mechanics
One background workflow: ~48+3 themes chunked into waves of ~5 (sequential phases → ~5 EDGAR-concurrent), then the synthesis agent. Resumable via `resumeFromRunId` if interrupted. Throttling waves (not 14-wide) is deliberate — EDGAR, not agent count, is the limit.
