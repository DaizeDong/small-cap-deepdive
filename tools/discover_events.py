"""
discover_events.py — Event-driven candidate discovery (Phase 5)

Two discovery modes retrieve event leads for independent verification:

  --spinoffs
      Enumerate recent Form 10-12B / 10-12B/A filings from EDGAR EFTS.
      These registrations can identify spinoff or carve-out candidates, but the form
      alone does not establish a separation event. A forced-selling thesis also
      requires evidence about the distribution and applicable index mandates.

  --insider-clusters
      Enumerate recent cluster open-market insider buys from openinsider.com
      /latest-cluster-buys. The feed supplies candidate purchase clusters for
      subsequent source and transaction verification.

Output: _common.reports_dir()/candidates_event_<mode>_<date>.json in the configured
versioned PRIVATE companion. The resolver includes SMALLCAP_RUN when set and
fails if private initialization is missing.
Records are shaped identically to candidates_<slug>.json so they flow directly
into: cheap_pass (kill-flags) -> deepdive_data -> deepdive-fanout.

Event discovery does not use the keyword theme-fit gate. Form types and cluster-feed
rows are discovery hints, not proof of the event thesis. Independent T1 event
verification remains mandatory before treating a candidate as a confirmed spinoff
or a verified open-market purchase cluster.

Design: reference/event-driven.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import shared spine: UA, REPORTS, http_get, today, slug, CFG
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UA, REPORTS, http_get, today, slug as _slug, CFG
from _event_insider import parse_cluster_page
from _deepdive_concepts import _get_sec_tickers
from filter_by_sic import (StageRows, stage_work, rows_completion,
                           parse_fts_page, write_stage_receipt, prepare_stage_output)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EFTS = "https://efts.sec.gov/LATEST/search-index"
OPENINSIDER_CLUSTER = "http://openinsider.com/latest-cluster-buys"

# Match "Company Name  (TICK)  (CIK 0001234567)"
_NAME_TICK_CIK = re.compile(r"^(.*?)\s*\(([A-Za-z0-9.\-]+)\)\s*\(CIK\s*(\d+)\)")
# Match "Company Name  (CIK 0001234567)", no ticker yet
_NAME_CIK = re.compile(r"^(.*?)\s*\(CIK\s+(\d+)\)")


def _parse_display_name(dn: str, source: dict | None = None) -> tuple[str, str, str]:
    """Return (name, ticker, cik) from an EDGAR display_names entry.

    EDGAR display_names have two forms:
      'Company Inc.  (TICK)  (CIK 0001234567)'   — ticker assigned
      'Company Inc.  (CIK 0001234567)'            — no ticker yet

    MINOR: when both regexes miss (e.g. malformed string), fall back to
    _source.ciks[0] (stripped of leading zeros) before dropping the record.
    """
    m = _NAME_TICK_CIK.match(dn)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).lstrip("0") or "0"
    m2 = _NAME_CIK.match(dn)
    if m2:
        return m2.group(1).strip(), "", m2.group(2).lstrip("0") or "0"
    # Fallback: try _source.ciks if the caller passed the raw EFTS _source dict
    if source:
        ciks = source.get("ciks", [])
        if ciks:
            fallback_cik = str(ciks[0]).lstrip("0") or "0"
            return dn.strip(), "", fallback_cik
    return dn.strip(), "", ""


# ---------------------------------------------------------------------------
# Market-cap enrichment (optional; band tagging)
# ---------------------------------------------------------------------------

def _yf_mktcap(ticker: str) -> float | None:
    """Fetch market cap from yfinance.  Returns None on any error."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("marketCap") or None
    except Exception:
        return None


