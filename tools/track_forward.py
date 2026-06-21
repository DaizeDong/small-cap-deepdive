"""
track_forward.py — Phase 6: Track-Forward Calibration / Brier Scoring

Epistemic purpose: log every deep-dive verdict, score it against realized returns after the
horizon matures, compute Brier score + calibration — so the rubric can be tuned by evidence
not vibes.

Without this, the skill is "confident garbage" risk: 3 runs produced 40 deep-dives and 0 BUYs
but we cannot know if that conservatism is CORRECT (market efficient) or MISCALIBRATED
(rubric too strict) without forward tracking.

Usage:
    # Record a verdict from a deepdive-fanout JSON:
    python tools/track_forward.py --record reports/smallcap/deepdive_verdicts.json

    # Record a single verdict via CLI flags:
    python tools/track_forward.py --record --ticker EGAN --rating 观察 --theme aeromro \\
        --mos-pct null --mos-basis abstain --catalyst null

    # Score matured verdicts (today - verdict_date >= horizon_months):
    python tools/track_forward.py --score

    # Generate scorecard markdown:
    python tools/track_forward.py --scorecard

    # Show pending/matured/scored counts:
    python tools/track_forward.py --status

    # Backfill null entry_price / benchmark_entry_price for seeded verdicts:
    python tools/track_forward.py --backfill

    # Run synthetic Brier math selftest (no network):
    python tools/track_forward.py --selftest

Output: metrics/verdicts.jsonl (append-only), metrics/scorecard.md

Notes:
    --backfill is the correct way to add prices to existing rows with null entry prices.
    Do NOT use --record for tickers already in verdicts.jsonl (dup-detection will warn+skip).
    --backfill is idempotent: rows with non-null entry_price are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, today

REPO = Path(__file__).resolve().parent.parent
METRICS_DIR = REPO / "metrics"
VERDICTS_FILE = METRICS_DIR / "verdicts.jsonl"
SCORECARD_FILE = METRICS_DIR / "scorecard.md"

# Default rating → implied_prob convention (used only when no model confidence is supplied).
# Rationale: 买入 predicts OUTperformance, 避开 predicts UNDERperformance.
# NOTE (P12): the LIVE path now derives implied_prob from the model's own confidence mapped by
# rating DIRECTION (see _implied_prob_from_confidence). RATING_PROB is the fallback when a verdict
# carries no confidence, and the reference anchor the calibration scorecard reports per bucket.
RATING_PROB = {
    "买入": 0.65,
    "观察": 0.50,
    "避开": 0.35,
}

# Rating → directional sign for confidence-as-probability mapping (P12a).
# 买入 predicts OUTperformance (+1), 避开 predicts UNDERperformance (-1), 观察 is neutral (0).
RATING_DIRECTION = {
    "买入": 1,
    "观察": 0,
    "避开": -1,
}

DEFAULT_HORIZON_MONTHS = 12
DEFAULT_BENCHMARK = "IWM"  # Russell 2000 small-cap ETF — correct universe comparison

# De-risk-native metric thresholds (P12c).
BLOWUP_DRAWDOWN_THRESHOLD = -0.40  # a horizon total return <= -40% counts as a "blowup"

# Calibration bucket edges for implied_prob
CALIB_BUCKETS = [(0.0, 0.40), (0.40, 0.55), (0.55, 0.70), (0.70, 1.01)]

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


def _implied_prob_from_confidence(rating: str, confidence: float | None) -> float:
    """Map a model confidence (0..1) to an implied probability of FAVORABLE outcome, by
    rating direction (P12a).

        favorable = stock total return > benchmark total return over horizon.

    Direction sign d = RATING_DIRECTION[rating] in {+1, 0, -1}:
        implied_prob = 0.5 + d * (confidence - 0.5)

    Examples:
        买入 (d=+1), confidence 0.70 -> 0.70   (high confidence the thesis resolves favorably)
        避开 (d=-1), confidence 0.70 -> 0.30   (high confidence in UNDERperformance)
        观察 (d= 0), any confidence  -> 0.50   (neutral by construction)
        买入 (d=+1), confidence 0.50 -> 0.50   (no edge)

    When confidence is None/invalid, fall back to the fixed RATING_PROB convention. Result is
    clamped to (0, 1) so Brier math is always well-defined.
    """
    d = RATING_DIRECTION.get(rating, 0)
    if confidence is None:
        return RATING_PROB.get(rating, 0.50)
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return RATING_PROB.get(rating, 0.50)
    # Tolerate confidence given as a percentage (e.g. 70 -> 0.70).
    if c > 1.0:
        c = c / 100.0
    p = 0.5 + d * (c - 0.5)
    # Clamp into the open interval so a perfectly-wrong/right Brier stays in [0,1] and never NaN.
    return min(0.999, max(0.001, p))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _months_between(date1: str, date2: str) -> float:
    """Approximate months between two YYYY-MM-DD strings."""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return (d2 - d1).days / 30.44


def _fetch_close(ticker: str, on_date: str, verbose: bool = False) -> float | None:
    """Fetch the DIVIDEND-ADJUSTED closing price for ticker on or near on_date via yfinance.

    Tries the exact date first (most recent trading day on or before on_date,
    within a ±7 calendar day search window).
    Returns None on any error (yfinance unavailable, ticker not found, etc.).

    Total-return basis (P12b): yfinance is called with auto_adjust=True, which back-adjusts the
    Close column for BOTH splits AND cash dividends. The price returned here is therefore a
    total-return series — (horizon_close - entry_close) / entry_close is the dividend-adjusted
    total return, not price-only. This removes the systematic bias that previously scored every
    high-dividend WATCH name (MLPs/utilities: UAN, ARTNA, MSEX, YORW) as an underperformer.
    With auto_adjust=True yfinance overwrites "Close" with the adjusted series and drops the
    separate "Adj Close" column, so preferring "Close" below already yields the adjusted value.

    Bug-fix (Phase 6 review): close price is now derived from hist_filt (the date-filtered
    slice), not from the unfiltered hist. The old code extracted close_col from hist before
    filtering, so iloc[-1] could return a price one trading day AFTER the intended date.
    """
    try:
        import yfinance as yf
        dt = datetime.strptime(on_date, "%Y-%m-%d")
        start = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
        end = (dt + timedelta(days=2)).strftime("%Y-%m-%d")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if hist is None or hist.empty:
            return None

        # Filter to on or before on_date FIRST, then resolve Close column from the filtered slice.
        hist_filt = hist[hist.index <= dt.strftime("%Y-%m-%d")]
        if hist_filt.empty:
            # Fallback: take the earliest available row (pre-listing or data gap edge case)
            hist_filt = hist

        # Resolve "Close" column: prefer "Close", then "Adj Close", then first column.
        # Only use the positional fallback if neither named column is present.
        if "Close" in hist_filt.columns:
            close_col = hist_filt["Close"]
        elif "Adj Close" in hist_filt.columns:
            close_col = hist_filt["Adj Close"]
        else:
            close_col = hist_filt.iloc[:, 0]

        raw = close_col.iloc[-1]
        price = float(raw.item() if hasattr(raw, "item") else raw)

        if verbose:
            resolved_date = hist_filt.index[-1]
            print(f"    [_fetch_close] {ticker} on_date={on_date} → resolved={resolved_date.date()} price={price:.4f}")

        return price
    except Exception:
        return None


def _load_verdicts() -> list[dict]:
    if not VERDICTS_FILE.exists():
        return []
    rows = []
    for line in VERDICTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _save_verdicts(rows: list[dict]) -> None:
    """Atomically rewrite verdicts.jsonl.

    Writes to a temp file in the same directory, flushes, then os.replace() to the
    final path. os.replace() is atomic on both POSIX and Windows (same-filesystem),
    so a mid-write crash cannot leave a truncated ledger.
    """
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = VERDICTS_FILE.with_suffix(".jsonl.tmp")
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    tmp_path.write_text(content, encoding="utf-8")
    # Flush is implicit after write_text closes the file; os.replace is atomic.
    os.replace(tmp_path, VERDICTS_FILE)


def _append_verdict(row: dict) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(VERDICTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _brier(implied_prob: float, favorable: bool) -> float:
    """Brier score for a single verdict: (p - o)^2 where o in {0, 1}."""
    o = 1.0 if favorable else 0.0
    return (implied_prob - o) ** 2


def _is_data_false_positive(row: dict) -> bool:
    """True if a verdict is an adversarially-resolved BUY data false-positive (P12d).

    These rows carry adjudication=="data_false_positive": a BUY-eligible (MoS>=30%) name that the
    validation campaign proved is a data/model pathology (debt truncation, wrong-entity,
    financial-SIC misroute, OCF-proxy, concentration, lumpy OCF). They are KEPT OUT of the
    price-Brier (they have no forward price horizon) but DO feed the BUY-data-integrity metric.
    """
    return row.get("adjudication") == "data_false_positive"


def _price_scorable(rows: list[dict]) -> list[dict]:
    """Scored verdicts eligible for the price-Brier: scored AND not a data_false_positive.

    The 19 backfilled BUY false-positives are adjudicated by balance-sheet cross-check, not by a
    forward price, so they must never contaminate the price-return Brier / calibration table.
    """
    return [r for r in rows if r.get("scored") and not _is_data_false_positive(r)]


# ---------------------------------------------------------------------------
# De-risk-native metrics (P12c)
#
# Brier-vs-IWM measures stock-picking. This scanner's job is blowup AVOIDANCE. These three
# metrics measure that directly and are reported alongside Brier in the scorecard.
# ---------------------------------------------------------------------------

def _blowup_avoidance_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Fraction of scored 观察/避开 (de-risk) verdicts whose stock horizon TOTAL RETURN avoided a
    blowup (return > threshold, default -40%). Higher is better.

    Only price-scorable, non-BUY verdicts with a non-null stock_return_pct are counted. Returns
    None when there are no such verdicts yet.
    """
    pool = [r for r in _price_scorable(rows)
            if r.get("rating") in ("观察", "避开") and r.get("stock_return_pct") is not None]
    if not pool:
        return None
    avoided = sum(1 for r in pool if (r["stock_return_pct"] / 100.0) > threshold)
    return avoided / len(pool)


