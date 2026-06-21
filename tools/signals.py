"""Between-filings DIAGNOSTIC side-channel for small-cap-deepdive (iteration-4, §5 Q2).

数据:yfinance(6m/12m 价格回报) + EDGAR EFTS(SC 13D/13G 持仓变动) + FINRA(空头,可达则取,否则 null)。
本模块实现 P16(基本面-价格背离)+ P17(持仓/空头定位)两个 between-filings 信号。

THE FIREWALL (approved philosophy decision Q2 — the single most important invariant)
-----------------------------------------------------------------------------------
Everything this module emits is DIAGNOSTIC-ONLY. The deepdive writes the result under a
SEPARATE top-level "signals" namespace (a sibling of "derived", NEVER inside it). The
firewall is enforced by *contract*, not by this module:

  * valuation.py, the buy_eligible composite, and the BUY trigger MUST NOT read any
    signals.* field. They stay anchored to T1 filing-derived valuation + zero kill-flags
    + buy_eligible. Signals can NEVER originate or up-weight a BUY.
  * Signals may be READ BY AN ANALYST/agent as labeled T2 context, and snapshotted by
    track_forward into the verdict row for FUTURE per-signal Brier calibration. They are
    track-forward-gated until their own predictive value exists.

This is how the diffusion thesis ("fundamentals improving, market hasn't priced it") gets
*operationalized* WITHOUT rebuilding the confident-but-wrong narrative engine: a real
divergence becomes labeled evidence an analyst can weigh, never a trigger that fires on
its own.

P16 (price_divergence) reads the fundamental trajectory FROM the passed deepdive_derived
(rev_slope_sign / contamination_ratio / fundamental_decline_flag) — it does NOT recompute
trajectory. It only adds the price-return leg and the divergence label.

Robust to network failure: compute_signals returns a partial dict + signals_error and
NEVER raises. The deepdive guards it again at the call site.

CLI:  python tools/signals.py --selftest
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone, timedelta

from _common import http_get

# EDGAR full-text search (EFTS) — same endpoint discover_events.py uses for 10-12B.
# Filtered by SUBJECT cik + forms=SC 13D,SC 13G enumerates ownership filings against the
# company. (Overlaps P11's 13D catalyst category — same enumeration endpoint, by design.)
EFTS = "https://efts.sec.gov/LATEST/search-index"

# FINRA equity short-interest CSV (bi-monthly, free, no key). Best-effort: if unreachable
# we record null + an explicit staleness_note rather than failing the block. The schema is
# not contractually stable, so a parse failure is treated the same as unreachable.
_FINRA_SI = "https://cdn.finra.org/equity/regsho/daily"  # placeholder host; guarded below


# ---------------------------------------------------------------------------
# P16 — Fundamental-vs-Price divergence
# ---------------------------------------------------------------------------

def _price_returns(ticker: str, price_fn=None) -> dict:
    """Trailing 6m / 12m total return from yfinance (dividend-adjusted if available).

    Returns {price_return_6m, price_return_12m, price_source, price_error?}. Each return is
    a fraction (0.10 == +10%) or None. price_fn is injectable for selftest so no network
    call is made there; it must return a list of (date, adj_close) ascending, or None.
    """
    out = {"price_return_6m": None, "price_return_12m": None, "price_source": None}
    if not ticker:
        out["price_error"] = "no_ticker"
        return out
    try:
        series = price_fn(ticker) if price_fn is not None else _yf_price_series(ticker)
    except Exception as e:  # never let a price pull crash the block
        out["price_error"] = f"price_fetch_error:{type(e).__name__}"
        return out
    if not series or len(series) < 2:
        out["price_error"] = "insufficient_price_history"
        return out

    out["price_source"] = "yfinance_adjclose"
    # series is ascending [(date, adj_close), ...]; last point is "now".
    last_dt, last_px = series[-1]
    if last_px is None or last_px <= 0:
        out["price_error"] = "bad_latest_price"
        return out

    def _ret_at(days_back: int) -> float | None:
        cutoff = last_dt - timedelta(days=days_back)
        # nearest point on-or-before cutoff (first historical anchor)
        anchor = None
        for dt, px in series:
            if dt <= cutoff and px and px > 0:
                anchor = px
        if anchor is None:
            return None
        return round(last_px / anchor - 1.0, 4)

    out["price_return_6m"] = _ret_at(182)
    out["price_return_12m"] = _ret_at(365)
    return out


def _yf_price_series(ticker: str):
    """Fetch ~13mo of daily adjusted closes from yfinance. Returns [(datetime, float)]."""
    import yfinance as yf
    hist = yf.Ticker(ticker).history(period="13mo", auto_adjust=True)
    if hist is None or hist.empty:
        return None
    series = []
    for idx, row in hist.iterrows():
        dt = idx.to_pydatetime()
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        close = row.get("Close")
        if close is not None and close == close and close > 0:  # not NaN, positive
            series.append((dt, float(close)))
    return series or None


def _divergence_label(rev_slope_sign, contamination_ratio, fundamental_decline_flag,
                      price_return_6m, price_return_12m) -> tuple[str, str]:
    """Classify divergence between fundamental trajectory (T1, READ from derived) and price.

    Returns (divergence_label, note). Labels:
      "unpriced_improvement"     fundamentals improving (rev_slope>0 AND not declining)
                                 AND price flat/down  -> THE diffusion thesis: a real change
                                 the market hasn't priced.
      "melting_ice_cube_priced"  fundamentals declining (decline_flag OR rev_slope<0)
                                 AND price up/elevated -> SIGA-shaped: decline already in
                                 the tape, no edge.
      "aligned"                  trajectory and price point the same way (both up / both down).
      "unclear"                  trajectory or price unknown, or a flat/mixed configuration.
    """
    # "elevated" price = either window meaningfully positive; "flat/down" = neither up.
    rets = [r for r in (price_return_6m, price_return_12m) if r is not None]
    if not rets:
        return "unclear", "no price-return data; cannot assess divergence."
    price_up = max(rets) >= 0.05         # >= +5% in either window => up/elevated
    price_down_flat = max(rets) < 0.05   # nothing meaningfully positive => flat/down

    declining = bool(fundamental_decline_flag) or (rev_slope_sign is not None and rev_slope_sign < 0)
    improving = (rev_slope_sign is not None and rev_slope_sign > 0) and not bool(fundamental_decline_flag)

    if improving and price_down_flat:
        return ("unpriced_improvement",
                "Fundamentals improving (rev_slope>0, no decline flag) while price is flat/down "
                "— the diffusion thesis (a real change the market may not have priced). "
                "DIAGNOSTIC ONLY: read as T2 context, never a BUY trigger.")
    if declining and price_up:
        return ("melting_ice_cube_priced",
                "Fundamentals declining while price is up/elevated — SIGA-shaped: the decline "
                "is already in the tape, no informational edge. DIAGNOSTIC ONLY.")
    if improving and price_up:
        return ("aligned", "Fundamentals improving and price up — trajectory and tape agree (priced in).")
    if declining and price_down_flat:
        return ("aligned", "Fundamentals declining and price down — trajectory and tape agree.")
    return ("unclear",
            "Flat/mixed trajectory or borderline price move; no clean divergence signal.")


def compute_price_divergence(deepdive_derived: dict, ticker: str, price_fn=None) -> dict:
    """P16 block: price returns + divergence label vs the READ fundamental trajectory.

    fundamental_trajectory is READ from deepdive_derived (NOT recomputed):
    rev_slope_sign, contamination_ratio, fundamental_decline_flag.
    """
    d = deepdive_derived or {}
    rev_slope_sign = d.get("rev_slope_sign")
    contamination_ratio = d.get("contamination_ratio")
    fundamental_decline_flag = d.get("fundamental_decline_flag")

    pr = _price_returns(ticker, price_fn=price_fn)
    label, note = _divergence_label(
        rev_slope_sign, contamination_ratio, fundamental_decline_flag,
        pr.get("price_return_6m"), pr.get("price_return_12m"),
    )
    block = {
        "price_return_6m": pr.get("price_return_6m"),
        "price_return_12m": pr.get("price_return_12m"),
        "price_source": pr.get("price_source"),
        "fundamental_trajectory": {
            "rev_slope_sign": rev_slope_sign,
            "contamination_ratio": contamination_ratio,
            "fundamental_decline_flag": fundamental_decline_flag,
            "read_from": "deepdive_derived (NOT recomputed)",
        },
        "divergence_label": label,
        "note": note,
    }
    if pr.get("price_error"):
        block["price_error"] = pr["price_error"]
    return block


# ---------------------------------------------------------------------------
# P17 — Ownership / short-interest positioning
# ---------------------------------------------------------------------------

def _recent_13d_13g(cik, lookback_days: int = 540, http_fn=http_get) -> list[dict]:
    """Enumerate recent SC 13D / SC 13G (and /A) filings for a SUBJECT cik via EDGAR EFTS.

    Returns a list of {form, file_date, filer} newest-first, or [] on any failure. http_fn
    is injectable for selftest. Overlaps P11's 13D catalyst category by design (same EFTS
    enumeration). Default lookback ~18 months captures the canonical small-cap activist /
    institutional accumulation window while staying bounded.

    EFTS query shape (verified against live efts.sec.gov 2026-06): pass NO `q` param. An
    empty quoted `q=""` makes the full-text engine require an (empty) phrase match and
    silently returns 0 hits for EVERY cik — the same omit-`q` pattern discover_events.py
    uses for 10-12B. Forms include the /A amendments implicitly (forms=SC 13D returns
    SC 13D and SC 13D/A); the date window is applied via startdt/enddt.
    """
    if cik is None or str(cik).strip() in ("", "nan"):
        return []
    cik10 = str(cik).split(".")[0].strip().zfill(10)
    now = datetime.now(timezone.utc)
    startdt = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    enddt = now.strftime("%Y-%m-%d")
    url = (f"{EFTS}?forms=SC%2013D,SC%2013G&ciks={cik10}"
           f"&dateRange=custom&startdt={startdt}&enddt={enddt}")
    try:
        r = http_fn(url, timeout=25)
        if r.status_code != 200:
            return []
        hits = r.json().get("hits", {}).get("hits", [])
    except Exception:
        return []

    out = []
    for h in hits:
        s = h.get("_source", {})
        form = s.get("form", "")
        file_date = s.get("file_date", "")
        # display_names[0] is the subject; the FILER (accumulator) is usually a later entry.
        names = s.get("display_names", []) or []
        filer = ""
        if len(names) > 1:
            filer = names[-1]
        elif names:
            filer = names[0]
        out.append({"form": form, "file_date": file_date, "filer": filer})
    out.sort(key=lambda x: x.get("file_date", ""), reverse=True)
    return out


def _short_interest(ticker: str, si_fn=None) -> dict:
    """FINRA short interest if reachable, else null with an explicit staleness_note.

    Returns {short_interest_pct, short_trend, staleness_note}. si_fn injectable for selftest;
    when it (or the live pull) is unavailable, short fields are null and labeled stale — never
    a hard failure. FINRA short interest is bi-monthly, so even when present it is ALWAYS stale
    relative to today; we say so explicitly.
    """
    out = {"short_interest_pct": None, "short_trend": None,
           "staleness_note": ("FINRA short interest is bi-monthly and not pulled here "
                              "(no stable free endpoint) — treat as UNAVAILABLE/STALE.")}
    if not ticker:
        return out
    if si_fn is None:
        return out  # no reachable free source wired; null + staleness_note (contract-compliant)
    try:
        val = si_fn(ticker)
    except Exception:
        return out
    if not val:
        return out
    out["short_interest_pct"] = val.get("short_interest_pct")
    out["short_trend"] = val.get("short_trend")
    out["staleness_note"] = val.get(
        "staleness_note",
        "FINRA short interest is bi-monthly — value lags today by up to ~2 weeks.")
    return out


def compute_ownership(ticker: str, cik, http_fn=http_get, si_fn=None) -> dict:
    """P17 block: recent 13D/13G enumeration + short interest (or null+staleness)."""
    filings = _recent_13d_13g(cik, http_fn=http_fn)
    si = _short_interest(ticker, si_fn=si_fn)
    return {
        "recent_13d_13g": filings,
        "recent_13d_13g_count": len(filings),
        "short_interest_pct": si["short_interest_pct"],
        "short_trend": si["short_trend"],
        "staleness_note": si["staleness_note"],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_signals(ticker: str, cik, deepdive_derived: dict,
                    price_fn=None, http_fn=http_get, si_fn=None) -> dict:
    """Build the top-level "signals" namespace. DIAGNOSTIC-ONLY (see THE FIREWALL).

    Returns a dict with keys: price_divergence (P16), ownership (P17), signals_meta.
    NEVER raises — on any error returns a partial dict plus signals_error so the deepdive
    can attach it without crashing. The caller (deepdive_data.py) writes this under a
    top-level "signals" key, a SIBLING of "derived" — never inside derived, and never read
    by valuation / buy_eligible / the BUY trigger.

    price_fn / http_fn / si_fn are injectable for selftest (no network).
    """
    signals: dict = {}
    errors = []

    try:
        signals["price_divergence"] = compute_price_divergence(
            deepdive_derived, ticker, price_fn=price_fn)
    except Exception as e:
        signals["price_divergence"] = None
        errors.append(f"price_divergence:{type(e).__name__}:{e}")

    try:
        signals["ownership"] = compute_ownership(
            ticker, cik, http_fn=http_fn, si_fn=si_fn)
    except Exception as e:
        signals["ownership"] = None
        errors.append(f"ownership:{type(e).__name__}:{e}")

    signals["signals_meta"] = {
        "diagnostic_only": True,
        "never_affects_buy": True,
        "sources": [
            "yfinance (price returns, dividend-adjusted close)",
            "EDGAR EFTS (SC 13D/13G ownership filings by subject CIK)",
            "FINRA short interest (bi-monthly, best-effort / often null)",
        ],
        "notes": (
            "Quarantined T2 side-channel (design §5 Q2). Read by an analyst/agent as labeled "
            "context and snapshotted by track_forward for FUTURE per-signal Brier calibration. "
            "MUST NOT be read by valuation.py, the buy_eligible composite, or the BUY trigger. "
            "A BUY stays anchored to T1 filing-derived valuation + zero kill-flags + buy_eligible."
        ),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if errors:
        signals["signals_error"] = "; ".join(errors)
    return signals


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> None:
    """P16 divergence-label logic + P17 robustness + firewall-flag assertions (no network)."""

    # ---- P16: declining fundamentals + price UP => melting_ice_cube_priced (SIGA shape) ----
    declining_derived = {
        "rev_slope_sign": -1,
        "contamination_ratio": 0.85,
        "fundamental_decline_flag": True,
    }
    # synthetic ascending price path spanning >12mo so both 6m and 12m anchors resolve.
    # +30% over the full window (price up/elevated). Points at 0 / 6mo / 12mo / "now".
    base = datetime(2025, 5, 1)
    up_path = [(base, 10.0),                              # 0 (12mo+ ago anchor)
               (base + timedelta(days=183), 11.0),       # ~6mo
               (base + timedelta(days=366), 12.0),       # ~12mo
               (base + timedelta(days=400), 13.0)]       # "now"
    sig = compute_signals("FAKE", "0000320193", declining_derived,
                          price_fn=lambda t: up_path,
                          http_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("net!")),
                          si_fn=None)
    # http_fn raising is caught -> ownership becomes a guarded block (not a crash)
    pd = sig["price_divergence"]
    assert pd["price_return_12m"] is not None and pd["price_return_12m"] > 0.2, (
        f"P16: 12m return should be ~+30%, got {pd['price_return_12m']}")
    assert pd["divergence_label"] == "melting_ice_cube_priced", (
        f"P16: declining fundamentals + price up must => melting_ice_cube_priced, "
        f"got {pd['divergence_label']}")
    # firewall: fundamental_trajectory is READ from derived, not recomputed
    assert pd["fundamental_trajectory"]["rev_slope_sign"] == -1, "P16: must read rev_slope_sign from derived"
    assert pd["fundamental_trajectory"]["read_from"].startswith("deepdive_derived"), (
        "P16: must declare it reads trajectory from derived (no recompute)")
    print(f"  P16: declining + price+30% -> {pd['divergence_label']}  OK")

    # ---- P16: improving fundamentals + price FLAT/down => unpriced_improvement (the thesis) ----
    improving_derived = {
        "rev_slope_sign": 1,
        "contamination_ratio": 1.1,
        "fundamental_decline_flag": False,
    }
    flat_path = [(base, 10.0),                            # 0 (12mo anchor)
                 (base + timedelta(days=183), 9.8),       # ~6mo
                 (base + timedelta(days=366), 9.9),       # ~12mo
                 (base + timedelta(days=400), 10.1)]      # "now" -> ~flat, <+5% both windows
    sig2 = compute_signals("FAKE", None, improving_derived,
                           price_fn=lambda t: flat_path, si_fn=None)
    pd2 = sig2["price_divergence"]
    assert pd2["divergence_label"] == "unpriced_improvement", (
        f"P16: improving fundamentals + flat price must => unpriced_improvement, "
        f"got {pd2['divergence_label']}")
    print(f"  P16: improving + price~flat -> {pd2['divergence_label']}  OK")

    # ---- P16: aligned (both up) ----
    label, _ = _divergence_label(1, 1.1, False, 0.30, 0.40)
    assert label == "aligned", f"P16: improving + up must => aligned, got {label}"
    # ---- P16: aligned (both down) — the 4th contract case (declining + price down) ----
    label_dd, _ = _divergence_label(-1, 0.8, True, -0.10, -0.20)
    assert label_dd == "aligned", f"P16: declining + price down must => aligned, got {label_dd}"
    # ---- P16: melting via rev_slope<0 ONLY (no decline_flag) + price up ----
    label_m, _ = _divergence_label(-1, 0.9, False, 0.10, 0.20)
    assert label_m == "melting_ice_cube_priced", (
        f"P16: rev_slope<0 (no flag) + price up must => melting_ice_cube_priced, got {label_m}")
    # ---- P16: unclear when no price data ----
    label_u, _ = _divergence_label(1, 1.1, False, None, None)
    assert label_u == "unclear", f"P16: no price data must => unclear, got {label_u}"
    # ---- P16: borderline — exactly +5% counts as up (>= threshold) ----
    label_b, _ = _divergence_label(1, 1.1, False, 0.05, 0.04)
    assert label_b == "aligned", f"P16: +5% is up (>= threshold) => aligned, got {label_b}"
    print("  P16: aligned(both up/both down) / melting-via-slope / unclear / threshold branches  OK")

    # ---- P17: ownership enumeration parses EFTS hits + sorts newest-first (mocked http) ----
    class _Resp:
        status_code = 200
        @staticmethod
        def json():
            return {"hits": {"hits": [
                {"_source": {"form": "SC 13G", "file_date": "2026-02-10",
                             "display_names": ["FAKECO  (FAKE)  (CIK 0000320193)",
                                               "VANGUARD GROUP INC  (CIK 0000102909)"]}},
                {"_source": {"form": "SC 13D", "file_date": "2026-05-01",
                             "display_names": ["FAKECO  (FAKE)  (CIK 0000320193)",
                                               "ACTIVIST LP  (CIK 0001111111)"]}},
            ]}}
    own = compute_ownership("FAKE", "320193",
                            http_fn=lambda *a, **k: _Resp(),
                            si_fn=None)
    assert own["recent_13d_13g_count"] == 2, f"P17: should enumerate 2 filings, got {own['recent_13d_13g_count']}"
    assert own["recent_13d_13g"][0]["file_date"] == "2026-05-01", "P17: must sort newest-first"
    assert own["recent_13d_13g"][0]["filer"].startswith("ACTIVIST"), "P17: filer = last display_name"
    # short interest null + explicit staleness when no source wired
    assert own["short_interest_pct"] is None, "P17: short interest must be null when unreachable"
    assert own["short_trend"] is None, "P17: short_trend null when unreachable"
    assert "STALE" in own["staleness_note"].upper() or "stale" in own["staleness_note"], (
        "P17: must label short-interest staleness explicitly")
    print(f"  P17: enumerated {own['recent_13d_13g_count']} 13D/13G newest-first, "
          f"short interest null+staleness labeled  OK")

    # ---- P17: short interest present via injected source ----
    own2 = compute_ownership("FAKE", "320193",
                             http_fn=lambda *a, **k: _Resp(),
                             si_fn=lambda t: {"short_interest_pct": 18.4, "short_trend": "rising"})
    assert own2["short_interest_pct"] == 18.4 and own2["short_trend"] == "rising", (
        "P17: injected short interest must populate")
    print("  P17: injected short interest populates  OK")

    # ---- CONTRACT SHAPE: compute_signals(ticker, cik, deepdive_derived) -> the 3 namespaces ----
    # The integration phase (deepdive_data.py) codes against exactly these top-level keys.
    for k in ("price_divergence", "ownership", "signals_meta"):
        assert k in sig, f"CONTRACT: compute_signals must emit top-level '{k}'"
    assert set(sig["price_divergence"]) >= {
        "price_return_6m", "price_return_12m", "fundamental_trajectory",
        "divergence_label", "note"}, "CONTRACT: price_divergence missing required fields"
    assert set(sig["ownership"]) >= {
        "recent_13d_13g", "short_interest_pct", "short_trend",
        "staleness_note"}, "CONTRACT: ownership missing required fields"
    print("  CONTRACT: compute_signals -> price_divergence + ownership + signals_meta  OK")

    # ---- THE FIREWALL: signals_meta flags ----
    meta = sig["signals_meta"]
    assert meta["never_affects_buy"] is True, "FIREWALL: signals_meta.never_affects_buy must be True"
    assert meta["diagnostic_only"] is True, "FIREWALL: signals_meta.diagnostic_only must be True"
    assert isinstance(meta["sources"], list) and meta["sources"], "signals_meta.sources must be a non-empty list"
    print("  FIREWALL: diagnostic_only=True, never_affects_buy=True  OK")

    # ---- robustness: network failure on BOTH legs -> partial + signals_error, no raise ----
    def _boom(*a, **k):
        raise RuntimeError("network down")
    sig3 = compute_signals("FAKE", "320193", declining_derived,
                           price_fn=_boom, http_fn=_boom, si_fn=None)
    # price leg catches internally -> block present with price_error; ownership http guarded -> empty
    assert "signals_meta" in sig3, "robustness: signals_meta must always be present"
    assert sig3["price_divergence"]["divergence_label"] == "unclear", (
        "robustness: price fetch failure -> unclear, not a crash")
    assert sig3["ownership"]["recent_13d_13g"] == [], "robustness: ownership failure -> empty list, not crash"
    print("  robustness: network failure -> partial result, no raise  OK")

    print("signals selftest PASS (P16 divergence labels + P17 ownership/short + firewall flags + robustness)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="signals — between-filings DIAGNOSTIC side-channel (P16/P17). "
                    "Library module; CLI supports --selftest only.")
    ap.add_argument("--selftest", action="store_true", help="Run selftest and exit")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    else:
        ap.error("signals.py is a library module; use --selftest to verify P16/P17 + the firewall.")
