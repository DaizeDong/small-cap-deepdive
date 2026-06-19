"""
discover_events.py — Event-driven candidate discovery (Phase 5)

Two discovery modes, each structurally high-precision (form-type enumeration replaces
keyword over-recall; no theme-fit gate is needed):

  --spinoffs
      Enumerate recent Form 10-12B / 10-12B/A filings from EDGAR EFTS.
      These are spinoff / carve-out registrations.  Forced index-fund selling
      is the mis-pricing catalyst: passive holders of the parent must sell the
      spun-off child if it is not eligible for their index mandate.

  --insider-clusters
      Enumerate recent cluster open-market insider buys from openinsider.com
      /latest-cluster-buys.  Multiple insiders buying at market price within a
      short window is the strongest management-conviction signal available without
      reading every Form 4.

Output: reports/smallcap/candidates_event_<mode>_<date>.json
Records are shaped identically to candidates_<slug>.json so they flow directly
into: cheap_pass (kill-flags) -> deepdive_data -> deepdive-fanout.

No theme-fit gate: form-type enumeration is structurally precise.  A Form 10-12B
is definitionally a spinoff registration; a cluster-buy table row is definitionally
an open-market purchase cluster.  Keyword over-recall (the problem that makes the
two-stage precision gate mandatory for theme discovery) does not apply here.

Design: reference/event-driven.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

# Import shared spine: UA, REPORTS, http_get, today, slug, CFG
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UA, REPORTS, http_get, today, slug as _slug, CFG

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EFTS = "https://efts.sec.gov/LATEST/search-index"
OPENINSIDER_CLUSTER = "http://openinsider.com/latest-cluster-buys"

# Match "Company Name  (TICK)  (CIK 0001234567)"
_NAME_TICK_CIK = re.compile(r"^(.*?)\s*\(([A-Za-z0-9.\-]+)\)\s*\(CIK\s*(\d+)\)")
# Match "Company Name  (CIK 0001234567)" — no ticker yet
_NAME_CIK = re.compile(r"^(.*?)\s*\(CIK\s+(\d+)\)")


def _parse_display_name(dn: str) -> tuple[str, str, str]:
    """Return (name, ticker, cik) from an EDGAR display_names entry.

    EDGAR display_names have two forms:
      'Company Inc.  (TICK)  (CIK 0001234567)'   — ticker assigned
      'Company Inc.  (CIK 0001234567)'            — no ticker yet
    """
    m = _NAME_TICK_CIK.match(dn)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).lstrip("0") or "0"
    m2 = _NAME_CIK.match(dn)
    if m2:
        return m2.group(1).strip(), "", m2.group(2).lstrip("0") or "0"
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


def _band(mktcap: float | None) -> str | None:
    max_mcap = CFG.get("market_cap_max", 2_000_000_000)
    watch_max = CFG.get("watch_band_max", 5_000_000_000)
    if mktcap is None or mktcap <= 0:
        return None
    if mktcap < max_mcap:
        return "deep"
    if mktcap < watch_max:
        return "watch"
    return None


# ---------------------------------------------------------------------------
# Mode 1 — Spinoffs via Form 10-12B
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
    now = datetime.now(timezone.utc)
    if enddt is None:
        enddt = now.strftime("%Y-%m-%d")
    if startdt is None:
        startdt = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    url = f"{EFTS}?forms=10-12B&dateRange=custom&startdt={startdt}&enddt={enddt}"
    try:
        r = http_get(url, timeout=30)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"  [error] EDGAR EFTS 10-12B: {e}", file=sys.stderr)
        return []

    hits = d.get("hits", {}).get("hits", [])
    total = d.get("hits", {}).get("total", {}).get("value", 0)
    print(f"  [spinoffs] EDGAR returned {total} hits ({len(hits)} in page)", file=sys.stderr)

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
            name, ticker, cik = _parse_display_name(dn)
            if not cik:
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
            "catalyst": catalyst,
            "event_type": "spinoff",
            "file_date": item["file_date"],
            "form": item["form"],
            "sic": item["sic"],
            "mktcap": mktcap,
            "band": b,
        })

    return candidates


# ---------------------------------------------------------------------------
# Mode 2 — Insider cluster buys via openinsider
# ---------------------------------------------------------------------------

class _ClusterTableParser(HTMLParser):
    """Reusable HTML table parser (same pattern as deepdive_data.insider_trades).

    Collects <td>/<th> text per <tr>, building a flat list of rows.
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_cell = False
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cur_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._in_cell = False
            self._cur_row.append("".join(self._cur_cell).strip())
        elif tag == "tr" and self._cur_row:
            self.rows.append(self._cur_row)
            self._cur_row = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cur_cell.append(data)