def _downside_capture_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Fraction of scored 避开 (AVOID) verdicts that did their job: UNDERperformed the benchmark
    (realized_excess_pct < 0) AND drew down past the blowup threshold. This is the de-risk
    "we correctly told you to run" rate. Higher means AVOID is genuinely flagging losers.

    Returns None when there are no scored AVOID verdicts with the needed fields.
    """
    pool = [r for r in _price_scorable(rows)
            if r.get("rating") == "避开"
            and r.get("stock_return_pct") is not None
            and r.get("realized_excess_pct") is not None]
    if not pool:
        return None
    captured = sum(
        1 for r in pool
        if r["realized_excess_pct"] < 0 and (r["stock_return_pct"] / 100.0) <= threshold
    )
    return captured / len(pool)


def _buy_data_integrity_rate(rows: list[dict]) -> float | None:
    """Fraction of all BUY verdicts that survive a balance-sheet cross-check, i.e. are NOT
    adjudicated data_false_positive. Measurable TODAY from the backfilled 19 — no 12-month wait.

    integrity = clean_BUYs / all_BUYs. With only the 19 validation false-positives logged and no
    clean BUY yet, this is 0.0 — the honest, decision-relevant headline number. Returns None when
    no BUY verdicts exist at all.
    """
    buys = [r for r in rows if r.get("rating") == "买入"]
    if not buys:
        return None
    clean = sum(1 for r in buys if not _is_data_false_positive(r))
    return clean / len(buys)


# ---------------------------------------------------------------------------
# Signals snapshot (P15/P16/P17) — DIAGNOSTIC-ONLY, RECORDED-BUT-INERT.
#
# THE FIREWALL (approved philosophy decision Q2): the between-filings side-channel computed by
# tools/signals.py lives in a SEPARATE top-level "signals" namespace and NEVER originates or
# up-weights a BUY. track_forward's only contact with it is to SNAPSHOT a compact summary into
# the verdict row so per-signal predictive value can be Brier-calibrated LATER. This snapshot is
# WRITE-ONLY from the scorer's perspective: implied_prob, rating, and every scoring path
# (_implied_prob_from_confidence, _brier, cmd_score, the scorecard) MUST NOT read it. It is
# recorded-but-inert — present in the row for future per-signal calibration, load-bearing on
# nothing today. The selftest asserts implied_prob/rating are identical with vs without it.
# ---------------------------------------------------------------------------

def _signals_snapshot(signals: dict | None) -> dict | None:
    """Build a compact, inert snapshot of the diagnostic signals for a verdict row.

    `signals` is the top-level "signals" namespace produced by tools/signals.compute_signals
    (a SIBLING of "derived", never inside it). This extracts just two diagnostic labels:

      - divergence_label   (P16): price_divergence.divergence_label, one of
                            {unpriced_improvement, melting_ice_cube_priced, aligned, unclear}.
      - ownership          (P17): a compact summary — the recent 13D/13G count, the single
                            newest 13D/13G filing (form/file_date/filer), short_interest_pct,
                            short_trend, and the explicit staleness_note label.

    Returns None when `signals` is absent/empty or carries nothing usable (so a row without a
    side-channel simply has signals_snapshot=None — no fabricated structure). The returned dict
    is for FORWARD CALIBRATION ONLY and is never consulted by any scoring code path.
    """
    if not isinstance(signals, dict) or not signals:
        return None

    snap: dict[str, Any] = {}

    pd = signals.get("price_divergence")
    if isinstance(pd, dict):
        snap["divergence_label"] = pd.get("divergence_label")

    own = signals.get("ownership")
    if isinstance(own, dict):
        filings = own.get("recent_13d_13g") or []
        count = own.get("recent_13d_13g_count")
        if count is None:
            count = len(filings)
        latest = None
        if filings:
            f0 = filings[0]
            if isinstance(f0, dict):
                latest = {
                    "form": f0.get("form"),
                    "file_date": f0.get("file_date"),
                    "filer": f0.get("filer"),
                }
        snap["ownership"] = {
            "recent_13d_13g_count": count,
            "latest_13d_13g": latest,
            "short_interest_pct": own.get("short_interest_pct"),
            "short_trend": own.get("short_trend"),
            "staleness_note": own.get("staleness_note"),
        }

    # Stamp the firewall provenance so a reader of verdicts.jsonl cannot mistake this for an input.
    if snap:
        snap["diagnostic_only"] = True
        return snap
    return None


def _extract_signals(rec: dict) -> dict | None:
    """Pull the diagnostic "signals" namespace out of a verdict-source record, if present.

    The deepdive output carries signals as a TOP-LEVEL key (sibling of "derived"). A verdict
    record fanned out from it may forward that namespace verbatim under "signals". Returns the
    dict or None — never raises. Reading the namespace here is the ONLY place the calibration
    layer touches it, and it is used solely to build the recorded-but-inert snapshot.
    """
    if not isinstance(rec, dict):
        return None
    sig = rec.get("signals")
    return sig if isinstance(sig, dict) else None


# ---------------------------------------------------------------------------
# --record
# ---------------------------------------------------------------------------

def _build_verdict_from_flags(args) -> dict:
    """Build a verdict dict from explicit CLI flags."""
    verdict_date = args.verdict_date or _today()
    rating = args.rating

    confidence: float | None = None
    if getattr(args, "confidence", None) not in (None, "", "null", "none"):
        try:
            confidence = float(args.confidence)
        except (TypeError, ValueError):
            confidence = None
    # P12a: implied_prob = model confidence mapped by rating direction (fallback RATING_PROB).
    implied_prob = _implied_prob_from_confidence(rating, confidence)

    mos_pct: float | None = None
    if args.mos_pct and args.mos_pct.lower() not in ("null", "none", ""):
        try:
            mos_pct = float(args.mos_pct)
        except ValueError:
            pass

    kill_flags: list[str] = []
    if args.kill_flags:
        kill_flags = [f.strip() for f in args.kill_flags.split(",") if f.strip()]

    catalyst: str | None = None
    if args.catalyst and args.catalyst.lower() not in ("null", "none", ""):
        catalyst = args.catalyst

    entry_date = verdict_date
    entry_price = _fetch_close(args.ticker, entry_date, verbose=True)
    benchmark_entry_price = _fetch_close(DEFAULT_BENCHMARK, entry_date, verbose=True)

    return {
        "verdict_date": verdict_date,
        "ticker": args.ticker,
        "cik": args.cik or None,
        "theme": args.theme or None,
        "rating": rating,
        "mos_pct": mos_pct,
        "mos_basis": args.mos_basis or "abstain",
        "kill_flags": kill_flags,
        "catalyst": catalyst,
        "confidence": confidence,
        "implied_prob": implied_prob,
        "horizon_months": DEFAULT_HORIZON_MONTHS,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "benchmark": DEFAULT_BENCHMARK,
        "benchmark_entry_price": benchmark_entry_price,
        "scored": False,
        "stock_return_pct": None,
        "realized_excess_pct": None,
        "brier": None,
        "adjudication": None,
        "fp_cause": None,
        # P15/P16/P17 diagnostic side-channel snapshot — recorded-but-inert (firewall). The CLI
        # flag path carries no signals namespace, so this is None here; the JSON-fanout path
        # (_build_verdicts_from_json) populates it from the deepdive's top-level "signals".
        "signals_snapshot": None,
        "notes": None,
    }


def _build_verdicts_from_json(path: Path) -> list[dict]:
    """Parse a deepdive_verdicts.json (list of verdict dicts) or a deepdive-fanout output."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raw = [raw]

    rows = []
    for rec in raw:
        ticker = rec.get("ticker", "")
        rating = rec.get("rating", "观察")
        # Normalize: deepdive-fanout may use English
        _rating_norm = {"buy": "买入", "watch": "观察", "hold": "观察",
                        "avoid": "避开", "sell": "避开"}
        rating = _rating_norm.get(rating.lower(), rating)

        # P12a: confidence-as-probability mapped by rating direction (fallback RATING_PROB).
        confidence: float | None = None
        raw_conf = rec.get("confidence")
        if raw_conf is not None and str(raw_conf).lower() not in ("null", "none", ""):
            try:
                confidence = float(raw_conf)
            except (TypeError, ValueError):
                confidence = None
        implied_prob = _implied_prob_from_confidence(rating, confidence)

        # mos_pct: from valuation json or report field
        mos_pct: float | None = None
        raw_mos = rec.get("margin_of_safety_pct") or rec.get("mos_pct")
        if raw_mos is not None:
            try:
                mos_pct = float(raw_mos)
            except (TypeError, ValueError):
                pass

        mos_basis = rec.get("mos_basis", "abstain")
        if mos_basis not in ("fcf_cap", "nav", "abstain"):
            mos_basis = "abstain"

        catalyst = rec.get("catalyst") or None
        if catalyst and str(catalyst).lower() in ("null", "none", ""):
            catalyst = None

        kill_flags_raw = rec.get("kill_flags") or rec.get("killflag_notes") or []
        if isinstance(kill_flags_raw, str):
            kill_flags = [kill_flags_raw] if kill_flags_raw else []
        else:
            kill_flags = list(kill_flags_raw)

        # verdict_date: try to infer from file or use today
        verdict_date = rec.get("verdict_date") or rec.get("date") or _today()

        cik = str(rec.get("cik", "")) or None
        theme = rec.get("theme") or rec.get("theme_slug") or None

        entry_date = verdict_date
        entry_price = _fetch_close(ticker, entry_date, verbose=True) if ticker else None
        benchmark_entry_price = _fetch_close(DEFAULT_BENCHMARK, entry_date, verbose=True)

        # P15/P16/P17 firewall: snapshot the diagnostic side-channel (recorded-but-inert). Read
        # the top-level "signals" namespace from the source record and compact it for FUTURE
        # per-signal Brier calibration. This does NOT touch rating/implied_prob computed above.
        signals_snapshot = _signals_snapshot(_extract_signals(rec))

        row = {
            "verdict_date": verdict_date,
            "ticker": ticker,
            "cik": cik,
            "theme": theme,
            "rating": rating,
            "mos_pct": mos_pct,
            "mos_basis": mos_basis,
            "kill_flags": kill_flags,
            "catalyst": catalyst,
            "confidence": confidence,
            "implied_prob": implied_prob,
            "horizon_months": DEFAULT_HORIZON_MONTHS,
            "entry_price": entry_price,
            "entry_date": entry_date,
            "benchmark": DEFAULT_BENCHMARK,
            "benchmark_entry_price": benchmark_entry_price,
            "scored": False,
            "stock_return_pct": None,
            "realized_excess_pct": None,
            "brier": None,
            "adjudication": None,
            "fp_cause": None,
            "signals_snapshot": signals_snapshot,
            "notes": None,
        }
        rows.append(row)
    return rows


