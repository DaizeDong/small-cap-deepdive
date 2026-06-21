"""_recall.py — P8 recall@gold: measure the recall FLOOR against hand-built true-member lists.

v0.3.3 refactor: extracted verbatim from track_forward.py to shrink that orchestrator. This module
owns the recall-floor AUDIT — the THEME_GOLD true-member cohorts, the recall@gold ratio + its
five-stage loss breakdown, and the candidate/universe recall-set readers that feed them.

Imports ONLY stdlib; it NEVER imports back from track_forward (no circular import). The
orchestrator re-exports every public symbol below so the PUBLIC API (track_forward.<symbol>) is
UNCHANGED. NO behavior change — this is a pure mechanical move.
"""
from __future__ import annotations

import csv as _csv
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# P8 — recall@gold: measure the recall FLOOR against hand-built true-member lists.
# ---------------------------------------------------------------------------
# filter_by_sic owns the SIC reverse-recall (the dedicated-SIC floor) and discover
# owns the FTS keyword recall; neither one MEASURES recall. P8's missing half is the
# audit: for the handful of themes where a true-member list can be hand-built, compute
# recall@gold = |recalled ∩ gold| / |gold| so the recall floor is a NUMBER, not a manual
# blurb re-scan. THEME_GOLD maps a theme slug to its hand-curated true-member tickers.
# Matching is case-insensitive substring against the theme slug (same convention as
# filter_by_sic.theme_sics), so "deathcare", "funeral_deathcare_2026" all resolve.
#
# Deathcare gold cohort (assessment §P8): the canonical public deathcare names. SCI/CSV
# are the pure operators (SIC 7200 — caught by the SIC floor); MATW (3360 castings),
# HI (Hillenbrand, 3559), STON (StoneMor, 6553 cemeteries), SNFCA (6199 finance) are
# cross-SIC by design — they are the residual FTS-only gap the SIC floor cannot reach,
# which is exactly what recall@gold quantifies.
THEME_GOLD: dict[str, list[str]] = {
    "deathcare": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    "funeral": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    "cemetery": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    # Coverage-test gold cohorts (2026-06-20) — hand-curated public small/mid-cap members.
    "water-utilities": ["YORW", "ARTNA", "MSEX", "GWRS", "CWCO", "PCYO", "SJW", "CWT", "AWR"],
    "railcar-leasing": ["GATX", "TRN", "GBX", "RAIL"],
    "regional-gaming": ["BYD", "RRR", "MCRI", "GDEN", "CNTY", "FLL", "ACEL"],
}

# EDGAR full-text search (EFTS) returns at most this many hits per query (the documented
# top-1000 page cap). A theme whose true universe exceeds 1000 FTS hits can silently drop
# real members past the cap; recall@gold warns when the recall set is at/over the cap so a
# low recall is attributed to the cap (a known FTS limit) rather than mistaken for a clean
# floor. The SIC reverse-recall (filter_by_sic) is the mitigation; this is the alarm.
FTS_TOP_HITS_CAP = 1000

# P8 loss-stage taxonomy: where a gold true-member fell out of the funnel. recall@gold is the
# headline NUMBER; the stage breakdown is the DIAGNOSIS — it attributes each gold member to the
# exact pipeline stage that lost it (or kept it), so a low recall floor is actionable rather than
# a single opaque ratio. Stages, in pipeline order:
#   recalled_final  — survived the whole funnel into the final candidate set (a TRUE recall hit)
#   sic_recovered   — FTS missed it but the SIC reverse-recall floor caught it (the P8 win)
#   dropped_mktcap  — recalled, then dropped by the market-cap band filter (out of size scope)
#   gated_out       — survived to deep-dive, then gated out (buy_ineligible / kill-flag)
#   fts_missed      — never recalled by ANY channel and not recovered by SIC (the true leak)
# A gold member lands in exactly one stage. recalled_final ∪ sic_recovered are the recall hits;
# the rest are the recall floor's residual leak, each with a cause attached.
RECALL_STAGES = (
    "recalled_final",
    "sic_recovered",
    "dropped_mktcap",
    "gated_out",
    "fts_missed",
)


def theme_gold(theme: str, mapping: dict[str, list[str]] | None = None) -> list[str]:
    """Return the hand-built gold true-member tickers for a theme, or [] if none exist.

    P8: only themes present in THEME_GOLD have a gold list to measure recall against.
    Matching is case-insensitive substring against the theme slug (so compound slugs
    resolve). [] means recall@gold is a no-op for that theme (no gold => not measurable).
    """
    if mapping is None:
        mapping = THEME_GOLD
    t = str(theme).lower()
    out: list[str] = []
    for key, tickers in mapping.items():
        if key in t:
            for tk in tickers:
                if tk.upper() not in out:
                    out.append(tk.upper())
    return out


