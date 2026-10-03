"""Measure final-set and discovery recall against a normalized gold cohort.

Discovery channels describe how members were found. Terminal stages describe
whether they survived later filters; both use the same distinct gold members.
This module imports only the standard library.
"""
from __future__ import annotations

import csv as _csv
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# P8, recall@gold: measure the recall FLOOR against hand-built true-member lists.
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
# are the pure operators (SIC 7200, caught by the SIC floor); MATW (3360 castings),
# HI (Hillenbrand, 3559), STON (StoneMor, 6553 cemeteries), SNFCA (6199 finance) are
# cross-SIC by design, they are the residual FTS-only gap the SIC floor cannot reach,
# which is exactly what recall@gold quantifies.
THEME_GOLD: dict[str, list[str]] = {
    "deathcare": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    "funeral": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    "cemetery": ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"],
    # Coverage-test gold cohorts (2026-06-20), hand-curated public small/mid-cap members.
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

# Every gold member has one terminal stage. Only recalled_final contributes to
# final-set recall. Discovery provenance is reported separately, so SIC recovery
# cannot conceal a later filter loss. fts_missed retains its legacy name for a
# member with no discovery evidence from either channel.
RECALL_STAGES = (
    "recalled_final",
    "dropped_mktcap",
    "gated_out",
    "discovered_not_final",
    "fts_missed",
)


def _ticker_set(tickers):
    return {str(ticker).strip().upper() for ticker in (tickers or []) if str(ticker).strip()}


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
        if str(key).lower() in t:
            for tk in tickers:
                ticker = str(tk).strip().upper()
                if ticker and ticker not in out:
                    out.append(ticker)
    return out


def recall_stage_breakdown(
    gold,
    recalled_tickers,
    fts_tickers=None,
    sic_tickers=None,
    mktcap_dropped=None,
    gated_out=None,
) -> dict[str, list[str]]:
    """Partition gold by final inclusion, recorded loss, or missing outcome.

    Final inclusion takes precedence over earlier loss tags. Otherwise a recorded
    market-cap loss precedes a gate loss. Channel evidence alone establishes
    discovery, not final inclusion or a known reason for exclusion.

    Output compatibility: the former sic_recovered terminal key is removed.
    Consumers should read discovery_channels['sic_only'] from recall_at_gold
    for SIC-only discovery, and discovered_not_final for an unknown final outcome.
    Only recalled_final contributes to the final-set recall numerator.
    """
    gold_set = _ticker_set(gold)
    recalled = _ticker_set(recalled_tickers)
    fts = _ticker_set(fts_tickers)
    sic = _ticker_set(sic_tickers)
    dropped = _ticker_set(mktcap_dropped)
    gated = _ticker_set(gated_out)

    out: dict[str, list[str]] = {stage: [] for stage in RECALL_STAGES}
    for tk in gold_set:
        if tk in recalled:
            stage = "recalled_final"
        elif tk in dropped:
            stage = "dropped_mktcap"
        elif tk in gated:
            stage = "gated_out"
        elif tk in fts or tk in sic:
            stage = "discovered_not_final"
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
    completion=None,
) -> dict | None:
    """P8 — recall@gold for a theme's recall set against its hand-built gold list.

    `recalled_tickers` is the final set supplied by the candidate or universe reader.
    Channel inputs separately establish upstream discovery. `fts_hit_count`, when known,
    is the raw FTS hit count; if it is at/over FTS_TOP_HITS_CAP a `fts_cap_warning` is set
    so a sub-1.0 recall is correctly attributed to the documented top-1000 page cap.

    The optional per-stage inputs (`fts_tickers`, `sic_tickers`, `mktcap_dropped`, `gated_out`)
    drive the loss-STAGE breakdown (see recall_stage_breakdown): when any are supplied the result
    carries a `stage_breakdown` dict attributing every gold member to the pipeline stage that lost
    or kept it. When none are supplied the breakdown is still emitted (every recalled gold member
    lands in recalled_final, every missing one in fts_missed) so the field is always present.
    A discovered member without a final result or loss tag is discovered_not_final.
    Completion describes the observation scope separately from these legacy partitions.
    With incomplete or absent evidence, missing_gold also appears in unknown_missing_gold;
    the observed ratios and gold denominator remain unchanged.

    Returns None when the theme has no gold list (not measurable). Otherwise returns:
      - gold:            sorted gold ticker list
      - recalled_gold:   gold members present in the recall set (the hits)
      - missing_gold:    gold members the recall set MISSED (the recall floor leak)
      - recall_at_gold:  |recalled∩gold| / |gold|  (float in [0,1])
      - fts_cap_warning: str|None — set iff fts_hit_count >= FTS_TOP_HITS_CAP
      - stage_breakdown: dict[stage -> sorted tickers] partitioning `gold` (see RECALL_STAGES)
      - discovery_channels: disjoint fts_only, sic_only, both, unattributed, not_discovered
      - discovered_gold: members with channel, final inclusion, or downstream loss evidence
      - discovery_recall_at_gold: |discovered_gold| / |gold|, using the same denominator
      - coverage_status / coverage_complete: whether upstream observations are complete
      - unknown_missing_gold: missing members whose absence is not a complete observation
    """
    gold = sorted(theme_gold(theme, mapping=mapping))
    if not gold:
        return None
    recalled = _ticker_set(recalled_tickers)
    fts, sic = _ticker_set(fts_tickers), _ticker_set(sic_tickers)
    dropped, gated = _ticker_set(mktcap_dropped), _ticker_set(gated_out)
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
        fts_tickers=fts,
        sic_tickers=sic,
        mktcap_dropped=dropped,
        gated_out=gated,
    )
    discovered = gold_set & (recalled | fts | sic | dropped | gated)
    channels = {
        "fts_only": sorted(gold_set & (fts - sic)),
        "sic_only": sorted(gold_set & (sic - fts)),
        "both": sorted(gold_set & fts & sic),
        "unattributed": sorted(discovered - fts - sic),
        "not_discovered": sorted(gold_set - discovered),
    }
    return {
        "theme": theme,
        "gold": gold,
        "recalled_gold": hit,
        "missing_gold": miss,
        "recall_at_gold": round(len(hit) / len(gold), 4),
        "fts_cap_warning": cap_warn,
        "stage_breakdown": stage_breakdown,
        "discovery_channels": channels,
        "discovered_gold": sorted(discovered),
        "discovery_recall_at_gold": round(len(discovered) / len(gold), 4),
        "completion": completion,
        "coverage_status": completion.get("status", "unavailable") if isinstance(completion, dict) else "unavailable",
        "coverage_complete": isinstance(completion, dict) and completion.get("status") == "complete",
        "unknown_missing_gold": [] if isinstance(completion, dict) and completion.get("status") == "complete" else miss,
    }


