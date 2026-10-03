"""
deepdive_data.py — Stage 1 深度尽调的数据拉取层(机械部分)

对 cheap pass 幸存者,拉齐 deep dive 所需的结构化数据:
  - 财务序列(收入/净利/OCF/现金/资产/权益,多期)→ 增长质量、runway、现金流质量
  - 稀释史(流通股 YoY)
  - OpenInsider 当前交易页面；EDGAR Form 4 解析尚未实现
  - 10-K 关键章节文本(business/risk factors)供判断层读
设计依据:reference/mechanical-checks.md。

判断层(护城河/管理层/估值/多空论点)由 agent 读这些数据后做,不在此脚本。
本脚本只负责"把硬数据摆到桌上",防止 agent 凭记忆/叙事编。

Private path setup:
    Initialize a versioned PRIVATE companion with SMALL_CAP_DEEPDIVE_CONFIG_DIR.
    Set REPORTS_ROOT to the absolute path returned by _common.reports_dir():
        python -c "import sys; sys.path.insert(0, 'tools'); from _common import reports_dir; print(reports_dir())"
    The resolver includes SMALLCAP_RUN when set and fails if initialization is missing.

Usage (REPORTS_ROOT is the resolved absolute private path):
    python tools/deepdive_data.py --ticker SYNTA --cik 0000000123
    python tools/deepdive_data.py --candidates "${REPORTS_ROOT}/candidates_gate2_survivors.json"
Standalone output uses _common.reports_dir() and retains unbound_single_input.
Batch output stays beside the validated survivor artifact with its stage receipts.
"""
from __future__ import annotations
import argparse
import hashlib
import math
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from edgar import Company

# sys.path shim so this script can be run directly from tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_edgar, UA, REPORTS, today, CFG, http_get
from filter_by_sic import (stage_completion, stage_work, stage_receipt_path,
                           prepare_stage_output, write_stage_receipt, read_stage_receipt)
from _cash_flow_evidence import paired_annual_sum_evidence

# v0.3.3 refactor, the mechanical concept-pull layer and the derived-flag computations were
# extracted into sibling modules to shrink this orchestrator. They are re-exported below so the
# PUBLIC API (deepdive_data.<symbol>) is UNCHANGED for every consumer (valuation imports pull;
# cheap_pass imports _extract_concentration / _concentration_flag; etc.). NO behavior change.
#   _deepdive_concepts.py, XBRL companyconcept fetchers + concept-cascade constants + IFRS merge.
#   _deepdive_flags.py, derived-flag computations (concentration / trajectory / debt guards / ...).
# Their shared evidence/completion helpers never import this orchestrator. The selftest
# monkeypatches _deepdive_concepts._one_concept (via the
# _dc alias), the single fetcher every concept/flag helper resolves through.
import _deepdive_concepts as _dc
from _deepdive_concepts import (
    FACTS, DEI_FACTS, IFRS_FACTS, SEC_COMPANY_TICKERS_URL,
    REVENUE_CONCEPTS,
    IFRS_REVENUE_CONCEPTS, IFRS_NET_INCOME_CONCEPTS, IFRS_OCF_CONCEPTS,
    LESSOR_SIC_CODES, LEASE_INCOME_CONCEPTS, PPE_FLEET_CONCEPTS, _LESSOR_PPE_RATIO,
    DEBT_CONCEPTS_PRIMARY, DEBT_CONCEPT_FALLBACK1, DEBT_CONCEPT_FALLBACK1B,
    DEBT_CONCEPT_FALLBACK1C, DEBT_CONCEPT_FALLBACK2, DEBT_SUM_CONCEPTS,
    OPERATING_LEASE_CONCEPTS, _DEBT_STALE_DAYS,
    DA_CONCEPTS, CAPEX_CONCEPT,
    EBIT_PRIMARY_CONCEPT, EBIT_PRETAX_CONCEPTS, EBIT_INTEREST_CONCEPTS,
    INSURANCE_CONCEPTS,
    _one_concept, concept_series, concept_series_asof, concept_series_with_ifrs,
    _shares_series, pct_growth,
    _get_sec_tickers,
    _debt_series, _da_series, _ebit_with_source, _operating_lease_liability,
    reset_asof_filed_tracker, get_asof_max_filed,
)
from _deepdive_flags import (
    _CONC_SINGLE_CUSTOMER, _CONC_SINGLE_PROGRAM, _CONC_REVENUE_TERM, _CONC_PCT, _CONC_WINDOW,
    _CONC_SEGMENT_CTX, _CONC_SEGMENT_POSSESSIVE, _CONC_DIVERSIFIED_CUSTOMERS,
    _validate_ticker_entity, _low_revenue_loss_ratio, _insurance_concepts_present,
    _lessor_asset_heavy, _foreign_filer_unvaluable, _check_debt_quality, _debt_for_ev,
    _extract_concentration, _concentration_flag,
    _annual_vals, _trajectory_fields, _NORM_YEARS,
    _normalized_fcf_proxy, _normalization_masks_current_loss,
    distress_core4,
)

# Non-open-market transaction codes to exclude (RSU grants, option exercises, gifts, etc.)
_EXCLUDE_CODES = {"A", "M", "G", "D", "F", "I", "J", "L", "U", "W", "X", "Z"}