def cmd_record(args) -> None:
    """--record: ingest one or more verdicts.

    Dup-detection: if (ticker, verdict_date) already exists in verdicts.jsonl, the row is
    SKIPPED with a warning. Do NOT use --record to add prices to existing seeded rows —
    use --backfill for that purpose. --backfill is idempotent and correctly fills null
    entry_price / benchmark_entry_price in-place without creating duplicate rows.
    """
    existing = _load_verdicts()
    existing_keys = {(r["ticker"], r["verdict_date"]) for r in existing}

    new_rows: list[dict] = []

    if args.record_path:
        path = Path(args.record_path)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        new_rows = _build_verdicts_from_json(path)
    elif args.ticker:
        new_rows = [_build_verdict_from_flags(args)]
    else:
        print("ERROR: --record requires either a file path or --ticker flags", file=sys.stderr)
        sys.exit(1)

    added = 0
    warned = 0
    for row in new_rows:
        key = (row["ticker"], row["verdict_date"])
        if key in existing_keys:
            print(f"WARN: {row['ticker']} on {row['verdict_date']} already logged — skipping "
                  f"(use --backfill to fill null entry prices for existing rows)")
            warned += 1
            continue
        existing_keys.add(key)
        _append_verdict(row)
        added += 1
        price_str = f"${row['entry_price']:.2f}" if row["entry_price"] else "N/A (yfinance unavailable)"
        bm_str = f"${row['benchmark_entry_price']:.2f}" if row["benchmark_entry_price"] else "N/A"
        print(f"  Recorded {row['ticker']} | {row['rating']} | p={row['implied_prob']} | "
              f"entry={price_str} | {DEFAULT_BENCHMARK}={bm_str} | horizon={row['horizon_months']}m")

    print(f"\nRecorded {added} new verdict(s). {warned} duplicate(s) skipped.")
    print(f"Verdicts file: {VERDICTS_FILE}")


# ---------------------------------------------------------------------------
# --backfill
# ---------------------------------------------------------------------------

def cmd_backfill(args) -> None:
    """--backfill: for every verdict with null entry_price or null benchmark_entry_price,
    fetch the historical close at its verdict_date (stock + IWM) and fill them in.

    Idempotent: rows where both entry_price and benchmark_entry_price are already non-null
    are skipped. Saves atomically via _save_verdicts.

    This is the correct way to populate prices for seeded verdicts. Do not use --record
    for tickers already in verdicts.jsonl (dup-detection will warn and skip).
    """
    rows = _load_verdicts()
    if not rows:
        print("No verdicts found in verdicts.jsonl.")
        return

    filled = 0
    skipped_already_filled = 0
    failed = []

    for row in rows:
        ticker = row.get("ticker", "")
        verdict_date = row.get("verdict_date", "")
        has_stock = row.get("entry_price") is not None
        has_bm = row.get("benchmark_entry_price") is not None

        if has_stock and has_bm:
            skipped_already_filled += 1
            continue

        # Fetch whichever is missing
        changed = False
        if not has_stock and ticker:
            price = _fetch_close(ticker, verdict_date, verbose=True)
            if price is not None:
                row["entry_price"] = price
                changed = True
            else:
                failed.append(f"{ticker} ({verdict_date}) — stock price unavailable")

        if not has_bm:
            benchmark = row.get("benchmark", DEFAULT_BENCHMARK)
            bm_price = _fetch_close(benchmark, verdict_date, verbose=True)
            if bm_price is not None:
                row["benchmark_entry_price"] = bm_price
                changed = True
            else:
                failed.append(f"{ticker} ({verdict_date}) — {benchmark} price unavailable")

        if changed:
            filled += 1
            ep = row.get("entry_price")
            bm = row.get("benchmark_entry_price")
            ep_str = f"${ep:.2f}" if ep is not None else "N/A"
            bm_str = f"${bm:.2f}" if bm is not None else "N/A"
            print(f"  Backfilled {ticker} | entry={ep_str} | {DEFAULT_BENCHMARK}={bm_str}")

    # Atomic save
    _save_verdicts(rows)

    total = len(rows)
    print(f"\nBackfill complete: {filled} filled | {skipped_already_filled} already had prices "
          f"| {len(failed)} failed | {total} total verdicts")
    if failed:
        print("\nFailed tickers (thin markets / delisted / data unavailable):")
        for f in failed:
            print(f"  - {f}")


# ---------------------------------------------------------------------------
# --backfill-validation-fp  (P12d)
# ---------------------------------------------------------------------------

# The 19 BUY-eligible (MoS>=30%) names from the 2026-06-19 validation campaign, every one a
# false positive with an identified XBRL/model cause (docs/2026-06-19-validation-report.md +
# reports/smallcap/2026-06-19_validation-v0.2.0/). MoS% as reported (whole-percent); fp_cause is
# the validated structural pathology. These are logged as rating=买入 with a NEW field
# adjudication="data_false_positive" so the BUY arm of the calibration loop is not permanently
# empty — and they are KEPT OUT of the price-Brier (adjudicated by balance-sheet cross-check,
# not by a forward price). cik is unknown in the validation artifacts (not emitted by valuation
# JSON) → null.
VALIDATION_FP_DATE = "2026-06-19"
VALIDATION_FP = [
    # (ticker, mos_pct, theme, fp_cause)
    ("CISS", 2355.0, "shipping",  "micro-cap collapse + debt=total-liabilities proxy"),
    ("AII",   290.0, "lowev",     "material_weakness + cash unavailable -> EV excludes cash"),
    ("GRNT",  209.0, "lowev",     "material_weakness + cash unavailable -> EV understated"),
    ("QFIN",  190.0, "lowev",     "debt=total-liabilities proxy + OCF-proxy + China VIE"),
    ("ARDT",  168.0, "cluster",   "OCF-proxy FCF (no capex) + large-cap out of scope"),
    ("VSNT",  153.0, "spinoff",   "large-cap scope leak + structural decline + linear terminal value"),
    ("SNFCA", 129.0, "microcap",  "NI unit anomaly from DEF 14A (32B vs 344M rev); wrong form"),
    ("DAC",   128.0, "shipping",  "OCF-proxy FCF (no capex)"),
    ("HCI",   118.0, "lowev",     "insurer financial-structure mismatch; FCF/EV model invalid"),
    ("FSBW",  104.0, "regbank",   "debt truncation (stale 2022) -> false fcf_cap routing"),
    ("GSL",   102.0, "shipping",  "total_debt=None -> EV collapses to market cap; ZERO flags raised"),
    ("GNE",    97.0, "lowev",     "over-normalized FCF; multiple kill-flags"),
    ("ESEA",   87.0, "shipping",  "going_concern + IFRS capex gaps"),
    ("FVRR",   82.0, "netnet",    "material_weakness"),
    ("SIGA",   76.0, "netnet",    "~90% single-customer BARDA concentration; lumpy/over-normalized OCF"),
    ("GIII",   73.0, "netnet",    "material_weakness"),
    ("RYAM",   63.0, "specchem",  "debt truncation 779M -> 21.5M -> false MoS"),
    ("TUSK",   55.0, "oilsvc",    "FEMA one-time OCF inflates 5yr avg; revenue collapsed"),
    ("CMRE",   45.0, "shipping",  "OCF-proxy FCF (no capex)"),
]


def _build_validation_fp_rows() -> list[dict]:
    """Build the 19 data_false_positive BUY verdict rows (P12d). Deterministic; no network."""
    rows = []
    for ticker, mos_pct, theme, fp_cause in VALIDATION_FP:
        rating = "买入"
        # confidence is not the axis here — these are adversarially RESOLVED. Keep the BUY
        # convention implied_prob=0.65 for reference, but they never enter the price-Brier.
        implied_prob = _implied_prob_from_confidence(rating, None)
        rows.append({
            "verdict_date": VALIDATION_FP_DATE,
            "ticker": ticker,
            "cik": None,
            "theme": theme,
            "rating": rating,
            "mos_pct": mos_pct,
            "mos_basis": "fcf_cap",
            "kill_flags": [],
            "catalyst": None,
            "confidence": None,
            "implied_prob": implied_prob,
            "horizon_months": DEFAULT_HORIZON_MONTHS,
            "entry_price": None,
            "entry_date": VALIDATION_FP_DATE,
            "benchmark": DEFAULT_BENCHMARK,
            "benchmark_entry_price": None,
            "scored": False,
            "stock_return_pct": None,
            "realized_excess_pct": None,
            "brier": None,
            "adjudication": "data_false_positive",
            "fp_cause": fp_cause,
            "signals_snapshot": None,  # backfilled FP cohort predates the side-channel
            "notes": "[validation 2026-06-19 BUY false-positive] kept OUT of price-Brier; "
                     "feeds BUY-data-integrity metric. See docs/2026-06-19-validation-report.md.",
        })
    return rows


def cmd_backfill_validation_fp(args) -> None:
    """--backfill-validation-fp: inject the 19 validation BUY false-positives (P12d).

    Idempotent: rows whose (ticker, verdict_date) already exist are skipped. These rows carry
    adjudication="data_false_positive" and are excluded from the price-Brier; they exist so the
    BUY arm of calibration is observable (BUY-data-integrity metric) instead of empty for 12+ months.
    """
    existing = _load_verdicts()
    existing_keys = {(r["ticker"], r["verdict_date"]) for r in existing}

    added = 0
    skipped = 0
    for row in _build_validation_fp_rows():
        key = (row["ticker"], row["verdict_date"])
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        _append_verdict(row)
        added += 1
        print(f"  Backfilled FP {row['ticker']} | MoS={row['mos_pct']:.0f}% | "
              f"adjudication=data_false_positive | cause={row['fp_cause']}")

    print(f"\nValidation FP backfill: {added} added | {skipped} already present "
          f"| {len(VALIDATION_FP)} total in cohort")
    integrity = _buy_data_integrity_rate(_load_verdicts())
    if integrity is not None:
        print(f"BUY data-integrity now: {integrity*100:.1f}% "
              f"(clean BUYs / all BUYs)")


# ---------------------------------------------------------------------------
# --score
# ---------------------------------------------------------------------------