def recall_stage_breakdown(
    gold,
    recalled_tickers,
    fts_tickers=None,
    sic_tickers=None,
    mktcap_dropped=None,
    gated_out=None,
) -> dict[str, list[str]]:
    """P8 — attribute each gold true-member to the pipeline stage that lost (or kept) it.

    The recall ratio is a single number; this is the per-stage DIAGNOSIS behind it. Each gold
    ticker is classified into exactly one RECALL_STAGES bucket, evaluated in pipeline order so the
    earliest-applicable cause wins:

      1. recalled_final — in the final recall set (`recalled_tickers`). A clean recall hit.
      2. sic_recovered  — NOT recalled, but present in the SIC reverse-recall set (`sic_tickers`)
                          and absent from the FTS set (`fts_tickers`): the SIC floor caught what
                          FTS missed. This is the quantity P8 exists to make visible.
      3. dropped_mktcap — NOT recalled, but listed in `mktcap_dropped`: it WAS recalled upstream
                          then removed by the market-cap band filter (size out of scope).
      4. gated_out      — NOT recalled, but listed in `gated_out`: it survived to deep-dive then
                          was gated out (buy_ineligible / kill-flag).
      5. fts_missed     — none of the above: never recalled by any channel and not recovered by
                          SIC. The true recall-floor leak.

    All inputs are case-insensitive ticker iterables (or None). Returns a dict keyed by every
    RECALL_STAGES name to a sorted ticker list (empty lists for unused stages). The five lists
    partition `gold` exactly (each member appears once), so the breakdown always reconciles to the
    headline recall ratio: |recalled_final| + |sic_recovered| == recall hits.
    """
    def _norm(xs):
        return {str(t).upper().strip() for t in (xs or []) if str(t).strip()}

    gold_set = _norm(gold)
    recalled = _norm(recalled_tickers)
    fts = _norm(fts_tickers)
    sic = _norm(sic_tickers)
    dropped = _norm(mktcap_dropped)
    gated = _norm(gated_out)

    out: dict[str, list[str]] = {stage: [] for stage in RECALL_STAGES}
    for tk in gold_set:
        if tk in recalled:
            stage = "recalled_final"
        elif tk in sic and tk not in fts:
            stage = "sic_recovered"
        elif tk in dropped:
            stage = "dropped_mktcap"
        elif tk in gated:
            stage = "gated_out"
        else:
            stage = "fts_missed"
        out[stage].append(tk)
    for stage in out:
        out[stage].sort()
    return out


def recall_at_gold(
    theme: str,
    recalled_tickers,
    fts_hit_count: int | None = None,
    mapping: dict[str, list[str]] | None = None,
    fts_tickers=None,
    sic_tickers=None,
    mktcap_dropped=None,
    gated_out=None,
) -> dict | None:
    """P8 — recall@gold for a theme's recall set against its hand-built gold list.

    `recalled_tickers` is the set/list of tickers the run actually recalled (FTS ∪ SIC
    reverse-recall — the union that filter_by_sic produces). `fts_hit_count`, when known,
    is the raw FTS hit count; if it is at/over FTS_TOP_HITS_CAP a `fts_cap_warning` is set
    so a sub-1.0 recall is correctly attributed to the documented top-1000 page cap.

    The optional per-stage inputs (`fts_tickers`, `sic_tickers`, `mktcap_dropped`, `gated_out`)
    drive the loss-STAGE breakdown (see recall_stage_breakdown): when any are supplied the result
    carries a `stage_breakdown` dict attributing every gold member to the pipeline stage that lost
    or kept it. When none are supplied the breakdown is still emitted (every recalled gold member
    lands in recalled_final, every missing one in fts_missed) so the field is always present.

    Returns None when the theme has no gold list (not measurable). Otherwise returns:
      - gold:            sorted gold ticker list
      - recalled_gold:   gold members present in the recall set (the hits)
      - missing_gold:    gold members the recall set MISSED (the recall floor leak)
      - recall_at_gold:  |recalled∩gold| / |gold|  (float in [0,1])
      - fts_cap_warning: str|None — set iff fts_hit_count >= FTS_TOP_HITS_CAP
      - stage_breakdown: dict[stage -> sorted tickers] partitioning `gold` (see RECALL_STAGES)
    """
    gold = theme_gold(theme, mapping=mapping)
    if not gold:
        return None
    recalled = {str(t).upper() for t in (recalled_tickers or [])}
    gold_set = set(gold)
    hit = sorted(gold_set & recalled)
    miss = sorted(gold_set - recalled)
    cap_warn = None
    if fts_hit_count is not None and fts_hit_count >= FTS_TOP_HITS_CAP:
        cap_warn = (
            f"FTS hit count {fts_hit_count} >= top-{FTS_TOP_HITS_CAP} cap — recall may be "
            f"truncated by the EFTS page limit; rely on the SIC reverse-recall floor"
        )
    stage_breakdown = recall_stage_breakdown(
        gold,
        recalled,
        fts_tickers=fts_tickers,
        sic_tickers=sic_tickers,
        mktcap_dropped=mktcap_dropped,
        gated_out=gated_out,
    )
    return {
        "theme": theme,
        "gold": gold,
        "recalled_gold": hit,
        "missing_gold": miss,
        "recall_at_gold": round(len(hit) / len(gold), 4),
        "fts_cap_warning": cap_warn,
        "stage_breakdown": stage_breakdown,
    }


