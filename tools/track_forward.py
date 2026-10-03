"""
track_forward.py — Phase 6: Track-Forward Calibration / Brier Scoring

Epistemic purpose: log every deep-dive verdict, score it against realized returns after the
horizon matures, compute Brier score + calibration — so the rubric can be tuned by evidence
not vibes.

Calibration needs dated verdicts and observed forward outcomes. A conservative
rating distribution alone does not establish that the rubric is correctly calibrated.

Private path setup:
    Initialize a versioned PRIVATE companion with SMALL_CAP_DEEPDIVE_CONFIG_DIR.
    Set REPORTS_ROOT to the absolute path returned by _common.reports_dir():
        python -c "import sys; sys.path.insert(0, 'tools'); from _common import reports_dir; print(reports_dir())"
    The resolver includes SMALLCAP_RUN when set and fails if initialization is missing.

Usage (REPORTS_ROOT is the resolved absolute private path):
    # Record a verdict from a deepdive-fanout JSON:
    python tools/track_forward.py --record "${REPORTS_ROOT}/deepdive_verdicts.json"

    # Record a single verdict via CLI flags:
    python tools/track_forward.py --record --ticker SYNTA --rating 观察 --theme synthetic \\
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

Output: _metrics_dir()/verdicts.jsonl and _metrics_dir()/scorecard.md.
_metrics_dir() resolves datadir.resolve_data_dir("small-cap-deepdive")/"metrics",
then proves the private output path. SMALL_CAP_DEEPDIVE_DATA_DIR may select the
private data root. These are versioned companion DATA, never paths inside this tool repo.

Notes:
    --backfill is the correct way to add prices to existing rows with null entry prices.
    Do NOT use --record for tickers already in verdicts.jsonl (dup-detection will warn+skip).
    --backfill is idempotent: rows with non-null entry_price are skipped.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import uuid
import os
import sys
import warnings
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, today
from _output_paths import prove_output_path, prepare_output

# v0.3.3 refactor, the scoring MATH and the P8 recall-floor audit were extracted into sibling
# modules to shrink this orchestrator. They are re-exported below so the PUBLIC API
# (track_forward.<symbol>) is UNCHANGED for every consumer (finalize_run ingests via
# _build_verdicts_from_json; filter_by_sic/reference docs cite THEME_GOLD; the selftest exercises
# every helper by bare name). Both submodules import ONLY stdlib, never back from this module ,
# so there is no circular import. NO behavior change.
#   _calibration.py, Brier kernel + confidence-as-prob (P12a) + data_false_positive predicate
#                     (P12d) + de-risk-native metrics (P12c).
#   _recall.py, THEME_GOLD + recall@gold + 5-stage loss breakdown + candidate/universe readers.
from _calibration import (
    RATING_PROB, RATING_DIRECTION, BLOWUP_DRAWDOWN_THRESHOLD, CALIB_BUCKETS,
    _parse_confidence, _validate_probability, _implied_prob_from_confidence, _brier,
    _is_data_false_positive, _price_scorable,
    _blowup_avoidance_rate, _downside_capture_rate, _buy_data_integrity_rate,
    _buy_data_integrity_summary, _adjudication_review, _adjudication_blocks_price,
    _require_adjudication_receipt, _favorable_outcome, _outcome_summary, _risk_metric_summary,
)
from _recall import (
    THEME_GOLD, FTS_TOP_HITS_CAP, RECALL_STAGES, SIC_REVERSE_MARKER,
    theme_gold, recall_stage_breakdown, recall_at_gold,
    _truthy_csv, _recall_set_from_candidate_files, _recall_set_from_universe_files,
)

# Real run outputs belong in the verified private companion repository.
# Resolve that location before every write and fail if it is unavailable.
# Public tool files must never serve as a fallback for private observations.
# datadir moved into the guards submodule: one copy for the fleet instead of one per repo,
# which had already begun to drift. The insert above stays, because sibling modules in this
# same tools/ directory are still imported by bare name.
_datadir_path = Path(__file__).resolve().parents[1] / "guards/tools/datadir.py"
if not _datadir_path.is_file():
    raise ImportError("Pinned guards resolver is missing; initialize the guards submodule")
_datadir_spec = importlib.util.spec_from_file_location("_smallcap_tracking_datadir", _datadir_path)
if _datadir_spec is None or _datadir_spec.loader is None:
    raise ImportError("Cannot load the pinned guards resolver; initialize the guards submodule")
_datadir = importlib.util.module_from_spec(_datadir_spec)
_datadir_spec.loader.exec_module(_datadir)
resolve_data_dir = _datadir.resolve_data_dir
DataDirNotInitialized = _datadir.DataDirNotInitialized

REPO = Path(__file__).resolve().parent.parent
SKILL = "small-cap-deepdive"


def _metrics_dir() -> Path:
    d = resolve_data_dir(SKILL)
    if d is None:
        raise DataDirNotInitialized(
            "small-cap-deepdive has no private data directory, so forward-tracking has nowhere to\n"
            "record verdicts. A freshly cloned public skill is SUPPOSED to look like this -- it\n"
            "ships uninitialized. Point it at your own store:\n"
            "    mkdir -p ~/.small-cap-deepdive-config/data/metrics\n"
            "    (or set SMALL_CAP_DEEPDIVE_DATA_DIR)\n"
            "The shape you are expected to produce is in metrics/verdicts.jsonl.example."
        )
    return prove_output_path(d / "metrics")


def _verdicts_file() -> Path:
    return _metrics_dir() / "verdicts.jsonl"


def _scorecard_file() -> Path:
    return _metrics_dir() / "scorecard.md"


class _LazyPath:
    """A Path that resolves at USE time, not import time.

    Every existing consumer reads `track_forward.VERDICTS_FILE` as a plain Path, and there is no
    path at all until a private data dir exists -- so resolving at import would make merely
    importing this module explode on a fresh clone. Defer it: importing stays free, and the
    DataDirNotInitialized (with instructions) fires only when something actually reaches for a file.
    """

    def __init__(self, fn):
        self._fn = fn

    def __fspath__(self):
        return os.fspath(self._fn())

    def __getattr__(self, name):
        return getattr(self._fn(), name)

    def __truediv__(self, other):
        return self._fn() / other

    def __str__(self):
        return str(self._fn())

    def __repr__(self):
        return "_LazyPath(%s)" % self._fn()


METRICS_DIR = _LazyPath(_metrics_dir)
VERDICTS_FILE = _LazyPath(_verdicts_file)
SCORECARD_FILE = _LazyPath(_scorecard_file)

DEFAULT_HORIZON_MONTHS = 12
DEFAULT_BENCHMARK = "IWM"  # Russell 2000 small-cap ETF, correct universe comparison


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


def _positive_price(value) -> float | None:
    """Accept a finite, strictly positive scalar without treating booleans as prices."""
    try:
        scalar = value.item() if hasattr(value, "item") else value
        if isinstance(scalar, bool):
            return None
        price = float(scalar)
    except (TypeError, ValueError, OverflowError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def _quote_date(value) -> date | None:
    """Return an ordinary date only when its calendar value is unambiguous."""
    try:
        if isinstance(value, datetime):
            value = value.date()
        text = value.isoformat() if isinstance(value, date) else value
        if not isinstance(text, str):
            return None
        parsed = date.fromisoformat(text)
        return parsed if parsed.isoformat() == text else None
    except (TypeError, ValueError, OverflowError):
        return None


def _fetch_close(ticker: str, on_date: str, verbose: bool = False,
                 *, evidence: dict | None = None) -> float | None:
    """Fetch a valid close on or before the requested date, within seven calendar days.

    The float/None API and injection point remain compatible. Callers can also retain
    availability, date and provider-basis evidence through the optional dictionary.
    The provider adjustment label does not prove that different retrieval snapshots
    share a corporate-action basis.
    """
    quote = evidence if evidence is not None else {}
    quote.clear()
    quote.update({
        "schema_version": 1, "available": False, "price": None,
        "ticker": ticker.strip().upper() if isinstance(ticker, str) else None,
        "requested_date": on_date, "resolved_date": None,
        "source": "yfinance", "price_basis": "yfinance_auto_adjust",
        "price_column": None, "reason": None,
    })

    def unavailable(reason: str) -> None:
        quote["reason"] = reason
        if verbose:
            print(f"    [_fetch_close] {quote['ticker']} on_date={on_date}: unavailable ({reason})")
        return None

    requested = _quote_date(on_date)
    if requested is None or not isinstance(on_date, str):
        return unavailable("invalid_requested_date")
    if not quote["ticker"]:
        return unavailable("invalid_ticker")
    try:
        import yfinance as yf
        start_date = requested - timedelta(days=7)
        end_date = requested + timedelta(days=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.download(quote["ticker"], start=start_date.isoformat(),
                               end=end_date.isoformat(), progress=False, auto_adjust=True)
        if hist is None or hist.empty:
            return unavailable("no_quotes")

        dated_rows = [(_quote_date(value), position) for position, value in enumerate(hist.index)]
        if any(day is None for day, _ in dated_rows):
            return unavailable("invalid_quote_date")
        eligible = [(day, position) for day, position in dated_rows
                    if start_date <= day <= requested]
        if not eligible:
            return unavailable("no_admissible_quote_date")
        resolved = max(day for day, _ in eligible)
        positions = [position for day, position in eligible if day == resolved]
        if len(positions) != 1:
            return unavailable("ambiguous_quote_date")

        # Support flat single-symbol columns and yfinance's explicit field/symbol pairs.
        columns = {"Close": [], "Adj Close": []}
        for position, label in enumerate(hist.columns):
            if isinstance(label, str) and label in columns:
                columns[label].append(position)
            elif isinstance(label, tuple) and len(label) == 2:
                for field in columns:
                    if label[0] == field and str(label[1]).upper() == quote["ticker"]:
                        columns[field].append(position)
                    elif label[1] == field and str(label[0]).upper() == quote["ticker"]:
                        columns[field].append(position)
        field = "Close" if columns["Close"] else "Adj Close"
        if not columns[field]:
            return unavailable("missing_price_column")
        if len(columns[field]) != 1:
            return unavailable("ambiguous_price_column")
        price = _positive_price(hist.iloc[positions[0], columns[field][0]])
        if price is None:
            return unavailable("invalid_price")
        quote.update(available=True, price=price, resolved_date=resolved.isoformat(),
                     price_column=field)
        if verbose:
            print(f"    [_fetch_close] {quote['ticker']} on_date={on_date}: "
                  f"resolved={quote['resolved_date']} price={price:.4f}")
        return price
    except Exception as exc:
        quote["error_type"] = type(exc).__name__
        return unavailable("quote_fetch_error")


def _fetch_return_snapshot(ticker: str, entry_date: str, horizon_date: str) -> dict:
    """Fetch both return endpoints in one corporate-action adjustment snapshot."""
    from _forward_snapshot import snapshot_return
    first, last = _quote_date(entry_date), _quote_date(horizon_date)
    if first is None or last is None or first >= last:
        return {"available": False, "reason": "invalid_snapshot_dates"}
    try:
        import yfinance as yf
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.download(ticker, start=(first - timedelta(days=7)).isoformat(),
                               end=(last + timedelta(days=1)).isoformat(),
                               progress=False, auto_adjust=True)
        if hist is None or hist.empty:
            return {"available": False, "reason": "no_quotes"}
        columns = {"Close": [], "Adj Close": []}
        for position, label in enumerate(hist.columns):
            if isinstance(label, str) and label in columns:
                columns[label].append(position)
            elif isinstance(label, tuple) and len(label) == 2:
                for field in columns:
                    if ((label[0] == field and str(label[1]).upper() == ticker.upper())
                            or (label[1] == field and str(label[0]).upper() == ticker.upper())):
                        columns[field].append(position)
        field = "Close" if columns["Close"] else "Adj Close"
        if not columns[field]:
            return {"available": False, "reason": "missing_price_column"}
        if len(columns[field]) != 1:
            return {"available": False, "reason": "ambiguous_price_column"}
        rows = []
        for position, stamp in enumerate(hist.index):
            day = _quote_date(stamp)
            value = hist.iloc[position, columns[field][0]]
            if hasattr(value, "item"):
                value = value.item()
            rows.append([day.isoformat() if day else None, value])
        return snapshot_return(ticker, entry_date, horizon_date, rows, price_column=field,
                               observed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        return {"available": False, "reason": "quote_fetch_error", "error_type": type(exc).__name__}


def _quote_problem(quote, ticker: str, requested_date: str, price=None) -> str | None:
    """Validate persisted or freshly fetched quote evidence before using its value."""
    if not isinstance(quote, dict) or not quote:
        return "quote_evidence_missing"
    if quote.get("available") is not True:
        reason = quote.get("reason")
        known_reasons = (
            "invalid_requested_date", "invalid_ticker", "no_quotes", "invalid_quote_date",
            "no_admissible_quote_date", "ambiguous_quote_date", "missing_price_column",
            "ambiguous_price_column", "invalid_price", "quote_fetch_error",
        )
        return reason if reason in known_reasons else "quote_unavailable"
    if type(quote.get("schema_version")) is not int or quote["schema_version"] != 1:
        return "unsupported_quote_evidence_schema"
    requested = _quote_date(requested_date)
    resolved = _quote_date(quote.get("resolved_date"))
    try:
        first_allowed = requested - timedelta(days=7) if requested is not None else None
    except OverflowError:
        first_allowed = None
    if (requested is None or resolved is None
            or first_allowed is None
            or not isinstance(quote.get("resolved_date"), str)
            or quote.get("requested_date") != requested.isoformat()
            or not first_allowed <= resolved <= requested):
        return "invalid_quote_date_evidence"
    if (not isinstance(ticker, str) or not ticker.strip()
            or quote.get("ticker") != ticker.strip().upper()):
        return "quote_ticker_mismatch"
    if quote.get("source") != "yfinance" or quote.get("price_basis") != "yfinance_auto_adjust":
        return "quote_basis_missing_or_unsupported"
    if quote.get("price_column") not in ("Close", "Adj Close"):
        return "quote_price_column_missing"
    quoted = _positive_price(quote.get("price"))
    if quoted is None:
        return "invalid_quote_price"
    if price is not None and _positive_price(price) != quoted:
        return "quote_price_mismatch"
    return None


def _quote_on(ticker: str, on_date: str, verbose: bool = False) -> dict:
    evidence = {}
    price = _fetch_close(ticker, on_date, verbose=verbose, evidence=evidence)
    problem = _quote_problem(evidence, ticker, on_date, price)
    if problem is not None or price is None:
        evidence.update(available=False, price=None, reason=problem or "invalid_quote_price")
    else:
        evidence["price"] = _positive_price(price)
    return evidence


def _entry_quote_problem(row: dict, price_key: str, quote_key: str, ticker: str) -> str | None:
    """Legacy entry values remain untouched until dated basis evidence is supplied."""
    price = _positive_price(row.get(price_key))
    if price is None:
        return "entry_price_unavailable_or_invalid"
    quote = row.get(quote_key)
    if (not isinstance(quote, dict) or not quote.get("resolved_date")
            or not quote.get("price_basis")):
        return "legacy_quote_evidence_missing"
    verdict_date = row.get("verdict_date")
    if row.get("entry_date", verdict_date) != verdict_date:
        return "entry_date_mismatch"
    return _quote_problem(quote, ticker, verdict_date, price)


class _VerdictSnapshot(list):
    """List-compatible ledger rows bound to the bytes and path originally read."""

    def __init__(self, rows, source_path, source_bytes):
        super().__init__(rows)
        self.source_path = source_path
        self.source_bytes = source_bytes


def _load_verdicts() -> list[dict]:
    try:
        path = Path(VERDICTS_FILE).resolve()
    except DataDirNotInitialized:
        return []
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return _VerdictSnapshot([], path, None)
    rows = []
    for number, line in enumerate(content.decode("utf-8").splitlines(), 1):
        line = line.strip()
        if line:
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid ledger JSON at line {number}; repair before rewriting") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Invalid ledger record at line {number}: expected an object")
            rows.append(row)
    return _VerdictSnapshot(rows, path, content)


@contextmanager
def _ledger_lock(target):
    """Fail fast on another writer; keep external quote work outside the lock.

    All ledger writers use this exclusive sibling file. A crashed writer may leave
    it behind: verify no tracker writer is running before manually removing it.
    There is deliberately no automatic stale-lock deletion.
    """
    lock_path = prepare_output(target.with_name(f".{target.name}.lock"))
    try:
        stream = lock_path.open("x", encoding="ascii")
    except FileExistsError as exc:
        raise RuntimeError("Ledger update already in progress; retry after the writer finishes. "
                           "If it crashed, verify no writer is active before removing " + str(lock_path)) from exc
    try:
        with stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock_path.unlink()


def _save_verdicts(rows: list[dict]) -> None:
    """Commit an unchanged snapshot, or initialize a ledger from a plain list.

    Quote retrieval happens before this short transaction. If any writer has
    changed the loaded bytes, reject the stale result and preserve the newer ledger.
    Reload and retry the command to score or backfill the current set of rows.
    """
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    target = prepare_output(VERDICTS_FILE)
    with _ledger_lock(target):
        try:
            current = target.read_bytes()
        except FileNotFoundError:
            current = None
        if isinstance(rows, _VerdictSnapshot):
            if rows.source_path != target or rows.source_bytes != current:
                raise RuntimeError("Ledger changed during quote retrieval; reload and retry. No rows were overwritten.")
        elif current is not None:
            raise RuntimeError("An existing ledger requires a loaded snapshot; reload before rewriting.")
        previous = [json.loads(line) for line in (current or b"").decode("utf-8").splitlines() if line.strip()]
        _validate_adjudication_writes(previous, rows)
        _replace_verdicts(target, content)


def _validate_adjudication_writes(previous, rows):
    """Preserve legacy claims while requiring evidence for new completed reviews."""
    for row in rows:
        old = next((item for item in previous if
                    (item.get("ticker"), item.get("verdict_date")) ==
                    (row.get("ticker"), row.get("verdict_date"))), None)
        fields = ("ticker", "cik", "verdict_date", "rating", "report_sha256",
                  "adjudication", "adjudication_evidence")
        if old is not None and all(old.get(field) == row.get(field) for field in fields):
            continue
        if old is not None and old.get("adjudication") == "data_false_positive" and (
                row.get("adjudication") != "data_false_positive"):
            raise ValueError("A persisted false-positive claim cannot be removed by a price update")
        _require_adjudication_receipt(row)


def _replace_verdicts(target, content):
    """Replace the entire ledger while the caller holds its exclusive lock."""
    tmp_path = prepare_output(target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp"))
    created = False
    try:
        with tmp_path.open("x", encoding="utf-8") as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        prove_output_path(target)
        os.replace(tmp_path, target)
    finally:
        if created:
            tmp_path.unlink(missing_ok=True)


def _append_verdict(row: dict) -> bool:
    """Atomically deduplicate and append; return whether a new row was recorded."""
    _require_adjudication_receipt(row)
    target = prepare_output(VERDICTS_FILE)
    with _ledger_lock(target):
        rows = _load_verdicts()
        if not isinstance(rows, _VerdictSnapshot) or rows.source_path != target:
            raise RuntimeError("Ledger destination changed; reload and retry before recording.")
        key = (row["ticker"], row["verdict_date"])
        if any((existing["ticker"], existing["verdict_date"]) == key for existing in rows):
            return False
        rows.append(row)
        content = "\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n"
        _replace_verdicts(target, content)
        return True



def _with_adjudication_receipt(row: dict, receipt: dict) -> dict:
    """Attach a supplied review without inventing or changing its verdict binding."""
    if not isinstance(receipt, dict):
        raise ValueError("Adjudication evidence must be an object")
    label = receipt.get("disposition")
    if row.get("adjudication") not in (None, label):
        raise ValueError("Receipt cannot replace a persisted adjudication label")
    if row.get("adjudication_evidence") not in (None, receipt):
        raise ValueError("Existing review evidence must be retained; conflicting replacement refused")
    updated = dict(row, adjudication=label, adjudication_evidence=receipt)
    _require_adjudication_receipt(updated)
    if _adjudication_review(updated)["status"] != "reviewed":
        raise ValueError("Receipt does not establish a completed review")
    return updated


def cmd_adjudicate(args) -> None:
    """Attach a private, verdict-bound receipt through the existing snapshot transaction."""
    receipt_path = prove_output_path(Path(args.adjudicate))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or not isinstance(receipt.get("verdict"), dict):
        raise ValueError("Receipt must contain its original verdict binding")
    binding = receipt["verdict"]
    rows = _load_verdicts()
    matches = [index for index, row in enumerate(rows) if
               row.get("ticker") == binding.get("ticker") and
               row.get("verdict_date") == binding.get("verdict_date")]
    if len(matches) != 1:
        raise ValueError("Receipt must select exactly one existing verdict")
    index = matches[0]
    rows[index] = _with_adjudication_receipt(rows[index], receipt)
    _save_verdicts(rows)
    print("Adjudication receipt recorded; source authenticity remains the reviewer's responsibility.")


def _integrity_description(summary: dict) -> str:
    rate = summary['rate']
    value = f"{rate * 100:.1f}%" if rate is not None else "N/A"
    coverage = summary['review_coverage']
    coverage_text = f"{coverage * 100:.1f}%" if coverage is not None else "N/A"
    return (f"{value}; clean {summary['clean_buys']}/{summary['reviewed_buys']} reviewed BUY; "
            f"reviewed {summary['reviewed_buys']}/{summary['total_buys']} ({coverage_text}); "
            f"pending {summary['pending_buys']}")


# ---------------------------------------------------------------------------
# Signals snapshot (P15/P16/P17), DIAGNOSTIC-ONLY, RECORDED-BUT-INERT.
#
# THE FIREWALL (approved philosophy decision Q2): the between-filings side-channel computed by
# tools/signals.py lives in a SEPARATE top-level "signals" namespace and NEVER originates or
# up-weights a BUY. track_forward retains the finalized snapshot or a legacy compact summary in
# the verdict row so per-signal predictive value can be Brier-calibrated LATER. This snapshot is
# WRITE-ONLY from the scorer's perspective: implied_prob, rating, and every scoring path
# (_implied_prob_from_confidence, _brier, cmd_score, the scorecard) MUST NOT read it. It is
# recorded-but-inert, present in the row for future per-signal calibration, load-bearing on
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
        completion = own.get("recent_13d_13g_completion")
        if not isinstance(completion, dict) or completion.get("status") != "complete":
            count = None
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
            "recent_13d_13g_completion": completion,
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
    if not isinstance(verdict_date, str) or _quote_date(verdict_date) is None:
        raise ValueError("Verdict date must be YYYY-MM-DD")
    rating = args.rating

    confidence = _parse_confidence(getattr(args, "confidence", None))
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
    entry_quote = _quote_on(args.ticker, entry_date, verbose=True)
    benchmark_entry_quote = _quote_on(DEFAULT_BENCHMARK, entry_date, verbose=True)

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
        "entry_price": entry_quote["price"],
        "entry_date": entry_date,
        "entry_quote": entry_quote,
        "benchmark": DEFAULT_BENCHMARK,
        "benchmark_entry_price": benchmark_entry_quote["price"],
        "benchmark_entry_quote": benchmark_entry_quote,
        "scored": False,
        "stock_return_pct": None,
        "realized_excess_pct": None,
        "brier": None,
        "adjudication": None,
        "fp_cause": None,
        # P15/P16/P17 diagnostic side-channel snapshot, recorded-but-inert (firewall). The CLI
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

    # Validate every confidence before any quote lookup or ledger write.
    confidences = []
    for rec in raw:
        confidence = _parse_confidence(rec.get("confidence"))
        unit = rec.get("confidence_unit")
        if unit not in (None, "percent", "fraction"):
            raise ValueError("Unknown confidence unit")
        if unit == "percent" and confidence is not None:
            confidence /= 100.0
        elif unit == "fraction" and confidence is not None and confidence > 1:
            raise ValueError("Fraction confidence must be between 0 and 1")
        confidences.append(confidence)
    rows = []
    for rec, confidence in zip(raw, confidences):
        ticker = rec.get("ticker", "")
        rating = rec.get("rating", "观察")
        # Normalize: deepdive-fanout may use English
        _rating_norm = {"buy": "买入", "watch": "观察", "hold": "观察",
                        "avoid": "避开", "sell": "避开"}
        rating = _rating_norm.get(rating.lower(), rating)

        # P12a: confidence-as-probability mapped by rating direction (fallback RATING_PROB).
        implied_prob = _implied_prob_from_confidence(rating, confidence)

        # mos_pct: from valuation json or report field
        mos_pct: float | None = None
        raw_mos = rec.get("margin_of_safety_pct")
        if raw_mos is None:
            raw_mos = rec.get("mos_pct")
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
        risk_count = rec.get("killflag_count", len(kill_flags))
        if type(risk_count) is not int or risk_count < 0:
            raise ValueError("Verdict killflag_count must be a nonnegative integer")
        risk_count = max(risk_count, len(kill_flags))

        # verdict_date: try to infer from file or use today
        verdict_date = rec.get("verdict_date") or rec.get("date") or _today()
        if not isinstance(verdict_date, str) or _quote_date(verdict_date) is None:
            raise ValueError("Verdict date must be YYYY-MM-DD")

        cik = str(rec["cik"]) if rec.get("cik") else None
        theme = rec.get("theme") or rec.get("theme_slug") or None

        entry_date = verdict_date
        entry_quote = _quote_on(ticker, entry_date, verbose=True)
        benchmark_entry_quote = _quote_on(DEFAULT_BENCHMARK, entry_date, verbose=True)

        # Keep diagnostic signals inert. Versioned snapshots validate claimed identity
        # and signal digest; their source descriptor remains retained, unverified metadata.
        # Legacy raw signals are compacted. Neither path changes rating/implied_prob.
        if "signals_snapshot" in rec:
            from _signal_snapshot import validate_signal_snapshot
            signals_snapshot = validate_signal_snapshot(
                rec["signals_snapshot"], ticker, cik, verdict_date)
        else:
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
            "killflag_count": risk_count,
            "unresolved_killflag_count": risk_count - len(kill_flags),
            "risk_evidence": rec.get("risk_evidence"),
            "verdict_date_source": rec.get("verdict_date_source"),
            "report_sha256": rec.get("report_sha256"),
            "catalyst": catalyst,
            "confidence": confidence,
            "implied_prob": implied_prob,
            "horizon_months": DEFAULT_HORIZON_MONTHS,
            "entry_price": entry_quote["price"],
            "entry_date": entry_date,
            "entry_quote": entry_quote,
            "benchmark": DEFAULT_BENCHMARK,
            "benchmark_entry_price": benchmark_entry_quote["price"],
            "benchmark_entry_quote": benchmark_entry_quote,
            "scored": False,
            "stock_return_pct": None,
            "realized_excess_pct": None,
            "brier": None,
            "adjudication": rec.get("adjudication"),
            "adjudication_evidence": rec.get("adjudication_evidence"),
            "fp_cause": rec.get("fp_cause"),
            "signals_snapshot": signals_snapshot,
            "notes": None,
        }
        _require_adjudication_receipt(row)
        rows.append(row)
    return rows


def cmd_record(args) -> None:
    """--record: ingest one or more verdicts.

    Dup-detection: if (ticker, verdict_date) already exists in verdicts.jsonl, the row is
    SKIPPED with a warning. Do NOT use --record to add prices to existing seeded rows —
    use --backfill for that purpose. --backfill is idempotent and correctly fills null
    entry_price / benchmark_entry_price in-place without creating duplicate rows.
    """
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
        if not _append_verdict(row):
            print(f"WARN: {row['ticker']} on {row['verdict_date']} already logged — skipping "
                  f"(use --backfill to fill null entry prices for existing rows)")
            warned += 1
            continue
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

    Idempotent: already-scored rows and rows where both entry values are non-null
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
    skipped_scored = 0
    failed = []

    for row in rows:
        if row.get("scored"):
            skipped_scored += 1
            continue
        ticker = row.get("ticker", "")
        verdict_date = row.get("verdict_date", "")
        has_stock = row.get("entry_price") is not None
        has_bm = row.get("benchmark_entry_price") is not None

        if has_stock and has_bm:
            skipped_already_filled += 1
            continue

        # Fetch whichever is missing
        changed = False
        if not has_stock:
            quote = _quote_on(ticker, verdict_date, verbose=True)
            row["entry_quote"] = quote
            if quote["available"]:
                row["entry_price"] = quote["price"]
                changed = True
            else:
                failed.append(f"{ticker} ({verdict_date}): stock quote unavailable ({quote['reason']})")

        if not has_bm:
            benchmark = row.get("benchmark", DEFAULT_BENCHMARK)
            quote = _quote_on(benchmark, verdict_date, verbose=True)
            row["benchmark_entry_quote"] = quote
            if quote["available"]:
                row["benchmark_entry_price"] = quote["price"]
                changed = True
            else:
                failed.append(f"{ticker} ({verdict_date}): {benchmark} quote unavailable ({quote['reason']})")

        if changed:
            filled += 1
            ep = _positive_price(row.get("entry_price"))
            bm = _positive_price(row.get("benchmark_entry_price"))
            ep_str = f"${ep:.2f}" if ep is not None else "N/A"
            bm_str = f"${bm:.2f}" if bm is not None else "N/A"
            print(f"  Backfilled {ticker} | entry={ep_str} | {DEFAULT_BENCHMARK}={bm_str}")

    # Atomic save
    _save_verdicts(rows)

    total = len(rows)
    print(f"\nBackfill complete: {filled} filled | {skipped_already_filled} already had prices "
          f"| {skipped_scored} already scored | {len(failed)} failed | {total} total verdicts")
    if failed:
        print("\nFailed tickers (thin markets / delisted / data unavailable):")
        for f in failed:
            print(f"  - {f}")


# ---------------------------------------------------------------------------
# Historical cohort promotion is retired. No real verdicts ship in executable constants.


def _build_validation_fp_rows() -> list[dict]:
    """Reject the retired route before it can alter the private calibration ledger."""
    raise RuntimeError("Historical validation backfill is retired; preserve private evidence without automatic adjudication.")


def cmd_backfill_validation_fp(args) -> None:
    """Retired CLI route; its production builder rejects before any ledger mutation."""
    added = 0
    skipped = 0
    rows = _build_validation_fp_rows()
    for row in rows:
        if not _append_verdict(row):
            skipped += 1
            continue
        added += 1
        print(f"  Backfilled FP {row['ticker']} | MoS={row['mos_pct']:.0f}% | "
              f"adjudication=data_false_positive | cause={row['fp_cause']}")

    print(f"\nValidation FP backfill: {added} added | {skipped} already present "
          f"| {len(rows)} total in supplied rows")
    integrity = _buy_data_integrity_summary(_load_verdicts())
    print("BUY data-integrity now: " + _integrity_description(integrity))


# ---------------------------------------------------------------------------
# --score
# ---------------------------------------------------------------------------

def cmd_score(args) -> None:
    """--score: for each unscored matured verdict, fetch horizon-end price and score."""
    rows = _load_verdicts()
    today_str = _today()
    today = _quote_date(today_str)
    if today is None:
        raise ValueError("Scoring date must be YYYY-MM-DD")

    matured = 0
    scored_now = 0
    still_pending = 0

    def unavailable(row: dict, reason: str) -> None:
        nonlocal still_pending
        row["score_unavailable_reason"] = reason
        still_pending += 1
        print(f"  WARN: {row.get('ticker', '')} remains unscored ({reason})")

    for row in rows:
        if row.get("scored"):
            continue
        # FP labels and unsupported adjudication claims remain outside price scoring.
        if _adjudication_blocks_price(row):
            continue
        verdict_date = row.get("verdict_date")
        vd = _quote_date(verdict_date)
        if not isinstance(verdict_date, str) or vd is None:
            unavailable(row, "invalid_verdict_date")
            continue
        horizon_months = row.get("horizon_months", DEFAULT_HORIZON_MONTHS)
        if isinstance(horizon_months, bool) or not isinstance(horizon_months, (int, float)):
            unavailable(row, "invalid_horizon_months")
            continue
        try:
            if not math.isfinite(horizon_months) or horizon_months <= 0:
                raise ValueError("invalid horizon")
            horizon_days = int(horizon_months * 30.44)
            horizon = vd + timedelta(days=horizon_days)
        except (ValueError, OverflowError):
            unavailable(row, "invalid_horizon_months")
            continue
        months_elapsed = (today - vd).days / 30.44
        if months_elapsed < horizon_months or horizon > today:
            still_pending += 1
            continue

        matured += 1
        if row.get("implied_prob") is None:
            unavailable(row, "missing_implied_prob")
            continue
        try:
            implied_prob = _validate_probability(row["implied_prob"])
        except ValueError:
            unavailable(row, "invalid_implied_prob")
            continue
        ticker = row.get("ticker", "")
        benchmark = row.get("benchmark", DEFAULT_BENCHMARK)

        # Frozen entry evidence fixes the observation date; its price is never rewritten.
        problem = _entry_quote_problem(row, "entry_price", "entry_quote", ticker)
        if problem is not None:
            unavailable(row, f"stock_entry:{problem}")
            continue
        problem = _entry_quote_problem(row, "benchmark_entry_price", "benchmark_entry_quote", benchmark)
        if problem is not None:
            unavailable(row, f"benchmark_entry:{problem}")
            continue

        horizon_date = horizon.isoformat()
        stock_snapshot = _fetch_return_snapshot(ticker, verdict_date, horizon_date)
        bm_snapshot = _fetch_return_snapshot(benchmark, verdict_date, horizon_date)
        row["return_snapshot"] = stock_snapshot
        row["benchmark_return_snapshot"] = bm_snapshot
        row["horizon_quote"] = stock_snapshot.get("horizon_quote")
        row["benchmark_horizon_quote"] = bm_snapshot.get("horizon_quote")
        if not stock_snapshot["available"]:
            unavailable(row, f"stock_snapshot:{stock_snapshot['reason']}")
            continue
        if not bm_snapshot["available"]:
            unavailable(row, f"benchmark_snapshot:{bm_snapshot['reason']}")
            continue
        if stock_snapshot["entry_quote"]["resolved_date"] != row["entry_quote"]["resolved_date"]:
            unavailable(row, "stock_snapshot:entry_date_changed")
            continue
        if bm_snapshot["entry_quote"]["resolved_date"] != row["benchmark_entry_quote"]["resolved_date"]:
            unavailable(row, "benchmark_snapshot:entry_date_changed")
            continue

        stock_return = stock_snapshot["return_fraction"]
        bm_return = bm_snapshot["return_fraction"]
        excess = stock_return - bm_return
        stock_return_pct = stock_return * 100
        bm_return_pct = bm_return * 100
        excess_pct = excess * 100
        if not all(math.isfinite(value) for value in
                   (stock_return, bm_return, excess, stock_return_pct, bm_return_pct, excess_pct)):
            unavailable(row, "nonfinite_return")
            continue
        favorable = excess > 0

        b = _brier(implied_prob, favorable)

        row["stock_return_pct"] = round(stock_return_pct, 2)
        row["realized_excess_pct"] = round(excess_pct, 2)
        row["stock_return_pct_unrounded"] = stock_return_pct
        row["realized_excess_pct_unrounded"] = excess_pct
        row["favorable"] = favorable
        row["brier"] = round(b, 6)
        row.pop("score_unavailable_reason", None)
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
    destination = prove_output_path(SCORECARD_FILE)
    rows = _load_verdicts()
    today_str = _today()

    # Price-Brier population excludes data_false_positive BUYs (P12d): they have no forward price.
    scored = _price_scorable(rows)
    fp_rows = [r for r in rows if _is_data_false_positive(r)]
    quarantined = [r for r in rows if _adjudication_blocks_price(r)]
    pending = [r for r in rows if not r.get("scored") and not _adjudication_blocks_price(r)]

    # De-risk-native metrics (P12c), measurable now, alongside / ahead of the price-Brier.
    blowup = _risk_metric_summary(rows, "avoidance", BLOWUP_DRAWDOWN_THRESHOLD)
    downside = _risk_metric_summary(rows, "capture", BLOWUP_DRAWDOWN_THRESHOLD)
    blowup_avoid = blowup["rate"]
    downside_cap = downside["rate"]
    buy_integrity = _buy_data_integrity_summary(rows)

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
        "Review coverage and outcomes among flagged names describe separate populations; the above-threshold rate does not establish successful loss avoidance.",
        "",
        "| Metric | Value | N | Notes |",
        "|---|---|---|---|",
        f"| BUY data-integrity (clean / reviewed BUY) | "
        f"{_integrity_description(buy_integrity)} | "
        f"{buy_integrity['reviewed_buys']} | "
        f"{buy_integrity['false_positive_buys']} receipt-backed data_false_positive |",
        f"| Above-threshold outcome rate (观察/避开 total return > {BLOWUP_DRAWDOWN_THRESHOLD*100:.0f}%) | "
        f"{(f'{blowup_avoid*100:.1f}%' if blowup_avoid is not None else '—')} | "
        f"{blowup['observed']} | "
        f"coverage {blowup['observed']}/{blowup['total']}; missing {blowup['missing']} |",
        f"| Downside-capture (避开 underperformed AND blew up) | "
        f"{(f'{downside_cap*100:.1f}%' if downside_cap is not None else '—')} | "
        f"{downside['observed']} | "
        f"coverage {downside['observed']}/{downside['total']}; missing {downside['missing']} |",
        "",
    ]

    lines += [f"Price quarantine: {len(quarantined)} verdicts (FP labels or unsupported review claims).", "",
              "Review coverage requires verdict-bound receipts; legacy labels alone remain pending.", ""]
    if fp_rows:
        lines += [
            "## BUY Data-Integrity (ledger adjudication labels)",
            "",
            f"{len(fp_rows)} ledger rows carry `data_false_positive`. These labels are excluded "
            "from price-Brier. Their presence does not prove review quality, historical provenance "
            "or current implementation performance; retain the underlying private evidence.",
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
        # Stored Brier scores remain available even when a legacy outcome lost precision.
        overall_brier = sum(r["brier"] for r in scored) / len(scored)
        outcomes = _outcome_summary(scored)
        overall_hit = f"{outcomes['rate']*100:.1f}%" if outcomes["rate"] is not None else "N/A"

        lines += [
            "## Overall",
            "",
            f"- **Scored verdicts:** {len(scored)}",
            f"- **Pending verdicts:** {len(pending)}",
            f"- **Overall Brier score:** {overall_brier:.4f} "
            f"(all {len(scored)} stored scores; 0=perfect, 0.25=uninformative random, 1=perfectly wrong)",
            f"- **Outcome coverage:** {outcomes['observed']}/{outcomes['total']}; "
            f"missing {outcomes['missing']} (legacy rounding or invalid outcome evidence)",
            f"- **Overall hit rate (stock beat benchmark):** {overall_hit}",
            "Outcome rates exclude unknown results; a legacy rounded zero is not evidence of failure.",
            "",
        ]

        # By rating bucket
        lines += [
            "## By Rating Bucket",
            "",
            "| Rating | N | Outcome N | Avg Brier | Hit Rate (stock > benchmark) | Implied p |",
            "|---|---|---|---|---|---|",
        ]
        for rating in ["买入", "观察", "避开"]:
            bucket = [r for r in scored if r.get("rating") == rating]
            if not bucket:
                lines.append(f"| {rating} | 0 | 0 | — | — | {RATING_PROB.get(rating, '—')} |")
                continue
            avg_b = sum(r["brier"] for r in bucket) / len(bucket)
            outcome = _outcome_summary(bucket)
            hit = f"{outcome['rate']*100:.1f}%" if outcome["rate"] is not None else "N/A"
            p = RATING_PROB.get(rating, 0.5)
            lines.append(f"| {rating} | {len(bucket)} | {outcome['observed']} | {avg_b:.4f} | {hit} | {p:.2f} |")

        # Calibration table
        # Calibration error = realized_freq − mean(implied_prob of members in bucket).
        # Using the mean implied_prob (not the bucket geometric midpoint) is correct because
        # all 观察 verdicts sit at exactly p=0.50, error must be realized_freq − 0.50,
        # not realized_freq − 0.475 (the midpoint of [0.40, 0.55)).
        lines += [
            "",
            "## Calibration Table",
            "",
            "*(Predicted probability bucket vs. realized favorable frequency)*",
            "*(Calibration error uses mean implied_prob and favorable frequency among known outcomes)*",
            "",
            "| p bucket | N | Outcome N | Mean implied_p | Realized freq | Calibration error |",
            "|---|---|---|---|---|---|",
        ]
        for (lo, hi) in CALIB_BUCKETS:
            bucket = [r for r in scored if lo <= r.get("implied_prob", 0.5) < hi]
            outcome = _outcome_summary(bucket)
            observed = outcome["rows"]
            if not observed:
                lines.append(f"| {lo:.2f}–{hi:.2f} | {len(bucket)} | 0 | — | — | — |")
                continue
            mean_p = sum(r.get("implied_prob", 0.5) for r in observed) / len(observed)
            realized = outcome["rate"]
            err = realized - mean_p
            lines.append(f"| {lo:.2f}–{hi:.2f} | {len(bucket)} | {len(observed)} | {mean_p:.3f} | {realized:.2f} | {err:+.2f} |")

        # Individual scored table
        lines += [
            "",
            "## Scored Verdicts",
            "",
            "| Ticker | Rating | p | Excess% | Favorable | Brier |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(scored, key=lambda x: x["verdict_date"]):
            outcome = _favorable_outcome(r)
            fav = "UNKNOWN" if outcome is None else ("YES" if outcome else "NO")
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

    prepare_output(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    quarantined = [r for r in rows if _adjudication_blocks_price(r)]
    scored = _price_scorable(rows)
    unscored = [r for r in rows if not r.get("scored") and not _adjudication_blocks_price(r)]

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
    print(f"  data_false_positive labels (out of price-Brier): {len(fp_rows)}")
    print(f"  Price quarantine (all unsupported claims and FP labels): {len(quarantined)}")
    buy_integrity = _buy_data_integrity_summary(rows)
    print("  BUY data-integrity:  " + _integrity_description(buy_integrity))

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

def cmd_recall_gold(args) -> int:
    """Report discovery and final-set recall using the same distinct gold cohort.

    Universe files retain upstream discovery and filter outcomes. Candidate files
    can additionally establish downstream gate losses. Those losses reduce final
    inclusion without erasing discovery provenance.
    """
    theme = args.theme
    if not theme:
        print("recall-gold requires --theme", file=sys.stderr)
        sys.exit(2)
    universe_paths = [Path(p) for p in (getattr(args, "universe", None) or [])]
    cand_paths = [Path(p) for p in (args.recall_gold or [])
                  if not str(p).endswith(".stage.json")]
    if not universe_paths and not cand_paths:
        print("recall-gold requires --universe (preferred) and/or candidate JSON path(s)",
              file=sys.stderr)
        sys.exit(2)

    upstream = []
    if universe_paths:
        # The gold cohort is the denominator; the universe supplies upstream evidence.
        observed = _recall_set_from_universe_files(universe_paths)
        recalled, fts_count, stage_sets = observed
        upstream.append(observed.completion)
        source = "universe"
        # Candidate gate outcomes occur after universe filtering.
        if cand_paths:
            candidate_observed = _recall_set_from_candidate_files(cand_paths)
            cand_final, _, cand_stages = candidate_observed
            upstream.append(candidate_observed.completion)
            stage_sets["gated_out"] |= cand_stages["gated_out"] - cand_final
            recalled -= stage_sets["gated_out"]
            source = "universe+candidates(gated_out)"
    else:
        # Legacy / fallback: post-filter candidate set only. WARN that recall is under-credited.
        observed = _recall_set_from_candidate_files(cand_paths)
        recalled, fts_count, stage_sets = observed
        upstream.append(observed.completion)
        source = "candidates (post-filter)"
        print("  [warn] recall-gold reading the POST-FILTER candidate set — size-capped / "
              "burn-rejected gold members will mislabel as fts_missed. Pass --universe "
              "<universe_*.csv> for a true recall floor (v0.3.1 #6).", file=sys.stderr)

    from filter_by_sic import stage_completion
    completion = stage_completion("recall_gold", len(recalled), upstream=upstream)
    res = recall_at_gold(
        theme, recalled, fts_hit_count=fts_count,
        fts_tickers=stage_sets["fts"],
        sic_tickers=stage_sets["sic"],
        mktcap_dropped=stage_sets["mktcap_dropped"],
        gated_out=stage_sets["gated_out"],
        completion=completion,
    )
    if res is None:
        print(f"recall@gold: no gold list for theme '{theme}' — not measurable")
        return 0
    print(f"recall@gold — theme '{theme}'  [source: {source}]")
    print(f"  observation coverage: {res['coverage_status']}")
    if not res["coverage_complete"]:
        print("  [WARN] incomplete observation; measured recall does not establish full coverage")
        print(f"  unknown_missing_gold: {', '.join(res['unknown_missing_gold']) or '—'}")
    print(f"  gold ({len(res['gold'])}):     {', '.join(res['gold'])}")
    print(f"  recalled_gold: {', '.join(res['recalled_gold']) or '—'}")
    print(f"  MISSING_gold:  {', '.join(res['missing_gold']) or '—'}")
    print(f"  recall@gold:   {res['recall_at_gold']*100:.1f}% "
          f"({len(res['recalled_gold'])}/{len(res['gold'])})")
    print(f"  discovery@gold: {res['discovery_recall_at_gold']*100:.1f}% "
          f"({len(res['discovered_gold'])}/{len(res['gold'])})")
    print("  discovery channels:")
    for channel, members in res['discovery_channels'].items():
        print(f"    {channel:<20} {len(members):>2}  {', '.join(members) or 'none'}")
    sb = res["stage_breakdown"]
    print(f"  loss-stage breakdown:")
    for stage in RECALL_STAGES:
        members = sb.get(stage) or []
        print(f"    {stage:<15} {len(members):>2}  {', '.join(members) or '—'}")
    if res["fts_cap_warning"]:
        print(f"  [WARN] {res['fts_cap_warning']}")
    return 0 if res["coverage_complete"] else 2


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

    # --- Test 5: bucket aggregation, 买入 bucket with 2 scored verdicts ---
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

    # --- Test 6: calibration table, bucket membership + mean-implied-prob error ---
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

    # --- Test 10 (P12d): retired history route cannot write or affect calibration ---
    from make_fixtures import tracking_scenarios, ownership_completion_fixture
    from unittest.mock import patch
    ledger = tracking_scenarios()["unreviewed"]
    before = _buy_data_integrity_summary(ledger)
    writes = []
    with patch.dict(globals(), {
            "_append_verdict": lambda row: writes.append(row) or True,
            "_load_verdicts": lambda: list(ledger)}):
        try:
            cmd_backfill_validation_fp(argparse.Namespace())
        except RuntimeError as exc:
            assert "retired" in str(exc)
        else:
            raise AssertionError("Retired history route must reject")
    assert writes == [], "Retired history route must not mutate the ledger"
    assert _buy_data_integrity_summary(ledger) == before
    assert before["reviewed_buys"] == 0 and before["rate"] is None

    # Independent synthetic metric arithmetic comes only from the fixture generator.
    fp_rows = [tracking_scenarios()["mixed"][1]]
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
    print("  PASS: retired history route is inert; synthetic false-positive excluded from price-Brier")

    # --- Test 11 (P12c): de-risk-native metrics (blowup-avoidance / downside-capture / BUY-integrity) ---
    # Synthetic BUY data-integrity: 1 false positive + 1 clean BUY -> 1/2.
    from make_fixtures import tracking_scenarios
    clean_buy = tracking_scenarios()['mixed'][0]
    integ_rows = fp_rows + [clean_buy]
    integ = _buy_data_integrity_rate(integ_rows)
    assert abs(integ - 0.5) < 1e-9, f"BUY data-integrity wrong: {integ}"
    # All-FP -> 0.0; no BUY at all -> None.
    assert _buy_data_integrity_rate(fp_rows) == 0.0, "all-FP integrity should be 0.0"
    assert _buy_data_integrity_rate([{"rating": "观察"}]) is None, "no-BUY integrity should be None"
    pending_review = _buy_data_integrity_summary(tracking_scenarios()['unreviewed'])
    assert pending_review['rate'] is None and pending_review['pending_buys'] == 1
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

    # --- P8: recall@gold, measure the recall floor against a hand-built gold list ---
    # theme_gold resolves via case-insensitive substring (compound slug), unmapped -> [].
    assert theme_gold("deathcare") == ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"], (
        f"P8: deathcare gold cohort mismatch: {theme_gold('deathcare')}"
    )
    assert theme_gold("funeral_deathcare_2026") == ["SCI", "CSV", "MATW", "HI", "STON", "SNFCA"], (
        "P8: compound slug must resolve the gold list (substring match)"
    )
    assert theme_gold("ai agents") == [], "P8: an unmapped theme must have NO gold list"
    # Coverage-test gold cohorts (2026-06-20).
    assert theme_gold("cov-water-utilities")[:2] == ["YORW", "ARTNA"], "P8: water-utilities gold cohort"
    assert {"GATX", "RAIL"} <= set(theme_gold("railcar-leasing")), "P8: railcar gold cohort"
    assert "BYD" in theme_gold("regional-gaming"), "P8: regional-gaming gold cohort"
    assert recall_at_gold("ai agents", ["NVDA"]) is None, (
        "P8: recall_at_gold must be None (not measurable) for an unmapped theme"
    )

    # Synthetic stage scenarios are isolated from the operational gold lookup above.
    from make_fixtures import source34_scenarios
    from unittest.mock import patch
    import _recall as _recall_module
    _recall_case = source34_scenarios()["recall"]
    _g0, _g1, _g2, _g3, _g4, _g5 = _recall_case["gold"]
    with patch.dict(_recall_module.THEME_GOLD,
                    {_recall_case["theme"]: _recall_case["gold"]}, clear=True):

        _full = recall_at_gold(_recall_case["theme"], [_g0, _g1, _g2, _g3, _g4, _g5, "NOISE"])
        assert _full["recall_at_gold"] == 1.0, f"P8: full recall must be 1.0, got {_full['recall_at_gold']}"
        assert _full["missing_gold"] == [], f"P8: full recall must miss none, got {_full['missing_gold']}"



        _part = recall_at_gold(_recall_case["theme"], [_g0.lower(), _g1.lower()])
        assert _part["recall_at_gold"] == round(2 / 6, 4), (
            f"P8: partial recall must be 2/6 (rounded), got {_part['recall_at_gold']}"
        )
        assert _part["recalled_gold"] == [_g1, _g0], f"P8: hits must normalize+sort: {_part['recalled_gold']}"
        assert _part["missing_gold"] == [_g3, _g2, _g5, _g4], (
            f"P8: missing must be the cross-SIC leak: {_part['missing_gold']}"
        )
        assert _part["fts_cap_warning"] is None, "P8: no cap warning when fts_hit_count omitted"


        _psb = _part["stage_breakdown"]
        assert set(_psb) == set(RECALL_STAGES), f"P8: stage_breakdown keys must be RECALL_STAGES: {set(_psb)}"
        assert _psb["recalled_final"] == [_g1, _g0], f"P8: default recalled_final: {_psb['recalled_final']}"
        assert _psb["fts_missed"] == [_g3, _g2, _g5, _g4], (
            f"P8: default missing -> fts_missed: {_psb['fts_missed']}"
        )
        assert _psb["discovered_not_final"] == [] and _psb["dropped_mktcap"] == [] and _psb["gated_out"] == [], (
            "P8: no per-stage inputs => only recalled_final/fts_missed populated"
        )
        _allmembers = [t for st in RECALL_STAGES for t in _psb[st]]
        assert sorted(_allmembers) == sorted(_part["gold"]), "P8: stages must partition gold exactly"
        assert len(_allmembers) == len(set(_allmembers)), "P8: each gold member in exactly one stage"
        assert len(_psb["recalled_final"]) == len(_part["recalled_gold"]), (
            "P8: final stage must reconcile to final-set recall hits"
        )


        _capped = recall_at_gold(_recall_case["theme"], [_g0], fts_hit_count=FTS_TOP_HITS_CAP)
        assert _capped["fts_cap_warning"] is not None and "cap" in _capped["fts_cap_warning"], (
            "P8: fts_hit_count >= 1000 must set the top-1000 cap warning"
        )
        _uncapped = recall_at_gold(_recall_case["theme"], [_g0], fts_hit_count=999)
        assert _uncapped["fts_cap_warning"] is None, "P8: below the cap must NOT warn"









        _gold = theme_gold(_recall_case["theme"])
        _sb = recall_stage_breakdown(
            _gold,
            recalled_tickers=[_g0],
            fts_tickers=[_g0],
            sic_tickers=[_g0, _g2],
            mktcap_dropped=[_g4],
            gated_out=[_g3],
        )
        assert _sb["recalled_final"] == [_g0], f"P8 stage: recalled_final: {_sb['recalled_final']}"
        assert len(_sb["discovered_not_final"]) == 1, "P8: one discovered member has no final outcome"
        assert _sb["dropped_mktcap"] == [_g4], f"P8 stage: dropped_mktcap: {_sb['dropped_mktcap']}"
        assert _sb["gated_out"] == [_g3], f"P8 stage: gated_out: {_sb['gated_out']}"
        assert _sb["fts_missed"] == [_g1, _g5], f"P8 stage: fts_missed: {_sb['fts_missed']}"

        _members = [t for st in RECALL_STAGES for t in _sb[st]]
        assert sorted(_members) == sorted(_gold), f"P8 stage: must partition gold exactly: {_members}"
        assert len(_members) == len(set(_members)) == len(_gold), "P8 stage: each member exactly once"


        _sb2 = recall_stage_breakdown(
            [_g0], recalled_tickers=[_g0], sic_tickers=[_g0], mktcap_dropped=[_g0], gated_out=[_g0],
        )
        assert _sb2["recalled_final"] == [_g0] and all(
            _sb2[s] == [] for s in RECALL_STAGES if s != "recalled_final"
        ), "P8 stage: recalled_final must take precedence over downstream tags"


        _resb = recall_at_gold(
            _recall_case["theme"], [_g0], fts_tickers=[_g0], sic_tickers=[_g0, _g2],
            mktcap_dropped=[_g4], gated_out=[_g3],
        )
        assert _resb["stage_breakdown"] == _sb, "P8 stage: recall_at_gold must embed the breakdown"
        _hits = len(_resb["stage_breakdown"]["recalled_final"])

        assert _resb["recalled_gold"] == [_g0], f"P8 stage: recalled_gold (final set): {_resb['recalled_gold']}"
        assert _hits == len(_resb['recalled_gold']) == 1, "P8: only final inclusion counts in final recall"
        assert len(_resb['discovered_gold']) == 4, "P8: channel and downstream-loss evidence establish discovery"




        import tempfile
        with tempfile.TemporaryDirectory() as _td:
            _cf = Path(_td) / "synthetic-candidates.json"
            _cf.write_text(json.dumps([
                {"ticker": _g0, "recall_channel": "both"},
                {"ticker": _g1, "recall_channel": "fts"},
                {"ticker": _g2, "recall_channel": "sic_reverse"},
                {"ticker": _g0.lower(), "recall_channel": "fts"},
                {"ticker": _g4, "recall_channel": "both", "dropped_stage": "mktcap"},
                {"ticker": _g3, "recall_channel": "fts", "buy_ineligible": True},
            ]), encoding="utf-8")
            _rset, _fts, _stages = _recall_set_from_candidate_files([_cf])

            assert _rset == {_g0, _g1, _g2}, f"P8: recall set dedupe/normalize: {_rset}"
            assert _fts == 5, f"P8: FTS-channel count (fts+both, excl sic_reverse): {_fts}"
            assert _stages["sic"] == {_g0, _g2, _g4}, f"P8: SIC-channel set: {_stages['sic']}"
            assert _stages["mktcap_dropped"] == {_g4}, f"P8: mktcap-dropped set: {_stages['mktcap_dropped']}"
            assert _stages["gated_out"] == {_g3}, f"P8: gated-out set: {_stages['gated_out']}"
            _res = recall_at_gold(
                _recall_case["theme"], _rset,
                fts_tickers=_stages["fts"], sic_tickers=_stages["sic"],
                mktcap_dropped=_stages["mktcap_dropped"], gated_out=_stages["gated_out"],
            )
            assert _res["recall_at_gold"] == round(3 / 6, 4), (
                f"P8: 3 of 6 gold recalled from candidate file, got {_res['recall_at_gold']}"
            )



            _fsb = _res["stage_breakdown"]
            assert _fsb["recalled_final"] == [_g1, _g2, _g0], f"P8 file stage recalled_final: {_fsb['recalled_final']}"
            assert _fsb["discovered_not_final"] == [], "P8: all discovered members have a recorded terminal outcome"
            assert _fsb["dropped_mktcap"] == [_g4], f"P8 file stage dropped_mktcap: {_fsb['dropped_mktcap']}"
            assert _fsb["gated_out"] == [_g3], f"P8 file stage gated_out: {_fsb['gated_out']}"
            assert _fsb["fts_missed"] == [_g5], f"P8 file stage fts_missed: {_fsb['fts_missed']}"
        print("  P8 recall@gold: floor measured + loss-stage breakdown "
              "(full/partial/cap-warn + 5-stage partition + file read)  OK")









        import tempfile as _tf6
        import csv as _csv6
        with _tf6.TemporaryDirectory() as _td6:

            _cf6 = Path(_td6) / "synthetic-candidates.json"
            _cf6.write_text(json.dumps([
                {"ticker": _g1, "recall_channel": "both"},
                {"ticker": _g5, "recall_channel": "fts"},
            ]), encoding="utf-8")
            _crec, _cfts, _cstg = _recall_set_from_candidate_files([_cf6])
            _cres = recall_at_gold(
                _recall_case["theme"], _crec, fts_hit_count=_cfts,
                fts_tickers=_cstg["fts"], sic_tickers=_cstg["sic"],
                mktcap_dropped=_cstg["mktcap_dropped"], gated_out=_cstg["gated_out"],
            )

            assert _cres["recall_at_gold"] == round(2 / 6, 4), (
                f"#6: post-filter candidates must read 2/6=33.3% (the regression), got {_cres['recall_at_gold']}"
            )
            assert _g0 in _cres["stage_breakdown"]["fts_missed"], (
                "#6: candidates-only mislabels size-capped first member as fts_missed (the bug being fixed)"
            )










            _uf6 = Path(_td6) / "synthetic-universe.csv"
            _ufields = ["name", "ticker", "cik", "sic", "matched_phrase", "flag_too_big",
                        "flag_illiquid", "band", "smallcap_candidate", "recall_channel"]
            with open(_uf6, "w", newline="", encoding="utf-8") as _ufh:
                _w = _csv6.DictWriter(_ufh, fieldnames=_ufields)
                _w.writeheader()
                _w.writerows(_recall_case["universe"])
            _urec, _ufts, _ustg = _recall_set_from_universe_files([_uf6])

            assert _urec == {_g1, _g5, _g2}, f"#6: universe survivor set: {_urec}"

            assert _ufts == 4, f"#6: universe FTS-hit count (fts+both): {_ufts}"
            assert _ustg["sic"] == {_g1, _g2, _g0}, f"#6: universe SIC-channel set: {_ustg['sic']}"
            assert _ustg["mktcap_dropped"] == {_g0, _g3}, (
                f"#6: size/liquidity drops attributed (NOT fts_missed): {_ustg['mktcap_dropped']}"
            )
            _ures = recall_at_gold(
                _recall_case["theme"], _urec, fts_hit_count=_ufts,
                fts_tickers=_ustg["fts"], sic_tickers=_ustg["sic"],
                mktcap_dropped=_ustg["mktcap_dropped"], gated_out=_ustg["gated_out"],
            )

            _u_sb = _ures["stage_breakdown"]
            _u_recalled_or_dropped = (
                set(_u_sb["recalled_final"]) | set(_u_sb["discovered_not_final"]) | set(_u_sb["dropped_mktcap"])
            )
            assert len(_u_recalled_or_dropped) == 5, (
                f"#6: 5/6 gold present in universe (only omitted member missing), got {sorted(_u_recalled_or_dropped)}"
            )


            assert _g0 in _u_sb["dropped_mktcap"], "#6: size-capped first member must attribute to dropped_mktcap, not fts_missed"
            assert _g3 in _u_sb["dropped_mktcap"], "#6: liquidity-dropped fourth member must attribute to dropped_mktcap, not fts_missed"
            assert _g0 not in _u_sb["fts_missed"] and _g3 not in _u_sb["fts_missed"], (
                "#6: recalled-then-dropped gold members must NEVER land in fts_missed"
            )




            assert _g2 in _u_sb["recalled_final"], (
                f"#6: SIC-recovered survivor third member must be recalled_final: {_u_sb['recalled_final']}"
            )
            assert _g2 in _ustg["sic"] and _g2 not in _ustg["fts"], (
                "#6: third member must be credited to the SIC floor (sic channel, FTS missed it)"
            )
            assert _u_sb["fts_missed"] == [_g4], (
                f"#6: only the omitted synthetic omitted member is the true recall leak: {_u_sb['fts_missed']}"
            )

            _represented_recall = len(_u_recalled_or_dropped) / 5.0
            assert _represented_recall == 1.0, f"#6: synthetic_recall represented-member recall must be ~100% at universe, got {_represented_recall}"

            assert _ures["recall_at_gold"] > _cres["recall_at_gold"], (
                "#6: universe recall@gold must exceed the post-filter candidate artifact"
            )
            assert len(_u_sb["fts_missed"]) < len(_cres["stage_breakdown"]["fts_missed"]), (
                "#6: universe must attribute fewer names to fts_missed than the candidates file"
            )




            class _A6:
                theme = _recall_case["theme"]
                universe = [str(_uf6)]
                recall_gold = [str(_cf6)]
            cmd_recall_gold(_A6())

            class _A6b:
                theme = _recall_case["theme"]
                universe = [str(_uf6)]
                recall_gold = None
            cmd_recall_gold(_A6b())


            _, _, _merge_cand = _recall_set_from_candidate_files([_cf6])
            _ustg["gated_out"] |= _merge_cand["gated_out"]
            _mres = recall_at_gold(
                _recall_case["theme"], _urec, fts_hit_count=_ufts,
                fts_tickers=_ustg["fts"], sic_tickers=_ustg["sic"],
                mktcap_dropped=_ustg["mktcap_dropped"], gated_out=_ustg["gated_out"],
            )
            assert _g0 in _mres["stage_breakdown"]["dropped_mktcap"], (
                "#6: candidates merge must not demote a universe dropped_mktcap name to fts_missed"
            )
        print("  v0.3.1 #6 recall@gold: UNIVERSE source — size/burn drops attributed to true stage "
              "(synthetic_recall 5/6 represented=100% at universe vs 2/6 candidate artifact)  OK")

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
            "recent_13d_13g_completion": ownership_completion_fixture(2),
            "short_interest_pct": 18.4,
            "short_trend": "rising",
            "staleness_note": "13F lags ~45d; short interest bi-monthly — positioning context only",
        },
        "signals_meta": {"diagnostic_only": True, "never_affects_buy": True, "sources": ["EDGAR"]},
    }

    # (a) snapshot shape, compact divergence_label + ownership summary (newest filing only).
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
    # otherwise-identical source records, one WITH signals, one WITHOUT, through the real builder
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
    # The two rows must be identical in EVERY other field, the ONLY permitted difference is the
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

def main() -> int | None:
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
                    help="Finite confidence: 0..1 fraction or >1..100 percent (1 means 100 percent). "
                         "Mapped by rating direction. Omit for the fixed RATING_PROB convention.")
    ap.add_argument("--kill-flags", default="", dest="kill_flags",
                    help="Comma-separated kill flags")
    ap.add_argument("--theme", default="", help="Theme slug")
    ap.add_argument("--verdict-date", default="", dest="verdict_date",
                    help="YYYY-MM-DD (defaults to today)")
    ap.add_argument("--adjudicate", metavar="PRIVATE_RECEIPT_JSON",
                    help="Attach a supplied verdict-bound review receipt to an existing private ledger row")
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
                    help="Retired: historical evidence cannot be automatically adjudicated or injected.")
    ap.add_argument("--recall-gold", nargs="+", dest="recall_gold", metavar="CANDIDATES_JSON",
                    help="P8: compute recall@gold for --theme against its hand-built gold "
                         "true-member list. Reads the POST-FILTER candidate set — prefer "
                         "--universe for a true recall floor (v0.3.1 #6). When passed with "
                         "--universe, contributes only its deep-dive gated_out stage.")
    ap.add_argument("--universe", nargs="+", dest="universe", metavar="UNIVERSE_CSV",
                    help="v0.3.1 #6: compute recall@gold against the UNIVERSE CSV(s) discover.py "
                         "emits (raw FTS ∪ SIC-reverse, pre band/burn/liquidity). The correct "
                         "recall denominator — credits the SIC floor and attributes size-capped / "
                         "burn-rejected gold members to their true loss stage. Use with "
                         "--recall-gold (--theme required).")
    ap.add_argument("--selftest", action="store_true",
                    help="Run synthetic Brier math selftest (no network)")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if args.adjudicate:
        cmd_adjudicate(args)
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

    if args.recall_gold or getattr(args, "universe", None):
        return cmd_recall_gold(args)

    ap.print_help()


if __name__ == "__main__":
    sys.exit(main())
