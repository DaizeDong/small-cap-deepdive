"""backtest.py — PIECE 4 of the point-in-time (PIT) backtest machinery (spec:
docs/backtest-2026-06/spec.md).

The HARNESS. One (theme, as-of) cell at a time:

  run_cell(theme, asof, horizon=12) ->
    1. reconstruct the survivorship-SAFE PIT universe (PIECE 2, _pit_universe.pit_universe):
       every theme-SIC filer with a 10-K/10-Q filingDate <= asof, INCLUDING later-delisted names.
    2. for EACH name: deepdive_data.pull(ticker, cik, as_of=asof) — a point-in-time pull that uses
       ONLY filings filed<=asof (no look-ahead, no restatement contamination) — then
       valuation.compute_valuation on a PIT entry market cap (PIECE 3, mktcap_asof = price-as-of-T x
       PIT shares-outstanding; yfinance marketCap is a CURRENT field and is never used).
    3. bucket each name in {buy_eligible / WATCH / AVOID / abstain} per the BUY contract:
       BUY = mos_basis in {fcf_cap, nav} AND MoS>=30 AND buy_eligible AND 0 kill-flags.
    4. join the forward return T->T+horizon (PIECE 3, forward_return; a delisted name realizes to its
       last close ~ -100%, which is the POINT a de-risk scanner is graded on AVOIDING).
    5. per-bucket stats (mean/median excess-vs-IWM, win-rate) + blowup-avoidance (of the >40%-drawdown
       names, what fraction the scanner put in AVOID/abstain) + a LOOK-AHEAD AUDIT line that ASSERTS
       the max filing_date observed across every pull in the cell is <= asof, and records the
       entry/exit/benchmark dates actually used.
    6. write the per-cell result to reports/smallcap/backtest/<asof>_<theme>.json.

Everything here is ADDITIVE: it imports the as-of variant of the live pulls (as_of=asof) and never
touches the live latest-filing default path (as_of=None reproduces it byte-identically — invariant
verified in deepdive_data / valuation selftests, not here).

CLI:
  python tools/backtest.py --selftest                         (offline, synthetic cell)
  python tools/backtest.py --theme <t> --asof YYYY-MM-DD [--horizon 12] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add tools dir to path for sibling imports (mirrors backtest_returns.py / _pit_universe.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# PIT machinery (PIECES 2 + 3) + the as-of-aware live layers.
from _pit_universe import pit_universe                         # PIECE 2
from backtest_returns import (                                 # PIECE 3
    forward_return_with_reason,
    benchmark_return,
    mktcap_asof,
    DEFAULT_HORIZON_MONTHS,
)
import deepdive_data                                           # PIECE 1 (pull as_of=)
from valuation import compute_valuation
from _valuation_model import _val_cfg
from make_report import _killflag_count                       # authoritative kill-flag definition

# Bucket labels. "buy_eligible" mirrors the spec's BUY bucket name (a name that satisfies the full
# mechanical BUY contract); WATCH / AVOID / abstain are the residual de-risk ladder.
BUCKET_BUY = "buy_eligible"
BUCKET_WATCH = "WATCH"
BUCKET_AVOID = "AVOID"
BUCKET_ABSTAIN = "abstain"
BUCKETS = (BUCKET_BUY, BUCKET_WATCH, BUCKET_AVOID, BUCKET_ABSTAIN)

# A name whose forward return is below this is a "blowup" for blowup-avoidance accounting. >40%
# drawdown over the horizon (spec §Metrics "Blowup-avoidance"). Realized to last close for delisted
# names, so a wiped-out name (~ -100%) is firmly inside this set.
BLOWUP_THRESHOLD = -0.40

# Output location for per-cell JSON (spec §Architecture 4). Fixed under the repo root — deliberately
# NOT the active-run REPORTS dir, so a backtest cell never lands inside a live discovery run.
_REPO_ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = _REPO_ROOT / "reports" / "smallcap" / "backtest"


# ---------------------------------------------------------------------------
# Bucketing — the BUY contract, expressed mechanically.
# ---------------------------------------------------------------------------


def _mos_pct_for_basis(val: dict) -> float | None:
    """The margin-of-safety PERCENT (x100) matching the active mos_basis.

    valuation emits margin_of_safety_pct / nav_margin_of_safety_pct as decimal FRACTIONS (e.g. 0.30
    = 30%). The BUY trigger's "MoS>=30" clause speaks in percent (see make_report._mos_field), so we
    multiply by 100 here and compare to 30. Returns None when no MoS exists for the basis (abstain,
    or a null band).
    """
    basis = val.get("mos_basis")
    if basis == "fcf_cap":
        frac = val.get("margin_of_safety_pct")
    elif basis == "nav":
        frac = val.get("nav_margin_of_safety_pct")
    else:
        return None
    if frac is None:
        return None
    try:
        return float(frac) * 100.0
    except (TypeError, ValueError):
        return None


def bucket_name(deep: dict, val: dict) -> dict:
    """Bucket ONE name into {buy_eligible / WATCH / AVOID / abstain} with the deciding fields.

    The de-risk ladder (spec §Architecture 4 + §Metrics):
      * buy_eligible (the rare BUY) — the FULL mechanical BUY contract holds:
          mos_basis in {fcf_cap, nav}  AND  MoS>=30  AND  buy_eligible(valuation)  AND  0 kill-flags.
      * abstain — mos_basis == "abstain" (no intrinsic band: foreign/IFRS un-valuable, financial-SIC
        routing, missing financials). The scanner has NO valuation opinion -> it sits out.
      * AVOID — the scanner has an opinion AND something disqualifies it: a kill-flag fired
        (going-concern / material-weakness / death-spiral / concentration=kill), OR the name is
        valuation-cheap-but-blocked (buy_eligible False) for a load-bearing reason. The "earn its
        name" bucket: a de-risk scanner must put blowups HERE (or abstain).
      * WATCH — has a valuation opinion, no kill-flags, but not a full BUY (MoS<30, or buy_eligible
        False on a softer downgrade like fcf_sustainability_uncertain). The on-deck bucket.

    Pure + deterministic: reads only deep/val fields, no network. Returns a dict carrying the bucket
    plus every field that decided it (so the per-cell JSON is auditable).
    """
    mos_basis = val.get("mos_basis") or "abstain"
    buy_eligible = bool(val.get("buy_eligible"))
    kill = _killflag_count(deep)
    mos_pct = _mos_pct_for_basis(val)

    has_band = (mos_basis in ("fcf_cap", "nav"))
    mos_ok = (mos_pct is not None and mos_pct >= 30.0)

    if mos_basis == "abstain":
        bucket = BUCKET_ABSTAIN
    elif has_band and mos_ok and buy_eligible and kill == 0:
        bucket = BUCKET_BUY
    elif kill > 0:
        # A kill-flag is BUY-blocking AND a de-risk signal -> AVOID (the bucket graded on blowups).
        bucket = BUCKET_AVOID
    elif has_band and mos_ok and not buy_eligible:
        # Valuation says "cheap" (MoS>=30) but a load-bearing guard blocks it -> AVOID. This is the
        # value-trap cohort the scanner must steer AWAY from, not merely WATCH.
        bucket = BUCKET_AVOID
    else:
        # Has an opinion, no kill-flags, not a full BUY (MoS<30 or a softer downgrade) -> WATCH.
        bucket = BUCKET_WATCH

    return {
        "bucket": bucket,
        "mos_basis": mos_basis,
        "mos_pct": round(mos_pct, 2) if mos_pct is not None else None,
        "buy_eligible": buy_eligible,
        "killflag_count": kill,
        "buy_ineligible_reasons": val.get("buy_ineligible_reasons") or [],
    }


# ---------------------------------------------------------------------------
# Look-ahead audit — the validity guarantee (spec §Look-ahead controls).
# ---------------------------------------------------------------------------


def _filing_dates_from_deep(deep: dict) -> list[str]:
    """Every observable filing date a single PIT pull exposes (YYYY-MM-DD strings, non-empty).

    Two observable upper bounds, both filed<=asof by construction of the as-of pull:
      * derived.asof_max_filing_date (FIX 1) — the AUTHORITATIVE one: the max "filed" date actually
        used across EVERY concept pull (revenue/ni/ocf/debt/... + the as-of 10-K/20-F/40-F). This is
        what makes the look-ahead audit NON-vacuous — without it the audit observed only the tenk
        date (and was empty when no tenk resolved). Emitted only when as_of is set; null/absent on
        the live latest-filing path.
      * tenk.filing_date — the most recent periodic disclosure an investor at asof could read; a
        secondary observable that survives even if asof_max_filing_date is null.
    We audit every observable date; max across them is the cell's look-ahead upper bound.
    """
    out: list[str] = []
    derived = deep.get("derived") or {}
    amfd = str(derived.get("asof_max_filing_date", "") or "").strip()
    if amfd:
        out.append(amfd[:10])
    tenk = deep.get("tenk") or {}
    fd = str(tenk.get("filing_date", "") or "").strip()
    if fd:
        out.append(fd[:10])
    return out


def look_ahead_audit(rows: list[dict], asof: str, benchmark: dict,
                     *, expect_dates: bool = False) -> dict:
    """Assert no look-ahead across the whole cell + record entry/exit/benchmark dates.

    rows are per-name result dicts (each may carry filing_dates + the forward_return block). The
    AUDIT (spec: "Per-cell audit asserts max(filing_date) <= T"):
      * max_filing_date <= asof  — RAISES AssertionError if any observable filing date is AFTER asof.
      * NON-VACUOUS: when expect_dates is True (a real cell with names), at least ONE filing date
        MUST have been observed — RAISES AssertionError otherwise. An audit that observed 0 dates is
        VACUOUS (it asserts nothing about look-ahead), which was bug (B): the whole validity point.
        non_vacuous in the returned dict records whether n_filing_dates_observed > 0.
      * records max_filing_date, the entry/exit date RANGE actually resolved by the price layer, and
        the benchmark's entry/exit dates, so the cell JSON proves the window used.
    Returns the audit dict (only reached when the assertions passed).
    """
    filing_dates: list[str] = []
    entry_dates: list[str] = []
    exit_dates: list[str] = []
    for r in rows:
        for fd in (r.get("filing_dates") or []):
            if fd:
                filing_dates.append(fd)
        fr = r.get("forward_return") or {}
        if fr.get("entry_date"):
            entry_dates.append(fr["entry_date"])
        if fr.get("exit_date"):
            exit_dates.append(fr["exit_date"])

    n_observed = len(filing_dates)
    max_fd = max(filing_dates) if filing_dates else None
    # THE look-ahead assertion. A filing observed after asof would be a leak — fail loud.
    assert max_fd is None or max_fd <= asof, (
        f"LOOK-AHEAD LEAK: max filing_date {max_fd} used in cell is AFTER asof {asof}")
    # NON-VACUITY assertion (bug B). A real cell that surfaced 0 filing dates proves nothing about
    # look-ahead — the audit would pass vacuously. Demand at least one observed date.
    if expect_dates:
        assert n_observed > 0, (
            "VACUOUS AUDIT: 0 filing dates observed across the cell — the look-ahead audit asserts "
            "nothing (bug B). Each name's PIT pull must surface derived.asof_max_filing_date.")

    return {
        "asof": asof,
        "max_filing_date": max_fd,
        "max_filing_date_le_asof": (max_fd is None or max_fd <= asof),
        "n_filing_dates_observed": n_observed,
        "non_vacuous": n_observed > 0,
        "entry_date_range": [min(entry_dates), max(entry_dates)] if entry_dates else None,
        "exit_date_range": [min(exit_dates), max(exit_dates)] if exit_dates else None,
        "benchmark": benchmark.get("benchmark"),
        "benchmark_entry_date": benchmark.get("entry_date"),
        "benchmark_exit_date": benchmark.get("exit_date"),
        "benchmark_target_exit_date": benchmark.get("target_exit_date"),
    }


# ---------------------------------------------------------------------------
# Per-bucket stats + blowup-avoidance (spec §Metrics).
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 6) if xs else None


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 6) if xs else None


def _is_unpriceable(r: dict) -> bool:
    """A name with NO ticker or NO priceable forward return (bug C).

    Unpriceable = (a) ticker-less filer (a CIK-only shell that slipped through, or the no_ticker
    return path), OR (b) a name whose forward return never resolved to a real price
    (no_entry_price / no_exit_price / not_found). These are NOT tradable names with real forward
    returns, so they are EXCLUDED from the graded per-bucket stats + blowup-avoidance entirely and
    reported as unpriceable_count. (They are still bucketed + retained in `names` for audit; FIX 2
    drops genuine ticker-less shells upstream, so this is the residual safety net.)
    """
    if not str(r.get("ticker") or "").strip():
        return True
    return r.get("total_return") is None


def per_bucket_stats(rows: list[dict], bench_return: float | None) -> dict:
    """Per-bucket mean/median forward return, EXCESS vs IWM, win-rate, n (spec §Metrics).

    Only PRICEABLE names (a real ticker + a realized forward return) are graded: unpriceable names
    (no ticker / no priceable return) are EXCLUDED so buckets reflect real tradable names with real
    forward returns (bug C — returns null everywhere made buckets meaningless). The excluded count
    is reported per bucket as `unpriceable_count`. n counts priceable members only. Excess =
    total_return - bench_return (per name); win-rate = fraction with total_return>0.
    """
    stats: dict = {}
    for b in BUCKETS:
        members = [r for r in rows if r.get("bucket") == b]
        priceable = [r for r in members if not _is_unpriceable(r)]
        unpriceable = len(members) - len(priceable)
        rets = [float(r["total_return"]) for r in priceable]
        excess = ([rr - bench_return for rr in rets] if bench_return is not None else [])
        wins = sum(1 for rr in rets if rr > 0)
        stats[b] = {
            "n": len(priceable),
            "n_with_return": len(priceable),
            "n_no_return": 0,
            "unpriceable_count": unpriceable,
            "mean_return": _mean(rets),
            "median_return": _median(rets),
            "mean_excess_vs_iwm": _mean(excess) if excess else None,
            "median_excess_vs_iwm": _median(excess) if excess else None,
            "win_rate": round(wins / len(rets), 4) if rets else None,
        }
    return stats


def blowup_avoidance(rows: list[dict]) -> dict:
    """Of names that suffered a >40% drawdown over the horizon, what fraction did the scanner steer
    into AVOID/abstain (spec §Metrics "Blowup-avoidance"; higher = the scanner earns its name).

    Only PRICEABLE names (real ticker + realized forward return) are eligible — unpriceable names
    (no ticker / no priceable return) cannot be measured blowups and are EXCLUDED, reported as
    unpriceable_count (bug C). avoided = put in AVOID or abstain; fraction = avoided / blowups.
    """
    priceable = [r for r in rows if not _is_unpriceable(r)]
    unpriceable = len(rows) - len(priceable)
    blowups = [r for r in priceable if float(r["total_return"]) <= BLOWUP_THRESHOLD]
    avoided = [r for r in blowups if r.get("bucket") in (BUCKET_AVOID, BUCKET_ABSTAIN)]
    return {
        "blowup_threshold": BLOWUP_THRESHOLD,
        "n_blowups": len(blowups),
        "n_blowups_in_avoid_or_abstain": len(avoided),
        "blowup_avoidance_fraction": (round(len(avoided) / len(blowups), 4) if blowups else None),
        "unpriceable_count": unpriceable,
        "blowup_tickers": [r.get("ticker") for r in blowups],
        "blowup_buckets": {r.get("ticker"): r.get("bucket") for r in blowups},
    }


# ---------------------------------------------------------------------------
# The harness — run one cell.
# ---------------------------------------------------------------------------


def _process_name(entity: dict, asof: str, horizon: int,
                  pull_fn, valuation_fn, mktcap_fn, forward_fn) -> dict:
    """Run ONE universe entity through the PIT pipeline -> a per-name result row.

    pull_fn / valuation_fn / mktcap_fn / forward_fn are injectable so the selftest is network-free.
    Every step is guarded: a name that fails to pull/value is recorded with status + reason, never
    dropped silently and never fabricated.
    """
    ticker = str(entity.get("ticker") or "").strip()
    cik = str(entity.get("cik") or "").strip()
    name = str(entity.get("name") or "")
    row: dict = {
        "ticker": ticker, "cik": cik, "name": name,
        "recall_channel": entity.get("recall_channel"),
        "delisted_after_asof": entity.get("delisted_after_asof"),
        "bucket": BUCKET_ABSTAIN, "status": "ok",
        "filing_dates": [], "total_return": None, "forward_return": None,
    }

    # 1. PIT deepdive pull (as_of=asof) — filings filed<=asof only.
    try:
        deep = pull_fn(ticker, cik, as_of=asof)
    except Exception as e:
        row["status"] = "pull_failed"
        row["reason"] = f"deepdive pull raised: {e!r}"
        return row
    row["filing_dates"] = _filing_dates_from_deep(deep)

    # 2. PIT entry market cap = price-as-of-T x PIT shares (NEVER yfinance marketCap).
    mc = mktcap_fn(ticker, asof, cik=cik) if ticker else {"mktcap": None, "reason": "no_ticker"}
    market_cap = mc.get("mktcap")
    row["mktcap_asof"] = market_cap
    row["mktcap_source"] = mc.get("source")

    # 3. Valuation. Needs a market cap; without one we can still bucket on the basis (abstain/nav).
    try:
        cfg = _val_cfg()
        val = valuation_fn(deep, int(market_cap) if market_cap else 0, cfg)
    except Exception as e:
        row["status"] = "valuation_failed"
        row["reason"] = f"compute_valuation raised: {e!r}"
        return row

    # 4. Bucket per the BUY contract.
    binfo = bucket_name(deep, val)
    row.update({k: binfo[k] for k in
                ("bucket", "mos_basis", "mos_pct", "buy_eligible",
                 "killflag_count", "buy_ineligible_reasons")})

    # 5. Forward return T->T+horizon (delisted -> realized-to-last-close ~ -100%).
    if ticker:
        fr = forward_fn(ticker, asof, horizon)
        row["forward_return"] = fr
        if fr.get("status") == "ok":
            row["total_return"] = fr.get("total_return")
            row["realized_to_last_close"] = fr.get("realized_to_last_close")
        else:
            row["return_status"] = fr.get("status")
            row["return_reason"] = fr.get("reason")
    else:
        row["return_status"] = "no_ticker"
        row["return_reason"] = "no ticker to fetch a forward return (CIK-only filer)"
    return row


def run_cell(theme: str, asof: str, horizon: int = DEFAULT_HORIZON_MONTHS,
             *, universe_fn=None, pull_fn=None, valuation_fn=None, mktcap_fn=None,
             forward_fn=None, benchmark_fn=None, limit: int | None = None,
             write: bool = True, sleep: float = 0.0) -> dict:
    """Run ONE (theme, asof) backtest cell and (optionally) write its per-cell JSON.

    Reconstructs the PIT universe, runs every name through the as-of pipeline, joins forward returns,
    computes per-bucket stats + blowup-avoidance, runs the look-ahead audit (which RAISES on a leak),
    and returns the full cell dict. All collaborators are injectable for the offline selftest; the
    defaults are the real PIT machinery.

    limit caps the number of universe names processed (a smoke-test convenience — NOT for the real
    panel, which runs the full universe per spec "Full data per cell (no sampling)").
    """
    universe_fn = universe_fn or pit_universe
    pull_fn = pull_fn or deepdive_data.pull
    valuation_fn = valuation_fn or compute_valuation
    mktcap_fn = mktcap_fn or mktcap_asof
    forward_fn = forward_fn or forward_return_with_reason
    benchmark_fn = benchmark_fn or benchmark_return

    universe = universe_fn(theme, asof)
    if limit is not None:
        universe = universe[:limit]

    rows: list[dict] = []
    for ent in universe:
        rows.append(_process_name(ent, asof, horizon,
                                  pull_fn, valuation_fn, mktcap_fn, forward_fn))
        if sleep:
            time.sleep(sleep)

    bench = benchmark_fn(asof, horizon)
    bench_ret = bench.get("total_return") if bench.get("status") == "ok" else None

    # RAISES on a look-ahead leak; also RAISES if a non-empty cell surfaced 0 filing dates (vacuous
    # audit, bug B). An empty universe legitimately has nothing to observe -> don't demand dates.
    audit = look_ahead_audit(rows, asof, bench, expect_dates=bool(rows))
    stats = per_bucket_stats(rows, bench_ret)
    blowups = blowup_avoidance(rows)

    bucket_counts = {b: sum(1 for r in rows if r.get("bucket") == b) for b in BUCKETS}
    unpriceable_count = sum(1 for r in rows if _is_unpriceable(r))
    cell = {
        "theme": theme,
        "asof": asof,
        "horizon_months": horizon,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe_size": len(universe),
        "n_processed": len(rows),
        "unpriceable_count": unpriceable_count,
        "bucket_counts": bucket_counts,
        "benchmark": {
            "ticker": bench.get("benchmark"),
            "status": bench.get("status"),
            "total_return": bench_ret,
            "reason": bench.get("reason"),
        },
        "per_bucket_stats": stats,
        "blowup_avoidance": blowups,
        "look_ahead_audit": audit,
        "names": rows,
    }
    if write:
        cell["output_path"] = str(_write_cell(cell))
    return cell


def _write_cell(cell: dict) -> Path:
    """Write the per-cell JSON to reports/smallcap/backtest/<asof>_<theme>.json."""
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    safe_theme = str(cell["theme"]).replace("/", "-").replace(" ", "-")
    path = BACKTEST_DIR / f"{cell['asof']}_{safe_theme}.json"
    path.write_text(json.dumps(cell, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Selftest — synthetic cell, fully injected (NO network).
# ---------------------------------------------------------------------------


def _selftest() -> None:
    """PIECE 4 unit assertions on a small synthetic cell. All collaborators injected — NO network.

    Builds five stubbed names exercising every bucket + the blowup/look-ahead math:
      BUYME  -> buy_eligible bucket, full-horizon WIN (+40%)         -> NOT a blowup
      WATCHR -> WATCH (MoS<30, no kill-flags), small WIN (+5%)       -> NOT a blowup
      TRAP   -> AVOID (MoS>=30 but buy_eligible False), BLOWUP (-70%)-> correctly avoided
      DYING  -> AVOID (kill-flag fired), BLOWUP delisted (-99%)      -> correctly avoided
      FORGN  -> abstain (no band), BLOWUP (-60%)                     -> correctly avoided (abstain)
      LEAK   -> (audit-only) a name whose tenk.filing_date is AFTER asof -> the audit MUST raise.
    """
    asof = "2020-06-30"
    horizon = 12

    # ---- synthetic deepdive + valuation builders (only the fields the harness reads) ----
    # asof_max_filing_date (FIX 1) defaults to the tenk filing_date here but is an INDEPENDENT field:
    # in production it's the max "filed" across every concept pull (often >= the tenk date). The
    # audit reads it FIRST (the authoritative non-vacuous source), then the tenk date.
    def _deep(ticker, cik, filing_date, going_concern=False, conc_kill=False,
              asof_max_filing_date=None):
        return {
            "ticker": ticker, "cik": cik,
            "tenk": {"available": True, "filing_form": "10-K", "filing_date": filing_date,
                     "has_going_concern": going_concern, "has_material_weakness": False,
                     "has_death_spiral": False},
            "derived": {"concentration_flag": ("kill" if conc_kill else None),
                        "asof_max_filing_date": (asof_max_filing_date
                                                 if asof_max_filing_date is not None
                                                 else filing_date)},
        }

    def _val(mos_basis, mos_frac, buy_eligible, reasons=None):
        return {
            "mos_basis": mos_basis,
            "margin_of_safety_pct": (mos_frac if mos_basis == "fcf_cap" else None),
            "nav_margin_of_safety_pct": (mos_frac if mos_basis == "nav" else None),
            "buy_eligible": buy_eligible,
            "buy_ineligible_reasons": reasons or [],
        }

    # Scripted tables keyed by ticker.
    DEEP = {
        "BUYME": _deep("BUYME", "111", "2020-03-15"),
        "WATCHR": _deep("WATCHR", "222", "2020-04-01"),
        "TRAP": _deep("TRAP", "333", "2019-12-20"),
        "DYING": _deep("DYING", "444", "2020-02-10", going_concern=True),
        # FORGN's tenk is 2020-05-05 but a later concept fact was filed 2020-06-15 (<=asof): the
        # authoritative asof_max_filing_date the audit must surface, proving it reads the FIX-1 field.
        "FORGN": _deep("FORGN", "555", "2020-05-05", asof_max_filing_date="2020-06-15"),
    }
    VAL = {
        "BUYME": _val("fcf_cap", 0.45, True),                              # band+MoS45+eligible+0kill -> BUY
        "WATCHR": _val("fcf_cap", 0.10, True),                            # MoS 10 < 30 -> WATCH
        "TRAP": _val("fcf_cap", 0.55, False, ["fundamental_decline_flag"]),# cheap but blocked -> AVOID
        "DYING": _val("fcf_cap", 0.50, False, ["going_concern"]),         # kill-flag -> AVOID
        "FORGN": _val("abstain", None, False, ["foreign_filer_unvaluable"]),# no band -> abstain
    }
    # Forward-return book (status ok) keyed by ticker.
    RET = {
        "BUYME": {"status": "ok", "total_return": 0.40, "realized_to_last_close": False,
                  "entry_date": "2020-06-30", "exit_date": "2021-06-30",
                  "target_exit_date": "2021-06-30"},
        "WATCHR": {"status": "ok", "total_return": 0.05, "realized_to_last_close": False,
                   "entry_date": "2020-06-30", "exit_date": "2021-06-30",
                   "target_exit_date": "2021-06-30"},
        "TRAP": {"status": "ok", "total_return": -0.70, "realized_to_last_close": False,
                 "entry_date": "2020-06-30", "exit_date": "2021-06-30",
                 "target_exit_date": "2021-06-30"},
        "DYING": {"status": "ok", "total_return": -0.99, "realized_to_last_close": True,
                  "entry_date": "2020-06-30", "exit_date": "2020-10-01",
                  "target_exit_date": "2021-06-30"},
        "FORGN": {"status": "ok", "total_return": -0.60, "realized_to_last_close": False,
                  "entry_date": "2020-06-30", "exit_date": "2021-06-30",
                  "target_exit_date": "2021-06-30"},
    }

    universe = [
        {"ticker": "BUYME", "cik": "111", "name": "Buy Me Co", "recall_channel": "sic_reverse",
         "delisted_after_asof": False},
        {"ticker": "WATCHR", "cik": "222", "name": "Watcher Inc", "recall_channel": "sic_reverse",
         "delisted_after_asof": False},
        {"ticker": "TRAP", "cik": "333", "name": "Value Trap Ltd", "recall_channel": "sic_reverse",
         "delisted_after_asof": False},
        {"ticker": "DYING", "cik": "444", "name": "Dying Corp", "recall_channel": "sic_reverse",
         "delisted_after_asof": True},
        {"ticker": "FORGN", "cik": "555", "name": "Foreign SA", "recall_channel": "sic_reverse",
         "delisted_after_asof": False},
    ]

    def fake_universe(theme, a):
        assert a == asof
        return universe

    def fake_pull(ticker, cik, as_of=None):
        assert as_of == asof, "harness MUST pull with as_of=asof (PIT), not the live default"
        return DEEP[ticker]

    def fake_valuation(deep, market_cap, cfg):
        return VAL[deep["ticker"]]

    def fake_mktcap(ticker, a, cik=None):
        return {"mktcap": 100_000_000, "source": "sec_shares_x_price"}

    def fake_forward(ticker, a, h):
        assert a == asof and h == horizon
        return RET[ticker]

    def fake_bench(a, h):
        # IWM +10% over the window.
        return {"status": "ok", "benchmark": "IWM", "total_return": 0.10,
                "entry_date": "2020-06-30", "exit_date": "2021-06-30",
                "target_exit_date": "2021-06-30"}

    cell = run_cell(
        "deathcare", asof, horizon,
        universe_fn=fake_universe, pull_fn=fake_pull, valuation_fn=fake_valuation,
        mktcap_fn=fake_mktcap, forward_fn=fake_forward, benchmark_fn=fake_bench,
        write=False,
    )

    # ---- 1) bucketing put every name where the BUY contract says ----
    by_t = {r["ticker"]: r for r in cell["names"]}
    assert by_t["BUYME"]["bucket"] == BUCKET_BUY, f"BUYME -> buy_eligible, got {by_t['BUYME']['bucket']}"
    assert by_t["WATCHR"]["bucket"] == BUCKET_WATCH, f"WATCHR -> WATCH, got {by_t['WATCHR']['bucket']}"
    assert by_t["TRAP"]["bucket"] == BUCKET_AVOID, f"TRAP (cheap-but-blocked) -> AVOID, got {by_t['TRAP']['bucket']}"
    assert by_t["DYING"]["bucket"] == BUCKET_AVOID, f"DYING (kill-flag) -> AVOID, got {by_t['DYING']['bucket']}"
    assert by_t["FORGN"]["bucket"] == BUCKET_ABSTAIN, f"FORGN (no band) -> abstain, got {by_t['FORGN']['bucket']}"
    assert by_t["DYING"]["killflag_count"] == 1, "going-concern -> killflag_count 1"
    assert cell["bucket_counts"] == {BUCKET_BUY: 1, BUCKET_WATCH: 1, BUCKET_AVOID: 2, BUCKET_ABSTAIN: 1}, (
        f"bucket counts: {cell['bucket_counts']}")

    # ---- 2) per-bucket stats: mean/median/excess-vs-IWM/win-rate math ----
    st = cell["per_bucket_stats"]
    assert st[BUCKET_BUY]["n"] == 1 and abs(st[BUCKET_BUY]["mean_return"] - 0.40) < 1e-9
    # excess vs IWM(+10%): BUY +40% -> +30% excess; win-rate 1.0 (one winner).
    assert abs(st[BUCKET_BUY]["mean_excess_vs_iwm"] - 0.30) < 1e-9, f"BUY excess: {st[BUCKET_BUY]}"
    assert st[BUCKET_BUY]["win_rate"] == 1.0, "BUY win-rate 1.0"
    assert st[BUCKET_WATCH]["win_rate"] == 1.0 and abs(st[BUCKET_WATCH]["mean_return"] - 0.05) < 1e-9
    # AVOID has two names: -0.70 and -0.99 -> mean -0.845, median -0.845, win-rate 0.0.
    assert abs(st[BUCKET_AVOID]["mean_return"] - (-0.845)) < 1e-9, f"AVOID mean: {st[BUCKET_AVOID]}"
    assert abs(st[BUCKET_AVOID]["median_return"] - (-0.845)) < 1e-9, f"AVOID median: {st[BUCKET_AVOID]}"
    assert st[BUCKET_AVOID]["win_rate"] == 0.0, "AVOID win-rate 0.0"
    # excess for AVOID: each return minus IWM(+0.10) -> mean(-0.80,-1.09) = -0.945.
    assert abs(st[BUCKET_AVOID]["mean_excess_vs_iwm"] - (-0.945)) < 1e-9, f"AVOID excess: {st[BUCKET_AVOID]}"

    # ---- 3) blowup-avoidance: 3 blowups (TRAP/DYING/FORGN), ALL in AVOID/abstain -> fraction 1.0 ----
    ba = cell["blowup_avoidance"]
    assert ba["n_blowups"] == 3, f"3 names below -40%: {ba}"
    assert ba["n_blowups_in_avoid_or_abstain"] == 3, "all blowups in AVOID/abstain"
    assert ba["blowup_avoidance_fraction"] == 1.0, f"blowup-avoidance fraction 1.0: {ba}"
    assert set(ba["blowup_tickers"]) == {"TRAP", "DYING", "FORGN"}, f"blowup set: {ba['blowup_tickers']}"
    # BUYME (+40%) and WATCHR (+5%) are NOT blowups.
    assert "BUYME" not in ba["blowup_tickers"] and "WATCHR" not in ba["blowup_tickers"]

    # ---- 4) look-ahead audit: NON-VACUOUS, reads derived.asof_max_filing_date (FIX 1) ----
    au = cell["look_ahead_audit"]
    # Max comes from FORGN's asof_max_filing_date (2020-06-15), NOT its tenk date (2020-05-05) —
    # proves the audit reads the FIX-1 field, the whole point of making the audit non-vacuous.
    assert au["max_filing_date"] == "2020-06-15", f"max filing date observed: {au['max_filing_date']}"
    assert au["max_filing_date"] <= asof and au["max_filing_date_le_asof"] is True, "audit passed"
    # NON-VACUOUS: each of 5 names surfaces BOTH asof_max_filing_date + tenk date -> 10 observed.
    assert au["n_filing_dates_observed"] == 10, f"non-vacuous observed count: {au['n_filing_dates_observed']}"
    assert au["non_vacuous"] is True, "audit must be non-vacuous (>0 filing dates) for a real cell"
    assert au["benchmark"] == "IWM" and au["benchmark_exit_date"] == "2021-06-30", f"bench dates: {au}"
    assert au["entry_date_range"] == ["2020-06-30", "2020-06-30"], f"entry range: {au['entry_date_range']}"

    # ---- 5) the audit MUST RAISE on a look-ahead leak (filing AFTER asof) ----
    leak_rows = [{"ticker": "LEAK", "filing_dates": ["2021-01-15"], "forward_return": {}}]
    raised = False
    try:
        look_ahead_audit(leak_rows, asof, {"benchmark": "IWM"})
    except AssertionError:
        raised = True
    assert raised, "look_ahead_audit MUST raise AssertionError when a filing_date is AFTER asof"

    # ---- 5b) the audit MUST RAISE on a VACUOUS cell (expect_dates but 0 dates observed, bug B) ----
    no_date_rows = [{"ticker": "NODATE", "filing_dates": [], "forward_return": {}}]
    # Without expect_dates a 0-date cell is allowed (e.g. an empty universe) and must NOT raise.
    au_vac = look_ahead_audit(no_date_rows, asof, {"benchmark": "IWM"})
    assert au_vac["non_vacuous"] is False and au_vac["max_filing_date"] is None, "0-date audit recorded vacuous"
    raised_vac = False
    try:
        look_ahead_audit(no_date_rows, asof, {"benchmark": "IWM"}, expect_dates=True)
    except AssertionError:
        raised_vac = True
    assert raised_vac, "look_ahead_audit MUST raise on a VACUOUS audit (0 filing dates) when expect_dates"

    # ---- 6) a name with no priceable return is EXCLUDED from graded stats (bug C), not fabricated ----
    def fake_forward_noret(ticker, a, h):
        if ticker == "WATCHR":
            return {"status": "no_exit_price", "total_return": None,
                    "reason": "entry resolved but NO close at/before target exit"}
        return RET[ticker]
    cell2 = run_cell(
        "deathcare", asof, horizon,
        universe_fn=fake_universe, pull_fn=fake_pull, valuation_fn=fake_valuation,
        mktcap_fn=fake_mktcap, forward_fn=fake_forward_noret, benchmark_fn=fake_bench,
        write=False,
    )
    w = {r["ticker"]: r for r in cell2["names"]}["WATCHR"]
    assert w["total_return"] is None and w["return_status"] == "no_exit_price", "no-return name recorded w/ reason"
    stW = cell2["per_bucket_stats"][BUCKET_WATCH]
    # WATCHR was the only WATCH name and is now unpriceable -> WATCH bucket is excluded from grading.
    assert stW["n"] == 0 and stW["n_with_return"] == 0, "unpriceable WATCH name excluded from graded n"
    assert stW["unpriceable_count"] == 1, f"unpriceable WATCH name counted: {stW}"
    assert stW["mean_return"] is None and stW["win_rate"] is None, "no fabricated number for an unpriceable bucket"
    assert cell2["unpriceable_count"] == 1, f"cell-level unpriceable_count: {cell2['unpriceable_count']}"
    # The no-priceable-return name is still surfaced in `names` (audit), just not graded.
    assert any(r["ticker"] == "WATCHR" for r in cell2["names"]), "unpriceable name retained for audit"

    # ---- 7) a ticker-less name (CIK-only shell, bug A residual) is EXCLUDED + counted unpriceable ----
    universe3 = universe + [
        {"ticker": "", "cik": "999", "name": "Shell Finance Corp", "recall_channel": "sic_reverse",
         "delisted_after_asof": False},
    ]
    DEEP3 = dict(DEEP)
    # The shell still surfaces a filing date (filed<=asof) so the cell audit stays non-vacuous.
    DEEP3[""] = _deep("", "999", "2020-01-10")
    VAL3 = dict(VAL); VAL3[""] = _val("abstain", None, False, ["no_financials"])
    RET3 = dict(RET)  # no entry for "" — but ticker-less names never call forward_fn.

    def fake_universe3(theme, a):
        return universe3
    def fake_pull3(ticker, cik, as_of=None):
        assert as_of == asof
        return DEEP3[ticker]
    def fake_valuation3(deep, market_cap, cfg):
        return VAL3[deep["ticker"]]
    def fake_forward3(ticker, a, h):
        return RET3[ticker]

    cell3 = run_cell(
        "deathcare", asof, horizon,
        universe_fn=fake_universe3, pull_fn=fake_pull3, valuation_fn=fake_valuation3,
        mktcap_fn=fake_mktcap, forward_fn=fake_forward3, benchmark_fn=fake_bench,
        write=False,
    )
    shell = {r["cik"]: r for r in cell3["names"]}["999"]
    assert shell["return_status"] == "no_ticker", "ticker-less name flagged no_ticker (never priced)"
    # The shell lands in abstain but must NOT be graded; the real FORGN abstain blowup still is.
    stAb = cell3["per_bucket_stats"][BUCKET_ABSTAIN]
    assert stAb["unpriceable_count"] == 1, f"ticker-less abstain name counted unpriceable: {stAb}"
    assert stAb["n"] == 1, f"only the priceable abstain name (FORGN) graded: {stAb}"
    assert cell3["unpriceable_count"] == 1, "cell-level unpriceable_count counts the shell"
    # Blowup-avoidance still sees the 3 priceable blowups (shell has no return -> not a blowup).
    assert cell3["blowup_avoidance"]["n_blowups"] == 3, f"shell excluded from blowups: {cell3['blowup_avoidance']}"
    assert cell3["blowup_avoidance"]["unpriceable_count"] == 1, "blowup-avoidance reports unpriceable_count"

    print("backtest selftest PASS (bucketing BUY-contract; per-bucket mean/median/excess-vs-IWM/win-rate; "
          "blowup-avoidance 3/3 in AVOID+abstain; look-ahead audit reads asof_max_filing_date, NON-vacuous, "
          "raises on leak AND on vacuous cell; unpriceable no-ticker/no-return names EXCLUDED from grading "
          "+ counted unpriceable_count)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> None:
    ap = argparse.ArgumentParser(
        description="backtest.py (PIECE 4) — run one point-in-time (theme, as-of) backtest cell.")
    ap.add_argument("--selftest", action="store_true", help="Run the offline synthetic-cell selftest and exit.")
    ap.add_argument("--theme", help="Theme name (must be SIC-floored in filter_by_sic.THEME_SIC).")
    ap.add_argument("--asof", help="As-of date YYYY-MM-DD (the point-in-time T).")
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_MONTHS,
                    help=f"Forward-return horizon in months (default {DEFAULT_HORIZON_MONTHS}).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap universe names processed (smoke-test ONLY; the panel runs the full universe).")
    ap.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between names (rate-limit courtesy).")
    ap.add_argument("--no-write", action="store_true", help="Do not write the per-cell JSON (print only).")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return
    if not (args.theme and args.asof):
        ap.error("use --selftest, or --theme <t> --asof YYYY-MM-DD [--horizon 12] [--limit N].")

    cell = run_cell(args.theme, args.asof, args.horizon,
                    limit=args.limit, write=not args.no_write, sleep=args.sleep)
    # Compact stdout summary (the full detail is in the per-cell JSON).
    summary = {
        "theme": cell["theme"], "asof": cell["asof"], "horizon_months": cell["horizon_months"],
        "universe_size": cell["universe_size"], "bucket_counts": cell["bucket_counts"],
        "benchmark": cell["benchmark"],
        "blowup_avoidance": cell["blowup_avoidance"],
        "look_ahead_audit": cell["look_ahead_audit"],
        "output_path": cell.get("output_path"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