class RecallReadResult(tuple):
    """Keep three-item unpacking while carrying the observation's completion evidence."""

    def __new__(cls, recalled, fts_count, stage_sets, completion):
        result = super().__new__(cls, (recalled, fts_count, stage_sets))
        result.completion = completion
        return result


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
    The tuple-compatible result carries .completion; unreadable inputs remain visible there.
    """
    # Artifact readers load receipt support only when called; module import stays stdlib-only.
    from filter_by_sic import read_stage_receipt, stage_completion, stage_work

    recalled: set[str] = set()
    fts_only = 0
    work, upstream = [], []
    stage_sets: dict[str, set[str]] = {
        "fts": set(), "sic": set(), "mktcap_dropped": set(), "gated_out": set(),
    }
    for p in paths:
        try:
            if Path(p).name.endswith(".stage.json"):
                raise ValueError("receipt is not a candidate artifact")
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            if isinstance(d, list):
                rows = d
            elif isinstance(d, dict) and ("candidates" in d or "rows" in d):
                rows = d.get("candidates", d.get("rows"))
            else:
                raise ValueError("invalid candidate envelope")
            if not isinstance(rows, list) or any(
                    not isinstance(r, dict) or not isinstance(r.get("ticker"), str)
                    or not r["ticker"].strip() for r in rows):
                raise ValueError("invalid candidate identity")
        except (OSError, ValueError, TypeError) as e:
            print(f"  [warn] recall-gold: cannot read {p}: {e}", file=sys.stderr)
            work.append(stage_work("candidate_file", Path(p).name, status="invalid",
                                   reason="unreadable_or_invalid_candidates"))
            continue
        receipt = read_stage_receipt(p, len(rows))
        upstream.append(receipt)
        work.append(stage_work("candidate_file", Path(p).name))
        if receipt["status"] == "invalid":
            continue
        for r in rows:
            tk = str(r.get("ticker") or "").upper().strip()
            ch = r.get("recall_channel")
            if ch in (None, "fts", "both"):
                fts_only += 1
                stage_sets["fts"].add(tk)
            if ch in ("sic_reverse", "sic", "both"):
                stage_sets["sic"].add(tk)
            if r.get("judgment_status") == "error":
                work.append(stage_work("candidate_outcome", tk, status="unavailable",
                                       reason="missing_gate_judgment"))
                continue
            dropped_stage = str(r.get("dropped_stage") or "").lower()
            if dropped_stage == "mktcap" or r.get("mktcap_dropped"):
                stage_sets["mktcap_dropped"].add(tk)
            elif (dropped_stage in ("gated", "gated_out") or r.get("gated_out") or r.get("buy_ineligible")
                  or (r.get("judgment_status") == "complete" and r.get("theme_fit") == "misrecall")):
                stage_sets["gated_out"].add(tk)
            else:
                # Not tagged as dropped downstream -> it is in the final recall set.
                recalled.add(tk)
    completion = stage_completion("recall_candidates", len(recalled), work=work, upstream=upstream)
    return RecallReadResult(recalled, fts_only, stage_sets, completion)


# ---------------------------------------------------------------------------
# P8 / v0.3.1 #6, recall@gold against the UNIVERSE (raw FTS ∪ SIC-reverse), not candidates.
# ---------------------------------------------------------------------------
# The candidate JSON is the POST band/burn/liquidity set, so a gold member that WAS recalled
# (present in the universe) but then size-capped / burn-rejected / mktcap-fetch-failed is absent
# from it and the breakdown mislabels it `fts_missed`, under-crediting the SIC floor and the FTS
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

    The universe CSV retains discoveries before band/burn/liquidity filtering.
    The gold cohort remains the denominator for both discovery and final recall.
    Every ticker present here was discovered; its filter flags separately record
    whether it reached the candidate set.

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

    A gold member present in a valid universe lands in recalled_final (survived) or dropped_mktcap
    (size/liquidity-dropped); only a gold member ABSENT from every universe file falls through to
    fts_missed in the legacy partition. The result's .completion distinguishes a proved
    absence from incomplete observation. A missing recall_channel is tolerated, while
    candidate flags must be explicit and an empty CSV must retain its required columns.
    """
    from filter_by_sic import read_stage_receipt, stage_completion, stage_work

    recalled: set[str] = set()
    fts_hits = 0
    work, upstream = [], []
    stage_sets: dict[str, set[str]] = {
        "fts": set(), "sic": set(), "mktcap_dropped": set(), "gated_out": set(),
    }
    for p in paths:
        try:
            # utf-8-sig tolerates a BOM; discover writes plain utf-8 via pandas.to_csv.
            text = Path(p).read_text(encoding="utf-8-sig")
            reader = _csv.DictReader(text.splitlines())
            if not {"ticker", "smallcap_candidate"}.issubset(reader.fieldnames or []):
                raise ValueError("universe requires ticker and smallcap_candidate")
            rows = list(reader)
            for row in rows:
                if (None in row or not isinstance(row.get("ticker"), str)
                        or not row["ticker"].strip()
                        or str(row.get("smallcap_candidate")).strip().lower()
                        not in {"true", "false", "1", "0", "yes", "no"}):
                    raise ValueError("invalid universe identity or candidate flag")
        except (OSError, ValueError, TypeError, _csv.Error) as e:
            print(f"  [warn] recall-gold: cannot read universe {p}: {e}", file=sys.stderr)
            work.append(stage_work("universe_file", Path(p).name, status="invalid",
                                   reason="unreadable_or_invalid_universe"))
            continue
        receipt = read_stage_receipt(p, len(rows))
        upstream.append(receipt)
        work.append(stage_work("universe_file", Path(p).name))
        if receipt["status"] == "invalid":
            continue
        for r in rows:
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
    completion = stage_completion("recall_universe", len(recalled), work=work, upstream=upstream)
    return RecallReadResult(recalled, fts_hits, stage_sets, completion)