def _recall_set_from_candidate_files(paths: list[Path]) -> tuple[set[str], int, dict[str, set[str]]]:
    """Read recalled tickers from one or more candidate JSON files (the run's recall set).

    Each file is a list of candidate rows (or a dict wrapping them under candidates/rows),
    each carrying a `ticker`. Returns (recalled_ticker_set, fts_only_count, stage_sets) where:
      - recalled_ticker_set — every ticker still present in the final candidate set
      - fts_only_count      — rows recalled by FTS (recall_channel in {fts, both} or untagged),
                              the figure compared against FTS_TOP_HITS_CAP for the cap warning
      - stage_sets          — dict with the per-stage ticker sets used by recall_stage_breakdown:
            "fts"            tickers with recall_channel in {fts, both}
            "sic"            tickers with recall_channel in {sic_reverse, both}
            "mktcap_dropped" tickers a row tags dropped on market cap (dropped_stage=="mktcap",
                             or a truthy "mktcap_dropped" flag)
            "gated_out"      tickers a row tags gated out (dropped_stage=="gated", or a truthy
                             "gated_out"/"buy_ineligible" flag)

    A row can be present in the candidate file but tagged as dropped/gated downstream; those
    rows feed the stage sets but are NOT added to recalled_ticker_set so the breakdown can
    attribute them past the final recall set.
    """
    recalled: set[str] = set()
    fts_only = 0
    stage_sets: dict[str, set[str]] = {
        "fts": set(), "sic": set(), "mktcap_dropped": set(), "gated_out": set(),
    }
    for p in paths:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [warn] recall-gold: cannot read {p}: {e}", file=sys.stderr)
            continue
        rows = d if isinstance(d, list) else (d.get("candidates") or d.get("rows") or [])
        for r in rows:
            tk = str(r.get("ticker") or "").upper().strip()
            if not tk:
                continue
            ch = r.get("recall_channel")
            if ch in (None, "fts", "both"):
                fts_only += 1
                stage_sets["fts"].add(tk)
            if ch in ("sic_reverse", "sic", "both"):
                stage_sets["sic"].add(tk)
            dropped_stage = str(r.get("dropped_stage") or "").lower()
            if dropped_stage == "mktcap" or r.get("mktcap_dropped"):
                stage_sets["mktcap_dropped"].add(tk)
            elif dropped_stage in ("gated", "gated_out") or r.get("gated_out") or r.get("buy_ineligible"):
                stage_sets["gated_out"].add(tk)
            else:
                # Not tagged as dropped downstream -> it is in the final recall set.
                recalled.add(tk)
    return recalled, fts_only, stage_sets


# ---------------------------------------------------------------------------
# P8 / v0.3.1 #6 — recall@gold against the UNIVERSE (raw FTS ∪ SIC-reverse), not candidates.
# ---------------------------------------------------------------------------
# The candidate JSON is the POST band/burn/liquidity set, so a gold member that WAS recalled
# (present in the universe) but then size-capped / burn-rejected / mktcap-fetch-failed is absent
# from it and the breakdown mislabels it `fts_missed` — under-crediting the SIC floor and the FTS
# recall both. The fix: read the UNIVERSE CSV that discover.py emits (the raw recall set, every
# FTS ∪ SIC-reverse hit BEFORE any size/liquidity filtering) so a gold member's loss is attributed
# to its TRUE stage. At universe level deathcare reads 5/6 recalled (only delisted STON genuinely
# fts_missed), not the 2/6 the post-filter candidates file reports.
#
# Universe CSV schema (discover.py): name,ticker,cik,sic,...,matched_phrase,...,flag_too_big,
# flag_illiquid,flag_no_price,flag_no_mktcap,band,smallcap_candidate[,recall_channel]. The
# recall_channel column is present only when discover ran with --sic-reverse; when absent every
# row is an FTS hit, except SIC-only rows discover stamps matched_phrase='[sic_reverse]'.
SIC_REVERSE_MARKER = "[sic_reverse]"


