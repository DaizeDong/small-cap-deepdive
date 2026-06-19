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

    # Run synthetic Brier math selftest (no network):
    python tools/track_forward.py --selftest

Output: metrics/verdicts.jsonl (append-only), metrics/scorecard.md
"""
from __future__ import annotations

import argparse
import json
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

# Default rating → implied_prob convention (overridable per record)
# Rationale: 买入 predicts OUTperformance, 避开 predicts UNDERperformance
RATING_PROB = {
    "买入": 0.65,
    "观察": 0.50,
    "避开": 0.35,
}

DEFAULT_HORIZON_MONTHS = 12
DEFAULT_BENCHMARK = "IWM"  # Russell 2000 small-cap ETF — correct universe comparison

# Calibration bucket edges for implied_prob
CALIB_BUCKETS = [(0.0, 0.40), (0.40, 0.55), (0.55, 0.70), (0.70, 1.01)]


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


def _fetch_close(ticker: str, on_date: str) -> float | None:
    """Fetch closing price for ticker on or near on_date via yfinance.

    Tries the exact date first (most recent trading day within ±5 calendar days).
    Returns None on any error (yfinance unavailable, ticker not found, etc.).
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
        # Use 'Close' column; take the row closest to on_date
        close_col = hist["Close"] if "Close" in hist.columns else hist.iloc[:, 0]
        # Filter to on or before on_date
        hist_filt = hist[hist.index <= dt.strftime("%Y-%m-%d")]
        if hist_filt.empty:
            hist_filt = hist  # fallback: take any row
        price = float(close_col.iloc[-1].item() if hasattr(close_col.iloc[-1], "item") else close_col.iloc[-1])
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
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    VERDICTS_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _append_verdict(row: dict) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(VERDICTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _brier(implied_prob: float, favorable: bool) -> float:
    """Brier score for a single verdict: (p - o)^2 where o in {0, 1}."""
    o = 1.0 if favorable else 0.0
    return (implied_prob - o) ** 2


# ---------------------------------------------------------------------------
# --record
# ---------------------------------------------------------------------------

def _build_verdict_from_flags(args) -> dict:
    """Build a verdict dict from explicit CLI flags."""
    verdict_date = args.verdict_date or _today()
    rating = args.rating
    implied_prob = RATING_PROB.get(rating, 0.50)

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
    entry_price = _fetch_close(args.ticker, entry_date)
    benchmark_entry_price = _fetch_close(DEFAULT_BENCHMARK, entry_date)

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
        "implied_prob": implied_prob,
        "horizon_months": DEFAULT_HORIZON_MONTHS,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "benchmark": DEFAULT_BENCHMARK,
        "benchmark_entry_price": benchmark_entry_price,
        "scored": False,
        "realized_excess_pct": None,
        "brier": None,
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
        implied_prob = RATING_PROB.get(rating, 0.50)

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
        entry_price = _fetch_close(ticker, entry_date) if ticker else None
        benchmark_entry_price = _fetch_close(DEFAULT_BENCHMARK, entry_date)

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
            "implied_prob": implied_prob,
            "horizon_months": DEFAULT_HORIZON_MONTHS,
            "entry_price": entry_price,
            "entry_date": entry_date,
            "benchmark": DEFAULT_BENCHMARK,
            "benchmark_entry_price": benchmark_entry_price,
            "scored": False,
            "realized_excess_pct": None,
            "brier": None,
            "notes": None,
        }
        rows.append(row)
    return rows


def cmd_record(args) -> None:
    """--record: ingest one or more verdicts."""
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
            print(f"WARN: {row['ticker']} on {row['verdict_date']} already logged — skipping")
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

        stock_return = (stock_horizon - entry_price) / entry_price
        bm_return = (bm_horizon - bm_entry) / bm_entry
        excess = stock_return - bm_return
        favorable = excess > 0

        implied_prob = row.get("implied_prob", 0.50)
        b = _brier(implied_prob, favorable)

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

    scored = [r for r in rows if r.get("scored")]
    pending = [r for r in rows if not r.get("scored")]

    lines = [
        "# Track-Forward Calibration Scorecard",
        "",
        f"> Generated: {today_str}",
        f"> Verdicts file: `metrics/verdicts.jsonl`",
        f"> Benchmark: {DEFAULT_BENCHMARK} (Russell 2000 small-cap ETF)",
        "",
    ]

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
        lines += [
            "",
            "## Calibration Table",
            "",
            "*(Predicted probability bucket vs. realized favorable frequency)*",
            "",
            "| p bucket | N | Realized freq | Calibration error |",
            "|---|---|---|---|",
        ]
        for (lo, hi) in CALIB_BUCKETS:
            bucket = [r for r in scored if lo <= r.get("implied_prob", 0.5) < hi]
            if not bucket:
                lines.append(f"| {lo:.2f}–{hi:.2f} | 0 | — | — |")
                continue
            mid = (lo + hi) / 2
            realized = sum(1 for r in bucket if r.get("realized_excess_pct", 0) > 0) / len(bucket)
            err = realized - mid
            lines.append(f"| {lo:.2f}–{hi:.2f} | {len(bucket)} | {realized:.2f} | {err:+.2f} |")

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

    scored = [r for r in rows if r.get("scored")]
    unscored = [r for r in rows if not r.get("scored")]

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
    print(f"  Scored:              {len(scored)}")
    print(f"  Matured (unscored):  {len(matured_unscored)}  <- run --score")
    print(f"  Pending (horizon not reached): {len(pending)}")

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

    # --- Test 6: calibration table bucket membership ---
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

    # --- Test 7: rating → prob convention ---
    for rating, expected_p in RATING_PROB.items():
        assert 0.0 < expected_p < 1.0, f"RATING_PROB[{rating}] = {expected_p} out of [0,1]"
        assert RATING_PROB["买入"] > RATING_PROB["观察"] > RATING_PROB["避开"], (
            "Convention must be: 买入 > 观察 > 避开"
        )
    print(f"  PASS: rating→prob convention: 买入={RATING_PROB['买入']}, "
          f"观察={RATING_PROB['观察']}, 避开={RATING_PROB['避开']}")

    print("\ntrack_forward selftest PASS — all Brier/calibration math verified")


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

    ap.print_help()


if __name__ == "__main__":
    main()