def cmd_score(args) -> None:
    """--score: for each unscored matured verdict, fetch horizon-end price and score."""
    rows = _load_verdicts()
    today_str = _today()

    matured = 0
    scored_now = 0
    still_pending = 0

    for row in rows:
        if row.get("scored"):
            continue
        # data_false_positive verdicts (P12d) are adjudicated by balance-sheet cross-check, not by
        # a forward price horizon — never price-score them.
        if _is_data_false_positive(row):
            continue
        months_elapsed = _months_between(row["verdict_date"], today_str)
        if months_elapsed < row.get("horizon_months", DEFAULT_HORIZON_MONTHS):
            still_pending += 1
            continue

        matured += 1
        ticker = row["ticker"]
        benchmark = row.get("benchmark", DEFAULT_BENCHMARK)

        # Horizon end date: verdict_date + horizon_months
        vd = datetime.strptime(row["verdict_date"], "%Y-%m-%d")
        horizon_days = int(row.get("horizon_months", DEFAULT_HORIZON_MONTHS) * 30.44)
        horizon_date = (vd + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

        stock_horizon = _fetch_close(ticker, horizon_date)
        bm_horizon = _fetch_close(benchmark, horizon_date)

        if stock_horizon is None or bm_horizon is None:
            print(f"  WARN: cannot fetch horizon price for {ticker} or {benchmark} at {horizon_date}; skipping")
            still_pending += 1
            continue

        entry_price = row.get("entry_price")
        bm_entry = row.get("benchmark_entry_price")

        if not entry_price or not bm_entry:
            print(f"  WARN: {ticker} missing entry prices; cannot score")
            still_pending += 1
            continue

        # Dividend-adjusted total returns (P12b): both legs use auto_adjust=True closes.
        stock_return = (stock_horizon - entry_price) / entry_price
        bm_return = (bm_horizon - bm_entry) / bm_entry
        excess = stock_return - bm_return
        favorable = excess > 0

        implied_prob = row.get("implied_prob", 0.50)
        b = _brier(implied_prob, favorable)

        row["stock_return_pct"] = round(stock_return * 100, 2)  # absolute total return (de-risk metrics)
        row["realized_excess_pct"] = round(excess * 100, 2)
        row["brier"] = round(b, 6)
        row["scored"] = True
        scored_now += 1
        print(f"  Scored {ticker}: stock={stock_return*100:+.1f}% bm={bm_return*100:+.1f}% "
              f"excess={excess*100:+.1f}% favorable={favorable} brier={b:.4f}")

    _save_verdicts(rows)
    print(f"\nMatured: {matured} | Scored now: {scored_now} | Still pending: {still_pending}")


# ---------------------------------------------------------------------------
# --scorecard
# ---------------------------------------------------------------------------

def cmd_scorecard(args) -> None:
    """--scorecard: aggregate scored verdicts and write metrics/scorecard.md."""
    rows = _load_verdicts()
    today_str = _today()

    # Price-Brier population excludes data_false_positive BUYs (P12d): they have no forward price.
    scored = _price_scorable(rows)
    fp_rows = [r for r in rows if _is_data_false_positive(r)]
    pending = [r for r in rows if not r.get("scored") and not _is_data_false_positive(r)]

    # De-risk-native metrics (P12c) — measurable now, alongside / ahead of the price-Brier.
    blowup_avoid = _blowup_avoidance_rate(rows)
    downside_cap = _downside_capture_rate(rows)
    buy_integrity = _buy_data_integrity_rate(rows)

    lines = [
        "# Track-Forward Calibration Scorecard",
        "",
        f"> Generated: {today_str}",
        f"> Verdicts file: `metrics/verdicts.jsonl`",
        f"> Benchmark: {DEFAULT_BENCHMARK} (Russell 2000 small-cap ETF)",
        f"> Returns: dividend-adjusted total return (yfinance auto_adjust=True)",
        "",
        "## De-Risk-Native Metrics",
        "",
        "*(A de-risk scanner's job is blowup AVOIDANCE, not beating IWM by a hair. These measure that.)*",
        "",
        "| Metric | Value | N | Notes |",
        "|---|---|---|---|",
        f"| BUY data-integrity (clean / all BUY) | "
        f"{(f'{buy_integrity*100:.1f}%' if buy_integrity is not None else '—')} | "
        f"{sum(1 for r in rows if r.get('rating')=='买入')} | "
        f"measurable today; {len(fp_rows)} adjudicated data_false_positive |",
        f"| Blowup-avoidance (观察/避开 avoided <= {BLOWUP_DRAWDOWN_THRESHOLD*100:.0f}% total return) | "
        f"{(f'{blowup_avoid*100:.1f}%' if blowup_avoid is not None else '—')} | "
        f"{len([r for r in scored if r.get('rating') in ('观察','避开') and r.get('stock_return_pct') is not None])} | "
        f"needs matured price verdicts |",
        f"| Downside-capture (避开 underperformed AND blew up) | "
        f"{(f'{downside_cap*100:.1f}%' if downside_cap is not None else '—')} | "
        f"{len([r for r in scored if r.get('rating')=='避开' and r.get('stock_return_pct') is not None])} | "
        f"needs matured 避开 verdicts |",
        "",
    ]

    if fp_rows:
        lines += [
            "## BUY Data-Integrity (validation false-positive cohort)",
            "",
            f"{len(fp_rows)} BUY-eligible (MoS>=30%) names from the 2026-06-19 validation campaign, each "
            "adjudicated `data_false_positive` by balance-sheet cross-check. Kept OUT of the price-Brier "
            "(no forward horizon); they populate the BUY-data-integrity metric so the BUY arm is not "
            "permanently empty.",
            "",
            "| Ticker | MoS% | fp_cause |",
            "|---|---|---|",
        ]
        for r in sorted(fp_rows, key=lambda x: -(x.get("mos_pct") or 0)):
            mos = r.get("mos_pct")
            mos_str = f"{mos:.0f}%" if mos is not None else "—"
            lines.append(f"| {r['ticker']} | {mos_str} | {r.get('fp_cause','—')} |")
        lines.append("")

    if not scored:
        # Compute earliest maturity date
        earliest_maturity = None
        for r in pending:
            vd = datetime.strptime(r["verdict_date"], "%Y-%m-%d")
            horizon_days = int(r.get("horizon_months", DEFAULT_HORIZON_MONTHS) * 30.44)
            maturity = vd + timedelta(days=horizon_days)
            if earliest_maturity is None or maturity < earliest_maturity:
                earliest_maturity = maturity

        earliest_str = earliest_maturity.strftime("%Y-%m-%d") if earliest_maturity else "unknown"

        lines += [
            "## Status: 0 Scored / " + str(len(pending)) + " Pending",
            "",
            "**Calibration unknown until verdicts mature.**",
            "",
            f"Earliest maturity date: **{earliest_str}**",
            "",
            "No rubric tuning is justified yet. Run `python tools/track_forward.py --score` "
            "periodically; once ~20 verdicts mature, calibration becomes statistically meaningful.",
            "",
            "This is the correct honest state. The epistemic spine of the skill (market-efficient "
            "vs. rubric-miscalibrated) cannot be resolved until forward data accumulates.",
            "",
            "## Pending Verdicts",
            "",
            "| Ticker | Theme | Rating | p_implied | Verdict Date | Maturity Date |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(pending, key=lambda x: x["verdict_date"]):
            vd = datetime.strptime(r["verdict_date"], "%Y-%m-%d")
            horizon_days = int(r.get("horizon_months", DEFAULT_HORIZON_MONTHS) * 30.44)
            maturity = (vd + timedelta(days=horizon_days)).strftime("%Y-%m-%d")
            lines.append(
                f"| {r['ticker']} | {r.get('theme','—')} | {r['rating']} | "
                f"{r.get('implied_prob',0.5):.2f} | {r['verdict_date']} | {maturity} |"
            )
    else:
        # Compute overall Brier
        overall_brier = sum(r["brier"] for r in scored) / len(scored)
        overall_hit_rate = sum(1 for r in scored if r.get("realized_excess_pct", 0) > 0) / len(scored)

        lines += [
            "## Overall",
            "",
            f"- **Scored verdicts:** {len(scored)}",
            f"- **Pending verdicts:** {len(pending)}",
            f"- **Overall Brier score:** {overall_brier:.4f} "
            "(0=perfect, 0.25=uninformative random, 1=perfectly wrong)",
            f"- **Overall hit rate (stock beat benchmark):** {overall_hit_rate*100:.1f}%",
            "",
        ]

        # By rating bucket
        lines += [
            "## By Rating Bucket",
            "",
            "| Rating | N | Avg Brier | Hit Rate (stock > benchmark) | Implied p |",
            "|---|---|---|---|---|",
        ]
        for rating in ["买入", "观察", "避开"]:
            bucket = [r for r in scored if r.get("rating") == rating]
            if not bucket:
                lines.append(f"| {rating} | 0 | — | — | {RATING_PROB.get(rating, '—')} |")
                continue
            avg_b = sum(r["brier"] for r in bucket) / len(bucket)
            hit = sum(1 for r in bucket if r.get("realized_excess_pct", 0) > 0) / len(bucket)
            p = RATING_PROB.get(rating, 0.5)
            lines.append(f"| {rating} | {len(bucket)} | {avg_b:.4f} | {hit*100:.1f}% | {p:.2f} |")

        # Calibration table
        # Calibration error = realized_freq − mean(implied_prob of members in bucket).
        # Using the mean implied_prob (not the bucket geometric midpoint) is correct because
        # all 观察 verdicts sit at exactly p=0.50 — error must be realized_freq − 0.50,
        # not realized_freq − 0.475 (the midpoint of [0.40, 0.55)).
        lines += [
            "",
            "## Calibration Table",
            "",
            "*(Predicted probability bucket vs. realized favorable frequency)*",
            "*(Calibration error = realized_freq − mean implied_prob of bucket members)*",
            "",
            "| p bucket | N | Mean implied_p | Realized freq | Calibration error |",
            "|---|---|---|---|---|",
        ]
        for (lo, hi) in CALIB_BUCKETS:
            bucket = [r for r in scored if lo <= r.get("implied_prob", 0.5) < hi]
            if not bucket:
                lines.append(f"| {lo:.2f}–{hi:.2f} | 0 | — | — | — |")
                continue
            mean_p = sum(r.get("implied_prob", 0.5) for r in bucket) / len(bucket)
            realized = sum(1 for r in bucket if r.get("realized_excess_pct", 0) > 0) / len(bucket)
            err = realized - mean_p
            lines.append(f"| {lo:.2f}–{hi:.2f} | {len(bucket)} | {mean_p:.3f} | {realized:.2f} | {err:+.2f} |")

        # Individual scored table
        lines += [
            "",
            "## Scored Verdicts",
            "",
            "| Ticker | Rating | p | Excess% | Favorable | Brier |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(scored, key=lambda x: x["verdict_date"]):
            fav = "YES" if r.get("realized_excess_pct", 0) > 0 else "NO"
            lines.append(
                f"| {r['ticker']} | {r['rating']} | {r.get('implied_prob',0.5):.2f} | "
                f"{r.get('realized_excess_pct','—')} | {fav} | {r.get('brier','—')} |"
            )

        lines += [
            "",
            "## Rubric Tuning Note",
            "",
            "Do NOT tune the rubric until ≥~20 verdicts have matured. "
            "Small samples produce false calibration signals. "
            "See `reference/track-forward.md` for methodology.",
        ]

    if pending:
        # Show earliest maturity for pending
        earliest_maturity = None
        for r in pending:
            vd = datetime.strptime(r["verdict_date"], "%Y-%m-%d")
            horizon_days = int(r.get("horizon_months", DEFAULT_HORIZON_MONTHS) * 30.44)
            maturity = vd + timedelta(days=horizon_days)
            if earliest_maturity is None or maturity < earliest_maturity:
                earliest_maturity = maturity
        if earliest_maturity and scored:
            lines += ["", f"*Earliest pending maturity: {earliest_maturity.strftime('%Y-%m-%d')}*"]

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    SCORECARD_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Scorecard written: {SCORECARD_FILE}")
    print(f"Scored: {len(scored)} | Pending: {len(pending)}")


# ---------------------------------------------------------------------------
# --status
# ---------------------------------------------------------------------------

def cmd_status(args) -> None:
    """--status: show counts of pending/matured/scored."""
    rows = _load_verdicts()
    today_str = _today()

    fp_rows = [r for r in rows if _is_data_false_positive(r)]
    scored = _price_scorable(rows)
    unscored = [r for r in rows if not r.get("scored") and not _is_data_false_positive(r)]

    matured_unscored = []
    pending = []
    for r in unscored:
        months_elapsed = _months_between(r["verdict_date"], today_str)
        if months_elapsed >= r.get("horizon_months", DEFAULT_HORIZON_MONTHS):
            matured_unscored.append(r)
        else:
            pending.append(r)

    print(f"Track-forward status — {today_str}")
    print(f"  Total verdicts:      {len(rows)}")
    print(f"  Scored (price):      {len(scored)}")
    print(f"  Matured (unscored):  {len(matured_unscored)}  <- run --score")
    print(f"  Pending (horizon not reached): {len(pending)}")
    print(f"  data_false_positive (BUY, out of price-Brier): {len(fp_rows)}")
    buy_integrity = _buy_data_integrity_rate(rows)
    if buy_integrity is not None:
        print(f"  BUY data-integrity:  {buy_integrity*100:.1f}% "
              f"({sum(1 for r in rows if r.get('rating')=='买入')} BUY verdicts)")

    if pending:
        earliest = None
        for r in pending:
            vd = datetime.strptime(r["verdict_date"], "%Y-%m-%d")
            horizon_days = int(r.get("horizon_months", DEFAULT_HORIZON_MONTHS) * 30.44)
            maturity = vd + timedelta(days=horizon_days)
            if earliest is None or maturity < earliest:
                earliest = maturity
        print(f"  Earliest maturity:   {earliest.strftime('%Y-%m-%d') if earliest else '—'}")

    if scored:
        overall_brier = sum(r["brier"] for r in scored) / len(scored)
        print(f"  Overall Brier:       {overall_brier:.4f}")
    else:
        print(f"  Overall Brier:       N/A (no scored verdicts yet)")


# ---------------------------------------------------------------------------
# --recall-gold (P8 recall floor measurement)
# ---------------------------------------------------------------------------

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


def cmd_recall_gold(args) -> None:
    """--recall-gold: compute recall@gold for a theme's recall set vs its hand-built gold list."""
    theme = args.theme
    if not theme:
        print("recall-gold requires --theme", file=sys.stderr)
        sys.exit(2)
    paths = [Path(p) for p in (args.recall_gold or [])]
    if not paths:
        print("recall-gold requires one or more candidate JSON paths", file=sys.stderr)
        sys.exit(2)
    recalled, fts_count, stage_sets = _recall_set_from_candidate_files(paths)
    res = recall_at_gold(
        theme, recalled, fts_hit_count=fts_count,
        fts_tickers=stage_sets["fts"],
        sic_tickers=stage_sets["sic"],
        mktcap_dropped=stage_sets["mktcap_dropped"],
        gated_out=stage_sets["gated_out"],
    )
    if res is None:
        print(f"recall@gold: no gold list for theme '{theme}' — not measurable")
        return
    print(f"recall@gold — theme '{theme}'")
    print(f"  gold ({len(res['gold'])}):     {', '.join(res['gold'])}")
    print(f"  recalled_gold: {', '.join(res['recalled_gold']) or '—'}")
    print(f"  MISSING_gold:  {', '.join(res['missing_gold']) or '—'}")
    print(f"  recall@gold:   {res['recall_at_gold']*100:.1f}% "
          f"({len(res['recalled_gold'])}/{len(res['gold'])})")
    sb = res["stage_breakdown"]
    print(f"  loss-stage breakdown:")
    for stage in RECALL_STAGES:
        members = sb.get(stage) or []
        print(f"    {stage:<15} {len(members):>2}  {', '.join(members) or '—'}")
    if res["fts_cap_warning"]:
        print(f"  [WARN] {res['fts_cap_warning']}")


# ---------------------------------------------------------------------------
# --selftest (synthetic Brier math, no network)
# ---------------------------------------------------------------------------

def _selftest() -> None:
    """Verify Brier/calibration math with synthetic in-memory data. No network calls."""
    print("Running track_forward selftest (synthetic Brier math, no network)...")

    # --- Test 1: per-row Brier = (p - o)^2 ---
    cases = [
        (0.65, True,  (0.65 - 1.0) ** 2),  # 买入, favorable
        (0.65, False, (0.65 - 0.0) ** 2),  # 买入, unfavorable
        (0.50, True,  (0.50 - 1.0) ** 2),  # 观察, favorable
        (0.50, False, (0.50 - 0.0) ** 2),  # 观察, unfavorable
        (0.35, True,  (0.35 - 1.0) ** 2),  # 避开, favorable
        (0.35, False, (0.35 - 0.0) ** 2),  # 避开, unfavorable
    ]
    for p, fav, expected in cases:
        got = _brier(p, fav)
        assert abs(got - expected) < 1e-9, (
            f"Brier({p}, {fav}) = {got} but expected {expected}"
        )
    print("  PASS: per-row Brier = (p - o)^2 for all 6 rating×outcome combinations")

    # --- Test 2: perfect prediction set → Brier = 0 ---
    perfect = [
        {"implied_prob": 1.0, "favorable": True,  "brier": _brier(1.0, True)},
        {"implied_prob": 0.0, "favorable": False, "brier": _brier(0.0, False)},
    ]
    perfect_avg = sum(r["brier"] for r in perfect) / len(perfect)
    assert abs(perfect_avg) < 1e-9, f"Perfect prediction Brier should be 0, got {perfect_avg}"
    print(f"  PASS: perfect prediction set → Brier = {perfect_avg}")

    # --- Test 3: worst-case (perfectly wrong) → Brier = 1 ---
    worst = [
        {"implied_prob": 1.0, "favorable": False, "brier": _brier(1.0, False)},
        {"implied_prob": 0.0, "favorable": True,  "brier": _brier(0.0, True)},
    ]
    worst_avg = sum(r["brier"] for r in worst) / len(worst)
    assert abs(worst_avg - 1.0) < 1e-9, f"Worst-case Brier should be 1.0, got {worst_avg}"
    print(f"  PASS: worst-case prediction set → Brier = {worst_avg}")

    # --- Test 4: uninformative (p=0.5 always) → Brier = 0.25 ---
    uninformative = [
        {"implied_prob": 0.5, "favorable": True,  "brier": _brier(0.5, True)},
        {"implied_prob": 0.5, "favorable": False, "brier": _brier(0.5, False)},
    ]
    uninf_avg = sum(r["brier"] for r in uninformative) / len(uninformative)
    assert abs(uninf_avg - 0.25) < 1e-9, f"Uninformative Brier should be 0.25, got {uninf_avg}"
    print(f"  PASS: uninformative (p=0.5) prediction set → Brier = {uninf_avg}")

    # --- Test 5: bucket aggregation — 买入 bucket with 2 scored verdicts ---
    bucket_verdicts = [
        {"rating": "买入", "implied_prob": 0.65, "brier": _brier(0.65, True),  "realized_excess_pct": 10.0},
        {"rating": "买入", "implied_prob": 0.65, "brier": _brier(0.65, False), "realized_excess_pct": -5.0},
    ]
    buy_briers = [r["brier"] for r in bucket_verdicts]
    avg_buy_brier = sum(buy_briers) / len(buy_briers)
    expected_buy_brier = ((0.65 - 1.0)**2 + (0.65 - 0.0)**2) / 2
    assert abs(avg_buy_brier - expected_buy_brier) < 1e-9, (
        f"Bucket avg Brier wrong: {avg_buy_brier} vs {expected_buy_brier}"
    )
    hit_rate = sum(1 for r in bucket_verdicts if r["realized_excess_pct"] > 0) / len(bucket_verdicts)
    assert abs(hit_rate - 0.5) < 1e-9, f"Hit rate should be 0.5, got {hit_rate}"
    print(f"  PASS: bucket aggregation — 买入 avg Brier={avg_buy_brier:.4f}, hit_rate={hit_rate:.1%}")

    # --- Test 6: calibration table — bucket membership + mean-implied-prob error ---
    # All 观察 verdicts sit at p=0.50. Calibration error must be realized_freq − 0.50,
    # NOT realized_freq − 0.475 (bucket midpoint of [0.40, 0.55)).
    calib_test = [
        {"implied_prob": 0.35, "realized_excess_pct": -5.0},  # 避开 bucket [0.0, 0.40)
        {"implied_prob": 0.50, "realized_excess_pct": 8.0},   # 观察 bucket [0.40, 0.55)
        {"implied_prob": 0.65, "realized_excess_pct": 12.0},  # 买入 bucket [0.55, 0.70)
    ]
    # Verify bucket assignments
    for lo, hi in CALIB_BUCKETS:
        bucket = [r for r in calib_test if lo <= r["implied_prob"] < hi]
        # Each prob should fall in exactly one bucket
        for r in calib_test:
            count = sum(1 for (l2, h2) in CALIB_BUCKETS if l2 <= r["implied_prob"] < h2)
            assert count == 1, f"p={r['implied_prob']} falls in {count} buckets (should be 1)"
    print("  PASS: calibration table — each implied_prob in exactly one bucket")

    # Verify calibration error uses mean_implied_prob of bucket members (not midpoint).
    # 观察 bucket [0.40, 0.55): one verdict at p=0.50, favorable (excess=8.0 > 0).
    # realized_freq = 1.0 / 1 = 1.0; mean_implied_p = 0.50; error = 1.0 - 0.50 = +0.50
    # NOT: 1.0 - 0.475 = +0.525 (the old midpoint-based error)
    obs_bucket = [r for r in calib_test if 0.40 <= r["implied_prob"] < 0.55]
    assert len(obs_bucket) == 1, f"Expected 1 verdict in 观察 bucket, got {len(obs_bucket)}"
    mean_p_obs = sum(r["implied_prob"] for r in obs_bucket) / len(obs_bucket)
    realized_obs = sum(1 for r in obs_bucket if r["realized_excess_pct"] > 0) / len(obs_bucket)
    calib_err_mean = realized_obs - mean_p_obs    # correct: uses mean implied_prob
    calib_err_mid  = realized_obs - (0.40 + 0.55) / 2  # wrong: uses geometric midpoint
    assert abs(calib_err_mean - (1.0 - 0.50)) < 1e-9, (
        f"Calibration error with mean_p wrong: {calib_err_mean}"
    )
    assert abs(calib_err_mid - (1.0 - 0.475)) < 1e-9, (
        f"Old midpoint error sanity check failed: {calib_err_mid}"
    )
    assert abs(calib_err_mean - calib_err_mid) > 1e-6, (
        "mean_p and midpoint errors should differ for 观察 bucket — check fix is applied"
    )
    print(f"  PASS: calibration error uses mean implied_prob ({mean_p_obs:.3f}), "
          f"not bucket midpoint (0.475): err={calib_err_mean:+.3f} vs midpoint-err={calib_err_mid:+.3f}")

    # --- Test 7: rating → prob convention ---
    for rating, expected_p in RATING_PROB.items():
        assert 0.0 < expected_p < 1.0, f"RATING_PROB[{rating}] = {expected_p} out of [0,1]"
        assert RATING_PROB["买入"] > RATING_PROB["观察"] > RATING_PROB["避开"], (
            "Convention must be: 买入 > 观察 > 避开"
        )
    print(f"  PASS: rating→prob convention: 买入={RATING_PROB['买入']}, "
          f"观察={RATING_PROB['观察']}, 避开={RATING_PROB['避开']}")

    # --- Test 8 (P12a): confidence-as-probability mapped by rating direction ---
    # buy: p = 0.5 + (c - 0.5); avoid: p = 0.5 - (c - 0.5); watch: p = 0.5 always.
    conf_cases = [
        ("买入", 0.70, 0.70),
        ("买入", 0.90, 0.90),
        ("买入", 0.50, 0.50),
        ("避开", 0.70, 0.30),
        ("避开", 0.90, 0.10),
        ("观察", 0.70, 0.50),   # neutral regardless of confidence
        ("观察", 0.95, 0.50),
    ]
    for rating, conf, expected in conf_cases:
        got = _implied_prob_from_confidence(rating, conf)
        assert abs(got - expected) < 1e-9, (
            f"_implied_prob_from_confidence({rating}, {conf}) = {got}, expected {expected}"
        )
    # Percentage form (70 -> 0.70) and None fallback to RATING_PROB.
    assert abs(_implied_prob_from_confidence("买入", 70) - 0.70) < 1e-9, "pct-form confidence not normalized"
    assert abs(_implied_prob_from_confidence("买入", None) - RATING_PROB["买入"]) < 1e-9, "None should fall back to RATING_PROB"
    assert abs(_implied_prob_from_confidence("避开", None) - RATING_PROB["避开"]) < 1e-9, "None avoid fallback wrong"
    # Direction symmetry: a buy and an avoid at the same confidence straddle 0.5 symmetrically.
    pb = _implied_prob_from_confidence("买入", 0.80)
    pa = _implied_prob_from_confidence("避开", 0.80)
    assert abs((pb - 0.5) + (pa - 0.5)) < 1e-9, "buy/avoid not symmetric about 0.5"
    # Clamp: extreme confidence stays in the open interval (Brier well-defined).
    assert 0.0 < _implied_prob_from_confidence("买入", 1.0) < 1.0, "p=1.0 must be clamped open"
    assert 0.0 < _implied_prob_from_confidence("避开", 1.0) < 1.0, "avoid p must be clamped open"
    print("  PASS: confidence-as-probability — direction map, %-form, None fallback, symmetry, clamp")

    # --- Test 9 (P12b): dividend-adjusted total return is the return basis ---
    # The excess is computed from auto_adjust closes; verify the return arithmetic on adjusted prices.
    entry, horizon = 100.0, 110.0       # +10% total return (price + reinvested dividends)
    bm_entry, bm_horizon = 200.0, 206.0  # +3% benchmark total return
    stock_return = (horizon - entry) / entry
    bm_return = (bm_horizon - bm_entry) / bm_entry
    excess = stock_return - bm_return
    assert abs(stock_return - 0.10) < 1e-9, "total return arithmetic wrong"
    assert abs(excess - 0.07) < 1e-9, f"excess total return wrong: {excess}"
    assert abs(_brier(0.65, excess > 0) - (0.65 - 1.0) ** 2) < 1e-9, "Brier on total-return outcome wrong"
    print(f"  PASS: dividend-adjusted total return — stock {stock_return:+.0%}, excess {excess:+.0%}")

    # --- Test 10 (P12d): data_false_positive class excluded from price-Brier ---
    fp_rows = _build_validation_fp_rows()
    assert len(fp_rows) == 19, f"expected 19 validation FP rows, got {len(fp_rows)}"
    assert len(VALIDATION_FP) == 19, f"VALIDATION_FP cohort must be 19, got {len(VALIDATION_FP)}"
    for r in fp_rows:
        assert r["adjudication"] == "data_false_positive", f"{r['ticker']} missing adjudication"
        assert r["rating"] == "买入", f"{r['ticker']} FP must be rated 买入"
        assert r["fp_cause"], f"{r['ticker']} missing fp_cause"
        assert r["mos_pct"] is not None and r["mos_pct"] >= 30.0, f"{r['ticker']} MoS must be >=30%"
        assert _is_data_false_positive(r), f"{r['ticker']} not recognized as data_false_positive"
    tickers = [r["ticker"] for r in fp_rows]
    assert len(set(tickers)) == 19, "duplicate ticker in validation FP cohort"
    for must in ("SIGA", "GSL", "VSNT", "HCI", "CMRE"):
        assert must in tickers, f"{must} missing from validation FP cohort"
    # A FP BUY scored=True must NOT count toward the price-Brier population.
    scored_fp = dict(fp_rows[0]); scored_fp["scored"] = True; scored_fp["brier"] = 0.1225
    mixed = [
        scored_fp,
        {"rating": "观察", "scored": True, "brier": 0.25, "stock_return_pct": 5.0,
         "realized_excess_pct": 2.0, "implied_prob": 0.5},
    ]
    ps = _price_scorable(mixed)
    assert len(ps) == 1 and not _is_data_false_positive(ps[0]), (
        "price-scorable population must exclude data_false_positive rows"
    )
    print(f"  PASS: data_false_positive class — 19-name cohort, all 买入/MoS>=30%, excluded from price-Brier")

    # --- Test 11 (P12c): de-risk-native metrics (blowup-avoidance / downside-capture / BUY-integrity) ---
    # BUY data-integrity: 19 FP + 1 clean BUY -> 1/20 = 0.05.
    clean_buy = {"rating": "买入", "adjudication": None}
    integ_rows = fp_rows + [clean_buy]
    integ = _buy_data_integrity_rate(integ_rows)
    assert abs(integ - (1.0 / 20.0)) < 1e-9, f"BUY data-integrity wrong: {integ}"
    # All-FP -> 0.0; no BUY at all -> None.
    assert _buy_data_integrity_rate(fp_rows) == 0.0, "all-FP integrity should be 0.0"
    assert _buy_data_integrity_rate([{"rating": "观察"}]) is None, "no-BUY integrity should be None"
    # Blowup-avoidance: 2 of 3 de-risk names avoided <= -40%.
    derisk = [
        {"rating": "观察", "scored": True, "stock_return_pct": -10.0},  # avoided
        {"rating": "避开", "scored": True, "stock_return_pct": -55.0},  # blew up
        {"rating": "避开", "scored": True, "stock_return_pct":  20.0},  # avoided
    ]
    ba = _blowup_avoidance_rate(derisk)
    assert abs(ba - (2.0 / 3.0)) < 1e-9, f"blowup-avoidance wrong: {ba}"
    assert _blowup_avoidance_rate([]) is None, "empty blowup-avoidance should be None"
    # Downside-capture: 避开 that underperformed AND blew up = 1 of 2 避开.
    dc_rows = [
        {"rating": "避开", "scored": True, "stock_return_pct": -55.0, "realized_excess_pct": -30.0},  # captured
        {"rating": "避开", "scored": True, "stock_return_pct":  20.0, "realized_excess_pct":  10.0},  # not
    ]
    dc = _downside_capture_rate(dc_rows)
    assert abs(dc - 0.5) < 1e-9, f"downside-capture wrong: {dc}"
    assert _downside_capture_rate([{"rating": "观察", "scored": True}]) is None, "no-避开 downside-capture should be None"
    print(f"  PASS: de-risk metrics — integrity={integ:.2f}, blowup-avoid={ba:.2f}, downside-capture={dc:.2f}")

    # --- P8: recall@gold — measure the recall floor against a hand-built gold list ---
    # theme_gold resolves via case-insensitive substring (compound slug), unmapped -> [].
    assert theme_gold("deathcare") == ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"], (
        f"P8: deathcare gold cohort mismatch: {theme_gold('deathcare')}"
    )
    assert theme_gold("funeral_deathcare_2026") == ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"], (
        "P8: compound slug must resolve the gold list (substring match)"
    )
    assert theme_gold("ai agents") == [], "P8: an unmapped theme must have NO gold list"
    assert recall_at_gold("ai agents", ["NVDA"]) is None, (
        "P8: recall_at_gold must be None (not measurable) for an unmapped theme"
    )

    # Full recall: every gold member present -> recall@gold == 1.0, missing empty.
    _full = recall_at_gold("deathcare", ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA", "NOISE"])
    assert _full["recall_at_gold"] == 1.0, f"P8: full recall must be 1.0, got {_full['recall_at_gold']}"
    assert _full["missing_gold"] == [], f"P8: full recall must miss none, got {_full['missing_gold']}"

    # Partial recall: SIC floor catches SCI/CSV (SIC-7200) but the cross-SIC names leak ->
    # recall@gold = 2/6, missing = the 4 cross-SIC members. This is the residual FTS-only gap.
    _part = recall_at_gold("deathcare", ["sci", "csv"])  # lower-case -> must normalize
    assert _part["recall_at_gold"] == round(2 / 6, 4), (
        f"P8: partial recall must be 2/6 (rounded), got {_part['recall_at_gold']}"
    )
    assert _part["recalled_gold"] == ["CSV", "SCI"], f"P8: hits must normalize+sort: {_part['recalled_gold']}"
    assert _part["missing_gold"] == ["HI", "MATW", "SNFCA", "STON"], (
        f"P8: missing must be the cross-SIC leak: {_part['missing_gold']}"
    )
    assert _part["fts_cap_warning"] is None, "P8: no cap warning when fts_hit_count omitted"
    # Default stage_breakdown (no per-stage inputs): recalled gold -> recalled_final, the rest ->
    # fts_missed, and the five lists partition gold exactly with no double-counting.
    _psb = _part["stage_breakdown"]
    assert set(_psb) == set(RECALL_STAGES), f"P8: stage_breakdown keys must be RECALL_STAGES: {set(_psb)}"
    assert _psb["recalled_final"] == ["CSV", "SCI"], f"P8: default recalled_final: {_psb['recalled_final']}"
    assert _psb["fts_missed"] == ["HI", "MATW", "SNFCA", "STON"], (
        f"P8: default missing -> fts_missed: {_psb['fts_missed']}"
    )
    assert _psb["sic_recovered"] == [] and _psb["dropped_mktcap"] == [] and _psb["gated_out"] == [], (
        "P8: no per-stage inputs => only recalled_final/fts_missed populated"
    )
    _allmembers = [t for st in RECALL_STAGES for t in _psb[st]]
    assert sorted(_allmembers) == sorted(_part["gold"]), "P8: stages must partition gold exactly"
    assert len(_allmembers) == len(set(_allmembers)), "P8: each gold member in exactly one stage"
    assert len(_psb["recalled_final"]) + len(_psb["sic_recovered"]) == len(_part["recalled_gold"]), (
        "P8: recalled_final ∪ sic_recovered must reconcile to recall hits"
    )

    # FTS top-1000 cap warning: a recall set at/over the cap warns; below the cap does not.
    _capped = recall_at_gold("deathcare", ["SCI"], fts_hit_count=FTS_TOP_HITS_CAP)
    assert _capped["fts_cap_warning"] is not None and "cap" in _capped["fts_cap_warning"], (
        "P8: fts_hit_count >= 1000 must set the top-1000 cap warning"
    )
    _uncapped = recall_at_gold("deathcare", ["SCI"], fts_hit_count=999)
    assert _uncapped["fts_cap_warning"] is None, "P8: below the cap must NOT warn"

    # P8 loss-stage breakdown — a SYNTHETIC candidate set + gold list exercising every stage.
    # Deathcare gold = {SCI, CSV, MATW, HI, STON, SNFCA}; construct one member per stage:
    #   SCI   -> recalled_final (FTS hit, survived to the final set)
    #   MATW  -> sic_recovered  (FTS missed it, SIC reverse-recall caught it)
    #   STON  -> dropped_mktcap (recalled then dropped by the market-cap band)
    #   HI    -> gated_out      (survived to deep-dive, then gated buy_ineligible)
    #   CSV   -> fts_missed     (never recalled by any channel)
    #   SNFCA -> fts_missed     (never recalled by any channel)
    _gold = theme_gold("deathcare")
    _sb = recall_stage_breakdown(
        _gold,
        recalled_tickers=["SCI"],
        fts_tickers=["SCI"],              # MATW absent from FTS -> SIC recovery is real
        sic_tickers=["SCI", "MATW"],     # MATW recovered by the SIC floor
        mktcap_dropped=["STON"],
        gated_out=["HI"],
    )
    assert _sb["recalled_final"] == ["SCI"], f"P8 stage: recalled_final: {_sb['recalled_final']}"
    assert _sb["sic_recovered"] == ["MATW"], f"P8 stage: sic_recovered: {_sb['sic_recovered']}"
    assert _sb["dropped_mktcap"] == ["STON"], f"P8 stage: dropped_mktcap: {_sb['dropped_mktcap']}"
    assert _sb["gated_out"] == ["HI"], f"P8 stage: gated_out: {_sb['gated_out']}"
    assert _sb["fts_missed"] == ["CSV", "SNFCA"], f"P8 stage: fts_missed: {_sb['fts_missed']}"
    # Stages partition gold exactly (every member once, no leaks, no double-count).
    _members = [t for st in RECALL_STAGES for t in _sb[st]]
    assert sorted(_members) == sorted(_gold), f"P8 stage: must partition gold exactly: {_members}"
    assert len(_members) == len(set(_members)) == len(_gold), "P8 stage: each member exactly once"
    # A member recalled into the final set is recalled_final even if also tagged elsewhere
    # (recalled wins; stage order is pipeline-priority). Verify precedence.
    _sb2 = recall_stage_breakdown(
        ["SCI"], recalled_tickers=["SCI"], sic_tickers=["SCI"], mktcap_dropped=["SCI"], gated_out=["SCI"],
    )
    assert _sb2["recalled_final"] == ["SCI"] and all(
        _sb2[s] == [] for s in RECALL_STAGES if s != "recalled_final"
    ), "P8 stage: recalled_final must take precedence over downstream tags"
    # recall_at_gold carries the same stage_breakdown when per-stage inputs are passed, and the
    # recall ratio reconciles to recalled_final ∪ sic_recovered.
    _resb = recall_at_gold(
        "deathcare", ["SCI"], fts_tickers=["SCI"], sic_tickers=["SCI", "MATW"],
        mktcap_dropped=["STON"], gated_out=["HI"],
    )
    assert _resb["stage_breakdown"] == _sb, "P8 stage: recall_at_gold must embed the breakdown"
    _hits = len(_resb["stage_breakdown"]["recalled_final"]) + len(_resb["stage_breakdown"]["sic_recovered"])
    # recalled_gold is the final-set ∩ gold (SCI only); sic_recovered is an ADDITIONAL floor hit.
    assert _resb["recalled_gold"] == ["SCI"], f"P8 stage: recalled_gold (final set): {_resb['recalled_gold']}"
    assert _hits == 2, f"P8 stage: recall hits incl SIC recovery = 2, got {_hits}"

    # _recall_set_from_candidate_files: reads ticker + recall_channel + downstream-drop tags,
    # tolerates list and dict-wrapped shapes, dedupes, counts FTS-channel rows, and returns the
    # per-stage ticker sets used by the breakdown.
    import tempfile
    with tempfile.TemporaryDirectory() as _td:
        _cf = Path(_td) / "candidates_deathcare.json"
        _cf.write_text(json.dumps([
            {"ticker": "SCI", "recall_channel": "both"},
            {"ticker": "CSV", "recall_channel": "fts"},
            {"ticker": "MATW", "recall_channel": "sic_reverse"},          # SIC-only -> not in fts count
            {"ticker": "sci", "recall_channel": "fts"},                   # dupe (case) -> one ticker
            {"ticker": "STON", "recall_channel": "both", "dropped_stage": "mktcap"},  # dropped on mktcap
            {"ticker": "HI", "recall_channel": "fts", "buy_ineligible": True},        # gated out
        ]), encoding="utf-8")
        _rset, _fts, _stages = _recall_set_from_candidate_files([_cf])
        # STON/HI tagged dropped downstream -> NOT in the final recall set.
        assert _rset == {"SCI", "CSV", "MATW"}, f"P8: recall set dedupe/normalize: {_rset}"
        assert _fts == 5, f"P8: FTS-channel count (fts+both, excl sic_reverse): {_fts}"
        assert _stages["sic"] == {"SCI", "MATW", "STON"}, f"P8: SIC-channel set: {_stages['sic']}"
        assert _stages["mktcap_dropped"] == {"STON"}, f"P8: mktcap-dropped set: {_stages['mktcap_dropped']}"
        assert _stages["gated_out"] == {"HI"}, f"P8: gated-out set: {_stages['gated_out']}"
        _res = recall_at_gold(
            "deathcare", _rset,
            fts_tickers=_stages["fts"], sic_tickers=_stages["sic"],
            mktcap_dropped=_stages["mktcap_dropped"], gated_out=_stages["gated_out"],
        )
        assert _res["recall_at_gold"] == round(3 / 6, 4), (
            f"P8: 3 of 6 gold recalled from candidate file, got {_res['recall_at_gold']}"
        )
        # File-driven stage breakdown: SCI/CSV/MATW survived to the final set (recalled_final);
        # STON dropped on mktcap; HI gated out; SNFCA never recalled (fts_missed). recalled wins
        # over the SIC tag, so MATW (in _rset) is recalled_final, not sic_recovered.
        _fsb = _res["stage_breakdown"]
        assert _fsb["recalled_final"] == ["CSV", "MATW", "SCI"], f"P8 file stage recalled_final: {_fsb['recalled_final']}"
        assert _fsb["sic_recovered"] == [], f"P8 file stage sic_recovered (recalled wins): {_fsb['sic_recovered']}"
        assert _fsb["dropped_mktcap"] == ["STON"], f"P8 file stage dropped_mktcap: {_fsb['dropped_mktcap']}"
        assert _fsb["gated_out"] == ["HI"], f"P8 file stage gated_out: {_fsb['gated_out']}"
        assert _fsb["fts_missed"] == ["SNFCA"], f"P8 file stage fts_missed: {_fsb['fts_missed']}"
    print("  P8 recall@gold: floor measured + loss-stage breakdown "
          "(full/partial/cap-warn + 5-stage partition + file read)  OK")

    # --- P15/P16/P17 (FIREWALL): signals_snapshot is RECORDED-BUT-INERT ---
    # The diagnostic side-channel may be SNAPSHOT into a verdict row for FUTURE per-signal Brier
    # calibration, but it must NEVER change implied_prob, rating, or any scoring. These tests
    # verify (a) the snapshot is built with the compact contracted shape, (b) it is recorded on
    # the row by the JSON-fanout record path, and (c) implied_prob/rating/Brier are byte-identical
    # with vs without a signals_snapshot present.
    #
    # A representative top-level "signals" namespace (sibling of "derived", per the firewall).
    _signals_ns = {
        "price_divergence": {
            "price_return_6m": -0.22,
            "price_return_12m": -0.35,
            "divergence_label": "melting_ice_cube_priced",
            "note": "fundamentals declining, price elevated",
        },
        "ownership": {
            "recent_13d_13g": [
                {"form": "SC 13D", "file_date": "2026-05-12", "filer": "ACTIVIST CAPITAL LP"},
                {"form": "SC 13G", "file_date": "2026-02-03", "filer": "INDEX FUND TRUST"},
            ],
            "recent_13d_13g_count": 2,
            "short_interest_pct": 18.4,
            "short_trend": "rising",
            "staleness_note": "13F lags ~45d; short interest bi-monthly — positioning context only",
        },
        "signals_meta": {"diagnostic_only": True, "never_affects_buy": True, "sources": ["EDGAR"]},
    }

    # (a) snapshot shape — compact divergence_label + ownership summary (newest filing only).
    _snap = _signals_snapshot(_signals_ns)
    assert _snap is not None, "FIREWALL: snapshot must be built from a populated signals namespace"
    assert _snap["divergence_label"] == "melting_ice_cube_priced", (
        f"FIREWALL: snapshot must carry price_divergence.divergence_label, got {_snap.get('divergence_label')}"
    )
    assert _snap["ownership"]["recent_13d_13g_count"] == 2, "FIREWALL: ownership count must be snapshotted"
    assert _snap["ownership"]["latest_13d_13g"] == {
        "form": "SC 13D", "file_date": "2026-05-12", "filer": "ACTIVIST CAPITAL LP"
    }, f"FIREWALL: latest_13d_13g must be the newest filing, got {_snap['ownership']['latest_13d_13g']}"
    assert _snap["ownership"]["short_interest_pct"] == 18.4, "FIREWALL: short_interest_pct snapshotted"
    assert _snap["ownership"]["short_trend"] == "rising", "FIREWALL: short_trend snapshotted"
    assert _snap["ownership"]["staleness_note"], "FIREWALL: staleness_note must be carried (labeled stale)"
    assert _snap["diagnostic_only"] is True, "FIREWALL: snapshot must stamp diagnostic_only=True"
    # Absent / empty / non-dict signals -> None (no fabricated structure).
    assert _signals_snapshot(None) is None, "FIREWALL: no signals -> snapshot None"
    assert _signals_snapshot({}) is None, "FIREWALL: empty signals -> snapshot None"
    assert _signals_snapshot({"signals_meta": {}}) is None, "FIREWALL: meta-only signals -> snapshot None"
    assert _extract_signals({"signals": _signals_ns}) is _signals_ns, "_extract_signals must pull the namespace"
    assert _extract_signals({"ticker": "X"}) is None, "_extract_signals must return None when absent"

    # (b) the snapshot is RECORDED on the row by the JSON-fanout record path, and (c) the rating/
    # implied_prob/Brier are IDENTICAL whether the signals namespace is present or not. Build two
    # otherwise-identical source records — one WITH signals, one WITHOUT — through the real builder
    # (network is exercised for prices, which we don't assert on; the firewall fields are local).
    import tempfile as _tempfile
    _base_rec = {
        "ticker": "TESTX", "rating": "买入", "confidence": 0.72,
        "margin_of_safety_pct": 41.0, "mos_basis": "fcf_cap",
        "theme": "firewalltest", "verdict_date": "2026-06-20", "cik": "0000000000",
    }
    # Stub price fetches so this block stays offline (selftest is no-network by contract); the
    # firewall assertions are on the local snapshot fields, not on prices.
    _orig_fetch_close = globals()["_fetch_close"]
    globals()["_fetch_close"] = lambda *a, **k: None
    try:
        with _tempfile.TemporaryDirectory() as _td:
            _p_with = Path(_td) / "with_signals.json"
            _p_without = Path(_td) / "without_signals.json"
            _rec_with = dict(_base_rec); _rec_with["signals"] = _signals_ns
            _rec_without = dict(_base_rec)
            _p_with.write_text(json.dumps([_rec_with]), encoding="utf-8")
            _p_without.write_text(json.dumps([_rec_without]), encoding="utf-8")
            _row_with = _build_verdicts_from_json(_p_with)[0]
            _row_without = _build_verdicts_from_json(_p_without)[0]
    finally:
        globals()["_fetch_close"] = _orig_fetch_close

    # (b) recorded: WITH-signals row carries the snapshot; WITHOUT-signals row has it as None.
    assert _row_with["signals_snapshot"] is not None, "FIREWALL: snapshot must be RECORDED on the row"
    assert _row_with["signals_snapshot"]["divergence_label"] == "melting_ice_cube_priced", (
        "FIREWALL: recorded snapshot must carry the divergence label"
    )
    assert _row_with["signals_snapshot"]["ownership"]["recent_13d_13g_count"] == 2, (
        "FIREWALL: recorded snapshot must carry the ownership summary"
    )
    assert _row_without["signals_snapshot"] is None, (
        "FIREWALL: a row built WITHOUT a signals namespace must have signals_snapshot=None"
    )
    assert "signals_snapshot" in _row_without, "schema: signals_snapshot key present even when None"

    # (c) INERT: the snapshot changes NOTHING about scoring. rating + implied_prob byte-identical.
    assert _row_with["rating"] == _row_without["rating"], (
        f"FIREWALL: rating must be identical with/without signals: "
        f"{_row_with['rating']} vs {_row_without['rating']}"
    )
    assert _row_with["implied_prob"] == _row_without["implied_prob"], (
        f"FIREWALL: implied_prob must be identical with/without signals: "
        f"{_row_with['implied_prob']} vs {_row_without['implied_prob']}"
    )
    # The two rows must be identical in EVERY other field — the ONLY permitted difference is the
    # signals_snapshot field itself (the recorded-but-inert diagnostic). Prices are stubbed to None
    # above so even entry_price/benchmark_entry_price match, leaving signals_snapshot the sole delta.
    _scoring_keys = [k for k in _row_with if k != "signals_snapshot"]
    for k in _scoring_keys:
        assert _row_with[k] == _row_without[k], (
            f"FIREWALL: field '{k}' differs with vs without signals "
            f"({_row_with[k]!r} vs {_row_without[k]!r}) — snapshot must be inert"
        )

    # And confirm the recorded snapshot can be Brier-scored LATER without affecting today's Brier:
    # the scorer reads implied_prob (unchanged by the snapshot), never signals_snapshot.
    _b_with = _brier(_row_with["implied_prob"], True)
    _b_without = _brier(_row_without["implied_prob"], True)
    assert _b_with == _b_without, "FIREWALL: Brier must not depend on the presence of a snapshot"
    print("  P15/P16/P17 FIREWALL: signals_snapshot RECORDED-BUT-INERT "
          "(snapshot shape + recorded on row + rating/implied_prob/Brier identical with vs without)  OK")

    print("\ntrack_forward selftest PASS — all Brier/calibration/de-risk/FP/firewall math verified")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="track_forward.py — Phase 6 track-forward calibration & Brier scoring"
    )
    ap.add_argument(
        "--record",
        nargs="?",
        const="",
        metavar="PATH",
        help="Ingest verdict(s). Pass a deepdive_verdicts.json path, OR use --ticker flags "
             "for a single verdict via CLI.",
    )
    ap.add_argument("--ticker", default="", help="Ticker for single-verdict --record")
    ap.add_argument("--cik", default="", help="CIK for single-verdict --record")
    ap.add_argument("--rating", default="观察", choices=["买入", "观察", "避开"],
                    help="Rating for single-verdict --record")
    ap.add_argument("--mos-pct", default="null", dest="mos_pct",
                    help="Margin of safety pct (float or null)")
    ap.add_argument("--mos-basis", default="abstain", dest="mos_basis",
                    choices=["fcf_cap", "nav", "abstain"],
                    help="mos_basis for single-verdict --record")
    ap.add_argument("--catalyst", default="null", help="Catalyst string or null")
    ap.add_argument("--confidence", default="", dest="confidence",
                    help="Model confidence 0..1 (P12a). Mapped to implied_prob by rating "
                         "direction. Omit to use the fixed RATING_PROB convention.")
    ap.add_argument("--kill-flags", default="", dest="kill_flags",
                    help="Comma-separated kill flags")
    ap.add_argument("--theme", default="", help="Theme slug")
    ap.add_argument("--verdict-date", default="", dest="verdict_date",
                    help="YYYY-MM-DD (defaults to today)")
    ap.add_argument("--score", action="store_true",
                    help="Score all matured unscored verdicts")
    ap.add_argument("--scorecard", action="store_true",
                    help="Write metrics/scorecard.md")
    ap.add_argument("--status", action="store_true",
                    help="Show pending/matured/scored counts")
    ap.add_argument("--backfill", action="store_true",
                    help="Fetch historical entry_price/benchmark_entry_price for seeded verdicts "
                         "with null prices. Idempotent — skips rows already filled. "
                         "Use this (not --record) to add prices to existing rows.")
    ap.add_argument("--backfill-validation-fp", action="store_true", dest="backfill_validation_fp",
                    help="Inject the 19 validation BUY false-positives as adjudication="
                         "data_false_positive (P12d). Idempotent. Kept out of the price-Brier.")
    ap.add_argument("--recall-gold", nargs="+", dest="recall_gold", metavar="CANDIDATES_JSON",
                    help="P8: compute recall@gold for --theme against its hand-built gold "
                         "true-member list, reading the run's recall set from one or more "
                         "candidate JSON files (FTS ∪ SIC-reverse union).")
    ap.add_argument("--selftest", action="store_true",
                    help="Run synthetic Brier math selftest (no network)")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if args.record is not None:
        args.record_path = args.record if args.record else None
        cmd_record(args)
        return

    if args.score:
        cmd_score(args)
        return

    if args.scorecard:
        cmd_scorecard(args)
        return

    if args.status:
        cmd_status(args)
        return

    if args.backfill:
        cmd_backfill(args)
        return

    if args.backfill_validation_fp:
        cmd_backfill_validation_fp(args)
        return

    if args.recall_gold:
        cmd_recall_gold(args)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