def _truthy_csv(v) -> bool:
    """A CSV cell read as a truthy boolean. Pandas/csv write bools as 'True'/'False' strings."""
    return str(v).strip().lower() in ("true", "1", "yes")


def _recall_set_from_universe_files(paths: list[Path]) -> tuple[set[str], int, dict[str, set[str]]]:
    """Read the UNIVERSE recall set from one or more discover.py universe CSV files.

    The universe CSV is the RAW recall set (FTS ∪ SIC-reverse) BEFORE band/burn/liquidity
    filtering — the correct denominator for recall@gold (v0.3.1 backlog #6). Every ticker that
    appears here was recalled by some channel; whether it survived downstream is a SEPARATE
    (loss-stage) question, which is exactly what this function attributes.

    Returns (recalled_ticker_set, fts_hit_count, stage_sets), mirroring
    _recall_set_from_candidate_files so cmd_recall_gold can use either source interchangeably:

      - recalled_ticker_set — tickers that survived the universe filters into the candidate set
                              (smallcap_candidate truthy). These are the universe-level
                              recalled_final hits.
      - fts_hit_count       — rows recalled by the FTS channel (recall_channel in {fts, both},
                              or — when the column is absent — any row NOT stamped with the
                              SIC-reverse marker). Compared against FTS_TOP_HITS_CAP.
      - stage_sets          — per-stage ticker sets for recall_stage_breakdown:
            "fts"            FTS-channel tickers (see fts_hit_count rule)
            "sic"            SIC-reverse-channel tickers (recall_channel in {sic_reverse, both},
                             or matched_phrase == '[sic_reverse]')
            "mktcap_dropped" tickers recalled into the universe but DROPPED before the candidate
                             set by a size/liquidity filter (smallcap_candidate falsey:
                             flag_too_big / band=='large' / illiquid / no-price / mktcap-fetch
                             fail). This is the universe-vs-candidate delta that the candidates
                             file silently lost; here it is attributed, NOT counted as fts_missed.
            "gated_out"      empty from the universe alone (gating is a deep-dive-stage outcome,
                             not visible in the universe CSV) — supplied by the candidates file
                             when both sources are merged.

    A gold member present in the universe lands in recalled_final (survived) or dropped_mktcap
    (size/liquidity-dropped); only a gold member ABSENT from every universe file falls through to
    fts_missed — the true recall leak. Tolerates a missing recall_channel column (older discover
    runs) and the empty-universe placeholder CSV discover writes when FTS returns nothing.
    """
    recalled: set[str] = set()
    fts_hits = 0
    stage_sets: dict[str, set[str]] = {
        "fts": set(), "sic": set(), "mktcap_dropped": set(), "gated_out": set(),
    }
    for p in paths:
        try:
            # utf-8-sig tolerates a BOM; discover writes plain utf-8 via pandas.to_csv.
            text = Path(p).read_text(encoding="utf-8-sig")
        except Exception as e:
            print(f"  [warn] recall-gold: cannot read universe {p}: {e}", file=sys.stderr)
            continue
        reader = _csv.DictReader(text.splitlines())
        for r in reader:
            tk = str(r.get("ticker") or "").upper().strip()
            if not tk:
                continue
            ch = (r.get("recall_channel") or "").strip().lower()
            phrase = (r.get("matched_phrase") or "").strip().lower()
            is_sic = ch in ("sic_reverse", "sic") or phrase == SIC_REVERSE_MARKER
            is_both = ch == "both"
            if is_both or (not is_sic):
                # FTS channel: recall_channel fts/both, OR (column absent) any non-SIC-marked row.
                fts_hits += 1
                stage_sets["fts"].add(tk)
            if is_sic or is_both:
                stage_sets["sic"].add(tk)
            # Universe -> candidate survival: smallcap_candidate truthy means it cleared the
            # size/liquidity filters. Anything else was recalled then size/liquidity-dropped.
            if _truthy_csv(r.get("smallcap_candidate")):
                recalled.add(tk)
            else:
                stage_sets["mktcap_dropped"].add(tk)
    return recalled, fts_hits, stage_sets