def _band(mktcap: float | None) -> str:
    """Return band tag for a market cap value.

    C3 — four explicit bands (no None ambiguity):
      "deep"    = mktcap < market_cap_max     → full deep-dive
      "watch"   = market_cap_max..watch_band_max → surface separately, no deep-dive
      "large"   = > watch_band_max            → out of scope, no deep-dive
      "unknown" = mktcap unavailable / pre-listing → process (likely spinoff)

    Previously the function returned None for both mktcap=None AND >watch_band_max,
    conflating "pre-listing / no data" with "too large".  This caused pre-listing
    spinoffs (the highest-catalyst cohort) to be silently skipped downstream.
    """
    max_mcap = CFG.get("market_cap_max", 2_000_000_000)
    watch_max = CFG.get("watch_band_max", 5_000_000_000)
    if mktcap is None or mktcap <= 0:
        return "unknown"
    if mktcap < max_mcap:
        return "deep"
    if mktcap < watch_max:
        return "watch"
    return "large"


# ---------------------------------------------------------------------------
# Mode 1, Spinoffs via Form 10-12B
# ---------------------------------------------------------------------------

def discover_spinoffs(
    days: int = 365,
    startdt: str | None = None,
    enddt: str | None = None,
    enrich_mktcap: bool = True,
) -> list[dict]:
    """Enumerate Form 10-12B / 10-12B/A filings from EDGAR EFTS.

    Returns a list of candidate dicts, one per unique CIK, sorted newest first.

    Args:
        days: look-back window in days (default 365; overridden if startdt/enddt given).
        startdt: ISO date string override for window start.
        enddt: ISO date string override for window end (default today).
        enrich_mktcap: if True, call yfinance for each ticker to set band.

    Parsing notes (empirically verified):
    - EFTS returns all fields including display_names, ciks, sics, file_date, form.
    - display_names have two variants: with ticker "(TICK)  (CIK N)" and without "(CIK N)".
    - Both 10-12B and 10-12B/A are returned when forms=10-12B.
    - Deduplication by CIK: keep earliest-filed record per company (original filing);
      for ticker, prefer the variant that has one (amendments often add the ticker).
    """
    if days < 1:
        raise ValueError("days must be positive")
    now = datetime.now(timezone.utc)
    if enddt is None:
        enddt = now.strftime("%Y-%m-%d")
    if startdt is None:
        startdt = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    if datetime.strptime(startdt, "%Y-%m-%d") > datetime.strptime(enddt, "%Y-%m-%d"):
        raise ValueError("startdt must not exceed enddt")

    url = f"{EFTS}?forms=10-12B&dateRange=custom&startdt={startdt}&enddt={enddt}"
    try:
        r = http_get(url, timeout=30)
        r.raise_for_status()
        d = r.json()
        hits, total, relation = parse_fts_page(d)
    except Exception as e:
        print(f"  [error] EDGAR EFTS 10-12B: {e}", file=sys.stderr)
        return StageRows(stage="event_spinoffs", work=[stage_work(
            "sec_fts_10_12b", f"{startdt}:{enddt}", 0, "unavailable", "request_or_schema_failed")])

    work = [stage_work("sec_fts_10_12b", f"{startdt}:{enddt}", 0)]
    if total > len(hits) or relation != "eq":
        work.append(stage_work("sec_fts_10_12b", f"{startdt}:{enddt}", 1,
                               "unavailable", "unfetched_pages"))
    print(f"  [spinoffs] EDGAR returned {total} hits ({len(hits)} in page)", file=sys.stderr)
    # MINOR: warn if EFTS response was truncated (more hits than returned)
    if total > len(hits):
        print(
            f"  [warn] truncated: {len(hits)} of {total} hits returned; "
            f"widen pagination or narrow date range to capture all filings.",
            file=sys.stderr,
        )

    # Deduplicate by CIK: prefer the record that has a ticker, else keep earliest.
    # Key: cik -> dict with best info so far
    by_cik: dict[str, dict] = {}
    for h in hits:
        s = h["_source"]
        file_date = s.get("file_date", "")
        form = s.get("form", "")  # "10-12B" or "10-12B/A"
        # Use root_forms for canonical type
        root_form = (s.get("root_forms") or [form])[0]

        for dn in s.get("display_names", []):
            # MINOR: pass source dict so fallback CIK extraction works on malformed names
            name, ticker, cik = _parse_display_name(dn, source=s)
            if not cik:
                work.append(stage_work("sec_fts_10_12b", f"{startdt}:{enddt}", 0,
                                       "partial", "unparsed_identity"))
                continue
            existing = by_cik.get(cik)
            if existing is None:
                by_cik[cik] = {
                    "cik": cik, "name": name, "ticker": ticker,
                    "file_date": file_date, "form": root_form,
                    "sic": (s.get("sics") or [""])[0],
                }
            else:
                # Upgrade ticker if currently missing
                if not existing["ticker"] and ticker:
                    existing["ticker"] = ticker
                # Keep earliest file date
                if file_date < existing["file_date"]:
                    existing["file_date"] = file_date

    candidates: list[dict] = []
    items = sorted(by_cik.values(), key=lambda x: x["file_date"], reverse=True)
    for item in items:
        ticker = item["ticker"]
        mktcap = None
        if enrich_mktcap and ticker:
            mktcap = _yf_mktcap(ticker)
            time.sleep(0.25)
        b = _band(mktcap)
        catalyst = f"spinoff: Form 10-12B filed {item['file_date']}"
        candidates.append({
            "ticker": ticker or "",
            "cik": item["cik"],
            "name": item["name"],
            "theme": "event:spinoff",
            "theme_slug": "event_spinoff",
            "horizon": None,          # D2: event-mode, no keyword-horizon concept applies
            "catalyst": catalyst,
            "event_type": "spinoff",
            "file_date": item["file_date"],
            "form": item["form"],
            "sic": item["sic"],
            "mktcap": mktcap,
            "band": b,
        })

    if enrich_mktcap:
        work.extend(stage_work("market_data", c["cik"], status="unavailable",
                               reason="missing_market_cap") for c in candidates if c["mktcap"] is None)
    return StageRows(candidates, stage="event_spinoffs", work=work)