def _parse_dollar(s: str) -> float:
    """Parse openinsider Value cell like '+$1,234,567' to float."""
    cleaned = re.sub(r"[^0-9.]", "", s)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _parse_int(s: str) -> int:
    """Parse quantity like '+125,360' to int."""
    cleaned = re.sub(r"[^0-9]", "", s)
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0


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

    The header row is detected dynamically to guard against layout changes;
    hardcoded fallback indices are used if no header is found.

    Returns a list of candidate dicts, one per company.
    """
    try:
        r = http_get(OPENINSIDER_CLUSTER, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  [error] openinsider cluster-buys fetch: {e}", file=sys.stderr)
        return []

    parser = _ClusterTableParser()
    parser.feed(html)

    # --- Detect column indices from header row ---
    # Header row has Ticker, Company Name, Ins, Trade Type, Value
    _FB_FILING = 1
    _FB_TRADE = 2
    _FB_TICKER = 3
    _FB_NAME = 4
    _FB_INS = 6
    _FB_TYPE = 7
    _FB_VALUE = 12

    filing_col = _FB_FILING
    trade_col = _FB_TRADE
    ticker_col = _FB_TICKER
    name_col = _FB_NAME
    ins_col = _FB_INS
    type_col = _FB_TYPE
    value_col = _FB_VALUE
    header_found = False

    for row in parser.rows:
        if len(row) < 10:
            continue
        row_low = [c.lower().replace("\xa0", " ").strip() for c in row]
        # Identify header row by presence of "ticker" and "value"
        if "ticker" in row_low and "value" in row_low:
            for i, cell in enumerate(row_low):
                if cell == "filing date" or cell == "filing\xa0date":
                    filing_col = i
                elif cell == "trade date" or cell == "trade\xa0date":
                    trade_col = i
                elif cell == "ticker":
                    ticker_col = i
                elif cell in ("company name", "company\xa0name"):
                    name_col = i
                elif cell == "ins":
                    ins_col = i
                elif cell in ("trade type", "trade\xa0type"):
                    type_col = i
                elif cell == "value":
                    value_col = i
            header_found = True
            break

    if not header_found:
        import logging
        logging.warning(
            "openinsider cluster-buys: header not found; using hardcoded column indices. "
            "Table layout may have changed."
        )

    # --- Parse data rows ---
    # Dedup by ticker: keep most recent filing date row per company
    by_ticker: dict[str, dict] = {}
    max_col = max(filing_col, trade_col, ticker_col, name_col, ins_col, type_col, value_col)

    for row in parser.rows:
        if len(row) <= max_col:
            continue
        trade_type = row[type_col].strip()
        # Must be open-market Purchase
        code_m = re.match(r"^([A-Z])", trade_type)
        if not code_m or code_m.group(1) != "P":
            continue
        ticker = row[ticker_col].strip()
        name = row[name_col].strip()
        if not ticker or not name:
            continue
        try:
            n_insiders = int(row[ins_col].strip())
        except (ValueError, IndexError):
            n_insiders = 0
        if n_insiders < min_insiders:
            continue
        value = _parse_dollar(row[value_col])
        filing_date = row[filing_col].strip()[:10]  # keep YYYY-MM-DD only
        trade_date = row[trade_col].strip()[:10]

        existing = by_ticker.get(ticker)
        if existing is None or filing_date > existing["filing_date"]:
            by_ticker[ticker] = {
                "ticker": ticker, "name": name,
                "n_insiders": n_insiders,
                "value": value,
                "filing_date": filing_date,
                "trade_date": trade_date,
            }

    print(
        f"  [insider-clusters] parsed {len(parser.rows)} HTML rows → "
        f"{len(by_ticker)} unique companies (min_insiders={min_insiders})",
        file=sys.stderr,
    )

    # --- Build candidate records ---
    candidates: list[dict] = []
    for item in sorted(by_ticker.values(), key=lambda x: x["filing_date"], reverse=True):
        ticker = item["ticker"]
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
            "cik": "",  # not provided by openinsider; resolved downstream by deepdive_data
            "name": item["name"],
            "theme": "event:insider_cluster",
            "theme_slug": "event_insider_cluster",
            "catalyst": catalyst,
            "event_type": "insider_cluster",
            "n_insiders": item["n_insiders"],
            "value_usd": item["value"],
            "filing_date": item["filing_date"],
            "trade_date": item["trade_date"],
            "mktcap": mktcap,
            "band": b,
        })

    return candidates


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _write(candidates: list[dict], mode: str) -> Path:
    date = today()
    out = REPORTS / f"candidates_event_{mode}_{date}.json"
    out.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
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
             "(default 2). Page already filters to cluster events.",
    )
    ap.add_argument(
        "--no-mktcap",
        action="store_true",
        help="Skip yfinance market-cap enrichment (faster; band will be null).",
    )
    args = ap.parse_args()

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
            f"  [warn] zero candidates returned — check network / source availability.",
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
    print(f"  2. Data pull:        python tools/deepdive_data.py --candidates {out}")
    print(f"  3. Rank:             python tools/rank.py --slug {mode}")
    print("  (No theme-fit gate: form-type enumeration replaces keyword precision gate.)")


if __name__ == "__main__":
    main()