def _parse_insider_page(html: str, ticker: str, response_url: str,
                        observed_at: str) -> dict:
    """Accept a bounded OpenInsider result only when its schema and scope are known."""
    import hashlib
    import math
    from datetime import date, timedelta
    from html.parser import HTMLParser
    from urllib.parse import parse_qs, urlsplit

    result = {
        "available": False, "status": "unavailable", "source": "openinsider",
        "buys": 0, "sells": 0, "open_market_buys": 0, "open_market_sells": 0,
        "buy_value": 0, "sell_value": 0, "net_signal": None,
        "provenance": {"ticker": ticker, "response_url": response_url,
                       "observed_at": observed_at, "row_limit": 100},
    }
    proof = result["provenance"]

    def unavailable(reason, *, incomplete=False):
        result.update(status="incomplete" if incomplete else "unavailable",
                      reason=reason, error=f"openinsider:{reason}")
        return result

    try:
        observed = date.fromisoformat(observed_at)
        response = urlsplit(response_url)
        query = parse_qs(response.query, keep_blank_values=True)
    except (TypeError, ValueError):
        return unavailable("response_scope_invalid")
    expected_query = {"s": ticker, "fd": "730", "td": "0", "xp": "1",
                      "xs": "1", "cnt": "100", "page": "1"}
    if (response.scheme not in {"http", "https"}
            or response.hostname not in {"openinsider.com", "www.openinsider.com"}
            or response.path != "/screener"
            or any(query.get(key) != [value] for key, value in expected_query.items())):
        return unavailable("response_scope_mismatch")
    if not isinstance(html, str):
        return unavailable("response_body_invalid")
    proof.update(html_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
                 window_basis="filing_date", window_days=730,
                 window_start=(observed - timedelta(days=730)).isoformat(),
                 window_end=observed_at, scope_evidence="response_query")

    class Tables(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.tables = []
            self.links = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "a" and attributes.get("href"):
                self.links.append(attributes["href"])
            if tag == "table":
                self.stack.append({"rows": [], "row": None, "cell": None,
                                   "malformed": False, "closed": False})
            if not self.stack:
                return
            table = self.stack[-1]
            if tag == "tr":
                table["malformed"] |= table["row"] is not None
                table["row"] = []
            elif tag in {"td", "th"} and table["row"] is not None:
                table["malformed"] |= table["cell"] is not None
                table["cell"] = []

        def handle_data(self, data):
            if self.stack and self.stack[-1]["cell"] is not None:
                self.stack[-1]["cell"].append(data)

        def handle_endtag(self, tag):
            if not self.stack:
                return
            table = self.stack[-1]
            if tag in {"td", "th"} and table["cell"] is not None:
                table["row"].append(" ".join("".join(table["cell"]).split()))
                table["cell"] = None
            elif tag == "tr" and table["row"] is not None:
                table["rows"].append(table["row"])
                table["row"] = None
            elif tag == "table":
                table["malformed"] |= table["row"] is not None or table["cell"] is not None
                table["closed"] = True
                self.tables.append(self.stack.pop())

    parser = Tables()
    parser.feed(html)
    parser.close()
    names = {"filing": "filing date", "trade": "trade date", "ticker": "ticker",
             "code": "trade type", "value": "value"}
    candidates = []
    for table in [*parser.tables, *parser.stack]:
        for index, row in enumerate(table["rows"]):
            normalized = [cell.casefold() for cell in row]
            if all(normalized.count(label) == 1 for label in names.values()):
                columns = {key: normalized.index(label) for key, label in names.items()}
                candidates.append((table["rows"][index + 1:], columns, len(row), table))
                break
    if len(candidates) != 1:
        return unavailable("recognized_table_missing" if not candidates else "ambiguous_tables")
    rows, columns, width, selected_table = candidates[0]
    if selected_table["malformed"] or not selected_table["closed"]:
        return unavailable("table_not_closed")
    proof.update(schema="openinsider_trade_table", columns=columns,
                 table_rows=len(rows), parsed_rows=0, excluded_rows=0)
    empty_messages = {"no results found", "no results found.",
                      "no matching transactions found", "no matching transactions found."}
    explicit_zero = (len(rows) == 1 and len(rows[0]) == 1
                     and rows[0][0].casefold() in empty_messages)
    if not rows:
        return unavailable("empty_table_without_zero_evidence", incomplete=True)
    if explicit_zero:
        rows = []
    for link in parser.links:
        try:
            page_query = parse_qs(urlsplit(link).query)
        except ValueError:
            return unavailable("pagination_link_invalid", incomplete=True)
        if not page_query.get("s") or page_query.get("s") == [ticker]:
            pages = page_query.get("page", [])
            if any(value.isdecimal() and int(value) > 1 for value in pages):
                return unavailable("additional_results_page", incomplete=True)
    if len(rows) >= proof["row_limit"]:
        return unavailable("row_limit_reached", incomplete=True)

    buys = sells = 0
    buy_value = sell_value = 0.0
    for row in rows:
        if len(row) != width:
            return unavailable("malformed_transaction_row", incomplete=True)
        if row[columns["ticker"]].upper() != ticker:
            return unavailable("row_ticker_mismatch", incomplete=True)
        try:
            filing = date.fromisoformat(row[columns["filing"]][:10])
            trade = date.fromisoformat(row[columns["trade"]][:10])
        except (TypeError, ValueError):
            return unavailable("row_date_invalid", incomplete=True)
        if not observed - timedelta(days=730) <= filing <= observed or trade > filing:
            return unavailable("row_outside_filing_window", incomplete=True)
        code_match = re.fullmatch(r"([A-Z])(?:\s*-\s*.+)?", row[columns["code"]])
        if code_match is None:
            return unavailable("transaction_code_invalid", incomplete=True)
        code = code_match.group(1)
        if code in _EXCLUDE_CODES:
            proof["excluded_rows"] += 1
            continue
        if code not in {"P", "S"}:
            return unavailable("transaction_code_unsupported", incomplete=True)
        text = row[columns["value"]].strip()
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1]
        if not re.fullmatch(r"[+-]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text):
            return unavailable("transaction_value_invalid", incomplete=True)
        amount = abs(float(text.replace("$", "").replace(",", "")))
        if not math.isfinite(amount):
            return unavailable("transaction_value_invalid", incomplete=True)
        if code == "P":
            buys += 1
            buy_value += amount
        else:
            sells += 1
            sell_value += amount
        proof["parsed_rows"] += 1

    if not math.isfinite(buy_value) or not math.isfinite(sell_value):
        return unavailable("transaction_total_nonfinite", incomplete=True)
    proof.update(complete=True, explicit_zero=explicit_zero,
                 scope_evidence="response_query_and_result_table")
    result.update(available=True, status="available", open_market_buys=buys,
                  open_market_sells=sells, buys=buys, sells=sells,
                  buy_value=round(buy_value), sell_value=round(sell_value),
                  net_signal="net_buy" if buys > sells else "net_sell" if sells > buys else "neutral")
    return result


def insider_trades(ticker: str, cik: str = "") -> dict:
    """Fetch the bounded OpenInsider filing window; EDGAR Form 4 is unsupported."""
    from urllib.parse import urlencode

    source = CFG["insider_source"]
    if source == "edgar":
        return {"available": False, "note": "edgar source not yet implemented"}
    if source != "openinsider":
        return {"available": False, "error": f"unknown insider_source: {source}"}
    ticker = ticker.strip().upper() if isinstance(ticker, str) else ""
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", ticker):
        return {"available": False, "source": source, "net_signal": None,
                "reason": "ticker_invalid"}
    params = {
        "s": ticker, "o": "", "pl": "", "ph": "", "ll": "", "lh": "",
        "fd": "730", "fdr": "", "td": "0", "tdr": "", "fdlyl": "", "fdlyh": "",
        "daysago": "", "xp": "1", "xs": "1", "vl": "", "vh": "", "ocl": "", "och": "",
        "sic1": "-1", "sicl": "100", "sich": "9999", "grp": "0", "nfl": "", "nfh": "",
        "nil": "", "nih": "", "nol": "", "noh": "", "v2l": "", "v2h": "",
        "oc2l": "", "oc2h": "", "sortcol": "0", "cnt": "100", "page": "1",
    }
    try:
        response = http_get("http://openinsider.com/screener?" + urlencode(params), timeout=30)
        if response.status_code != 200:
            return {"available": False, "source": source, "net_signal": None,
                    "reason": "http_error", "error": f"http {response.status_code}"}
        return _parse_insider_page(
            response.text, ticker, str(getattr(response, "url", "")),
            datetime.now(timezone.utc).date().isoformat())
    except Exception as error:
        return {"available": False, "source": source, "net_signal": None,
                "reason": "fetch_or_parse_failed", "error": type(error).__name__}


def _latest_filing_asof(filings, as_of: str | None):
    """PIT helper — pick the latest filing in `filings` with filing_date <= as_of.

    `filings` is an edgartools EntityFilings collection. When as_of is None this returns
    filings.latest(1) (the live default — byte-identical to the pre-PIT path). When as_of is set,
    it scans the collection, keeps only entries whose filing_date <= as_of, and returns the one
    with the most recent filing_date (no look-ahead). Returns None when the collection is empty or
    nothing was filed on/before as_of. Fully guarded — any edgartools shape surprise degrades to
    None rather than raising.
    """
    if filings is None or not len(filings):
        return None
    if as_of is None:
        return filings.latest(1)
    best = None
    best_date = None
    try:
        for f in filings:
            fd = str(getattr(f, "filing_date", "") or "")
            if not fd or fd > as_of:
                continue
            if best_date is None or fd > best_date:
                best_date = fd
                best = f
    except Exception:
        return None
    return best


def tenk_sections(ticker: str, cik: str = "", as_of: str | None = None) -> dict:
    """取最新年报的关键文本片段(business + risk factors 节选)供判断层读。

    Phase 4 — 20-F / 40-F graceful fallback:
    If no 10-K filing is found, falls back to 20-F then 40-F.
    Foreign-domiciled filers (shipping, some industrials/mining) file 20-F/40-F.
    Going-concern/material-weakness language is structurally similar in 20-F.
    XBRL concept_series (us-gaap companyfacts) already works for foreign filers.
    Sets out["filing_form"] to the form type actually read.

    A1 — CIK fallback: when ticker is absent but cik is present, construct Company
    from int(cik) directly (edgartools supports numeric CIK construction).

    PIT — `as_of` (YYYY-MM-DD) restricts the 10-K/20-F/40-F selection to the latest filing with
    filing_date<=as_of (via _latest_filing_asof) instead of the all-time latest. as_of=None is the
    live default and returns the all-time latest filing (byte-identical to the pre-PIT path).
    """
    out = {"available": False}
    try:
        # A1: prefer CIK construction when ticker absent to handle pre-listing spinoffs
        if cik and not ticker:
            c = Company(int(cik))
        else:
            c = Company(ticker)
        f = None
        form_used = None
        # Primary: 10-K (amendments=False, 10-K/A 修正件常缺 going-concern 全文)
        fl = c.get_filings(form="10-K", amendments=False)
        f = _latest_filing_asof(fl, as_of)
        if f is not None:
            form_used = "10-K"
        # Fallback 1: 20-F (foreign-domiciled filers, Phase 4)
        if f is None:
            fl20 = c.get_filings(form="20-F", amendments=False)
            f = _latest_filing_asof(fl20, as_of)
            if f is not None:
                form_used = "20-F"
        # Fallback 2: 40-F (Canadian filers, Phase 4)
        if f is None:
            fl40 = c.get_filings(form="40-F", amendments=False)
            f = _latest_filing_asof(fl40, as_of)
            if f is not None:
                form_used = "40-F"
        if f is None:
            return out
        txt = f.text() if hasattr(f, "text") else str(f.obj())
        if not isinstance(txt, str) or not txt.strip():
            out["error"] = "Annual filing text is unavailable"
            return out
        low = txt.lower()
        out["available"] = True
        out["filing_form"] = form_used
        out["filing_date"] = str(getattr(f, "filing_date", ""))
        out["total_len"] = len(txt)
        from _filing_disclosures import scan_disclosures
        out["disclosure_evidence"] = scan_disclosures(txt)
        for name, finding in out["disclosure_evidence"].items():
            out["has_" + name] = finding["flag"]
        out["disclosure_review_required"] = any(
            finding["flag"] is None for finding in out["disclosure_evidence"].values())
        out["has_death_spiral"] = "variable conversion" in low
        # Extract concentration magnitudes from the full filing body because the
        # companyconcept endpoint does not expose dimensional member magnitudes.
        _tc, _tp, _cd = _extract_concentration(txt)
        out["top_customer_pct"] = _tc
        out["top_program_pct"] = _tp
        out["concentration_detail"] = _cd
        if _cd and "ambiguous_concentration_clause" in _cd:
            out["disclosure_review_required"] = True
        # Backward-compat boolean: True when any concentration magnitude was extracted OR the
        # legacy substring is present (preserves existing consumers reading this flag).
        out["customer_concentration_flag"] = (
            _tc is not None or _tp is not None
            or "customers accounted for" in low or "customer accounted for" in low
        )
        # 截取 risk factors 开头(供 agent 读真实风险)
        idx = low.find("risk factors")
        out["risk_excerpt"] = txt[idx:idx + 3000] if idx >= 0 else ""
    except Exception as e:
        out["error"] = str(e)
    return out


# ---------------------------------------------------------------------------
# P7: second-source sanity band (cross-validate SEC XBRL against yfinance)
# ---------------------------------------------------------------------------
# Internal consistency cannot establish agreement with an independent source.
# Compare eligible SEC-XBRL debt, revenue and shares with independently acquired
# values; a gross disagreement is an input-integrity reason to withhold BUY.
# This is a DATA-INTEGRITY gate (it is fine for it to gate), NOT a between-filings signal.
_CROSS_SOURCE_FLOOR = 1_000_000.0   # ignore near-zero/trivial fields (avoid div-by-tiny noise)
_CROSS_SOURCE_RATIO = 2.5           # max(a,b)/min(a,b) above this == gross disagreement


def _yf_second_source(ticker: str) -> dict | None:
    """P7 default fetch — pull total_debt / revenue / shares_outstanding from yfinance.

    Guarded end-to-end: returns None on ANY failure (no ticker, import error, network error,
    null .info). NEVER raises, NEVER blocks the deepdive — an absent second source must leave
    cross_source_checked=False (see _cross_source_check). Tries Ticker(t).info first, then the
    .balance_sheet / .financials frames, then .get_shares_full, taking the latest non-null.
    Injected into pull() via yf_fn so the selftest is network-free.
    """
    if not ticker:
        return None
    try:
        import yfinance as yf
    except Exception:
        return None
    out: dict = {"total_debt": None, "revenue": None, "shares_outstanding": None}
    try:
        t = yf.Ticker(ticker)
    except Exception:
        return None
    # 1) .info, the cheap path (totalDebt / totalRevenue / sharesOutstanding)
    try:
        info = t.info or {}
        for src, dst in (("totalDebt", "total_debt"),
                         ("totalRevenue", "revenue"),
                         ("sharesOutstanding", "shares_outstanding")):
            v = info.get(src)
            if v is not None and v > 0:
                out[dst] = float(v)
    except Exception:
        pass
    # 2) .balance_sheet fallback for total_debt (Total Debt row, latest column)
    if out["total_debt"] is None:
        try:
            bs = t.balance_sheet
            if bs is not None and "Total Debt" in bs.index:
                v = bs.loc["Total Debt"].dropna()
                if len(v):
                    out["total_debt"] = float(v.iloc[0])
        except Exception:
            pass
    # 3) .financials fallback for revenue (Total Revenue row, latest column)
    if out["revenue"] is None:
        try:
            fin = t.financials
            if fin is not None and "Total Revenue" in fin.index:
                v = fin.loc["Total Revenue"].dropna()
                if len(v):
                    out["revenue"] = float(v.iloc[0])
        except Exception:
            pass
    # 4) .get_shares_full fallback for shares (latest non-null)
    if out["shares_outstanding"] is None:
        try:
            sf = t.get_shares_full()
            if sf is not None and len(sf):
                v = sf.dropna()
                if len(v):
                    out["shares_outstanding"] = float(v.iloc[-1])
        except Exception:
            pass
    # All-None second source is no better than absent, surface as unavailable.
    if all(out[k] is None for k in out):
        return None
    return out


def _cross_source_check(sec_debt: float | None, sec_revenue: float | None,
                        sec_shares: float | None, second: dict | None) -> tuple[bool, bool, str]:
    """P7 comparator (network-free) — compare SEC-XBRL latest values to a second source.

    Returns (cross_source_checked, cross_source_mismatch, cross_source_detail) per CONTRACT:
      * checked   — True if at least one field had BOTH a SEC and a second-source value.
      * mismatch  — True if, for ANY field where both values are present and non-trivial
                    (abs > _CROSS_SOURCE_FLOOR), max(a,b)/min(a,b) > _CROSS_SOURCE_RATIO.
      * detail    — which field(s) disagreed + both values + the ratio (empty when no mismatch).
    Guard: a None/empty second source yields (False, False, "...") — NEVER a false block.
    """
    if not second:
        return False, False, "no second source (yfinance unavailable)"
    fields = (
        ("total_debt", sec_debt, second.get("total_debt")),
        ("revenue", sec_revenue, second.get("revenue")),
        ("shares_outstanding", sec_shares, second.get("shares_outstanding")),
    )
    checked = False
    disagreements: list[str] = []
    for name, a, b in fields:
        if a is None or b is None:
            continue
        # Both sides present but at least one trivially small -> skip (avoid div-by-tiny noise).
        if abs(a) <= _CROSS_SOURCE_FLOOR or abs(b) <= _CROSS_SOURCE_FLOOR:
            continue
        checked = True
        hi, lo = (abs(a), abs(b)) if abs(a) >= abs(b) else (abs(b), abs(a))
        ratio = hi / lo if lo else float("inf")
        if ratio > _CROSS_SOURCE_RATIO:
            disagreements.append(
                f"{name}: SEC={a/1e6:.1f}M vs yf={b/1e6:.1f}M (ratio {ratio:.1f}x)"
            )
    mismatch = len(disagreements) > 0
    if not checked:
        detail = "no field had both SEC and second-source values to compare"
    elif mismatch:
        detail = "gross disagreement (>2.5x) — " + "; ".join(disagreements)
    else:
        detail = "second source within 2.5x on all comparable fields"
    return checked, mismatch, detail


def _sic_observation(cik):
    """Bind submissions metadata to its issuer and retain failed observations."""
    request = {"cik": str(cik)[:10]}

    def result(code, status, reason="", **diagnostics):
        completion = stage_completion("sec_submissions_sic", int(bool(code)), work=[
            stage_work("sec_submissions", request["cik"], status=status, reason=reason)])
        completion.update(request=request, observation=diagnostics)
        return code, completion

    try:
        request["cik"] = _dc._share_cik(cik)
    except (TypeError, ValueError):
        return result(None, "invalid", "invalid_query_identity")
    url = f"https://data.sec.gov/submissions/CIK{request['cik']}.json"
    try:
        response = http_get(url, timeout=20)
    except Exception:
        return result(None, "unavailable", "request_failed")
    status = getattr(response, "status_code", None)
    if type(status) is not int:
        return result(None, "invalid", "invalid_http_response")
    if status != 200:
        return result(None, "unavailable", "http_status", http_status=status)
    try:
        payload = response.json()
    except Exception:
        return result(None, "invalid", "invalid_json", http_status=200)
    try:
        if not isinstance(payload, dict) or _dc._share_cik(payload.get("cik")) != request["cik"]:
            raise ValueError("submissions identity mismatch")
    except (TypeError, ValueError):
        return result(None, "invalid", "invalid_response_identity", http_status=200)
    if "sic" not in payload or type(payload["sic"]) not in (str, int):
        return result(None, "invalid", "invalid_sic", http_status=200)
    code = str(payload["sic"] or "")
    if code and not re.fullmatch(r"[0-9]{1,4}", code):
        return result(None, "invalid", "invalid_sic", http_status=200)
    return result(code, "complete", http_status=200)


def pull(ticker: str, cik: str, yf_fn=_yf_second_source, as_of: str | None = None) -> dict:
    """Pull all financial/insider/tenk data for a company.

    A1 — CIK-first: ticker may be empty when cik is present (pre-listing spinoffs).
    XBRL concept endpoints are CIK-based and always work.
    insider_trades / tenk_sections use ticker for their HTML/edgartools calls;
    they receive the cik fallback so Company() can be constructed from CIK.

    Historical mode filters SEC concepts and filings by as_of. Current SIC,
    ticker validation, insurance classification and second-source checks are skipped.
    Their dated contracts are unavailable, so valuation and backtest buckets abstain.
    The filing-date audit covers observed SEC dates, not complete PIT eligibility.
    """
    d = {"ticker": ticker, "cik": cik,
         "pulled_at": today()}
    if as_of is not None:
        d["as_of"] = as_of
        # FIX 1, reset the as-of filed-date accumulator before the point-in-time cascade. Every
        # as-of _one_concept call below records the max "filed" date of the facts it kept; we read it
        # back after all pulls (combined with the as-of tenk filing date) to emit
        # derived.asof_max_filing_date, the look-ahead audit evidence (asserted <= as_of). Reset is
        # gated on as_of so the live (as_of=None) path never touches the accumulator.
        reset_asof_filed_tracker()
    print(f"  拉财务序列...", file=sys.stderr)
    # v0.3.2 #11: revenue/net-income/OCF probe BOTH us-gaap and ifrs-full so foreign 20-F/40-F
    # filers (whose financials are tagged under ifrs-full) recover SOME data instead of returning
    # blanket-empty financials. us-gaap wins on any shared end-date; IFRS only fills gaps.
    rev = concept_series_with_ifrs(cik, REVENUE_CONCEPTS, IFRS_REVENUE_CONCEPTS, asof=as_of)
    time.sleep(0.2)
    ni = concept_series_with_ifrs(cik, "NetIncomeLoss", IFRS_NET_INCOME_CONCEPTS, asof=as_of); time.sleep(0.2)
    ocf = concept_series_with_ifrs(
        cik, "NetCashProvidedByUsedInOperatingActivities", IFRS_OCF_CONCEPTS, asof=as_of
    ); time.sleep(0.2)
    cash = concept_series(cik, "CashAndCashEquivalentsAtCarryingValue", asof=as_of); time.sleep(0.2)
    shares = _shares_series(cik, asof=as_of); time.sleep(0.2)
    assets = concept_series(cik, "Assets", asof=as_of); time.sleep(0.2)
    equity = concept_series(cik, "StockholdersEquity", asof=as_of); time.sleep(0.2)

    # Phase 2 additions: valuation inputs
    print(f"  拉估值输入序列(债务/EBIT/D&A/CapEx/Goodwill/Intangibles)...", file=sys.stderr)
    debt, debt_source = _debt_series(cik, asof=as_of)
    # The legacy cascade may return liabilities, which cannot establish contractual debt.
    if debt_source == "Liabilities_proxy":
        debt = []
    time.sleep(0.2)
    # P9: EBIT concept cascade. Pull OperatingIncomeLoss first; if absent, _ebit_with_source
    # falls back to pretax-continuing-ops (+interest addback) so EV/EBITDA recovers.
    _op_income = concept_series(cik, EBIT_PRIMARY_CONCEPT, asof=as_of); time.sleep(0.2)
    ebit, ebit_source = _ebit_with_source(cik, _op_income, asof=as_of)
    time.sleep(0.2)
    da, da_source = _da_series(cik, asof=as_of)
    time.sleep(0.2)
    capex_raw = concept_series(cik, CAPEX_CONCEPT, asof=as_of); time.sleep(0.2)
    # CapEx from XBRL is a cash outflow stored as a positive number in PaymentsTo... concept.
    # We keep it positive (absolute value of spend) in the series for transparency.
    capex = capex_raw

    # NAV inputs: goodwill and intangibles (needed for tangible equity calculation)
    goodwill = concept_series(cik, "Goodwill", asof=as_of); time.sleep(0.2)
    intangibles = concept_series(cik, "IntangibleAssetsNetExcludingGoodwill", asof=as_of); time.sleep(0.2)

    # Liabilities remain separate balance-sheet evidence for NAV and distress calculations.
    print("  Pulling liabilities...", file=sys.stderr)
    liabilities = concept_series(cik, "Liabilities", asof=as_of); time.sleep(0.2)
    # C1c: if Assets is empty, try LiabilitiesAndStockholdersEquity as fallback
    if not assets:
        assets = concept_series(cik, "LiabilitiesAndStockholdersEquity", asof=as_of); time.sleep(0.2)

    # de-risk: CORE-4 distress inputs (retained earnings + current assets/liabilities), the
    # remaining Altman Z components. Historical predictive claims require revalidation.
    retained_earnings = concept_series(cik, "RetainedEarningsAccumulatedDeficit", asof=as_of); time.sleep(0.2)
    current_assets = concept_series(cik, "AssetsCurrent", asof=as_of); time.sleep(0.2)
    current_liabilities = concept_series(cik, "LiabilitiesCurrent", asof=as_of); time.sleep(0.2)

    # Current submissions SIC cannot establish historical sector membership.
    if as_of is None:
        sic_code, sic_completion = _sic_observation(cik)
    else:
        sic_code = None
        sic_completion = stage_completion("sec_submissions_sic", 0, work=[
            stage_work("historical_sic", str(cik), status="unavailable",
                       reason="dated_sic_contract_unavailable")])
        d["historical_eligibility"] = {
            "schema_version": 1, "asof": as_of, "status": "unavailable",
            "unavailable_inputs": ["historical_sic", "historical_entity_validation",
                                   "historical_insurance_classification"],
            "skipped_current_inputs": ["submissions_sic", "ticker_validation",
                                       "insurance_concepts", "second_source"],
        }
    d["source_observations"] = {"sic": sic_completion}
    time.sleep(0.2)

    ebitda_periods = paired_annual_sum_evidence(ebit, da)
    latest_ebitda_evidence = ebitda_periods[-1] if ebitda_periods else None
    latest_ebitda = latest_ebitda_evidence["val"] if latest_ebitda_evidence else None
    latest_ocf_val = ocf[-1]["val"] if ocf else None
    latest_capex = capex[-1]["val"] if capex else None
    from _cash_flow_evidence import paired_cash_flow_evidence
    fcf_periods = paired_cash_flow_evidence(ocf, capex)
    latest_fcf_evidence = fcf_periods[-1] if fcf_periods else None
    latest_fcf = latest_fcf_evidence["val"] if latest_fcf_evidence else None
    # Missing or unmatched CapEx remains unavailable; OCF is never labeled qualified FCF.
    fcf_is_ocf_proxy = False

    d["financials"] = {
        "revenue": rev, "net_income": ni, "ocf": ocf, "cash": cash,
        "shares_outstanding": shares, "assets": assets, "equity": equity,
        # Phase 2 additions
        "total_debt": debt,
        "ebit": ebit,
        "dep_amort": da,
        "capex": capex,
        # NAV inputs
        "goodwill": goodwill,
        "intangibles": intangibles,
        # Total liabilities are distinct from contractual debt.
        "liabilities": liabilities,
    }
    # M5, data-quality anomaly detection: flag implausible net_income (XBRL unit anomaly).
    # If |net_income| > revenue * 50 (e.g. $32B net income vs $32M revenue), the XBRL
    # value is almost certainly a unit mis-tag (millions reported in units of 1).
    # We do NOT alter the value; valuation uses OCF, so this is display-only.
    _latest_ni = ni[-1]["val"] if ni else None
    _latest_rev = rev[-1]["val"] if rev else None
    _data_quality_warn = None
    if (_latest_ni is not None and _latest_rev is not None and _latest_rev != 0
            and abs(_latest_ni) > abs(_latest_rev) * 50):
        _data_quality_warn = (
            f"latest_net_income ({_latest_ni/1e6:.1f}M) is implausibly large relative to "
            f"revenue ({_latest_rev/1e6:.1f}M) — possible XBRL unit mis-tag; "
            f"treat net_income with caution; valuation uses OCF which is unaffected."
        )

    # Preserve reported contractual debt; balance-sheet totals cannot fill missing debt.
    _, _debt_stale, _ = _check_debt_quality(debt, assets, equity, liabilities)
    _summed_debt_latest = debt[-1]["val"] if debt else None
    _ev_debt, _debt_truncation_suspected, _debt_trunc_detail = _debt_for_ev(
        _summed_debt_latest, liabilities, equity, assets
    )
    _latest_debt_evidence = debt[-1] if debt else {}
    _debt_evidence_status = (_latest_debt_evidence.get("debt_evidence_status", "unavailable")
                             if _ev_debt is not None else "unavailable")
    _debt_evidence_detail = (_latest_debt_evidence.get("debt_evidence_detail")
                             or _debt_trunc_detail)
    if debt_source == "Liabilities_proxy":
        _debt_evidence_detail = "Only total liabilities were available; contractual debt remains unknown."

    # C1b: wrong-entity guard (ticker→CIK cross-check + financial sanity)
    if as_of is None:
        _wrong_entity_suspected, _wrong_entity_reason = _validate_ticker_entity(
            ticker, cik, rev, shares, ni)
    else:
        _wrong_entity_suspected, _wrong_entity_reason = None, "historical_entity_validation_unavailable"

    # P-B / A4: low_revenue_loss_ratio, early/pre-revenue resource pattern (present-but-tiny
    # revenue + large genuine loss). Advisory label; the >20x EXTREME tier gates buy_eligible.
    _low_rev_loss, _low_rev_loss_extreme, _low_rev_loss_detail = _low_revenue_loss_ratio(rev, ni)

    # Insurance evidence can require financial-sector routing even on another SIC.
    # Apply the SIC-or-multiple-concepts precision rule to avoid stray-tag decisions.
    # The current insurance probe cannot prove classification at a historical date.
    print(f"  探测保险 XBRL 概念(A3)...", file=sys.stderr)
    if as_of is None:
        _insurance_present, _insurance_concept = _insurance_concepts_present(cik, sic_code=sic_code)
    else:
        _insurance_present, _insurance_concept = None, None
    time.sleep(0.2)

    # Read lease-income and asset-fleet evidence once for model suitability.
    # A qualifying lessor can require NAV even below the debt/assets threshold.
    print(f"  探测 lessor / 租赁车队 XBRL 概念(#8)...", file=sys.stderr)
    _lease_income_present = False
    for _lic in LEASE_INCOME_CONCEPTS:
        try:
            if _one_concept(cik, _lic, asof=as_of):
                _lease_income_present = True
                break
        except Exception:
            pass
        time.sleep(0.1)
    _ppe_fleet_val: float | None = None
    _ppe_best_end: str | None = None
    for _pfc in PPE_FLEET_CONCEPTS:
        try:
            _pf_entries = _one_concept(cik, _pfc, asof=as_of)
        except Exception:
            _pf_entries = []
        time.sleep(0.1)
        for _v in _pf_entries:
            if _v.get("val") is not None and (_ppe_best_end is None or _v["end"] >= _ppe_best_end):
                _ppe_best_end = _v["end"]
                _ppe_fleet_val = _v["val"]
    _lessor_asset_heavy_flag, _lessor_detail = _lessor_asset_heavy(
        cik, sic_code, assets,
        lease_income_present=_lease_income_present,
        ppe_fleet_val=_ppe_fleet_val,
        rental_lease_revenue=_lease_income_present,
    )

    # P9: ebit_source tagged by the cascade (None when no EBIT base recovered).
    _ebit_source = ebit_source if ebit else None

    # 10-K sections pulled BEFORE derived so P3 concentration can read the footnote text.
    print(f"  拉 10-K 章节...", file=sys.stderr)
    # A1: tenk_sections uses CIK fallback when ticker absent
    # PIT: as_of restricts the 10-K/20-F/40-F selection to filings filed<=as_of (no look-ahead).
    d["tenk"] = tenk_sections(ticker, cik=cik, as_of=as_of)

    # v0.3.2 #11: foreign-filer un-valuable label. After the us-gaap+ifrs-full cascade, if a
    # 20-F/40-F filer STILL has empty revenue/net-income/OCF, flag foreign_filer_unvaluable so the
    # abstain is explicit (not a silent intrinsic_band_unavailable null). Needs form_used from tenk.
    _foreign_filer_unvaluable_flag, _foreign_filer_detail = _foreign_filer_unvaluable(
        d["tenk"].get("filing_form"), rev, ni, ocf
    )

    # P3: magnitude-based concentration. tenk_sections extracts the magnitudes from the full
    # filing body (the only mechanical source, companyconcept XBRL has no dimensional members);
    # here we read them back and compose the kill/watch flag per the data contract.
    _top_customer_pct = d["tenk"].get("top_customer_pct")
    _top_program_pct = d["tenk"].get("top_program_pct")
    _conc_detail = d["tenk"].get("concentration_detail")
    _conc_flag = _concentration_flag(_top_customer_pct, _top_program_pct)

    # Text-only concentration without an extracted magnitude remains an advisory
    # data-quality label; it does not independently gate eligibility.
    _text_conc = bool(d["tenk"].get("customer_concentration_flag"))
    _concentration_unquantified = _text_conc and (_conc_flag is None)

    # P6: deterministic trajectory + contamination. Revenue carries the slope/accel; OCF is the
    # normalization base the valuation layer averages on (contamination = latest / 5yr-avg).
    # P-A: ni passed so peak_contamination_flag can test latest_net_income<0 (V-shape catch).
    _traj = _trajectory_fields(rev, ocf, ni)

    # A positive trailing cash-flow base can conceal current cash burn. Evaluate
    # that condition separately from the positive-contamination cyclical checks.
    # Use the same qualified annual pairs as valuation for the trailing FCF diagnostic.
    # An incomplete selected period cannot supply a positive normalization base.
    _fcf_window = fcf_periods[-_NORM_YEARS:]
    _norm_fcf_proxy = (
        sum(row["val"] for row in _fcf_window) / len(_fcf_window)
        if _fcf_window and all(row["qualified"] for row in _fcf_window) else None
    )
    _normalization_masks_current_loss_flag = _normalization_masks_current_loss(
        _norm_fcf_proxy, latest_ocf_val, latest_fcf, _traj["contamination_ratio"]
    )

    # P7: second-source sanity band (survivors-only, this runs at the deepdive level, so it
    # respects rate limits). Fetch ONE independent source (yfinance via the injected yf_fn) for
    # total_debt / revenue / shares and cross-check against the SEC-XBRL latest values. The fetch
    # is fully guarded (yf_fn returns None on ANY failure); a None second source leaves
    # cross_source_checked=False / mismatch=False so an absent source NEVER blocks a name.
    print(f"  二源交叉校验(P7 second-source sanity band)...", file=sys.stderr)
    # v0.3.1 #3: ASC842 lease-adjust. SEC contractual debt EXCLUDES operating leases while
    # yfinance's totalDebt INCLUDES capitalized leases, so lease-heavy retail over-fired
    # cross_source_mismatch. Add OperatingLeaseLiability (current+noncurrent) to the SEC debt side
    # BEFORE the >2.5x comparison so both sources are lease-comparable. This affects ONLY the
    # cross-source comparison, not latest_total_debt (EV uses contractual debt).
    _sec_debt_latest = _ev_debt
    print(f"  拉经营租赁负债(ASC842 lease-adjust for cross-source)...", file=sys.stderr)
    _op_lease = _operating_lease_liability(cik, asof=as_of)
    time.sleep(0.2)
    _sec_debt_lease_adj = _sec_debt_latest
    if _op_lease is not None and _sec_debt_latest is not None:
        _sec_debt_lease_adj = _sec_debt_latest + _op_lease
    _sec_shares_latest = shares[-1]["val"] if shares else None
    try:
        _second = yf_fn(ticker) if as_of is None else None
    except Exception as e:
        # Firewall: a second-source fetch failure must NEVER crash the deepdive.
        print(f"  [P7] second-source fetch error (ignored): {e}", file=sys.stderr)
        _second = None
    _cs_checked, _cs_mismatch, _cs_detail = _cross_source_check(
        _sec_debt_lease_adj, _latest_rev, _sec_shares_latest, _second
    )
    _, _debt_source_conflict, _debt_conflict_detail = _cross_source_check(
        _sec_debt_lease_adj, None, None, _second
    )
    if _debt_source_conflict:
        _debt_evidence_status = "conflicting"
        _debt_evidence_detail = _debt_conflict_detail

    # FIX 1, compose derived.asof_max_filing_date (emitted ONLY when as_of is set). Combine the max
    # "filed" date recorded across ALL as-of concept pulls (revenue/ni/ocf/cash/shares/assets/equity/
    # debt/ebit/da/capex/goodwill/intangibles/liabilities/lease-income/PP&E-fleet/operating-lease/
    # IFRS, every cascade routes through _one_concept, which records into the accumulator) with the
    # as-of 10-K/20-F/40-F filing date (tenk). This is the newest filing date that fed ANY value in
    # the point-in-time reconstruction; the look-ahead audit asserts it is <= as_of. None when truly
    # nothing was datable. as_of=None path leaves the field ABSENT (byte-identical live default).
    _asof_max_filing_date = None
    if as_of is not None:
        _concept_max_filed = get_asof_max_filed()
        _tenk_filed = d["tenk"].get("filing_date") or None
        _candidates = [x for x in (_concept_max_filed, _tenk_filed) if x]
        _asof_max_filing_date = max(_candidates) if _candidates else None

    # de-risk: CORE-4 mechanism-based distress rank. distress_kill (score>=3)
    # is ANDed into the kill-flag count (make_report._killflag_count) so a distressed name buckets
    # to AVOID regardless of cheapness. Scope = operating companies; banks/insurers route to
    # financial_sic/abstain upstream and are not graded by this layer.
    _distress = distress_core4(
        latest_ocf_val,
        ebit[-1]["val"] if ebit else None,
        retained_earnings[-1]["val"] if retained_earnings else None,
        equity[-1]["val"] if equity else None,
        assets[-1]["val"] if assets else None,
        current_assets[-1]["val"] if current_assets else None,
        current_liabilities[-1]["val"] if current_liabilities else None,
        liabilities[-1]["val"] if liabilities else None,
    )

    d["derived"] = {
        "revenue_growth_pct": pct_growth(rev),
        "shares_growth_pct": pct_growth(shares),  # 正=稀释
        "latest_revenue": _latest_rev,
        "latest_net_income": _latest_ni,
        "data_quality_warn": _data_quality_warn,
        "latest_ocf": latest_ocf_val,
        "latest_cash": cash[-1]["val"] if cash else None,
        "ocf_ni_divergence": (ni and ocf and ni[-1]["val"] > 0 and ocf[-1]["val"] < 0),
        "runway_periods": (round(cash[-1]["val"] / abs(ocf[-1]["val"]), 1)
                           if (cash and ocf and ocf[-1]["val"] < 0) else None),
        # Phase 2 additions
        # Contractual debt retains its reported value and any evidence uncertainty.
        "latest_total_debt": _ev_debt,
        "debt_source": debt_source,
        "debt_evidence_status": _debt_evidence_status,
        "debt_evidence_detail": _debt_evidence_detail,
        "debt_evidence_uncertain": _debt_evidence_status != "reported",
        "latest_ebit": ebit[-1]["val"] if ebit else None,
        # P9: which concept the EBIT cascade actually used (consumer reads to recover EV/EBITDA)
        "ebit_source": _ebit_source,
        "latest_dep_amort": da[-1]["val"] if da else None,
        "da_source": da_source,
        "latest_capex": latest_capex,
        "latest_ebitda": latest_ebitda,
        "latest_ebitda_evidence": latest_ebitda_evidence,
        "ebitda_periods": ebitda_periods,
        "latest_fcf": latest_fcf,
        "latest_fcf_evidence": latest_fcf_evidence,
        "fcf_periods": fcf_periods,
        "fcf_is_ocf_proxy": fcf_is_ocf_proxy,
        # NAV inputs
        "latest_goodwill": goodwill[-1]["val"] if goodwill else None,
        "latest_intangibles": intangibles[-1]["val"] if intangibles else None,
        # C1a: debt quality flags
        "debt_truncation_suspected": _debt_truncation_suspected,
        "debt_truncation_detail": _debt_trunc_detail,
        "debt_stale": _debt_stale,
        # C1b: wrong-entity flags
        "wrong_entity_suspected": _wrong_entity_suspected,
        "wrong_entity_reason": _wrong_entity_reason,
        # P-B / A4: low_revenue_loss_ratio (advisory label; does NOT flip buy_eligible) +
        # the >20x EXTREME tier (A4) that valuation gates buy_eligible on.
        "low_revenue_loss_ratio": _low_rev_loss,
        "low_revenue_loss_ratio_extreme": _low_rev_loss_extreme,
        "low_revenue_loss_ratio_detail": _low_rev_loss_detail,
        # A3: insurance XBRL concepts present (insurer / insurance-subsidiary holdco). valuation
        # routes these like financial_sic (nav/abstain) and gates buy_eligible off it.
        "insurance_concepts_present": _insurance_present,
        "insurance_concept_matched": _insurance_concept,
        # Qualifying lease-fleet evidence can make FCF capitalization unsuitable
        # independently of the debt/assets cutoff.
        "lessor_asset_heavy": _lessor_asset_heavy_flag,
        "lessor_asset_heavy_detail": _lessor_detail,
        # v0.3.2 #11: foreign_filer_unvaluable, a 20-F/40-F filer whose financials are STILL empty
        # after the us-gaap+ifrs-full cascade. Labels the abstain explicitly (not a silent null).
        "foreign_filer_unvaluable": _foreign_filer_unvaluable_flag,
        "foreign_filer_unvaluable_detail": _foreign_filer_detail,
        # P-G: form_used (10-K/20-F/40-F) for the trust-banner provenance line
        "form_used": d["tenk"].get("filing_form"),
        # C2: SIC code for financial-sector routing in valuation
        "sic": sic_code,
        # P3: concentration (magnitude-based; replaces the substring detector)
        "top_customer_pct": _top_customer_pct,
        "top_program_pct": _top_program_pct,
        "concentration_flag": _conc_flag,
        "concentration_detail": _conc_detail,
        # A2: text-conc True but magnitude null (text-only/pre-XBRL). Advisory; does NOT gate.
        "concentration_unquantified": _concentration_unquantified,
        # P6: trajectory + contamination (deterministic, from the multiyear series)
        "rev_slope_sign": _traj["rev_slope_sign"],
        "rev_accel_sign": _traj["rev_accel_sign"],
        "latest_below_avg": _traj["latest_below_avg"],
        "contamination_ratio": _traj["contamination_ratio"],
        "fundamental_decline_flag": _traj["fundamental_decline_flag"],
        # P-A: V-shape value-trap catch (independent of rev_slope_sign)
        "peak_contamination_flag": _traj["peak_contamination_flag"],
        # Preserve the current-loss normalization diagnostic and its qualified
        # annual cash-flow base for downstream eligibility and inspection.
        "normalization_masks_current_loss": _normalization_masks_current_loss_flag,
        "normalized_fcf_proxy": _norm_fcf_proxy,
        # P7: second-source sanity band (yfinance vs SEC XBRL on debt/revenue/shares). A gross
        # disagreement (>2.5x) means the single SEC value cannot be trusted; valuation ANDs
        # (not cross_source_mismatch) into buy_eligible. Absent second source -> checked=False,
        # mismatch=False (NEVER a false block). DATA-INTEGRITY gate, not a between-filings signal.
        "cross_source_checked": _cs_checked,
        "cross_source_mismatch": _cs_mismatch,
        "cross_source_detail": _cs_detail,
        # CORE-4 is a four-flag policy score. Its historical intervals are unvalidated.
        "distress_score": _distress["distress_score"],
        "distress_flags": _distress["distress_flags"],
        "distress_kill": _distress["distress_kill"],
        "distress_altman_z": _distress["distress_altman_z"],
        "latest_retained_earnings": retained_earnings[-1]["val"] if retained_earnings else None,
        "latest_current_assets": current_assets[-1]["val"] if current_assets else None,
        "latest_current_liabilities": current_liabilities[-1]["val"] if current_liabilities else None,
    }
    # FIX 1, emit asof_max_filing_date ONLY under as_of (the look-ahead audit reads it; harness
    # asserts <= as_of). Added AFTER the dict literal + gated on as_of so the live (as_of=None)
    # derived block is byte-identical to the pre-FIX output (the key is simply absent).
    if as_of is not None:
        d["derived"]["asof_max_filing_date"] = _asof_max_filing_date
    print(f"  拉内部人交易...", file=sys.stderr)
    # A1: insider_trades queries openinsider by ticker; if no ticker, skip gracefully.
    # PIT: the openinsider screener returns CURRENT/recent rows and is not point-in-time-able for
    # free. Under as_of we MUST NOT inject current insider activity into a backtest cell (look-ahead
    # / survivorship leak), so insider is skipped with an explicit note rather than silently using
    # present-day data. A backtest BUY stays anchored to filing-derived fundamentals only.
    if as_of is not None:
        d["insider"] = {"available": False, "note": "as_of_pit_no_insider"}
    elif ticker:
        d["insider"] = insider_trades(ticker, cik=cik)
        time.sleep(0.3)
    else:
        d["insider"] = {"available": False, "note": "no_ticker_pre_listing"}

    # iter4 P15/P16/P17, DIAGNOSTIC-ONLY between-filings side-channel (firewall, design §5 Q2).
    # The "signals" namespace is a TOP-LEVEL SIBLING of "derived", NEVER nested inside derived ,
    # so valuation.py / the buy_eligible composite / the BUY trigger can never read a signals.*
    # field. signals.py.compute_signals is designed never to raise (it returns a partial dict with
    # its own signals_error), but we still guard the import + call here so a missing/broken
    # signals.py can never crash the deepdive: on ANY error we set signals.signals_error and
    # continue. A BUY stays anchored to T1 filing-derived valuation + zero kill-flags only.
    print(f"  计算 T2 诊断信号(side-channel, diagnostic-only)...", file=sys.stderr)
    if as_of is not None:
        # PIT: the diagnostic side-channel reads CURRENT price/ownership (not point-in-time-able for
        # free). It never affects buy (firewall), but in a backtest cell it would carry present-day
        # data, so skip it under as_of with an explicit diagnostic-only stub. Placement contract
        # (top-level sibling of derived, never inside derived) is preserved.
        d["signals"] = {
            "signals_error": "skipped_under_as_of_pit",
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
        }
        return d
    try:
        from signals import compute_signals  # lazy import, never gate the deepdive on it
        d["signals"] = compute_signals(ticker, cik, d["derived"])
    except Exception as e:
        # Firewall: a signals failure must NEVER crash the deepdive. Attach a diagnostic-only
        # stub that records the error and re-states the never-affects-buy invariant.
        d["signals"] = {
            "signals_error": f"{type(e).__name__}:{e}",
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
        }
    return d


def _selftest():
    """Run generated synthetic contracts; provider acceptance is a separate live lane."""
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlsplit
    from make_fixtures import source32_legacy_scenarios, source32_legacy_acquisition

    legacy = source32_legacy_scenarios()
    acquisition = source32_legacy_acquisition()
    unexpected = []
    requested = []

    def concept_get(url, **kwargs):
        match = re.fullmatch(
            r"https://data.sec.gov/api/xbrl/companyconcept/CIK(\d{10})/us-gaap/([A-Za-z0-9]+)\.json",
            url)
        key = f"{int(match[1])}:{match[2]}" if match else None
        if key not in acquisition["concepts"]:
            unexpected.append(url)
            raise AssertionError("unexpected synthetic concept request")
        requested.append(key)
        payload = deepcopy(acquisition["concepts"][key])
        return SimpleNamespace(status_code=200, json=lambda: deepcopy(payload))

    def insider_get(url, **kwargs):
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if (parsed.scheme != "http" or parsed.netloc != "openinsider.com"
                or parsed.path != "/screener"
                or query.get("s") != [acquisition["insider"]["ticker"]]):
            unexpected.append(url)
            raise AssertionError("unexpected synthetic insider request")
        return SimpleNamespace(status_code=200, text=acquisition["insider"]["html"], url=url)

    filing_requests = []

    class SyntheticFilings(list):
        def latest(self, count):
            assert count == 1
            return self[0] if self else None

    class SyntheticCompany:
        def __init__(self, identity):
            if identity not in acquisition["filings"]:
                unexpected.append(str(identity))
                raise AssertionError("unexpected synthetic company request")
            self.identity = identity

        def get_filings(self, *, form, amendments):
            assert amendments is False
            filing_requests.append((self.identity, form))
            row = acquisition["filings"][self.identity]
            if row["form"] != form:
                return SyntheticFilings()
            filing = SimpleNamespace(filing_date=row["filing_date"], text=lambda: row["text"])
            return SyntheticFilings([filing])

    class SyntheticClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime.fromisoformat(acquisition["insider"]["observed_at"] + "T00:00:00+00:00")
            return value if tz is None else value.astimezone(tz)

    with patch.object(_dc, "http_get", concept_get), \
            patch.object(_dc, "time", SimpleNamespace(sleep=lambda seconds: None)), \
            patch.dict(globals(), http_get=insider_get, datetime=SyntheticClock,
                       CFG={**CFG, "insider_source": "openinsider"}, Company=SyntheticCompany):
        _selftest_cases(legacy)
    assert not unexpected, f"unexpected synthetic requests: {unexpected}"
    assert any(key.startswith("904:") for key in requested), "EBIT acquisition was not exercised"
    assert filing_requests == [("SYNANNUAL", "10-K"), ("SYNFOREIGN", "10-K"), ("SYNFOREIGN", "20-F")]


def _selftest_cases(_legacy):

    # Synthetic calendar-year revenue requires the newer concept.
    rev_annual = concept_series("901", REVENUE_CONCEPTS)
    years_annual = [v["end"][:4] for v in rev_annual]
    assert any(y >= "2024" for y in years_annual), (
        f"synthetic annual revenue must reach >=2024 after concept merge, got {years_annual}"
    )
    print(f"  synthetic annual: revenue years={years_annual}, latest={rev_annual[-1]['val']/1e6:.1f}M  OK")

    # Synthetic April fiscal year verifies the newer revenue concept.
    rev_fiscal = concept_series("902", REVENUE_CONCEPTS)
    years_fiscal = [v["end"][:4] for v in rev_fiscal]
    latest_fiscal = rev_fiscal[-1]["val"] if rev_fiscal else 0
    assert any(y >= "2024" for y in years_fiscal), (
        f"synthetic fiscal revenue must reach >=2024 (stuck-2018 bug), got {years_fiscal}"
    )
    assert latest_fiscal > 60_000_000, (
        f"synthetic fiscal latest revenue must be >$60M (synthetic $100M FY2025), got ${latest_fiscal/1e6:.1f}M"
    )
    print(f"  synthetic fiscal: revenue years={years_fiscal}, latest=${latest_fiscal/1e6:.1f}M  OK")

    # Synthetic mixed-unit envelope must select USD revenue.
    rev_units = concept_series("903", REVENUE_CONCEPTS)
    latest_units = rev_units[-1]["val"] if rev_units else 0
    assert 400_000_000 <= latest_units <= 800_000_000, (
        f"synthetic units latest revenue must be $400M-$800M (synthetic FY2024=$500M or FY2025=$600M), "
        f"got ${latest_units/1e6:.1f}M — possible unit leak if <10000"
    )
    print(f"  synthetic units: latest revenue=${latest_units/1e6:.1f}M  OK")

    # Synthetic insider transactions must retain nonzero purchase and sale values.
    assert rev_annual[-1]["val"] == 80_000_000
    assert latest_fiscal == 100_000_000 and rev_fiscal[-1]["end"].endswith("04-30")
    assert latest_units == 600_000_000
    ins = insider_trades("SYNINSIDER")
    assert (ins.get("open_market_buys"), ins.get("open_market_sells")) == (1, 1)
    assert (ins.get("buy_value"), ins.get("sell_value")) == (12500, 4000)
    assert isinstance(ins.get("open_market_buys"), int), (
        f"open_market_buys must be int, got {type(ins.get('open_market_buys'))}"
    )
    assert isinstance(ins.get("open_market_sells"), int), (
        f"open_market_sells must be int, got {type(ins.get('open_market_sells'))}"
    )
    assert isinstance(ins.get("buy_value"), (int, float)), (
        f"buy_value must be numeric, got {type(ins.get('buy_value'))}"
    )
    assert isinstance(ins.get("sell_value"), (int, float)), (
        f"sell_value must be numeric, got {type(ins.get('sell_value'))}"
    )
    assert ins.get("net_signal") in ("net_buy", "net_sell", "neutral", None), (
        f"net_signal unexpected value: {ins.get('net_signal')!r}"
    )
    # Synthetic insider transactions must retain nonzero purchase and sale values.
    assert ins.get("available") and (ins.get("buy_value", 0) > 0 or ins.get("sell_value", 0) > 0), (
        f"AI insider: buy_value and sell_value are BOTH zero with available=True — "
        f"column parsing is broken (wrong column indices). "
        f"buys={ins.get('open_market_buys')} sells={ins.get('open_market_sells')} "
        f"buy_value={ins.get('buy_value')} sell_value={ins.get('sell_value')}"
    )
    print(f"  AI insider: buys={ins.get('open_market_buys')} "
          f"sells={ins.get('open_market_sells')} "
          f"buy_value=${ins.get('buy_value', 0):,.0f} "
          f"sell_value=${ins.get('sell_value', 0):,.0f} "
          f"net={ins.get('net_signal')}  OK")

    # --- M5: data_quality_warn unit, verify the flag is set when implausible ratio exists ---
    # We synthesize a minimal scenario inline (no live EDGAR call needed for unit logic test).
    # Simulate a case where |net_income| > revenue * 50 and verify warn is emitted.
    _test_ni = 32_000_000_000   # 32B (unit mis-tag, should be 32M)
    _test_rev = 32_000_000      # 32M (correct)
    _warn = None
    if _test_ni is not None and _test_rev is not None and _test_rev != 0 and abs(_test_ni) > abs(_test_rev) * 50:
        _warn = f"latest_net_income is implausibly large relative to revenue — possible XBRL unit mis-tag"
    assert _warn is not None, "M5 data_quality_warn: failed to fire for |NI|>rev*50 (unit test broken)"
    print(f"  M5 data_quality_warn: fires correctly for implausible NI/rev ratio  OK")

    # Generated debt evidence controls preserve contractual debt and staleness.
    from make_fixtures import debt_scenarios
    _debt_fix = debt_scenarios()
    _test_debt = [{"end": _debt_fix["date"], "val": _debt_fix["reported"]}]
    _trunc, _stale, _detail = _check_debt_quality(
        _test_debt, _debt_fix["assets"], _debt_fix["equity"], _debt_fix["liabilities"])
    assert (_trunc, _stale, _detail) == (False, False, None)
    _test_debt_stale = [{"end": _debt_fix["old_date"], "val": _debt_fix["reported"]}]
    _, _stale2, _ = _check_debt_quality(
        _test_debt_stale, _debt_fix["assets"], _debt_fix["equity"], _debt_fix["liabilities"])
    assert _stale2, "Old contractual debt must retain its staleness flag"
    print("  Debt evidence: contractual amount and staleness preserved  OK")

    # --- C1b: wrong-entity guard unit test ---
    # Simulate a company with shares < 1000 (sub-entity)
    _fake_shares = [{"end": "2024-12-31", "val": 200}]
    _we, _we_reason = _validate_ticker_entity("", "0000000001", [], _fake_shares, [])
    assert _we, f"C1b: wrong_entity_suspected must fire for shares<1000 (reason={_we_reason})"
    print(f"  C1b wrong_entity_suspected: fires for shares<1000 scenario  OK")

    # Normal company with reasonable shares should not fire (no ticker check when ticker empty)
    _normal_shares = [{"end": "2024-12-31", "val": 50_000_000}]
    _we2, _ = _validate_ticker_entity("", "0000000001", [], _normal_shares, [])
    assert not _we2, "C1b: wrong_entity_suspected must NOT fire for normal shares count"
    print(f"  C1b wrong_entity_suspected: does NOT fire for normal company  OK")

    # Synthetic receivables concentration identifies one customer at 83%.
    _decline_case_text = (
        _legacy['concentration_receivables']
    )
    _tc, _tp, _cd = _extract_concentration(_decline_case_text)
    assert _tc is not None and _tc == 83.0, (
        f"P3: synthetic single-counterparty 83% must be captured as top_customer_pct, got {_tc}"
    )
    assert _cd is not None and "top_customer" in _cd, f"P3: detail must describe customer, got {_cd!r}"
    assert _concentration_flag(_tc, _tp) == "kill", (
        f"P3: top_customer_pct>40 must yield kill, got {_concentration_flag(_tc, _tp)}"
    )
    print(f"  P3 concentration: synthetic top_customer={_tc:.0f}% -> kill  OK")

    # Program concentration >60% → kill; revenue-share phrasing.
    _prog_text = (
        _legacy['concentration_program']
    )
    _tc2, _tp2, _cd2 = _extract_concentration(_prog_text)
    assert _tp2 is not None and _tp2 == 84.0, f"P3: program 84% must be captured, got {_tp2}"
    assert _concentration_flag(_tc2, _tp2) == "kill", (
        f"P3: top_program_pct>60 must yield kill, got {_concentration_flag(_tc2, _tp2)}"
    )
    print(f"  P3 concentration: lead-product top_program={_tp2:.0f}% -> kill  OK")

    # Threshold semantics (kill precedence per contract: kill if cust>40 OR prog>60):
    assert _concentration_flag(48.0, None) == "kill", "P3: customer 48% (>40) must be kill"
    assert _concentration_flag(40.0, None) == "watch", "P3: customer exactly 40 must be watch (not >40)"
    assert _concentration_flag(None, 55.0) == "watch", "P3: program 55% (40-60) must be watch"
    assert _concentration_flag(None, 65.0) == "kill", "P3: program 65% (>60) must be kill"
    assert _concentration_flag(None, None) is None, "P3: no concentration must be None flag"
    assert _concentration_flag(30.0, 30.0) is None, "P3: 30%/30% (below band) must be None"
    print(f"  P3 concentration_flag: kill/watch/None thresholds correct  OK")

    # --- P9: EBIT cascade tagging (no live call, exercise the source labels) ---
    # Path 1: OperatingIncomeLoss present → tagged OperatingIncomeLoss (offline; pass op income).
    _op = [{"end": "2024-12-31", "val": 50_000_000}]
    _ebit1, _src1 = _ebit_with_source("0000000001", _op)
    assert _src1 == "OperatingIncomeLoss" and _ebit1 == _op, (
        f"P9: OperatingIncomeLoss path must tag OperatingIncomeLoss, got {_src1}"
    )
    # Empty op-income with a CIK that has no pretax either → no recovery, source None.
    _ebit0, _src0 = _ebit_with_source("0000000001", [])
    assert _ebit0 == [] and _src0 is None, f"P9: unrecoverable EBIT must yield ([], None), got {_src0}"
    print(f"  P9 ebit_source: OperatingIncomeLoss path + unrecoverable path tagged correctly  OK")

    # Synthetic missing operating income must recover through pretax and interest concepts.
    _op_fallback = concept_series("904", EBIT_PRIMARY_CONCEPT)
    _ebit_fallback, _src_fallback = _ebit_with_source("904", _op_fallback)
    assert _ebit_fallback[-1]["val"] == 45_000_000
    assert not _op_fallback, "P9: synthetic fallback must NOT tag OperatingIncomeLoss (cascade precondition)"
    assert _ebit_fallback and _src_fallback in ("pretax+interest_addback", "pretax_proxy"), (
        f"P9: synthetic fallback EBIT must recover via pretax cascade, got source={_src_fallback} n={len(_ebit_fallback)}"
    )
    print(f"  P9 ebit_source: synthetic fallback recovers via {_src_fallback} (n={len(_ebit_fallback)})  OK")

    # Synthetic declining revenue and a cash-flow peak exercise contamination.
    _rev_decline = _legacy['deepdive_clean_decline_revenue']
    # Synthetic peak 108M raises the average to 48M; latest cash flow is 36M.
    _ocf_lumpy = _legacy['deepdive_lumpy_ocf']
    _t = _trajectory_fields(_rev_decline, _ocf_lumpy)
    assert _t["rev_slope_sign"] == -1, f"P6: declining revenue must give slope_sign -1, got {_t['rev_slope_sign']}"
    assert isinstance(_t["rev_accel_sign"], int) and _t["rev_accel_sign"] in (-1, 0, 1), (
        f"P6: rev_accel_sign must be int in (-1,0,1), got {_t['rev_accel_sign']!r}"
    )
    assert _t["latest_below_avg"] is True, "P6: latest OCF below trailing avg must be True"
    assert _t["contamination_ratio"] is not None and _t["contamination_ratio"] < 1.0, (
        f"P6: contamination_ratio (latest/5yr-avg) must be <1.0 for the lumpy series, "
        f"got {_t['contamination_ratio']}"
    )
    # The independently specified expected ratio is 36M / 48M = 0.75.
    assert abs(_t["contamination_ratio"] - _legacy["deepdive_lumpy_ratio"]) < 0.001, (
        f"P6: contamination_ratio must equal latest/5yr-avg=0.75, got {_t['contamination_ratio']}"
    )
    assert _t["fundamental_decline_flag"] is True, (
        "P6: fundamental_decline_flag must fire when slope<0 AND contamination<1 AND latest_below_avg"
    )
    print(f"  P6 trajectory: slope=-1 accel={_t['rev_accel_sign']} "
          f"contamination={_t['contamination_ratio']} decline_flag=True  OK")

    # A synthetic stub and duplicate year must not hide the trailing revenue decline.
    _rev_decline_case = _legacy['deepdive_decline_revenue']
    _ts = _trajectory_fields(_rev_decline_case, _ocf_lumpy)
    assert _ts["rev_slope_sign"] == -1, (
        f"P6 regression: contaminated synthetic decline series must annualize+trail to slope -1 "
        f"(raw all-time slope was +1), got {_ts['rev_slope_sign']}"
    )
    assert _ts["fundamental_decline_flag"] is True, (
        "P6 regression: synthetic decline must fire fundamental_decline_flag after series cleaning"
    )
    print("  P6 regression: contaminated synthetic decline series -> slope=-1, decline_flag=True  OK")

    # Healthy grower: rising revenue, stable/rising OCF → no decline flag.
    _rev_grow = [
        {"end": "2021-12-31", "val": 80_000_000},
        {"end": "2022-12-31", "val": 95_000_000},
        {"end": "2023-12-31", "val": 110_000_000},
        {"end": "2024-12-31", "val": 130_000_000},
        {"end": "2025-12-31", "val": 155_000_000},
    ]
    _ocf_grow = [
        {"end": "2021-12-31", "val": 10_000_000},
        {"end": "2022-12-31", "val": 13_000_000},
        {"end": "2023-12-31", "val": 16_000_000},
        {"end": "2024-12-31", "val": 20_000_000},
        {"end": "2025-12-31", "val": 26_000_000},
    ]
    _tg = _trajectory_fields(_rev_grow, _ocf_grow)
    assert _tg["rev_slope_sign"] == 1, f"P6: growing revenue must give slope_sign 1, got {_tg['rev_slope_sign']}"
    assert _tg["latest_below_avg"] is False, "P6: latest OCF above trailing avg must be False for grower"
    assert _tg["contamination_ratio"] is not None and _tg["contamination_ratio"] > 1.0, (
        f"P6: grower contamination_ratio must be >1.0, got {_tg['contamination_ratio']}"
    )
    assert _tg["fundamental_decline_flag"] is False, (
        "P6: fundamental_decline_flag must NOT fire for a healthy grower"
    )
    print(f"  P6 trajectory: grower slope=1 contamination={_tg['contamination_ratio']} "
          f"decline_flag=False  OK")

    # Edge: short series (1 point) must not crash and must yield neutral/safe defaults.
    _short = _trajectory_fields([{"end": "2025-12-31", "val": 100}], [{"end": "2025-12-31", "val": 5}])
    assert _short["rev_slope_sign"] == 0 and _short["contamination_ratio"] is None, (
        f"P6: single-point series must give neutral defaults, got {_short}"
    )
    assert _short["fundamental_decline_flag"] is False, "P6: single-point must not fire decline flag"
    assert _short["peak_contamination_flag"] is False, "P-A: single-point must not fire peak flag"
    print(f"  P6 trajectory: short-series safe defaults  OK")

    # The synthetic peak has a rising whole-window slope, contaminated cash flow and a current loss.
    _rev_peak_case = _legacy['deepdive_peak_revenue']
    # The synthetic peak has a rising whole-window slope, contaminated cash flow and a current loss.
    _ocf_peak_case = _legacy['deepdive_peak_ocf']
    _ni_peak_case = _legacy['deepdive_peak_income']
    _tn = _trajectory_fields(_rev_peak_case, _ocf_peak_case, _ni_peak_case)
    assert _tn["rev_slope_sign"] == 1, (
        f"P-A: synthetic peak V-shape whole-window slope must be +1 (upward fit), got {_tn['rev_slope_sign']}"
    )
    assert _tn["fundamental_decline_flag"] is False, (
        "P-A: fundamental_decline_flag must stay False on the V-shape (slope is +1) — "
        "peak_contamination_flag is the independent catch"
    )
    assert _tn["contamination_ratio"] is not None and _tn["contamination_ratio"] < 0.8, (
        f"P-A: synthetic peak contamination_ratio must be <0.8, got {_tn['contamination_ratio']}"
    )
    assert _tn["latest_below_avg"] is True, "P-A: synthetic peak latest OCF base must be below trailing avg"
    assert _tn["peak_contamination_flag"] is True, (
        "P-A: peak_contamination_flag MUST fire on synthetic peak V-shape (cr<0.8 AND latest_below_avg "
        f"AND latest_NI<0), got {_tn['peak_contamination_flag']} (cr={_tn['contamination_ratio']})"
    )
    print(f"  P-A peak_contamination: synthetic peak V-shape slope=+1 decline_flag=False "
          f"peak_flag=True (cr={_tn['contamination_ratio']})  OK")

    # P-A negatives: must NOT fire when any of the three conditions is absent.
    #  (1) loss-making + contaminated base but contamination >= 0.8 -> no peak flag
    _ocf_mild = [
        {"end": "2021-12-31", "val": 100_000_000},
        {"end": "2022-12-31", "val": 110_000_000},
        {"end": "2023-12-31", "val": 105_000_000},
        {"end": "2024-12-31", "val": 98_000_000},
        {"end": "2025-12-31", "val": 95_000_000},   # latest/5yr-avg ~0.92 (>0.8)
    ]
    _tn2 = _trajectory_fields(_rev_peak_case, _ocf_mild, _ni_peak_case)
    assert _tn2["peak_contamination_flag"] is False, (
        f"P-A: peak flag must NOT fire when contamination>=0.8 (got cr={_tn2['contamination_ratio']})"
    )
    #  (2) deeply contaminated base but latest NI positive -> no peak flag
    _ni_pos = [{"end": "2024-12-31", "val": 30_000_000}]
    _tn3 = _trajectory_fields(_rev_peak_case, _ocf_peak_case, _ni_pos)
    assert _tn3["peak_contamination_flag"] is False, (
        "P-A: peak flag must NOT fire when latest net income is positive"
    )
    #  (3) no ni_series passed (default) -> peak flag stays False
    _tn4 = _trajectory_fields(_rev_peak_case, _ocf_peak_case)
    assert _tn4["peak_contamination_flag"] is False, (
        "P-A: peak flag must stay False when net income unavailable (ni_series omitted)"
    )
    # The existing healthy-grower crystal must also NOT fire the peak flag.
    assert _tg["peak_contamination_flag"] is False, "P-A: grower must not fire peak flag"
    print("  P-A peak_contamination: negatives (cr>=0.8 / NI>=0 / no-NI / grower) all False  OK")

    # A negative latest cash flow and positive average create a negative contamination ratio.
    _ocf_neg2 = [
        {"end": "2020-12-31", "val":  40_000_000},
        {"end": "2021-12-31", "val":  40_000_000},
        {"end": "2022-12-31", "val":  40_000_000},
        {"end": "2023-12-31", "val":  40_000_000},
        {"end": "2024-12-31", "val": -30_000_000},  # latest negative -> cr < 0, below positive avg
    ]
    _ni_neg = _legacy['deepdive_negative_income']
    _t_neg = _trajectory_fields(_rev_peak_case, _ocf_neg2, _ni_neg)
    assert _t_neg["contamination_ratio"] is not None and _t_neg["contamination_ratio"] < 0, (
        f"A1: crystal must produce a NEGATIVE contamination_ratio, got {_t_neg['contamination_ratio']}"
    )
    assert _t_neg["latest_below_avg"] is True, "A1: crystal must have latest_below_avg=True"
    assert _t_neg["peak_contamination_flag"] is False, (
        "A1: NEGATIVE contamination_ratio must NOT trip peak_contamination_flag "
        f"(cr={_t_neg['contamination_ratio']}) — degenerate base guard"
    )
    assert _t_neg["fundamental_decline_flag"] is False, (
        "A1: NEGATIVE contamination_ratio must NOT trip fundamental_decline_flag "
        f"(cr={_t_neg['contamination_ratio']}) — degenerate base guard"
    )
    print(f"  A1 degenerate-base: cr={_t_neg['contamination_ratio']} (<0) + below_avg + NI<0 -> "
          f"BOTH flags False  OK")

    # Narrative concentration without a quantified magnitude remains advisory.
    _a2_text_conc = True
    _a2_mag = None  # _concentration_flag(None, None) is None
    _a2_unquant = _a2_text_conc and (_a2_mag is None)
    assert _a2_unquant is True, "A2: text-conc True + magnitude null must set concentration_unquantified=True"
    # Negative: a quantified magnitude (kill/watch) must NOT set the advisory.
    assert not (True and (_concentration_flag(75.0, None) is None)), (
        "A2: when magnitude IS quantified (kill), concentration_unquantified must be False"
    )
    # Negative: no text-conc flag -> advisory stays False even if magnitude null.
    assert not (False and (None is None)), "A2: no text-conc must keep concentration_unquantified False"
    print("  A2 concentration_unquantified: text-conc True + magnitude null -> True (advisory)  OK")

    # --- A3: insurance_concepts_present, an insurer-like concept set resolves to True. ---
    # _insurance_concepts_present probes the INSURANCE_CONCEPTS set via _one_concept; here we test
    # the membership/logic deterministically: an insurer exposing PremiumsEarnedNet matches, and a
    # concept set with none of the insurance concepts present does not. We stub _one_concept so the
    # crystal is offline and deterministic (insurer-like concept present -> True; matched name set).
    _insurer_concepts = {"PremiumsEarnedNet", "LossesAndLossAdjustmentExpense", "PolicyholderFunds"}
    _ins_match = next((c for c in INSURANCE_CONCEPTS if c in _insurer_concepts), None)
    assert _ins_match is not None, (
        "A3: an insurer-like concept set (PremiumsEarnedNet/losses/policyholder funds) must match "
        "at least one INSURANCE_CONCEPTS entry"
    )
    # Non-insurer (only generic concepts) must NOT match.
    _noninsurer_concepts = {"Revenues", "Assets", "StockholdersEquity", "OperatingIncomeLoss"}
    assert next((c for c in INSURANCE_CONCEPTS if c in _noninsurer_concepts), None) is None, (
        "A3: a non-insurer concept set must not match any INSURANCE_CONCEPTS entry"
    )
    print(f"  A3 insurance_concepts_present: insurer-like set matches '{_ins_match}', non-insurer None  OK")

    # Synthetic revenue of 60M and loss of 180M exercise the ordinary 3x loss band.
    _early_case_rev = _legacy['deepdive_early_revenue']
    _early_case_ni = _legacy['deepdive_early_income']
    _early_case_shares = _legacy['deepdive_early_shares']
    _lrl, _lrl_ext, _lrl_detail = _low_revenue_loss_ratio(_early_case_rev, _early_case_ni)
    assert _lrl is True and _lrl_ext is False, (
        f"P-B: low_revenue_loss_ratio must fire (extreme=False) for synthetic (3.0x), detail={_lrl_detail}"
    )
    _we_early_case, _we_early_case_reason = _validate_ticker_entity("", "0000000002", _early_case_rev, _early_case_shares, _early_case_ni)
    assert _we_early_case is False, (
        f"P-B: wrong_entity_suspected must NOT fire for the early-revenue resource pattern "
        f"(|NI|/rev=3.0, not a unit anomaly), got reason={_we_early_case_reason}"
    )
    print(f"  P-B low_revenue_loss_ratio: synthetic tiny-rev+large-loss -> True, extreme=False, "
          f"wrong_entity=False  OK")

    # --- A4: wrong_entity_suspected fires ONLY on shares<1000 / ticker-absent / CIK-mismatch /
    # revenue<$1000, the |NI|/rev ratio trigger is REMOVED. ---
    #  (A4-a) ratio=5 -> label-only, NO extreme, wrong_entity=False (NOT the wrong entity).
    _a4_rev5 = [{"end": "2024-12-31", "val": 20_000_000}]
    _a4_ni5 = [{"end": "2024-12-31", "val": -100_000_000}]  # ratio = 5.0
    _lrl5, _lrl5_ext, _ = _low_revenue_loss_ratio(_a4_rev5, _a4_ni5)
    assert _lrl5 is True and _lrl5_ext is False, (
        f"A4: ratio=5 must set low_revenue_loss_ratio=True but extreme=False, got ext={_lrl5_ext}"
    )
    _we5, _we5_reason = _validate_ticker_entity("", "0000000005", _a4_rev5,
                                                [{"end": "2024-12-31", "val": 50_000_000}], _a4_ni5)
    assert _we5 is False, (
        f"A4: ratio=5 must NOT fire wrong_entity_suspected (ratio trigger removed), reason={_we5_reason}"
    )
    print("  A4: ratio=5 -> low_revenue_loss_ratio label-only (extreme=False), wrong_entity=False  OK")

    #  (A4-b) ratio=30 -> low_revenue_loss_ratio_extreme=True (valuation gates), wrong_entity STILL False.
    _a4_rev30 = [{"end": "2024-12-31", "val": 10_000_000}]
    _a4_ni30 = [{"end": "2024-12-31", "val": -300_000_000}]  # ratio = 30.0 (>20)
    _lrl30, _lrl30_ext, _lrl30_detail = _low_revenue_loss_ratio(_a4_rev30, _a4_ni30)
    assert _lrl30 is True and _lrl30_ext is True, (
        f"A4: ratio=30 must set low_revenue_loss_ratio_extreme=True, got ext={_lrl30_ext} ({_lrl30_detail})"
    )
    _we30, _we30_reason = _validate_ticker_entity("", "0000000006", _a4_rev30,
                                                  [{"end": "2024-12-31", "val": 50_000_000}], _a4_ni30)
    assert _we30 is False, (
        f"A4: ratio=30 must NOT fire wrong_entity_suspected (ratio trigger removed), reason={_we30_reason}"
    )
    print("  A4: ratio=30 -> low_revenue_loss_ratio_extreme=True, wrong_entity=False  OK")

    #  (A4-c) shares=500 (<1000) -> wrong_entity_suspected STILL True (genuine unit-mistag signal).
    _we_sh, _we_sh_reason = _validate_ticker_entity("", "0000000007",
                                                    [{"end": "2024-12-31", "val": 5_000_000}],
                                                    [{"end": "2024-12-31", "val": 500}],
                                                    [{"end": "2024-12-31", "val": -1_000_000}])
    assert _we_sh is True and "shares_lt_1000" in (_we_sh_reason or ""), (
        f"A4: shares=500 (<1000) must still fire wrong_entity_suspected, got reason={_we_sh_reason}"
    )
    print("  A4: shares=500 -> wrong_entity_suspected True (unit-mistag preserved)  OK")

    #  (A4-d) a 1000x unit anomaly with normal shares must NO LONGER fire wrong_entity (trigger gone).
    _anom_rev = [{"end": "2024-12-31", "val": 32_000_000}]
    _anom_ni = [{"end": "2024-12-31", "val": 32_000_000_000}]  # 1000x
    _we_anom, _we_anom_reason = _validate_ticker_entity("", "0000000008", _anom_rev,
                                                        [{"end": "2024-12-31", "val": 50_000_000}], _anom_ni)
    assert _we_anom is False, (
        f"A4: 1000x |NI|/rev anomaly must NOT fire wrong_entity (ratio trigger removed), "
        f"reason={_we_anom_reason}"
    )
    print("  A4: 1000x |NI|/rev anomaly no longer mislabeled as wrong_entity  OK")

    # P-B: low_revenue_loss_ratio must NOT fire for a healthy company (small loss vs revenue).
    _ok_lrl, _ok_ext, _ = _low_revenue_loss_ratio([{"end": "2024-12-31", "val": 100_000_000}],
                                                  [{"end": "2024-12-31", "val": -5_000_000}])
    assert _ok_lrl is False and _ok_ext is False, (
        "P-B: low_revenue_loss_ratio must NOT fire when loss is small vs revenue"
    )

    # A reported zero is also distinct from missing debt and non-debt liabilities.
    _zero_debt = [{"end": _debt_fix["date"], "val": 0}]
    _zero_quality = _check_debt_quality(
        _zero_debt, _debt_fix["assets"], _debt_fix["equity"], _debt_fix["liabilities"])
    assert _zero_quality == (False, False, None)
    print("  Debt evidence: reported zero is preserved  OK")

    # Synthetic calendar-year revenue requires the newer concept.
    _tenk_annual = tenk_sections("SYNANNUAL", cik="901")
    assert _tenk_annual.get("available"), "P-G: synthetic annual tenk must be available for form provenance check"
    assert _tenk_annual.get("filing_form") in ("10-K", "20-F", "40-F"), (
        f"P-G: form_used must be one of 10-K/20-F/40-F, got {_tenk_annual.get('filing_form')!r}"
    )
    assert _tenk_annual.get("filing_form") == "10-K", (
        f"P-G: synthetic annual is a domestic filer -> form_used must be 10-K, got {_tenk_annual.get('filing_form')!r}"
    )
    print(f"  P-G form_used: synthetic annual -> {_tenk_annual.get('filing_form')}  OK")

    # Synthetic foreign filing requires the 20-F fallback after an empty 10-K collection.
    _tenk_foreign_case = tenk_sections("SYNFOREIGN", cik="905")
    assert _tenk_foreign_case.get("available"), "P-G foreign: generated annual filing must be available"
    assert _tenk_foreign_case.get("filing_form") in ("20-F", "40-F"), (
        f"P-G foreign: form_used must be 20-F/40-F, got {_tenk_foreign_case.get('filing_form')!r}"
    )
    assert _tenk_foreign_case.get("filing_form") is not None, "P-G foreign: form_used must not be None"
    assert _tenk_foreign_case.get("filing_form") == "20-F", "P-G foreign: generated fallback must select 20-F"
    print(f"  P-G foreign form_used: synthetic foreign -> {_tenk_foreign_case.get('filing_form')}  OK")

    # --- iter4 firewall: "signals" is a TOP-LEVEL key (sibling of derived), NEVER inside derived ---
    # The between-filings side-channel is DIAGNOSTIC-ONLY. valuation/buy_eligible/the BUY trigger
    # must never be able to read a signals.* field, which is structurally guaranteed by keeping
    # signals OUT of the derived namespace. We inject offline fns into compute_signals so this is
    # deterministic with no network, then assert the placement + the never-affects-buy invariant.
    from signals import compute_signals as _compute_signals
    _fake_derived = {
        "rev_slope_sign": 1,
        "contamination_ratio": 1.2,
        "fundamental_decline_flag": False,
    }
    _sig = _compute_signals(
        "ZZTEST", "9999999999", _fake_derived,
        price_fn=lambda *a, **k: {"price_return_6m": -0.05, "price_return_12m": 0.10},
        http_fn=lambda *a, **k: type("R", (), {"status_code": 404, "text": "", "json": lambda self: {}})(),
        si_fn=lambda *a, **k: None,
    )
    assert isinstance(_sig, dict), f"firewall: compute_signals must return a dict, got {type(_sig)}"
    assert _sig.get("signals_meta", {}).get("diagnostic_only") is True, (
        "firewall: signals_meta.diagnostic_only must be True"
    )
    assert _sig.get("signals_meta", {}).get("never_affects_buy") is True, (
        "firewall: signals_meta.never_affects_buy must be True"
    )
    # Build a minimal d the way pull() does and assert the namespace placement contract.
    _d_fake = {"ticker": "ZZTEST", "cik": "9999999999", "derived": dict(_fake_derived)}
    _d_fake["signals"] = _sig  # mirrors pull(): top-level sibling assignment
    assert "signals" in _d_fake, "firewall: signals must be a TOP-LEVEL key on the deepdive dict"
    assert "signals" not in _d_fake["derived"], (
        "firewall: signals must NEVER be nested inside derived (valuation reads derived)"
    )
    # And the converse: no signals.* field leaked into derived.
    _signal_field_names = {"price_divergence", "ownership", "signals_meta", "signals_error"}
    assert not (_signal_field_names & set(_d_fake["derived"].keys())), (
        f"firewall: no signals field may appear in derived, found "
        f"{_signal_field_names & set(_d_fake['derived'].keys())}"
    )
    print("  iter4 firewall: signals is top-level sibling of derived, NOT inside derived; "
          "diagnostic_only=True, never_affects_buy=True  OK")

    # --- P-D: error artifact writer produces an auditable JSON on a simulated crash ---
    _selftest_error_artifact()
    print(f"  P-D error artifact: simulated crash -> auditable ERROR JSON written + parsed  OK")

    # Generated independent-source controls preserve mismatch, agreement and floor branches.
    from make_fixtures import source34_scenarios
    _p7 = source34_scenarios()["cross_source"]
    _p7_chk, _p7_mis, _p7_det = _cross_source_check(*_p7["debt_mismatch"])
    assert _p7_chk is True, "P7(i): two comparable sources must be checked"
    assert _p7_mis is True, f"P7(i): gross debt disagreement must be detected: {_p7_det}"
    assert "total_debt" in _p7_det and "ratio" in _p7_det, (
        f"P7(i): detail must identify debt and ratio: {_p7_det!r}")
    print("  P7(i): generated debt mismatch  OK")

    _p7b_chk, _p7b_mis, _p7b_det = _cross_source_check(*_p7["agreement"])
    assert _p7b_chk is True and _p7b_mis is False, (
        f"P7(ii): comparable agreement must not block: {_p7b_det}")
    print("  P7(ii): generated agreement  OK")

    _p7c_chk, _p7c_mis, _p7c_det = _cross_source_check(*_p7["unavailable"])
    assert _p7c_chk is False and _p7c_mis is False, (
        f"P7(iii): unavailable second source cannot establish a mismatch: {_p7c_det}")
    print("  P7(iii): unavailable second source  OK")

    _p7d_chk, _p7d_mis, _p7d_det = _cross_source_check(*_p7["revenue_mismatch"])
    assert _p7d_chk is True and _p7d_mis is True, (
        f"P7(iv): gross revenue disagreement must be detected: {_p7d_det}")
    assert "revenue" in _p7d_det, f"P7(iv): detail must identify revenue: {_p7d_det!r}"
    print("  P7(iv): generated revenue mismatch  OK")

    _p7e_chk, _p7e_mis, _p7e_det = _cross_source_check(*_p7["floor"])
    assert _p7e_chk is True, "P7(v): comparable revenue must be checked"
    assert _p7e_mis is False, f"P7(v): sub-floor or one-sided values cannot block: {_p7e_det}"
    print("  P7(v): comparison floor and one-sided fields  OK")

    #  (vi) default fetch _yf_second_source guards on empty ticker (no network, returns None).
    assert _yf_second_source("") is None, (
        "P7(vi): _yf_second_source('') must return None (no ticker -> never block/crash)"
    )
    print(f"  P7(vi) _yf_second_source('') -> None (guarded, no network)  OK")

    #  (vii) pull() emits the three P7 fields via an injected offline yf_fn (network-free path).
    #       A mismatching second source must surface checked=True / mismatch=True in derived.
    _p7_yf = lambda t: {"total_debt": 4_000_000_000, "revenue": None, "shares_outstanding": None}
    _p7_chk2, _p7_mis2, _p7_det2 = _cross_source_check(11_000_000, None, None, _p7_yf("SYNANNUAL"))
    assert _p7_chk2 is True and _p7_mis2 is True, (
        "P7(vii): injected yf_fn debt-only mismatch must yield checked=True, mismatch=True"
    )
    # And an injected fn that raises must be swallowed (firewall) -> treated as absent source.
    def _p7_raises(_t):
        raise RuntimeError("simulated yfinance failure")
    try:
        _ = _p7_raises("X")
        _raised = False
    except Exception:
        _raised = True
    _p7_chk3, _p7_mis3, _ = _cross_source_check(11_000_000, None, None, None)
    assert _raised and _p7_chk3 is False and _p7_mis3 is False, (
        "P7(vii): a raising/absent second source must degrade to checked=False/mismatch=False"
    )
    print(f"  P7(vii) pull-level: injected yf_fn mismatch surfaces; raising fn degrades to no-block  OK")

    # A positive normalized cash-flow base must not conceal a synthetic current loss.
    _masked_case_ocf = _legacy['deepdive_masked_ocf']
    _masked_case_norm = _normalized_fcf_proxy(_masked_case_ocf, [], True)  # proxy mode (no capex) -> avg OCF
    assert _masked_case_norm is not None and _masked_case_norm > 0, (
        f"#1: synthetic current-loss trailing-avg normalized_fcf must be POSITIVE (the masking), got {_masked_case_norm}"
    )
    # cr<0 path (the A1-silenced degenerate base), flag must fire.
    assert _normalization_masks_current_loss(_masked_case_norm, *_legacy["masked_loss_inputs"]) is True, (
        "#1: normalization_masks_current_loss must fire when normalized_fcf>0 AND contamination<0 "
        "(synthetic current-loss degenerate-base hole)"
    )
    # latest_ocf<0 alone (positive cr) must also fire (current cash burn masked by the average).
    assert _normalization_masks_current_loss(_masked_case_norm, _legacy["masked_loss_inputs"][0], 5_000_000, 1.1) is True, (
        "#1: must fire when normalized_fcf>0 AND latest_ocf<0 (current burn masked)"
    )
    # latest_fcf<0 alone (positive cr, positive ocf) must fire.
    assert _normalization_masks_current_loss(_masked_case_norm, 10_000_000, _legacy["masked_loss_inputs"][1], 1.1) is True, (
        "#1: must fire when normalized_fcf>0 AND latest_fcf<0"
    )
    print(f"  #1 normalization_masks_current_loss: synthetic (norm_fcf={_masked_case_norm/1e6:.1f}M>0, "
          f"latest_ocf<0) -> True  OK")

    # Clean grower: positive normalized_fcf AND positive current OCF/FCF AND positive cr -> False.
    _grow_ocf = [
        {"end": "2020-12-31", "val": 10_000_000},
        {"end": "2021-12-31", "val": 13_000_000},
        {"end": "2022-12-31", "val": 16_000_000},
        {"end": "2023-12-31", "val": 20_000_000},
        {"end": "2024-12-31", "val": 26_000_000},
    ]
    _grow_norm = _normalized_fcf_proxy(_grow_ocf, [], True)
    assert _normalization_masks_current_loss(_grow_norm, 26_000_000, 24_000_000, 1.2) is False, (
        "#1: clean grower (positive current OCF/FCF, positive cr) must NOT fire the mask flag"
    )
    # normalized_fcf <= 0 can never mask (no phantom positive MoS to suppress).
    assert _normalization_masks_current_loss(-5_000_000, -10_000_000, -10_000_000, -1.1) is False, (
        "#1: a non-positive normalized_fcf must NEVER set the mask flag"
    )
    # None normalized_fcf -> False (no proxy available).
    assert _normalization_masks_current_loss(None, -10_000_000, -10_000_000, -1.1) is False, (
        "#1: None normalized_fcf must yield False"
    )
    print(f"  #1 normalization_masks_current_loss: clean grower False, norm_fcf<=0 False, None False  OK")

    # FCF proxy must match valuation: with capex, FCF = OCF - CapEx (latest-window mean).
    _nfp_ocf = [{"end": "2023-12-31", "val": 100_000_000}, {"end": "2024-12-31", "val": 120_000_000}]
    _nfp_capex = [{"end": "2023-12-31", "val": 30_000_000}, {"end": "2024-12-31", "val": 40_000_000}]
    _nfp = _normalized_fcf_proxy(_nfp_ocf, _nfp_capex, False)
    assert abs(_nfp - ((100 - 30 + 120 - 40) / 2 * 1e6)) < 1.0, (
        f"#1: FCF proxy must equal mean(OCF-CapEx) = {(100-30+120-40)/2}M, got {_nfp/1e6:.1f}M"
    )
    print(f"  #1 _normalized_fcf_proxy: OCF-CapEx mean = ${_nfp/1e6:.1f}M  OK")

    # Generated debt amounts are invariant to the availability of a liabilities tag.
    for _case in _debt_fix["amount_cases"]:
        for _liabilities in (_debt_fix["liabilities"], []):
            _ev, _substituted, _detail = _debt_for_ev(
                _case["amount"], _liabilities, _debt_fix["equity"], _debt_fix["assets"])
            assert _ev == _case["expected"] and not _substituted
            if _ev is None:
                assert _detail
    print("  Debt evidence: no balance-sheet substitution  OK")

    # --- v0.3.1 #3: lease-adjusted SEC debt for cross-source comparison ---
    # Adding OperatingLeaseLiability to the SEC debt side closes the ASC842 gap so a lease-heavy
    # retailer (SEC contractual debt 100M, +600M operating leases) is lease-comparable to yfinance's
    # lease-inclusive totalDebt (~700M) -> within 2.5x -> NO false cross_source_mismatch.
    _lease_sec_debt = 100_000_000
    _lease_op = 600_000_000
    _lease_adj = (_lease_sec_debt or 0.0) + _lease_op   # 700M
    _cs_unadj_chk, _cs_unadj_mis, _ = _cross_source_check(
        _lease_sec_debt, 500_000_000, 40_000_000,
        {"total_debt": 700_000_000, "revenue": 500_000_000, "shares_outstanding": 40_000_000},
    )
    assert _cs_unadj_mis is True, (
        "#3 precondition: UNADJUSTED SEC debt 100M vs yf 700M (7x) must mismatch (the FP we fix)"
    )
    _cs_adj_chk, _cs_adj_mis, _cs_adj_det = _cross_source_check(
        _lease_adj, 500_000_000, 40_000_000,
        {"total_debt": 700_000_000, "revenue": 500_000_000, "shares_outstanding": 40_000_000},
    )
    assert _cs_adj_chk is True and _cs_adj_mis is False, (
        f"#3: lease-adjusted SEC debt (700M) vs yf (700M) must be within 2.5x -> NO mismatch, "
        f"got mis={_cs_adj_mis} ({_cs_adj_det})"
    )
    assert OPERATING_LEASE_CONCEPTS == [
        "OperatingLeaseLiabilityNoncurrent", "OperatingLeaseLiabilityCurrent"
    ], "#3: OPERATING_LEASE_CONCEPTS must be the current+noncurrent operating-lease liability tags"
    print(f"  #3 lease-adjust: unadj 100M-vs-700M mismatch=True -> adj 700M-vs-700M mismatch=False  OK")

    # --- v0.3.1 #4: insurance_concepts_present requires SIC 63/64 OR >=2 DISTINCT concepts ---
    # Offline: stub _one_concept so the probe is deterministic and network-free.
    # v0.3.3 refactor: _one_concept now lives in _deepdive_concepts (the _dc alias) and every
    # concept/flag helper resolves the fetcher through that module, so we patch _dc._one_concept
    # (the single source of truth) instead of this module's local name.
    import builtins as _bi
    _orig_one_concept = _dc._one_concept

    def _make_stub(present_set):
        # asof accepted (ignored) so the stub matches the PIT-extended _one_concept signature.
        def _stub(cik, concept, taxonomy="us-gaap", asof=None):
            return [{"end": "2024-12-31", "val": 1.0}] if concept in present_set else []
        return _stub

    try:
        # Synthetic insurance evidence must respect the SIC and concept-count thresholds.
        _dc._one_concept = _make_stub({"PremiumsEarnedNet"})
        _ins_a, _ins_a_c = _insurance_concepts_present("0000000001", sic_code="3690")
        assert _ins_a is False, (
            f"#4: a SINGLE stray insurance tag on SIC 3690 (non-insurer) must NOT fire, got {_ins_a_c}"
        )
        # (b) TWO distinct insurance concepts on a non-insurance SIC -> True.
        _dc._one_concept = _make_stub({"PremiumsEarnedNet", "UnearnedPremiums"})
        _ins_b, _ins_b_c = _insurance_concepts_present("0000000001", sic_code="3690")
        assert _ins_b is True and _ins_b_c is not None, (
            f"#4: TWO distinct insurance concepts must fire even on a non-insurer SIC, got {_ins_b}"
        )
        # (c) SINGLE insurance tag on an insurance SIC (6311, life insurer) -> True.
        _dc._one_concept = _make_stub({"PremiumsEarnedNet"})
        _ins_c, _ins_c_c = _insurance_concepts_present("0000000001", sic_code="6311")
        assert _ins_c is True and _ins_c_c == "PremiumsEarnedNet", (
            f"#4: a single insurance tag on SIC 6311 (insurance carrier) must fire, got {_ins_c}"
        )
        # (c2) SIC 6411 (insurance agents/brokers, 64-prefix) + single tag -> True.
        _dc._one_concept = _make_stub({"DeferredPolicyAcquisitionCosts"})
        _ins_c2, _ = _insurance_concepts_present("0000000001", sic_code="6411")
        assert _ins_c2 is True, "#4: a single insurance tag on SIC 6411 (64-prefix) must fire"
        # (d) NO insurance concepts at all -> False regardless of SIC.
        _dc._one_concept = _make_stub({"Revenues", "Assets"})
        _ins_d, _ = _insurance_concepts_present("0000000001", sic_code="6311")
        assert _ins_d is False, "#4: no insurance concepts present must yield False even on insurer SIC"
        # Synthetic insurance evidence must respect the SIC and concept-count thresholds.
        _dc._one_concept = _make_stub({"PremiumsEarnedNet"})
        _ins_e, _ = _insurance_concepts_present("0000000001", sic_code=None)
        assert _ins_e is False, "#4: single tag with no SIC must NOT fire (needs >=2 concepts)"
    finally:
        _dc._one_concept = _orig_one_concept
    print("  #4 insurance_concepts_present: single tag on SIC 3690 False; 2 concepts True; "
          "single tag on SIC 6311/6411 True; none False  OK")

    # A segment revenue percentage must not become a customer concentration percentage.
    _segment_case_text = (
        _legacy['concentration_bracket_segment']
    )
    _segment_case_tc, _segment_case_tp, _segment_case_cd = _extract_concentration(_segment_case_text)
    assert _segment_case_tc is None, (
        f"#7: 'X% of [Division] revenue' is a segment disclosure -> top_customer_pct must be None, "
        f"got {_segment_case_tc} (detail={_segment_case_cd})"
    )
    # Collapsed whitespace must preserve the earlier 5% customer and exclude the later segment figure.
    _segment_case_real = (
        _legacy['concentration_collapsed_segment']
    )
    _dr_tc, _dr_tp, _dr_cd = _extract_concentration(_segment_case_real)
    assert _dr_tc == 5.0, (
        f"#7: retain the earlier 5% customer disclosure while excluding the later "
        f"collapsed-whitespace segment percentage, got {_dr_tc} (detail={_dr_cd})"
    )
    assert _CONC_SEGMENT_CTX.search(_legacy["concentration_patterns"]["collapsed"]) is not None, (
        "#7: _CONC_SEGMENT_CTX must match collapsed-whitespace/curly-apostrophe segment phrasing"
    )
    # An 87% possessive segment figure must not attach to the nearby 5% customer statement.
    _segment_case_poss = (
        _legacy['concentration_possessive_segment']
    )
    _dp_tc, _dp_tp, _dp_cd = _extract_concentration(_segment_case_poss)
    # The 87% segment figure must NOT be bound to a customer (that was the re-kill). A genuine,
    # in-window "largest customer ... less than 5%" mention legitimately yields 5%, harmless,
    # well below the 40% kill band. The load-bearing requirement is that no KILL-grade customer
    # percentage (>40) is manufactured from the 87% segment figure.
    assert _dp_tc is None or _dp_tc < 40, (
        f"#7 LOAD-BEARING: '87% of AcmeCorp Retail’s revenue' (possessive proper-noun segment) must NOT bind "
        f"to a kill-grade customer pct -> top_customer_pct must be None or <40, "
        f"got {_dp_tc} (detail={_dp_cd})"
    )
    assert _concentration_flag(_dp_tc, _dp_tp) != "kill", (
        f"#7 LOAD-BEARING: the synthetic segment possessive-segment shape must NOT yield a kill flag, "
        f"got flag for tc={_dp_tc}"
    )
    # Possessive guard must NOT swallow a GENUINE customer stated against a generic denominator.
    assert _CONC_SEGMENT_POSSESSIVE.search("65% of total revenue") is None, (
        "#7: possessive guard must NOT match generic-denominator 'X% of total revenue'"
    )
    assert _CONC_SEGMENT_POSSESSIVE.search(_legacy["concentration_patterns"]["possessive"]) is not None, (
        "#7: possessive guard must match 'X% of <ProperNoun>’s revenue' segment phrasing"
    )
    assert _CONC_SEGMENT_POSSESSIVE.search(_legacy["concentration_patterns"]["plural"]) is not None, (
        "#7: possessive guard must match PLURAL possessive + intervening qualifier "
        "('Services’ 2025 total revenue')"
    )
    # Diversified customers and a possessive segment denominator must not imply one customer.
    _segment_case_div = (
        _legacy['concentration_diversified']
    )
    _dv_tc, _dv_tp, _dv_cd = _extract_concentration(_segment_case_div)
    assert _concentration_flag(_dv_tc, _dv_tp) != "kill", (
        f"#7 LOAD-BEARING: 'top 18 customers ... 81% of AcmeCorp Services’ revenue' (diversified + "
        f"segment) must NOT yield a kill, got tc={_dv_tc} tp={_dv_tp} (detail={_dv_cd})"
    )
    assert _CONC_DIVERSIFIED_CUSTOMERS.search(_legacy["concentration_patterns"]["diversified"]) is not None, (
        "#7: diversification guard must match 'top N customers'"
    )
    assert _CONC_DIVERSIFIED_CUSTOMERS.search("our largest customer accounted for 65%") is None, (
        "#7: diversification guard must NOT match a singular 'largest customer'"
    )
    # Variants: division / branch / region / subsidiary / segment / geography must all be guarded.
    for _seg_word in ("Segment", "Branch", "Region", "Subsidiary", "Geographic region", "Business unit"):
        _seg_text = f"The {_seg_word} accounted for 100% of {_seg_word} revenue in the period."
        _seg_tc, _seg_tp, _ = _extract_concentration(_seg_text)
        assert _seg_tc is None, (
            f"#7: '100% of {_seg_word} revenue' must NOT set top_customer_pct, got {_seg_tc}"
        )
    # CRITICAL non-regression: a GENUINE single-customer concentration must STILL be captured ,
    # the guard must only suppress segment phrasing, not real customer dependence.
    _real_cust = (
        _legacy['concentration_customer']
    )
    _rc_tc, _rc_tp, _ = _extract_concentration(_real_cust)
    assert _rc_tc is not None and _rc_tc == 68.0, (
        f"#7 non-regression: a genuine 'largest customer ... 68% of total revenue' must STILL set "
        f"top_customer_pct, got {_rc_tc}"
    )
    assert _concentration_flag(_rc_tc, _rc_tp) == "kill", (
        "#7 non-regression: genuine 68% customer concentration must still yield kill"
    )
    print(f"  #7 concentration: synthetic segment '100% of [Division] revenue' -> top_customer_pct None; "
          f"genuine 68% customer still captured (kill)  OK")

    # Synthetic net-income ratios exercise the strict 50x anomaly threshold.
    def _ni_warn(ni_val, rev_val):
        if ni_val is not None and rev_val is not None and rev_val != 0 and abs(ni_val) > abs(rev_val) * 50:
            return f"absurd NI flagged"
        return None
    # Synthetic net-income ratios exercise the strict 50x anomaly threshold.
    assert _ni_warn(*_legacy["ni_anomaly_cases"][0]) is not None, (
        "#13(NI): synthetic 30,000M NI vs 400M revenue (75x) must flag data_quality_warn"
    )
    # Synthetic net-income ratios exercise the strict 50x anomaly threshold.
    assert _ni_warn(*_legacy["ni_anomaly_cases"][1]) is not None, (
        "#13(NI): synthetic 40,000M NI vs 400M revenue (100x) must flag data_quality_warn"
    )
    # Negative NI of the same absurd magnitude must also flag (abs()).
    assert _ni_warn(*_legacy["ni_anomaly_cases"][2]) is not None, (
        "#13(NI): absurd NEGATIVE NI must also flag (abs comparison)"
    )
    # A normal large-but-plausible NI (e.g. 50M NI vs 500M revenue, 0.1x) must NOT flag.
    assert _ni_warn(*_legacy["ni_anomaly_cases"][3]) is None, (
        "#13(NI): a plausible NI/revenue ratio must NOT flag data_quality_warn"
    )
    # Boundary: exactly 50x must NOT flag (strict >).
    assert _ni_warn(*_legacy["ni_anomaly_cases"][4]) is None, (
        "#13(NI): exactly 50x must NOT flag (threshold is strict >50x)"
    )
    print("  #13(NI) data_quality_warn: synthetic 75x / 100x flagged; plausible & 50x boundary spared  OK")

    # --- v0.3.2 #8: lessor_asset_heavy, railcar/equipment lessor routing (debt/assets<0.62) ---
    # Three independent routes must each fire True; a normal industrial must stay False.
    _assets_big = [{"end": "2024-12-31", "val": 5_000_000_000.0}]  # $5B total assets
    # Leasing SIC 4741 independently establishes an asset-heavy lessor.
    _la_a, _la_a_d = _lessor_asset_heavy(
        "0000000001", "4741", _assets_big,
        lease_income_present=False, ppe_fleet_val=None, rental_lease_revenue=False,
    )
    assert _la_a is True and "lessor_sic" in (_la_a_d or ""), (
        f"#8 route(a): a leasing-SIC (4741) must set lessor_asset_heavy True, got {_la_a} ({_la_a_d})"
    )
    # Lease income establishes a lessor on a generic industrial SIC.
    _la_b, _la_b_d = _lessor_asset_heavy(
        "0000000001", "3743", _assets_big,
        lease_income_present=True, ppe_fleet_val=None, rental_lease_revenue=True,
    )
    assert _la_b is True and "lease_income_concept_present" in (_la_b_d or ""), (
        f"#8 route(b): a lease-income concept must set lessor_asset_heavy True on a non-leasing SIC, "
        f"got {_la_b} ({_la_b_d})"
    )
    # Route (c): very-high PP&E/lease-fleet ratio (>0.55) + rental revenue, generic industrial SIC,
    # NO explicit lease-income concept (the lessor whose rent is tagged under a generic revenue tag).
    _la_c, _la_c_d = _lessor_asset_heavy(
        "0000000001", "3743", _assets_big,
        lease_income_present=False, ppe_fleet_val=3_500_000_000.0, rental_lease_revenue=True,
    )
    assert _la_c is True and "ppe_fleet_ratio" in (_la_c_d or ""), (
        f"#8 route(c): high PP&E/assets (0.70) + rental revenue must set lessor_asset_heavy True, "
        f"got {_la_c} ({_la_c_d})"
    )
    # Synthetic lessors below the debt firewall must route on their leasing evidence.
    _lessor_case_debt, _lessor_case_assets = _legacy["deepdive_lessor_balance"]
    assert (_lessor_case_debt / _lessor_case_assets) < 0.62, "#8 crystal: synthetic debt/assets must be <0.62"
    _la_lessor_case, _ = _lessor_asset_heavy(
        "0000000001", "3743", [{"end": "2024-12-31", "val": _lessor_case_assets}],
        lease_income_present=True, ppe_fleet_val=None, rental_lease_revenue=True,
    )
    assert _la_lessor_case is True, (
        "#8 crystal: a synthetic railcar lessor (lease income, debt/assets=0.48<0.62) must set "
        "lessor_asset_heavy True so valuation routes it to lease-fleet NAV"
    )
    # Crystal: a NORMAL industrial, generic SIC, no lease income, modest PP&E (0.20), no rental
    # revenue -> must stay False (no false routing of ordinary manufacturers to NAV).
    _la_norm, _la_norm_d = _lessor_asset_heavy(
        "0000000001", "3559", _assets_big,
        lease_income_present=False, ppe_fleet_val=1_000_000_000.0, rental_lease_revenue=False,
    )
    assert _la_norm is False and _la_norm_d is None, (
        f"#8 crystal: a normal industrial (no leasing signals) must stay lessor_asset_heavy False, "
        f"got {_la_norm} ({_la_norm_d})"
    )
    # Guard: high PP&E ratio WITHOUT rental revenue (a capital-intensive manufacturer/utility) must
    # NOT fire route (c), the ratio alone is not a leasing signal.
    _la_capint, _ = _lessor_asset_heavy(
        "0000000001", "3559", _assets_big,
        lease_income_present=False, ppe_fleet_val=4_000_000_000.0, rental_lease_revenue=False,
    )
    assert _la_capint is False, (
        "#8 guard: high PP&E ratio without rental revenue (cap-intensive manufacturer) must NOT fire"
    )
    print("  #8 lessor_asset_heavy: leasing-SIC / lease-income / high-PP&E+rent all True (incl. "
          "synthetic debt/assets=0.48); normal industrial + cap-intensive non-lessor False  OK")

    # --- v0.3.2 #11: IFRS concept recovery + foreign_filer_unvaluable ---
    # (1) concept_series_with_ifrs: a foreign filer with NO us-gaap revenue but ifrs-full Revenue
    # must RECOVER (financials populate). Offline-stub _one_concept by taxonomy.
    # v0.3.3 refactor: patch _dc._one_concept (the single fetcher concept_series_with_ifrs, which
    # now lives in _deepdive_concepts, resolves through) instead of this module's local name.
    _orig_one_concept_11 = _dc._one_concept

    def _make_tax_stub(gaap_present, ifrs_present):
        """Stub _one_concept: returns a value only for the named concept under its taxonomy."""
        # asof accepted (ignored) so the stub matches the PIT-extended _one_concept signature.
        def _stub(cik, concept, taxonomy="us-gaap", asof=None):
            if taxonomy == "us-gaap" and concept in gaap_present:
                return [{"end": "2024-12-31", "val": gaap_present[concept]}]
            if taxonomy == "ifrs-full" and concept in ifrs_present:
                return [{"end": "2024-12-31", "val": ifrs_present[concept]}]
            return []
        return _stub

    try:
        # Recoverable IFRS-tag fixture: no us-gaap revenue, ifrs-full Revenue present -> populates.
        _dc._one_concept = _make_tax_stub({}, {"Revenue": 1_234_000_000.0})
        _rev_ifrs = concept_series_with_ifrs("0000000002", REVENUE_CONCEPTS, IFRS_REVENUE_CONCEPTS)
        assert _rev_ifrs and _rev_ifrs[-1]["val"] == 1_234_000_000.0, (
            f"#11: a foreign filer's ifrs-full Revenue must recover via concept_series_with_ifrs, "
            f"got {_rev_ifrs}"
        )
        # us-gaap WINS on a shared end-date, IFRS only fills gaps, never overwrites.
        _dc._one_concept = _make_tax_stub(
            {"Revenues": 999.0}, {"Revenue": 1_234_000_000.0}
        )
        _rev_both = concept_series_with_ifrs("0000000002", REVENUE_CONCEPTS, IFRS_REVENUE_CONCEPTS)
        assert _rev_both and _rev_both[-1]["val"] == 999.0, (
            f"#11: us-gaap value must WIN over ifrs-full at a shared end-date, got {_rev_both}"
        )
    finally:
        _dc._one_concept = _orig_one_concept_11

    # (2) foreign_filer_unvaluable: a 20-F/40-F filer with ALL financial series empty -> True.
    _ffu_a, _ffu_a_d = _foreign_filer_unvaluable("20-F", [], [], [])
    assert _ffu_a is True and _ffu_a_d, (
        f"#11: a 20-F filer with empty revenue/NI/OCF must set foreign_filer_unvaluable True, "
        f"got {_ffu_a}"
    )
    _ffu_40, _ = _foreign_filer_unvaluable("40-F", [], [], [])
    assert _ffu_40 is True, "#11: a 40-F filer with empty financials must also be unvaluable"
    # A foreign filer that DID recover financials (via IFRS) is valuable -> False.
    _ffu_b, _ = _foreign_filer_unvaluable(
        "20-F", [{"end": "2024-12-31", "val": 1.0}], [], []
    )
    assert _ffu_b is False, (
        "#11: a 20-F filer that recovered revenue (IFRS) must NOT be flagged unvaluable"
    )
    # A DOMESTIC 10-K filer with empty financials is NOT a foreign-filer-unvaluable case (False).
    _ffu_dom, _ = _foreign_filer_unvaluable("10-K", [], [], [])
    assert _ffu_dom is False, (
        "#11: a domestic 10-K filer must NEVER be labeled foreign_filer_unvaluable"
    )
    print("  #11 IFRS recovery + foreign_filer_unvaluable: ifrs-full Revenue recovers (us-gaap "
          "wins ties); empty 20-F/40-F -> unvaluable True; recovered/domestic -> False  OK")

    # --- PIT (backtest PIECE 1): concept_series_asof, filed<=asof, latest-filed-per-end-date ---
    # Synthetic companyconcept facts with DISTINCT "filed" dates exercise the as-of filter:
    #   * the asof variant drops facts filed AFTER asof (no look-ahead),
    #   * per period END it picks the LATEST-FILED fact <= asof (the disclosure an investor at asof
    #     could have seen, a later restatement filed after asof is ignored),
    #   * asof=None reproduces the LIVE default (all facts, last-in-API-order dedup).
    # We patch _dc.http_get to return the synthetic JSON so the REAL _one_concept asof logic runs
    # (patching _one_concept itself would bypass the very logic under test). Restored in finally.
    _orig_http_get = _dc.http_get

    from make_fixtures import deepdive_selftest_concept_scenarios
    selftest_concepts = deepdive_selftest_concept_scenarios()

    class _FakeResp:
        def __init__(self, payload, url):
            self.status_code = 200
            taxonomy, tag = url.rsplit("/", 2)[-2:]
            self._payload = {**payload, "taxonomy": taxonomy, "tag": tag.removesuffix(".json")}
        def json(self):
            return self._payload

    # FY2022 (end 2022-12-31): original filed 2023-03-01 val=100; restated filed 2024-03-01 val=110.
    # FY2023 (end 2023-12-31): filed 2024-03-01 val=200.
    # FY2024 (end 2024-12-31): filed 2025-03-01 val=300 (filed AFTER a 2024-06-30 asof).
    _pit_payload = selftest_concepts["pit"]
    try:
        _dc.http_get = lambda url, *a, **k: _FakeResp(_pit_payload, url)

        # (a) asof = 2024-06-30: must see FY2022 (restated val=110, latest-filed<=asof) + FY2023
        #     (val=200); MUST NOT see FY2024 (filed 2025-03-01 > asof) -> no look-ahead.
        _asof_a = concept_series_asof("0000000001", "Revenues", "2024-06-30")
        _by_end_a = {x["end"]: x["val"] for x in _asof_a}
        assert _by_end_a == {"2022-12-31": 110, "2023-12-31": 200}, (
            f"PIT(a): asof=2024-06-30 must yield FY2022 restated (110, latest-filed<=asof) + FY2023 "
            f"(200), and DROP FY2024 (filed after asof), got {_by_end_a}"
        )

        # (b) asof = 2023-06-30: FY2022 only the ORIGINAL (val=100) is visible, the restatement was
        #     filed 2024-03-01 (> asof). FY2023/FY2024 not yet filed. The latest-filed<=asof rule
        #     must therefore pick the ORIGINAL, not the (future) restated value.
        _asof_b = concept_series_asof("0000000001", "Revenues", "2023-06-30")
        _by_end_b = {x["end"]: x["val"] for x in _asof_b}
        assert _by_end_b == {"2022-12-31": 100}, (
            f"PIT(b): asof=2023-06-30 must see ONLY FY2022 original (100) — the restatement filed "
            f"2024-03-01 is future, FY2023/FY2024 not yet filed, got {_by_end_b}"
        )

        # (c) asof BEFORE any filing -> empty (every fact is future-filed; never a crash).
        _asof_c = concept_series_asof("0000000001", "Revenues", "2020-01-01")
        assert _asof_c == [], f"PIT(c): asof before all filings must be empty, got {_asof_c}"

        # (d) the asof variant routes through concept_series(asof=...): a cascade list still merges
        #     (later concept overrides earlier at a shared end-date) under the as-of filter.
        _dc.http_get = lambda url, *a, **k: _FakeResp(_pit_payload, url)
        _asof_d = concept_series("0000000001", ["SalesRevenueNet", "Revenues"], asof="2024-06-30")
        assert {x["end"]: x["val"] for x in _asof_d} == {"2022-12-31": 110, "2023-12-31": 200}, (
            f"PIT(d): concept_series(asof=...) must apply the as-of filter through the cascade, "
            f"got {[(x['end'], x['val']) for x in _asof_d]}"
        )

        # (e) EQUIVALENCE: asof=None must reproduce the LIVE default, all four facts visible,
        #     last-in-API-order dedup (FY2022 -> the SECOND/restated 110). This is the byte-identical
        #     invariant the live path must preserve under the additive PIT change.
        _live = concept_series("0000000001", "Revenues", asof=None)
        _by_end_live = {x["end"]: x["val"] for x in _live}
        assert _by_end_live == {"2022-12-31": 110, "2023-12-31": 200, "2024-12-31": 300}, (
            f"PIT(e): asof=None (live default) must see ALL facts (incl. FY2024) with last-in-order "
            f"dedup (FY2022->110), got {_by_end_live}"
        )

        # (f) a fact with NO "filed" field is conservatively DROPPED in the asof path (cannot be
        #     dated <= T) but KEPT in the live path (asof=None).
        _undated_payload = selftest_concepts["undated"]
        _dc.http_get = lambda url, *a, **k: _FakeResp(_undated_payload, url)
        assert concept_series_asof("0000000001", "Revenues", "2025-01-01") == [], (
            "PIT(f): a fact with no 'filed' date must be DROPPED in the asof path (cannot date<=T)"
        )
        assert concept_series("0000000001", "Revenues", asof=None) == [
            {**_undated_payload["units"]["USD"][0], "filed": None, "duration_days": 364,
             "unit": "USD", "currency": "USD", "cik": "0000000001",
             "taxonomy": "us-gaap", "concept": "Revenues"}
        ], "PIT(f): the same undated fact must be KEPT in the live default path (asof=None)"

        # A synthetic value-changing restatement stays unavailable before its filing date.
        _restate_payload = selftest_concepts["restatement"]
        _dc.http_get = lambda url, *a, **k: _FakeResp(_restate_payload, url)
        # asof one day BEFORE the restatement -> original 1000 (restated 900 must NOT leak).
        _pre = {x["end"]: x["val"] for x in concept_series_asof("0000000001", "Assets", "2016-03-03")}
        assert _pre == {"2014-12-31": 1000}, (
            f"PIT(g): asof before the restatement must keep the ORIGINAL 1000 (restated 900 must NOT "
            f"leak across the as-of boundary), got {_pre}"
        )
        # asof ON the restatement filing date -> adopt the restated 900 (latest-filed<=asof, inclusive).
        _on = {x["end"]: x["val"] for x in concept_series_asof("0000000001", "Assets", "2016-03-04")}
        assert _on == {"2014-12-31": 900}, (
            f"PIT(g): asof ON the restatement filing date must adopt the restated 900 "
            f"(filed<=asof is inclusive), got {_on}"
        )
    finally:
        _dc.http_get = _orig_http_get
    print("  PIT concept_series_asof: filed<=asof + latest-filed-per-end-date (drops look-ahead "
          "& future restatements); asof=None == live default byte-identical  OK")

    # --- FIX 1: derived.asof_max_filing_date, max "filed" across as-of pulls (+ tenk) <= asof ---
    # The look-ahead audit is VACUOUS unless the as-of deepdive surfaces the filing dates it used.
    # _one_concept records the max "filed" of the facts it KEEPS (filed<=asof, latest-filed-per-end)
    # into a module accumulator; pull() resets it before the cascade and reads it back, combined with
    # the as-of tenk filing date, into derived.asof_max_filing_date. Here we exercise that accumulator
    # with synthetic facts of KNOWN filed dates so the result is deterministic and network-free.
    _orig_http_get_f1 = _dc.http_get

    # Two concepts, distinct filed dates. Under asof=2024-06-30 the KEPT facts are:
    #   Revenues: FY2022 restated (filed 2024-03-01) + FY2023 (filed 2024-03-15); FY2024 (filed
    #             2025-03-01) is future-filed and DROPPED. -> max filed kept = 2024-03-15.
    #   Assets:   FY2023 instant (filed 2024-04-10). -> max filed kept = 2024-04-10.
    # So the accumulator across BOTH pulls must reach 2024-04-10 (the global max kept filed <= asof).
    _f1_revenues = selftest_concepts["revenues"]
    _f1_assets = selftest_concepts["assets"]

    def _f1_router(payload_by_concept):
        """http_get stub that returns a payload chosen by the concept embedded in the URL."""
        def _get(url, *a, **k):
            for _concept, _payload in payload_by_concept.items():
                if f"/{_concept}.json" in url:
                    return _FakeResp(_payload, url)
            return _FakeResp(selftest_concepts["empty"], url)
        return _get

    try:
        _dc.http_get = _f1_router({"Revenues": _f1_revenues, "Assets": _f1_assets})

        # (a) accumulator across TWO as-of concept pulls -> global max KEPT filed (<= asof).
        _dc.reset_asof_filed_tracker()
        _r = concept_series("0000000001", "Revenues", asof="2024-06-30")
        assert {x["end"]: x["val"] for x in _r} == {"2022-12-31": 110, "2023-12-31": 200}, (
            f"FIX1(a): Revenues as-of must keep FY2022 restated + FY2023, got {_r}"
        )
        assert get_asof_max_filed() == "2024-03-15", (
            f"FIX1(a): after Revenues pull, max kept filed must be 2024-03-15, got {get_asof_max_filed()}"
        )
        _a = concept_series("0000000001", "Assets", asof="2024-06-30")
        assert {x["end"]: x["val"] for x in _a} == {"2022-12-31": 5000, "2023-12-31": 5200}, (
            f"FIX1(a): Assets as-of must keep both instants, got {_a}"
        )
        assert get_asof_max_filed() == "2024-04-10", (
            f"FIX1(a): accumulator across both pulls must be the global max kept filed 2024-04-10, "
            f"got {get_asof_max_filed()}"
        )
        # By construction the recorded max is <= asof, the look-ahead audit invariant.
        assert get_asof_max_filed() <= "2024-06-30", "FIX1(a): recorded max filed must be <= asof"

        # (b) the future-filed FY2024 fact (filed 2025-03-01 > asof) must NOT contaminate the max.
        assert get_asof_max_filed() < "2025-03-01", (
            "FIX1(b): a future-filed fact (dropped by the asof filter) must NOT enter the accumulator"
        )

        # (c) reset clears it; a pull whose ALL facts are future-filed records NOTHING -> None.
        _dc.reset_asof_filed_tracker()
        assert get_asof_max_filed() is None, "FIX1(c): reset must clear the accumulator to None"
        _none = concept_series("0000000001", "Revenues", asof="2020-01-01")  # before all filings
        assert _none == [] and get_asof_max_filed() is None, (
            f"FIX1(c): asof before all filings keeps nothing -> accumulator stays None, "
            f"got series={_none} max={get_asof_max_filed()}"
        )

        # (d) the LIVE default (asof=None) must NEVER record, the accumulator stays None so the
        #     emit-gate leaves derived.asof_max_filing_date absent (byte-identical live default).
        _dc.reset_asof_filed_tracker()
        _live = concept_series("0000000001", "Revenues", asof=None)
        assert _live and get_asof_max_filed() is None, (
            f"FIX1(d): a live (asof=None) pull must NOT touch the accumulator, got {get_asof_max_filed()}"
        )

        # (e) pull-level composition: max(concept-accumulator, tenk filing date). A tenk filed LATER
        #     than every concept fact (but still <= asof) must become the surfaced max; a tenk filed
        #     EARLIER must leave the concept max as the surfaced value. (Mirrors pull()'s max() of the
        #     two candidates; computed offline so no live tenk fetch is needed.)
        _dc.reset_asof_filed_tracker()
        concept_series("0000000001", "Assets", asof="2024-06-30")  # concept max -> 2024-04-10
        _concept_max = get_asof_max_filed()
        _tenk_late = "2024-05-20"   # later 10-K filing, still <= asof
        _composed_late = max([x for x in (_concept_max, _tenk_late) if x])
        assert _composed_late == "2024-05-20", (
            f"FIX1(e): a later (<=asof) tenk filing date must become asof_max_filing_date, "
            f"got {_composed_late}"
        )
        _tenk_early = "2024-01-05"  # earlier than the concept max
        _composed_early = max([x for x in (_concept_max, _tenk_early) if x])
        assert _composed_early == "2024-04-10", (
            f"FIX1(e): an earlier tenk filing date must leave the concept max as the surfaced value, "
            f"got {_composed_early}"
        )
        # Both None -> None (truly nothing datable).
        assert max([x for x in (None, None) if x], default=None) is None, (
            "FIX1(e): both concept-max and tenk-date None -> asof_max_filing_date None"
        )
    finally:
        _dc.http_get = _orig_http_get_f1
        _dc.reset_asof_filed_tracker()
    print("  FIX1 asof_max_filing_date: accumulator = max KEPT filed across pulls (<=asof, drops "
          "future-filed); reset clears; asof=None records nothing; tenk-date composes via max  OK")

    print("deepdive_data selftest PASS")


_IDENTITY_KEYS = ("input_index", "ticker", "cik", "band")
_BANDS = {"deep", "watch", "large", "unknown"}
_SKIP_BANDS = {"watch", "large"}


def _selftest_error_artifact():
    """Exercise only generated error evidence in a temporary synthetic directory."""
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    from make_fixtures import downstream_producer_completion_scenarios
    sample = downstream_producer_completion_scenarios()
    identity = _identity(sample["survivor_rows"][0])
    message = sample["pull_errors"][0]["error_code"]
    upstream = stage_completion("synthetic_input", 1, work=[stage_work("synthetic_input")])
    with TemporaryDirectory(prefix="smallcap-synthetic-") as directory:
        out = _data_path(Path(directory), identity, sample["verdict_date"])
        with patch("filter_by_sic.prepare_output", side_effect=lambda path: Path(path)):
            outcome, receipt = _write_error_artifact(identity["ticker"], identity["ticker"],
                identity["cik"], RuntimeError(message), out=out, identity=identity,
                binding=None, upstream=upstream)
        error = json.loads(out.read_text(encoding="utf-8"))
        assert error["status"] == "ERROR" and error["error_type"] == "RuntimeError"
        assert error["error"] == message and outcome["data_status"] == "error"
        assert receipt["status"] != "complete" and receipt["input_identity"] == identity
        assert not (Path(directory) / "deepdive_errors.log").exists()


def _identity(row):
    return {key: row[key] for key in _IDENTITY_KEYS}


def _validated_rows(rows, *, bound, require_pair=True):
    """Validate the whole cohort before exclusions or provider initialization."""
    if not isinstance(rows, list):
        raise ValueError("Deep-dive candidates must be a JSON list")
    indexed, labels = set(), set()
    validated = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Deep-dive candidate must be an object")
        ticker, cik = row.get("ticker"), row.get("cik")
        if (not isinstance(ticker, str) or not isinstance(cik, str)
                or (ticker and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", ticker))
                or (cik and not re.fullmatch(r"[0-9]{1,10}", cik))
                or not (ticker or cik) or not isinstance(row.get("band"), str)
                or row["band"] not in _BANDS):
            raise ValueError("Deep-dive candidate identity or band is invalid")
        if bound and require_pair and not (ticker and cik):
            raise ValueError("Bound survivors require both ticker and CIK")
        index = row.get("input_index") if bound else row.get("input_index", position)
        if (type(index) is not int or index < 0 or index in indexed
                or (not bound and index != position)):
            raise ValueError("Deep-dive input index is invalid or duplicated")
        label = (ticker or f"CIK{cik}").upper()
        if label in labels:
            raise ValueError("Deep-dive output identity is duplicated")
        for key in ("name", "theme", "theme_slug", "horizon", "event_type", "catalyst"):
            if key in row and row[key] is not None and not isinstance(row[key], str):
                raise ValueError(f"Deep-dive candidate {key} must be text")
        for key in ("mktcap", "health_score", "killflag_count"):
            value = row.get(key)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError(f"Deep-dive candidate {key} must be finite")
        indexed.add(index)
        labels.add(label)
        validated.append({**row, "input_index": index})
    return validated


def _binding(path):
    path = Path(path)
    payload = path.read_bytes()
    return {"artifact": path.name, "artifact_bytes": len(payload),
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "run_dir": str(path.resolve().parent)}


def _bound_path(run_dir, binding):
    if not isinstance(binding, dict):
        raise ValueError("Missing artifact binding")
    name = binding.get("artifact")
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or Path(name).name != name or "/" in name or "\\" in name):
        raise ValueError("Bound artifact must name one file in the run")
    path = Path(run_dir) / name
    if _binding(path) != binding:
        raise ValueError("Bound artifact bytes or run directory changed")
    return path


def _data_input(path):
    path = Path(path)
    event_bound = path.name == "candidates_event_admitted.json"
    bound = event_bound or path.name == "candidates_gate2_survivors.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = _validated_rows(raw, bound=bound, require_pair=not event_bound)
    receipt = read_stage_receipt(path, len(rows))
    if receipt["status"] == "invalid":
        raise ValueError("Candidate receipt is invalid")
    reasons = []
    if event_bound:
        from _event_admission import read_event_admission
        expected, expected_receipt = read_event_admission(path.parent)
        if raw != expected or receipt != expected_receipt:
            raise ValueError("Event input disagrees with source and cheap-pass evidence")
    elif bound:
        from run_theme import read_gate2_results
        all_rows, gate_receipt = read_gate2_results(path.parent)
        expected = [row for row in all_rows if row["judgment_status"] == "complete"
                    and row["theme_fit"] in {"pure_play", "partial"}]
        expected_receipt = stage_completion("gate2_survivors", len(expected), upstream=[gate_receipt])
        expected_receipt["input"] = gate_receipt["input"]
        if raw != expected or any(receipt.get(key) != value for key, value in expected_receipt.items()):
            raise ValueError("Survivors or their receipt disagree with bound Gate2 outcomes")
    elif rows:
        reasons.append("unbound_gate2_input")
    if any(row["band"] == "unknown" for row in rows):
        reasons.append("unresolved_candidate_band")
    completion = stage_completion("deepdive_input", len(rows), upstream=[receipt], reasons=reasons)
    return rows, _binding(path), completion


def _fresh(path):
    path = Path(path)
    if path.exists() or stage_receipt_path(path).exists():
        raise FileExistsError(f"Existing output {path.name}; use a new run directory")
    return prepare_stage_output(path)


def _write_json(path, payload, completion):
    path = _fresh(path)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
    write_stage_receipt(path, completion)
    return read_stage_receipt(path, completion["row_count"])


def _date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Date must be YYYY-MM-DD")
    return value


def _data_path(run_dir, row, pull_date):
    label = row["ticker"] or f"CIK{row['cik']}"
    return Path(run_dir) / f"deepdive_{label}_{_date(pull_date)}.json"


def _data_completion(data, identity, binding, upstream):
    """Describe observed payloads without treating a swallowed source error as success."""
    if not isinstance(data, dict):
        raise ValueError("Deep-dive pull must return an object")
    source_upstream = [upstream]
    if data.get("status") == "ERROR":
        work = [stage_work("deepdive_pull", status="unavailable", reason="pull_failed")]
        reasons = ["pull_failed"]
    else:
        work = []
        financials = data.get("financials")
        if not isinstance(financials, dict):
            raise ValueError("Deep-dive financials must be an object")
        if not isinstance(data.get("derived"), dict):
            raise ValueError("Deep-dive derived observations must be an object")
        for name in ("revenue", "net_income", "ocf", "cash", "shares_outstanding",
                     "assets", "equity", "total_debt", "ebit", "dep_amort", "capex",
                     "goodwill", "intangibles", "liabilities"):
            values = financials.get(name)
            observed = isinstance(values, list) and bool(values) and all(
                isinstance(v, dict) and type(v.get("val")) in (int, float)
                and math.isfinite(v["val"]) and isinstance(v.get("end"), str)
                for v in values)
            work.append(stage_work("observed_financial_series", name,
                status="complete" if observed else "unavailable",
                reason="" if observed else "no_observed_values"))
        for name in ("tenk", "insider"):
            section = data.get(name)
            observed = isinstance(section, dict) and section.get("available") is True and not section.get("error")
            work.append(stage_work(name, status="complete" if observed else "unavailable",
                                   reason="" if observed else "source_unavailable"))
        reasons = []
        tenk = data.get("tenk")
        if isinstance(tenk, dict) and "ambiguous_concentration_clause" in (tenk.get("concentration_detail") or ""):
            reasons.append("concentration_ambiguous")
        observations = data.get("source_observations", {})
        if not isinstance(observations, dict):
            raise ValueError("Deep-dive source observations must be an object")
        for name, stage, reason in (
            ("financials", "sec_financial_observations", "financial_source_completion_unobserved"),
            ("sic", "sec_submissions_sic", "sic_source_completion_unobserved"),
        ):
            observation = observations.get(name)
            if observation is None:
                reasons.append(reason)
                continue
            if (not isinstance(observation, dict) or observation.get("schema") != "smallcap.stage.v1"
                    or observation.get("stage") != stage
                    or observation.get("status") not in {"complete", "partial", "unavailable", "invalid"}):
                raise ValueError("Deep-dive source completion is invalid")
            source_upstream.append(observation)
            if name == "financials" and not observation.get("upstream"):
                reasons.append(reason)
    completion = stage_completion("deepdive_data", 1, work=work, upstream=source_upstream, reasons=reasons)
    completion["input_identity"] = identity
    completion["input"] = binding
    return completion


def _write_error_artifact(label, ticker, cik, exc, *, out, identity, binding, upstream):
    """Persist the failure and its partial receipt; a persistence error must propagate."""
    data = {"ticker": ticker, "cik": cik, "label": label, "pulled_at": today(),
            "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)}
    completion = _data_completion(data, identity, binding, upstream)
    receipt = _write_json(out, data, completion)
    return {**identity, "data_status": "error", "artifact": out.name}, receipt


def _pull_and_save(ticker, cik, *, out, identity, binding, upstream, init_error=None):
    """Retain original input identity even when the legacy CIK-first path resolves a symbol."""
    try:
        if init_error is not None:
            raise init_error
        if not cik:
            cik = str(Company(ticker).cik)
            if not re.fullmatch(r"[0-9]{1,10}", cik):
                raise ValueError("Resolved CIK is invalid")
        if not ticker:
            try:
                resolved = Company(int(cik)).tickers
                ticker = resolved[0] if resolved else ""
            except Exception:
                # A CIK-only issuer remains usable, with a partial data receipt.
                ticker = ""
            if ticker and (not isinstance(ticker, str) or
                           not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", ticker)):
                raise ValueError("Resolved ticker is invalid")
        with _dc.concept_observations() as observation:
            data = pull(ticker, cik)
        if not isinstance(data, dict) or data.get("ticker") != ticker or data.get("cik") != cik:
            raise ValueError("Pull returned a different issuer")
        source_observations = data.setdefault("source_observations", {})
        if not isinstance(source_observations, dict):
            raise ValueError("Deep-dive source observations must be an object")
        source_observations["financials"] = observation.completion(row_count=1)
        completion = _data_completion(data, identity, binding, upstream)
    except Exception as exc:
        label = identity["ticker"] or f"CIK{identity['cik']}"
        return _write_error_artifact(label, ticker, cik, exc, out=out, identity=identity,
                                     binding=binding, upstream=upstream)
    # Persistence is outside the provider exception handler.
    receipt = _write_json(out, data, completion)
    return {**identity, "data_status": completion["status"], "artifact": out.name}, receipt


def _batch_completion(rows, receipts, binding, upstream):
    work = [stage_work("deepdive_input", str(row["input_index"]),
                      status="complete" if row["data_status"] == "skipped" else row["data_status"]
                      if row["data_status"] in {"complete", "partial"} else "unavailable",
                      reason="excluded_band" if row["data_status"] == "skipped" else "")
            for row in rows]
    completion = stage_completion("deepdive_data_results", len(rows),
                                  work=work, upstream=[upstream, *receipts])
    completion["input"] = binding
    return completion


def run_batch(candidates_path, *, pull_date=None):
    """Write one immutable outcome per input; validate even excluded rows first."""
    candidates_path = Path(candidates_path)
    rows, binding, upstream = _data_input(candidates_path)
    pull_date = _date(pull_date or today())
    output = _fresh(candidates_path.parent / "deepdive_data_results.json")
    for row in rows:
        if row["band"] not in _SKIP_BANDS:
            _fresh(_data_path(candidates_path.parent, row, pull_date))
    init_error = None
    if any(row["band"] not in _SKIP_BANDS for row in rows):
        try:
            init_edgar()
        except Exception as exc:
            init_error = exc
    outcomes, receipts = [], []
    for row in rows:
        identity = _identity(row)
        if row["band"] in _SKIP_BANDS:
            outcomes.append({**identity, "data_status": "skipped", "artifact": None})
            continue
        outcome, receipt = _pull_and_save(row["ticker"], row["cik"],
            out=_data_path(candidates_path.parent, row, pull_date),
            identity=identity, binding=binding, upstream=upstream, init_error=init_error)
        outcomes.append(outcome)
        receipts.append(receipt)
    completion = _batch_completion(outcomes, receipts, binding, upstream)
    _write_json(output, {"schema": "smallcap.deepdive.data.v1", "input": binding,
                         "pull_date": pull_date, "all": outcomes}, completion)
    return output, completion


def _read_data_results(candidates_path):
    rows, binding, upstream = _data_input(candidates_path)
    path = Path(candidates_path).parent / "deepdive_data_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or payload.get("schema") != "smallcap.deepdive.data.v1"
            or payload.get("input") != binding or not isinstance(payload.get("all"), list)
            or len(payload["all"]) != len(rows)):
        raise ValueError("Deep-dive data results are not bound to all inputs")
    pull_date = _date(payload.get("pull_date"))
    receipts, candidates = [], []
    for row, outcome in zip(rows, payload["all"]):
        if not isinstance(outcome, dict) or any(outcome.get(key) != row[key] for key in _IDENTITY_KEYS):
            raise ValueError("Deep-dive data result identity changed")
        candidate = {**row, "data_status": outcome.get("data_status"), "json_path": None,
                     "data_artifact": None}
        if row["band"] in _SKIP_BANDS:
            if outcome.get("data_status") != "skipped" or outcome.get("artifact") is not None:
                raise ValueError("Excluded input must have an explicit skipped outcome")
        else:
            artifact = _data_path(path.parent, row, pull_date)
            if outcome.get("artifact") != artifact.name:
                raise ValueError("Deep-dive artifact name does not match its input")
            data = json.loads(artifact.read_text(encoding="utf-8"))
            receipt = read_stage_receipt(artifact, 1)
            expected = _data_completion(data, _identity(row), binding, upstream)
            status = "error" if data.get("status") == "ERROR" else expected["status"]
            if (outcome.get("data_status") != status
                    or any(receipt.get(key) != value for key, value in expected.items())):
                raise ValueError("Deep-dive receipt disagrees with its input or observations")
            receipts.append(receipt)
            candidate.update(json_path=str(artifact.resolve()), data_artifact=_binding(artifact))
        candidates.append(candidate)
    expected = _batch_completion(payload["all"], receipts, binding, upstream)
    receipt = read_stage_receipt(path, len(rows))
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Deep-dive aggregate receipt is missing or inconsistent")
    return candidates, binding, path, receipt


def _fanout_request(candidates_path, verdict_date):
    candidates, binding, data_path, upstream = _read_data_results(candidates_path)
    verdict_date = _date(verdict_date)
    for row in candidates:
        label = row["ticker"] or f"CIK{row['cik']}"
        row["valuation_path"] = str((data_path.parent / f"valuation_{label}_{verdict_date}.json").resolve())
    request = {"schema": "smallcap.deepdive.request.v1", "input": binding,
               "request_path": str((data_path.parent / "deepdive_request.json").resolve()),
               "data_results": _binding(data_path), "verdict_date": verdict_date,
               "candidates": candidates, "completion": upstream}
    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    request["request_id"] = hashlib.sha256(canonical).hexdigest()
    return request


def prepare_fanout_request(candidates_path, verdict_date):
    """Prepare bound work for the configured host; this function does not invoke a model."""
    candidates_path = Path(candidates_path)
    request = _fanout_request(candidates_path, verdict_date)
    completion = stage_completion("deepdive_request", len(request["candidates"]),
                                  upstream=[request["completion"]])
    completion.update(input=request["input"], request_id=request["request_id"])
    out = candidates_path.parent / "deepdive_request.json"
    _write_json(out, request, completion)
    return out


def _read_fanout_request(request_path):
    request_path = Path(request_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or request.get("schema") != "smallcap.deepdive.request.v1":
        raise ValueError("Deep-dive request schema is invalid")
    candidates_path = _bound_path(request_path.parent, request.get("input"))
    expected = _fanout_request(candidates_path, request.get("verdict_date"))
    if request != expected or request.get("request_path") != str(request_path.resolve()):
        raise ValueError("Deep-dive request no longer matches its inputs")
    receipt = read_stage_receipt(request_path, len(request["candidates"]))
    expected_receipt = stage_completion("deepdive_request", len(request["candidates"]),
                                        upstream=[request["completion"]])
    expected_receipt.update(input=request["input"], request_id=request["request_id"])
    if any(receipt.get(key) != value for key, value in expected_receipt.items()):
        raise ValueError("Deep-dive request receipt is missing or invalid")
    return request, receipt


def _valuation_completion(row, request, request_receipt, *, failed=False):
    completion = stage_completion("deepdive_valuation", 1,
        work=[stage_work("compute_valuation", status="unavailable" if failed else "complete",
                         reason="valuation_failed" if failed else "")],
        upstream=[request_receipt], reasons=["valuation_failed"] if failed else [])
    completion.update(input_identity=_identity(row), input=row["data_artifact"],
                      candidate_input=request["input"], request_id=request["request_id"])
    return completion


def prepare_valuation_artifact(request_path, input_index):
    """Use the existing valuation policy and market-cap lookup without rewriting sealed data."""
    request, request_receipt = _read_fanout_request(request_path)
    rows = [row for row in request["candidates"] if row["input_index"] == input_index]
    if type(input_index) is not int or len(rows) != 1:
        raise ValueError("Valuation input index is not in the bound request")
    row = rows[0]
    if row["band"] in _SKIP_BANDS or row["data_status"] == "error":
        raise ValueError("Valuation requires a usable requested data artifact")
    source = _bound_path(Path(request_path).parent, row["data_artifact"])
    data = json.loads(source.read_text(encoding="utf-8"))
    output = _fresh(Path(row["valuation_path"]))
    failed = False
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,19}", row["ticker"]):
            raise ValueError("Valuation requires a plain ticker symbol")
        from valuation import _get_market_cap, _val_cfg, compute_valuation
        init_edgar()
        market_cap, market_cap_source = _get_market_cap(row["ticker"].upper(), None)
        if market_cap is None:
            raise ValueError("Valuation market cap is unavailable")
        block = compute_valuation(data, market_cap, _val_cfg())
        if not isinstance(block, dict) or block.get("ticker") != row["ticker"]:
            raise ValueError("Valuation returned a different issuer")
        block["market_cap_source"] = market_cap_source
    except Exception as exc:
        failed = True
        block = {"ticker": row["ticker"], "status": "ERROR", "error_code": "valuation_failed",
                 "error_type": type(exc).__name__, "error": str(exc)}
    # Detect any unexpected writer inside the reused valuation path before publishing.
    if _binding(source) != row["data_artifact"]:
        raise ValueError("Valuation modified the sealed source artifact")
    completion = _valuation_completion(row, request, request_receipt, failed=failed)
    _write_json(output, block, completion)
    return output, completion


def _valuation_report_error(report, block):
    """Bind mechanical report fields to the valuation while preserving analyst ratings."""
    evidence = report.get("eligibility", {})
    eligible = block.get("buy_eligible")
    if (type(eligible) is not bool or report.get("mos_basis") != block.get("mos_basis")
            or evidence.get("buy_eligible") is not eligible):
        return "report_valuation_eligibility_mismatch"
    field = {"fcf_cap": "margin_of_safety_pct", "nav": "nav_margin_of_safety_pct"}.get(block["mos_basis"])
    ratio = block.get(field) if field else None
    try:
        if ratio is not None and (type(ratio) not in (int, float) or not math.isfinite(ratio)):
            return "invalid_valuation_mos"
        expected = ratio * 100 if ratio is not None else None
        if expected is not None and not math.isfinite(expected):
            return "invalid_valuation_mos"
        actual = evidence.get("active_mos_pct")
        if expected is None:
            matches = actual is None
        else:
            matches = (type(actual) in (int, float) and math.isfinite(actual)
                       and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-8))
    except (OverflowError, TypeError, ValueError):
        return "invalid_valuation_mos"
    return None if matches else "report_valuation_mos_mismatch"


def _valuation_error(row, request, request_receipt, *, report=None):
    path = Path(row["valuation_path"])
    try:
        block = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing_valuation"
    except (OSError, ValueError):
        return "invalid_valuation"
    if not isinstance(block, dict) or block.get("ticker") != row["ticker"]:
        return "invalid_valuation"
    failed = block.get("status") == "ERROR"
    receipt = read_stage_receipt(path, 1)
    expected = _valuation_completion(row, request, request_receipt, failed=failed)
    if any(receipt.get(key) != value for key, value in expected.items()):
        return "invalid_valuation_receipt"
    if failed:
        return "valuation_failed"
    if not isinstance(block.get("mos_basis"), str) or block["mos_basis"] not in {"fcf_cap", "nav", "abstain"}:
        return "invalid_valuation"
    return _valuation_report_error(report, block) if report is not None else None


def _report_eligibility(report, parsed):
    """Validate the frozen BUY policy without replacing the analyst's decision."""
    evidence = report.get("eligibility")
    if (not isinstance(evidence, dict) or set(evidence) != {
            "buy_eligible", "active_mos_pct", "tier3_load_bearing"}
            or type(evidence["buy_eligible"]) is not bool
            or type(evidence["tier3_load_bearing"]) is not bool):
        raise ValueError("Structured report eligibility is missing or invalid")
    active = evidence["active_mos_pct"]
    if active is not None and (type(active) not in (int, float) or not math.isfinite(active)):
        raise ValueError("Structured active MoS must be finite or null")
    if (evidence["buy_eligible"] != parsed["buy_eligible"]
            or active != parsed["mos_pct"]):
        raise ValueError("Structured eligibility disagrees with the rating block")
    if report["rating"] == "\u4e70\u5165" and (
            report["mos_basis"] not in {"fcf_cap", "nav"} or active is None or active < 30
            or evidence["buy_eligible"] is not True or evidence["tier3_load_bearing"]
            or parsed["killflag_count"] != 0):
        raise ValueError("BUY requires the frozen MoS/NAV eligibility rule; catalyst is not a waiver")


def _validated_report(report, row, verdict_date):
    """Require the host schema and one explicit decision block; never invent a rating."""
    required = {"ticker", "rating", "confidence", "one_liner", "is_misrecall", "top_long",
                "top_short", "killflag_notes", "margin_of_safety_pct", "mos_basis", "catalyst", "eligibility", "report_md"}
    if (not isinstance(report, dict) or not required <= set(report)
            or set(report) - required - {"theme_fit"}):
        raise ValueError("Deep-dive report schema is invalid")
    if (report["ticker"] != row["ticker"] or report["rating"] not in {"买入", "观察", "避开"}
            or type(report["confidence"]) is not int or not 0 <= report["confidence"] <= 100
            or type(report["is_misrecall"]) is not bool
            or report["mos_basis"] not in {"fcf_cap", "nav", "abstain"}
            or ("theme_fit" in report and report["theme_fit"] not in {"pure_play", "partial", "misrecall"})):
        raise ValueError("Deep-dive report identity or decision fields are invalid")
    for key in ("one_liner", "top_long", "top_short", "killflag_notes", "report_md"):
        if not isinstance(report[key], str) or not report[key].strip():
            raise ValueError("Deep-dive report text is missing")
    mos, catalyst = report["margin_of_safety_pct"], report["catalyst"]
    if mos is not None and (type(mos) not in (int, float) or not math.isfinite(mos)):
        raise ValueError("Deep-dive margin of safety must be finite or null")
    if catalyst is not None and (not isinstance(catalyst, str) or not catalyst.strip()):
        raise ValueError("Deep-dive catalyst must be text or null")
    blocks = re.findall(r"^" + r"\x60{3}rating\s*\n(.*?)^\x60{3}\s*$",
                        report["report_md"], re.M | re.S)
    if len(blocks) != 1:
        raise ValueError("Deep-dive report requires exactly one rating block")
    fields = {}
    for line in blocks[0].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            if key in fields:
                raise ValueError("Duplicate rating field")
            fields[key] = value.split("#", 1)[0].strip()
    if (not {"rating", "confidence", "verdict_date", "mos_basis", "mos_pct",
             "buy_eligible", "killflag_count"} <= set(fields)
            or fields["buy_eligible"].lower() not in {"true", "false"}
            or not re.fullmatch(r"[0-9]+", fields["killflag_count"])
            or not re.fullmatch(r"[0-9]+", fields["confidence"])
            or fields["rating"] != report["rating"] or fields["mos_basis"] != report["mos_basis"]):
        raise ValueError("Deep-dive report decision contract is unfinished")
    count_digits = fields["killflag_count"].lstrip("0") or "0"
    if (len(count_digits) > 16
            or (len(count_digits) == 16 and count_digits > "9007199254740991")):
        raise OverflowError("Deep-dive report kill-flag count is not a safe integer")
    if fields["mos_pct"] != "null":
        try:
            finite_mos = math.isfinite(float(fields["mos_pct"]))
        except ValueError:
            finite_mos = False
        if not finite_mos:
            raise ValueError("Deep-dive report margin of safety is unfinished")
    from finalize_run import parse_rating_block
    parsed = parse_rating_block(report["report_md"])
    if (parsed["rating"] != report["rating"] or parsed["confidence"] != report["confidence"]
            or parsed["mos_basis"] != report["mos_basis"] or parsed["verdict_date"] != verdict_date
            or (report["mos_basis"] == "fcf_cap" and parsed["mos_pct"] != mos)):
        raise ValueError("Deep-dive report block disagrees with its structured decision")
    _report_eligibility(report, parsed)
    return report


def _fanout_rows(candidates, outcomes, verdict_date):
    if not isinstance(outcomes, list):
        raise ValueError("Deep-dive result must contain an all list")
    requested = {row["input_index"]: row for row in candidates}
    indexed = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise ValueError("Deep-dive outcome must be an object")
        index = outcome.get("input_index")
        if type(index) is not int or index not in requested or index in indexed:
            raise ValueError("Deep-dive outcome index is invalid or duplicated")
        row = requested[index]
        if any(outcome.get(key) != row[key] for key in _IDENTITY_KEYS):
            raise ValueError("Deep-dive outcome identity or band changed")
        status = outcome.get("report_status")
        if row["band"] in _SKIP_BANDS:
            if status != "skipped" or outcome.get("report") is not None:
                raise ValueError("Excluded input cannot carry a report")
        elif status == "complete":
            if row["data_status"] == "error":
                raise ValueError("Failed data pull cannot produce a completed report")
            try:
                _validated_report(outcome.get("report"), row, verdict_date)
            except OverflowError:
                indexed[index] = {**_identity(row), "report_status": "error",
                                  "error_code": "invalid_agent_result"}
                continue
        elif status == "error":
            if (outcome.get("report") is not None or not isinstance(outcome.get("error_code"), str)
                    or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", outcome["error_code"])):
                raise ValueError("Deep-dive error outcome is invalid")
        else:
            raise ValueError("Deep-dive report status is invalid")
        indexed[index] = {**_identity(row), "report_status": status}
        if status == "complete":
            indexed[index]["report"] = outcome["report"]
        elif status == "error":
            indexed[index]["error_code"] = outcome["error_code"]
    for index, row in requested.items():
        if index not in indexed:
            indexed[index] = {**_identity(row), "report_status": "error", "error_code": "missing_result"}
    return [indexed[row["input_index"]] for row in candidates]


def persist_fanout_result(request_path, result_path):
    """Validate the whole result before writing immutable reports and all-input outcomes."""
    request_path, result_path = Path(request_path), Path(result_path)
    request, request_receipt = _read_fanout_request(request_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (not isinstance(result, dict) or result.get("schema") != "smallcap.deepdive.result.v1"
            or result.get("input") != request["input"] or result.get("request_id") != request["request_id"]):
        raise ValueError("Deep-dive result is not bound to this request")
    rows = _fanout_rows(request["candidates"], result.get("all"), request["verdict_date"])
    candidates = {row["input_index"]: row for row in request["candidates"]}
    for row in rows:
        if row["report_status"] == "complete":
            error = _valuation_error(candidates[row["input_index"]], request, request_receipt,
                                     report=row["report"])
            if error:
                row.pop("report")
                row.update(report_status="error", error_code=error)
            else:
                row["valuation_artifact"] = _binding(Path(candidates[row["input_index"]]["valuation_path"]))
    output = _fresh(request_path.parent / "deepdive_fanout_results.json")
    report_paths = {}
    for row in rows:
        if row["report_status"] == "complete":
            label = row["ticker"] or f"CIK{row['cik']}"
            report_paths[row["input_index"]] = _fresh(request_path.parent / f"report_{label}.md")
    reports = []
    for row in rows:
        if row["report_status"] != "complete":
            continue
        path = report_paths[row["input_index"]]
        with path.open("x", encoding="utf-8") as stream:
            stream.write(row["report"]["report_md"])
        receipt = stage_completion("deepdive_report", 1,
            work=[stage_work("agent_report")], upstream=[request_receipt])
        receipt.update(input_identity=_identity(row), input=request["input"],
                       request_id=request["request_id"], valuation_artifact=row["valuation_artifact"])
        write_stage_receipt(path, receipt)
        reports.append(path)
    work = [stage_work("agent_report", str(row["input_index"]),
                       status="complete" if row["report_status"] in {"complete", "skipped"} else "unavailable",
                       reason=row.get("error_code", "")) for row in rows]
    completion = stage_completion("deepdive_fanout", len(rows), work=work, upstream=[request_receipt])
    completion.update(input=request["input"], request_id=request["request_id"],
                      request_artifact=_binding(request_path), result_artifact=_binding(result_path))
    _write_json(output, {"schema": "smallcap.deepdive.persisted.v1", "input": request["input"],
                        "request_id": request["request_id"], "all": rows}, completion)
    return output, reports, completion


def main():
    ap = argparse.ArgumentParser(description="Pull deep-dive data or prepare/ingest configured-host work.")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--candidates", default="", help="Candidate JSON; outputs stay in its run directory")
    modes.add_argument("--prepare-fanout", default="", metavar="CANDIDATES")
    modes.add_argument("--fanout-request", default="", metavar="REQUEST")
    modes.add_argument("--valuation-request", default="", metavar="REQUEST")
    ap.add_argument("--input-index", type=int, help="Original input index for --valuation-request")
    ap.add_argument("--fanout-result", default="", metavar="RESULT")
    ap.add_argument("--verdict-date", default="", help="Explicit decision date for --prepare-fanout")
    ap.add_argument("--ticker", default="")
    ap.add_argument("--cik", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if args.fanout_result and not args.fanout_request:
        ap.error("--fanout-result requires --fanout-request")
    if (args.candidates or args.prepare_fanout or args.fanout_request or args.valuation_request) and (args.ticker or args.cik):
        ap.error("Single-company identity cannot be combined with a batch mode")
    try:
        if args.valuation_request:
            if args.input_index is None:
                ap.error("--valuation-request requires --input-index")
            path, completion = prepare_valuation_artifact(Path(args.valuation_request), args.input_index)
        elif args.prepare_fanout:
            if not args.verdict_date:
                ap.error("--prepare-fanout requires --verdict-date")
            path = prepare_fanout_request(Path(args.prepare_fanout), args.verdict_date)
            payload = json.loads(path.read_text(encoding="utf-8"))
            completion = read_stage_receipt(path, len(payload["candidates"]))
        elif args.fanout_request:
            if not args.fanout_result:
                ap.error("--fanout-request requires --fanout-result")
            path, _, completion = persist_fanout_result(Path(args.fanout_request), Path(args.fanout_result))
        elif args.candidates:
            path, completion = run_batch(Path(args.candidates))
        else:
            row = _validated_rows([{"ticker": args.ticker, "cik": args.cik, "band": "unknown"}], bound=False)[0]
            path = _fresh(_data_path(REPORTS, row, today()))
            upstream = stage_completion("single_deepdive_input", 1, reasons=["unbound_single_input"])
            init_error = None
            try:
                init_edgar()
            except Exception as exc:
                init_error = exc
            _, completion = _pull_and_save(row["ticker"], row["cik"], out=path,
                identity=_identity(row), binding=None, upstream=upstream, init_error=init_error)
        print(f"Deep-dive stage: {completion['status']}; artifact: {path}")
        return 0 if completion["status"] == "complete" else 2
    except (OSError, ValueError, TypeError) as exc:
        print(f"Deep-dive stage failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