# ---------------------------------------------------------------------------
# Mode 2, Insider cluster buys via openinsider
# ---------------------------------------------------------------------------

def discover_insider_clusters(
    min_insiders: int = 2,
    enrich_mktcap: bool = True,
) -> list[dict]:
    """Enumerate cluster open-market insider buys from openinsider /latest-cluster-buys.

    The page already filters to cluster buys (multiple insiders buying same company).
    We parse the HTML table, filter to open-market Purchase (type 'P') rows, and
    require Ins >= min_insiders (default 2).

    Column layout (empirically verified, 17 cols):
      0:X  1:Filing Date  2:Trade Date  3:Ticker  4:Company Name  5:Industry
      6:Ins  7:Trade Type  8:Price  9:Qty  10:Owned  11:%Own  12:Value
      13:1d  14:1w  15:1m  16:6m

    A recognized header is required; unknown layouts remain unavailable.

    Returns a list of candidate dicts, one per company.
    """
    if min_insiders < 1:
        raise ValueError("min_insiders must be positive")
    try:
        r = http_get(OPENINSIDER_CLUSTER, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  [error] openinsider cluster-buys fetch: {e}", file=sys.stderr)
        return StageRows(stage="event_insider_clusters", work=[stage_work(
            "openinsider_cluster", status="unavailable", reason="request_failed")])

    parsed = parse_cluster_page(html, observed_date=today(),
                                response_url=getattr(r, "url", None), min_insiders=min_insiders)
    work = [stage_work("openinsider_cluster", "latest_cluster_buys", 0,
                       status=parsed["status"],
                       reason=parsed["reasons"][0] if parsed["reasons"] else "")]
    work.extend(stage_work("openinsider_cluster", status="partial", reason=reason)
                for reason in parsed["reasons"][1:])
    by_ticker = {item["ticker"]: item for item in parsed["records"]}
    # Bind issuer identity before the candidate artifact and its admission evidence
    # are frozen. Failed mapping work remains upstream evidence, even on usable rows.
    tickers = _get_sec_tickers() if by_ticker else {}
    upstream = [rows_completion(tickers, "sec_tickers")] if by_ticker else []

    # --- Build candidate records ---
    candidates: list[dict] = []
    for item in sorted(by_ticker.values(), key=lambda x: x["filing_date"], reverse=True):
        ticker = item["ticker"]
        cik = tickers.get(ticker.upper(), {}).get("cik", "")
        work.append(stage_work("sec_ticker_identity", ticker,
                               status="complete" if cik else "unavailable",
                               reason="" if cik else "unresolved_event_identity"))
        mktcap = None
        if enrich_mktcap:
            mktcap = _yf_mktcap(ticker)
            time.sleep(0.25)
        b = _band(mktcap)
        catalyst = (
            f"cluster insider buy: {item['n_insiders']} insiders, "
            f"${item['value']:,.0f}, trade date {item['trade_date']}"
        )
        candidates.append({
            "ticker": ticker,
            "cik": cik,
            "name": item["name"],
            "theme": "event:insider_cluster",
            "theme_slug": "event_insider_cluster",
            "horizon": None,          # D2: event-mode, no keyword-horizon concept applies
            "catalyst": catalyst,
            "event_type": "insider_cluster",
            "n_insiders": item["n_insiders"],
            "value_usd": item["value"],
            "filing_date": item["filing_date"],
            "trade_date": item["trade_date"],
            "mktcap": mktcap,
            "band": b,
        })

    if enrich_mktcap:
        work.extend(stage_work("market_data", c["ticker"], status="unavailable",
                               reason="missing_market_cap") for c in candidates if c["mktcap"] is None)
    result = StageRows(candidates, stage="event_insider_clusters", work=work, upstream=upstream)
    result.completion["request"] = {"scope": "returned_latest_cluster_buys_page", "min_insiders": min_insiders}
    result.completion["page_evidence"] = parsed["proof"]
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _write(candidates: list[dict], mode: str) -> Path:
    date = today()
    out = prepare_stage_output(REPORTS / f"candidates_event_{mode}_{date}.json")
    out.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_stage_receipt(out, rows_completion(candidates))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "discover_events.py — Event-driven small-cap candidate discovery (Phase 5).\n"
            "\n"
            "Enumerates candidates by SEC form type (structurally high-precision;\n"
            "no theme-fit gate needed) and writes a candidates_event_<mode>_<date>.json\n"
            "file shaped identically to candidates_<slug>.json from theme discovery,\n"
            "so it flows directly into: cheap_pass -> deepdive_data -> deepdive-fanout.\n"
            "\n"
            "See reference/event-driven.md for rationale, caveats, and how to interpret output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_grp = ap.add_mutually_exclusive_group(required=True)
    mode_grp.add_argument(
        "--spinoffs",
        action="store_true",
        help=(
            "Enumerate recent Form 10-12B / 10-12B/A registrations (spinoff/carve-out).\n"
            "Catalyst: forced index-fund selling of the spun-off entity."
        ),
    )
    mode_grp.add_argument(
        "--insider-clusters",
        action="store_true",
        help=(
            "Enumerate recent cluster open-market insider buys from openinsider.\n"
            "Catalyst: multiple insiders buying at market price = management conviction signal."
        ),
    )
    ap.add_argument(
        "--days",
        type=int,
        default=365,
        help="Look-back window in days for spinoffs mode (default 365). "
             "Use --startdt/--enddt for exact dates.",
    )
    ap.add_argument(
        "--startdt",
        default=None,
        help="Spinoffs: EFTS start date override (YYYY-MM-DD). "
             "Overrides --days if provided.",
    )
    ap.add_argument(
        "--enddt",
        default=None,
        help="Spinoffs: EFTS end date override (YYYY-MM-DD). Default today.",
    )
    ap.add_argument(
        "--min-insiders",
        type=int,
        default=2,
        help="Insider-clusters: minimum number of distinct insiders buying "
             "(default 2; rubric category (b) floor — enumerate at the rubric floor "
             "so the deep-dive/human can prefer 3+ for higher conviction). "
             "Page already filters to cluster events.",
    )
    ap.add_argument(
        "--no-mktcap",
        action="store_true",
        help="Skip yfinance market-cap enrichment (faster; band will be null).",
    )
    args = ap.parse_args()
    if args.days < 1 or args.min_insiders < 1:
        ap.error("--days and --min-insiders must be positive")
    try:
        start = datetime.strptime(args.startdt, "%Y-%m-%d") if args.startdt else None
        end = datetime.strptime(args.enddt, "%Y-%m-%d") if args.enddt else datetime.now(timezone.utc).replace(tzinfo=None)
        if start is not None and start > end:
            raise ValueError("startdt must not exceed enddt")
    except ValueError as exc:
        ap.error(f"invalid date window: {exc}")

    enrich = not args.no_mktcap

    if args.spinoffs:
        print("[discover_events] Mode: spinoffs (Form 10-12B)", file=sys.stderr)
        candidates = discover_spinoffs(
            days=args.days,
            startdt=args.startdt,
            enddt=args.enddt,
            enrich_mktcap=enrich,
        )
        mode = "spinoffs"
    else:  # --insider-clusters
        print("[discover_events] Mode: insider-clusters (openinsider)", file=sys.stderr)
        candidates = discover_insider_clusters(
            min_insiders=args.min_insiders,
            enrich_mktcap=enrich,
        )
        mode = "insider_clusters"

    if not candidates:
        print(
            f"  Zero candidates; stage status: {rows_completion(candidates)['status']}.",
            file=sys.stderr,
        )
    else:
        print(f"  Found {len(candidates)} candidates.", file=sys.stderr)

    out = _write(candidates, mode)

    # --- Summary print (first 5) ---
    print(f"\n=== Event Discovery: {mode} ===")
    print(f"Total candidates: {len(candidates)}")
    print(f"Output: {out}")
    print()
    if args.spinoffs:
        print(f"{'Ticker':10} {'CIK':12} {'Date':12} {'Band':6}  Name")
        print("-" * 80)
        for c in candidates[:5]:
            mc = (f"${c['mktcap']/1e6:.0f}M" if c.get("mktcap") else "—")
            print(
                f"{c['ticker'] or '(no ticker)':10} "
                f"{c['cik']:12} "
                f"{c['file_date']:12} "
                f"{str(c.get('band') or '—'):6}  "
                f"{c['name'][:40]}"
            )
            print(f"  catalyst: {c['catalyst']}")
    else:
        print(f"{'Ticker':8} {'#Ins':4} {'Value':14} {'Date':12} {'Band':6}  Name")
        print("-" * 80)
        for c in candidates[:5]:
            print(
                f"{c['ticker']:8} "
                f"{c['n_insiders']:4} "
                f"${c['value_usd']:>12,.0f} "
                f"{c['filing_date']:12} "
                f"{str(c.get('band') or '—'):6}  "
                f"{c['name'][:35]}"
            )
            print(f"  catalyst: {c['catalyst']}")

    print()
    print("Next steps (SKILL.md 'events' entry mode):")
    print(f"  1. Kill-flag scan:   python tools/cheap_pass.py --universe {out}")
    print(f"  2. Data pull:        python tools/deepdive_data.py --candidates {out.parent / 'candidates_event_admitted.json'}")
    print(f"  3. Rank:             python tools/rank.py --slug {mode}")
    print("  (No theme-fit gate: form-type enumeration replaces keyword precision gate.)")
    status = rows_completion(candidates)["status"]
    print(f"Stage status: {status}")
    return 0 if status == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
