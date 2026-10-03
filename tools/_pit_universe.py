"""
_pit_universe.py — PIECE 2 of the point-in-time (PIT) backtest machinery (spec:
docs/backtest-2026-06/spec.md).

Reconstruct the SURVIVORSHIP-SAFE universe of theme filers as-of a date T.

Why this is survivorship-safe (the whole point — see spec §"Why free EDGAR makes
this survivorship-safe"): SEC EDGAR is point-in-time and immutable. A filing's
`filingDate` and original accession never change, and a company's submissions
history PERSISTS after it delists or blows up. So for any as-of date T we can
enumerate every entity that was a *filer* in the theme's dedicated SIC and had a
10-K/10-Q with `filingDate <= T` — INCLUDING entities that later delisted. We do
NOT exclude inactive/delisted filers; their EDGAR record is exactly what lets the
de-risk scanner be graded on avoiding blowups. yfinance cannot do this (it drops
delisted names); EDGAR can.

Method (most reliable free EDGAR path):
  1. SEED the CIK set from the dedicated-SIC browse enumeration — reuse
     filter_by_sic.sic_reverse_recall (browse-edgar getcompany?SIC=...), the same
     SIC recall FLOOR the live discover path uses. This is the recall channel;
     each seed row is tagged recall_channel="sic_reverse" by that helper.
     (Spec: "seed the CIK set from the SIC browse/full-text recall.")
  2. For EACH seed CIK, read its per-CIK submissions index
     (data.sec.gov/submissions/CIK<10>.json, plus any older "files" overflow
     shards) and retain observed periodic filings with filingDate <= T. This
     dates the observed filing evidence. Current SIC membership and missing
     source work still limit historical coverage; they cannot establish a
     complete point-in-time universe.

Each surviving row is {cik, name, ticker, recall_channel, first_periodic_filing,
earliest_filing_asof, delisted_after_asof?}. Dated symbol facts and current-symbol
fallbacks are distinguished in completion.identities. Missing symbols remain
unavailable evidence; dropped_no_asof_ticker counts unresolved identities, not
proven nontrading entities. recall_channel records how the CIK
entered the universe (currently always "sic_reverse" — the SIC floor is the seed;
the field is preserved so a future FTS-as-of seed can tag "fts"/"both" via the
same union semantics as filter_by_sic.union_recall).

Themes with no dedicated SIC (not in filter_by_sic.THEME_SIC) return [] — opt-in
by construction, mirroring the live SIC-floor behavior (spec: "Fall back to FTS-as-of
where no SIC floor"; that FTS-as-of seed is a future add — for the 5 panel themes,
all are SIC-floored).

Everything here is ADDITIVE and read-only. It touches no live path.

CLI: --selftest only (offline, mock-fetch unit assertions).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import http_get
from filter_by_sic import (theme_sics, sic_reverse_recall, StageRows,
                           stage_work, rows_completion, _canonical_cik)

# Periodic ("was a filer") forms that establish theme-filer status as-of T. A
# company is a theme filer as-of T iff it filed one of these on/before T. Foreign
# annual reports (20-F/40-F) count too, they are the foreign-filer analogue of the
# 10-K and a foreign theme member is still a member (it just carries abstain
# downstream). Amendments (…/A) count as well (still a periodic disclosure event).
PERIODIC_FORMS = ("10-K", "10-Q", "20-F", "40-F")

_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
_SUBMISSIONS_SHARD = "https://data.sec.gov/submissions/{name}"
# Point-in-time ticker resolution (FIX 2): dei:TradingSymbol is the cover-page
# trading symbol an entity disclosed on its periodic filings. It is survivorship-
# safe: a name that listed in 2019 and delisted in 2021 STILL carries its
# 2019/2020 TradingSymbol fact in EDGAR (filings are immutable), so we can resolve
# the symbol an investor at as-of T would have traded under, even for names that
# no longer exist today. This is exactly what `submissions.tickers` (the CURRENT
# ticker list) cannot give us for delisted names (it goes empty after delisting).
_DEI_CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/dei/{concept}.json"


def _is_periodic(form: str) -> bool:
    """True if `form` is a periodic report (10-K/10-Q/20-F/40-F, incl. /A amendments).

    Matched by prefix so "10-K", "10-K/A", "10-KT", "20-F/A" all count. Case- and
    whitespace-insensitive.
    """
    f = str(form or "").strip().upper()
    if not f:
        return False
    return any(f.startswith(p) for p in PERIODIC_FORMS)


def _scan_recent_block(recent: dict, asof: str) -> tuple[bool, str | None, str | None]:
    """Scan ONE submissions `recent`-shaped block (parallel form/filingDate arrays).

    Pure helper (no network) so the selftest exercises the date/form logic on a
    fixture. Returns (has_periodic_le_asof, earliest_periodic_filing_date,
    latest_periodic_filing_date) over periodic forms with filingDate <= asof.
      - has_periodic_le_asof — at least one periodic report filed on/before asof.
      - earliest_periodic_filing_date — MIN filingDate among periodic forms <= asof
        (used to assert "first filing before asof"); None if none qualify.
      - latest_periodic_filing_date — MAX filingDate among periodic forms <= asof
        (the most recent disclosure an investor at asof would have had); None if none.
    Guarded: a malformed block degrades to (False, None, None), never raises.
    """
    try:
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
    except AttributeError:
        return (False, None, None)
    earliest: str | None = None
    latest: str | None = None
    n = min(len(forms), len(dates))
    for i in range(n):
        fd = str(dates[i] or "")
        if not fd or fd > asof:
            continue
        if not _is_periodic(forms[i]):
            continue
        if earliest is None or fd < earliest:
            earliest = fd
        if latest is None or fd > latest:
            latest = fd
    return (earliest is not None, earliest, latest)


def _latest_string_fact_le_asof(units: dict, asof: str, evidence=None) -> str | None:
    """Pick the latest-FILED non-empty string fact value with filed <= asof.

    Pure helper (no network) so the selftest exercises the date logic on a
    fixture. `units` is a companyconcept `units` dict (concept -> list of fact
    rows). dei:TradingSymbol is a text concept, so its facts live under a unit
    key whose exact name varies; we iterate EVERY unit list rather than assume one
    key. Each fact carries its own "filed" date — we keep only facts disclosed
    on/before asof (no look-ahead) and return the value of the LATEST-FILED such
    fact (the most recent symbol an investor at asof would have seen). Ties on
    "filed" resolve to later API order (mirrors the concept-series dedup). Returns
    a stripped, upper-cased symbol, or None if nothing qualifies. Guarded.
    """
    best_filed: str | None = None
    best_val: str | None = None
    try:
        unit_lists = list(units.values())
    except AttributeError:
        return None
    for vals in unit_lists:
        if not isinstance(vals, list):
            continue
        for v in vals:
            try:
                filed = str(v.get("filed") or "")
            except AttributeError:
                continue
            try:
                parsed = datetime.strptime(filed, "%Y-%m-%d")
            except ValueError:
                continue
            if parsed.strftime("%Y-%m-%d") != filed:
                continue
            if filed > asof:  # future-filed -> drop (no look-ahead)
                continue
            raw = v.get("val")
            if not isinstance(raw, str):
                continue
            sym = str(raw or "").strip()
            if not sym:
                continue
            # Latest-filed wins; tie -> later API order (>= keeps last seen at same date).
            if best_filed is None or filed >= best_filed:
                best_filed = filed
                best_val = sym.upper()
    if evidence is not None:
        evidence["filed"] = best_filed
    return best_val


def cik_trading_symbol_asof(cik: str | int, asof: str, fetch=None,
                            submissions_tickers=None, evidence=None) -> str | None:
    """Resolve a POINT-IN-TIME trading symbol for ONE CIK as-of `asof`.

    Survivorship-safe ticker resolution (FIX 2). Strategy:
      1. PRIMARY — dei:TradingSymbol companyconcept: the latest fact filed <= asof.
         This is the cover-page symbol the entity disclosed on a filing visible at
         asof. It persists in EDGAR even after the name delists, so a later-delisted
         issuer still resolves to the symbol it traded under as-of T.
      2. FALLBACK — `submissions.tickers` (the CURRENT ticker list passed in by the
         caller via `submissions_tickers`): used ONLY when dei:TradingSymbol has no
         fact <= asof. This catches still-listed names whose XBRL cover-page tag is
         sparse. It is NOT survivorship-safe (goes empty for delisted names), so it
         is strictly a secondary path — the primary path is what keeps delisted
         names resolvable.
    Returns an upper-cased symbol or None. The optional evidence mapping records
    the date and source; current-symbol fallback is not historical identity proof.
    None means unavailable identity evidence, not proven nontrading.
    `fetch` and `submissions_tickers` are injectable for the offline selftest.
    """
    if fetch is None:
        fetch = http_get
    datetime.strptime(asof, "%Y-%m-%d")
    evidence = evidence if evidence is not None else {}
    evidence.update({"asof": asof, "source": "unavailable", "filed": None,
                     "pit_proven": False, "work": [],
                     "observed_at": datetime.now(timezone.utc).isoformat()})
    cik10 = _canonical_cik(cik).zfill(10)

    # PRIMARY: dei:TradingSymbol, latest fact filed <= asof.
    try:
        r = fetch(_DEI_CONCEPT.format(cik10=cik10, concept="TradingSymbol"), timeout=20)
        if getattr(r, "status_code", 200) != 200:
            raise ValueError("symbol request failed")
        doc = r.json()
        if (not isinstance(doc, dict) or _canonical_cik(doc.get("cik")).zfill(10) != cik10
                or doc.get("taxonomy") != "dei" or doc.get("tag") != "TradingSymbol"
                or not isinstance(doc.get("units"), dict)):
            raise ValueError("invalid symbol envelope")
        units = doc["units"]
        if any(not isinstance(values, list) or any(not isinstance(v, dict) for v in values)
               for values in units.values()):
            raise ValueError("invalid symbol facts")
        sym = _latest_string_fact_le_asof(units, asof, evidence)
        evidence["work"].append(stage_work("dei_trading_symbol", cik10))
        if sym:
            evidence.update({"source": "dei_trading_symbol", "pit_proven": True, "symbol": sym})
            return sym
    except Exception:
        evidence["work"].append(stage_work("dei_trading_symbol", cik10,
                                           status="unavailable", reason="request_or_schema_failed"))

    # FALLBACK: current submissions tickers (still-listed names only).
    if submissions_tickers:
        for t in submissions_tickers:
            s = str(t or "").strip()
            if s:
                evidence.update({"source": "current_submissions", "symbol": s.upper()})
                evidence["work"].append(stage_work("symbol_identity", cik10,
                    status="unavailable", reason="current_symbol_unproved_asof"))
                return s.upper()
    evidence["work"].append(stage_work("symbol_identity", cik10,
                                       status="unavailable", reason="symbol_evidence_unavailable"))
    return None


def _valid_filing_block(block):
    if not isinstance(block, dict):
        return False
    forms, dates = block.get("form"), block.get("filingDate")
    if not isinstance(forms, list) or not isinstance(dates, list) or len(forms) != len(dates):
        return False
    try:
        for form, filed in zip(forms, dates):
            if not isinstance(form, str) or not form or not isinstance(filed, str):
                return False
            if datetime.strptime(filed, "%Y-%m-%d").strftime("%Y-%m-%d") != filed:
                return False
    except ValueError:
        return False
    return True


def cik_periodic_asof(cik: str | int, asof: str, fetch=None,
                      sleep: float = 0.0, resolve_ticker: bool = True, evidence=None) -> dict | None:
    """PIT submissions probe for ONE CIK: was it a periodic filer on/before asof?

    Reads the per-CIK submissions index (and any older "files" overflow shards, so
    pre-2015 history is not missed for early as-of dates) and scans every periodic
    report (10-K/10-Q/20-F/40-F, incl. /A) for filingDate <= asof.

    Returns None when no qualifying filing was observed or retrieval failed.
    Pass an evidence dict to distinguish those outcomes and retain failed shards.
    Otherwise returns:
      {
        "cik": <plain digit string>,
        "name": <entity name from submissions>,
        "ticker": <POINT-IN-TIME symbol as-of asof (dei:TradingSymbol filed<=asof,
                   submissions.tickers fallback), or "" if none — see below>,
        "first_periodic_filing": <MIN periodic filingDate seen, any date>,
        "earliest_filing_asof": <MIN periodic filingDate <= asof>,
        "latest_filing_asof": <MAX periodic filingDate <= asof>,
        "delisted_after_asof": <bool | None>,  # see below
      }
    `ticker` uses a dated dei:TradingSymbol fact when available. Current-symbol
    fallback is explicitly unproved historical identity in evidence["identity"].
    An empty ticker means unavailable symbol evidence. Set resolve_ticker=False
    to skip the extra companyconcept fetch.
    `delisted_after_asof` is a best-effort flag derived from whether ANY periodic
    filing exists AFTER asof: if the entity kept filing periodic reports after asof
    it was clearly still active (False); if its last periodic report is on/before
    asof it MAY have delisted (True) — survivorship-safe either way, because we KEEP
    the row regardless (the realized return / last-close logic lives in PIECE 3).
    This legacy filing-activity flag is not delisting proof; evidence records
    delisting_proven=False. fetch is injectable for offline selftests.
    """
    if fetch is None:
        fetch = http_get
    datetime.strptime(asof, "%Y-%m-%d")
    evidence = evidence if evidence is not None else {}
    evidence.update({"asof": asof, "work": [], "identity": {}, "outcome": "unavailable",
                     "delisting_proven": False})
    try:
        cik_plain = _canonical_cik(cik)
    except ValueError:
        evidence["work"].append(stage_work("submissions", status="invalid", reason="invalid_query_identity"))
        return None
    cik10 = cik_plain.zfill(10)

    blocks: list[dict] = []
    name = ""
    ticker = ""
    first_periodic_any: str | None = None
    has_periodic_after_asof = False

    try:
        r = fetch(_SUBMISSIONS.format(cik10=cik10), timeout=20)
        if getattr(r, "status_code", 200) != 200:
            raise ValueError("submissions request failed")
        doc = r.json()
        if not isinstance(doc, dict) or not isinstance(doc.get("filings"), dict):
            raise ValueError("invalid submissions envelope")
    except Exception:
        evidence["work"].append(stage_work("submissions", cik_plain,
                                           status="unavailable", reason="request_or_schema_failed"))
        return None

    try:
        if _canonical_cik(doc.get("cik")) != cik_plain:
            raise ValueError("submissions issuer mismatch")
    except ValueError:
        evidence["work"].append(stage_work("submissions", cik_plain,
                                           status="invalid", reason="invalid_response_identity"))
        return None

    name = str(doc.get("name", "") or "")
    current_tickers = doc.get("tickers") or []
    if not isinstance(current_tickers, list) or any(not isinstance(t, str) for t in current_tickers):
        current_tickers = []
        evidence["work"].append(stage_work("submissions_tickers", cik_plain,
                                           status="unavailable", reason="invalid_ticker_list"))
    # POINT-IN-TIME ticker (FIX 2): dei:TradingSymbol filed<=asof (survivorship-safe),
    # falling back to current submissions tickers only for still-listed names.
    if resolve_ticker:
        ticker = cik_trading_symbol_asof(
            cik_plain, asof, fetch=fetch, submissions_tickers=current_tickers,
            evidence=evidence["identity"]) or ""

    filings = doc.get("filings") or {}
    recent = filings.get("recent")
    if _valid_filing_block(recent):
        blocks.append(recent)
        evidence["work"].append(stage_work("submissions", cik_plain))
    else:
        evidence["work"].append(stage_work("submissions", cik_plain,
                                           status="unavailable", reason="invalid_recent_block"))

    # Older filings spill into "files" overflow shards (each a {form,filingDate,...}
    # block). For early as-of dates (e.g. 2020) the qualifying first 10-K may live
    # ONLY in a shard. Failed shards remain explicit unresolved work in evidence.
    shards = filings.get("files")
    if not isinstance(shards, list):
        evidence["work"].append(stage_work("submissions_shards", cik_plain,
                                           status="unavailable", reason="missing_shard_index"))
        shards = []
    for shard in shards:
        sname = str(shard.get("name", "") or "") if isinstance(shard, dict) else ""
        if not sname:
            evidence["work"].append(stage_work("submissions_shard", cik_plain,
                                               status="unavailable", reason="invalid_shard_descriptor"))
            continue
        if sleep:
            time.sleep(sleep)
        try:
            sr = fetch(_SUBMISSIONS_SHARD.format(name=sname), timeout=20)
            if getattr(sr, "status_code", 200) != 200:
                raise ValueError("shard request failed")
            block = sr.json()
            if not _valid_filing_block(block):
                raise ValueError("invalid shard block")
            blocks.append(block)
            evidence["work"].append(stage_work("submissions_shard", sname))
        except Exception:
            evidence["work"].append(stage_work("submissions_shard", sname,
                                               status="unavailable", reason="request_or_schema_failed"))
            continue

    earliest_asof: str | None = None
    latest_asof: str | None = None
    has_periodic_le = False
    for blk in blocks:
        ok, e_asof, l_asof = _scan_recent_block(blk, asof)
        if ok:
            has_periodic_le = True
            if e_asof and (earliest_asof is None or e_asof < earliest_asof):
                earliest_asof = e_asof
            if l_asof and (latest_asof is None or l_asof > latest_asof):
                latest_asof = l_asof
        # Track ANY periodic filing (any date) for first_periodic + after-asof flag.
        try:
            forms = blk.get("form") or []
            dates = blk.get("filingDate") or []
        except AttributeError:
            forms, dates = [], []
        for i in range(min(len(forms), len(dates))):
            fd = str(dates[i] or "")
            if not fd or not _is_periodic(forms[i]):
                continue
            if first_periodic_any is None or fd < first_periodic_any:
                first_periodic_any = fd
            if fd > asof:
                has_periodic_after_asof = True

    if not has_periodic_le:
        evidence["outcome"] = ("no_periodic_observed" if all(
            item["status"] == "complete" for item in evidence["work"]) else "unavailable")
        return None

    evidence["outcome"] = "periodic_observed"

    return {
        "cik": cik_plain,
        "name": name,
        "ticker": ticker,
        "first_periodic_filing": first_periodic_any,
        "earliest_filing_asof": earliest_asof,
        "latest_filing_asof": latest_asof,
        # If it filed periodic reports AFTER asof it was still active then -> False.
        # If its last periodic report is on/before asof it may have delisted -> True.
        "delisted_after_asof": (False if has_periodic_after_asof else True),
    }


def pit_universe(theme: str, asof: str, fetch=None, max_pages: int = 20,
                 sleep: float = 0.0, seed_fn=None, probe_fn=None,
                 return_stats: bool = False):
    """Observed historical theme candidates as-of `asof` (YYYY-MM-DD).

    Returns a list of {cik, name, ticker, recall_channel, first_periodic_filing,
    earliest_filing_asof, latest_filing_asof, delisted_after_asof} for each observed entity
    that (a) lives in the theme's dedicated SIC (the recall seed), (b) had a
    10-K/10-Q (or 20-F/40-F) with filingDate <= asof — INCLUDING entities that
    later delisted (NOT excluded) — AND (c) has a resolved symbol. Completion
    evidence distinguishes dated facts from unproved current-symbol fallback.
    A theme with no historical seed returns unavailable empty rows.

    The existing symbol-required output selection is preserved. Missing symbols
    remain unresolved identities in the evidence. Neither a current SIC seed nor
    a successful symbol lookup establishes historical universe completeness.

    return_stats=False (default) -> the survivor list (backward-compatible: the
    harness's `len(universe)` and per-row access are unchanged).
    return_stats=True -> (survivors, stats) where stats = {
        "seeds": <#unique seed CIKs probed>,
        "periodic_filers": <#that were periodic filers <= asof>,
        "dropped_no_asof_ticker": <#periodic filers DROPPED for no as-of ticker>,
        "kept": <#survivors (== len(survivors))>,
      }. The harness (FIX 3) surfaces dropped_no_asof_ticker per cell.

    seed_fn / probe_fn are injectable for the offline selftest:
      seed_fn(theme)  -> list of {cik, name, recall_channel} seed rows
                         (defaults to filter_by_sic.sic_reverse_recall, which uses
                         browse-edgar by the theme's dedicated SIC).
      probe_fn(cik, asof) -> the cik_periodic_asof result dict or None.
    """
    if seed_fn is None:
        def seed_fn(t):
            return sic_reverse_recall(t, fetch=fetch, max_pages=max_pages)
    use_default_probe = probe_fn is None
    datetime.strptime(asof, "%Y-%m-%d")
    if max_pages < 1 or sleep < 0:
        raise ValueError("max_pages must be positive and sleep nonnegative")

    if not theme_sics(theme):
        # No dedicated SIC -> no SIC seed. (FTS-as-of seed is a future add per spec.)
        empty = StageRows(stage="pit_universe", reasons=["no_historical_seed_for_theme"])
        stats = {"seeds": 0, "periodic_filers": 0, "dropped_no_asof_ticker": 0,
                 "kept": 0, "unavailable_probes": 0, "unproved_historical_symbols": 0,
                 "completion": empty.completion}
        return (empty, stats) if return_stats else empty

    try:
        seeds = seed_fn(theme)
    except Exception:
        seeds = StageRows(stage="pit_seed", work=[stage_work(
            "sic_seed", theme, status="unavailable", reason="seed_failed")])
    out: list[dict] = []
    seen: set[str] = set()
    n_seeds = 0
    n_periodic = 0
    n_dropped_no_ticker = 0
    n_unavailable = 0
    n_unproved = 0
    work, identities = [], []
    for s in seeds:
        cik = str(s.get("cik", "")).split(".")[0].strip().lstrip("0") or ""
        if not cik or cik in seen:
            continue
        seen.add(cik)
        n_seeds += 1
        if sleep:
            time.sleep(sleep)
        probe_evidence = {}
        try:
            if use_default_probe:
                probe = cik_periodic_asof(cik, asof, fetch=fetch, sleep=sleep,
                                          evidence=probe_evidence)
            else:
                probe = probe_fn(cik, asof)
                probe_evidence = {"outcome": "unavailable", "work": [stage_work(
                    "periodic_probe", cik, status="unavailable", reason="missing_probe_evidence")]}
        except Exception:
            probe = None
            probe_evidence["outcome"] = "unavailable"
            probe_evidence.setdefault("work", []).append(stage_work(
                "periodic_probe", cik, status="unavailable", reason="probe_failed"))
        work.extend(probe_evidence.get("work", []))
        identity = probe_evidence.get("identity", {})
        work.extend(identity.get("work", []))
        identities.append({"cik": cik, **probe_evidence})
        if probe is None:
            if probe_evidence.get("outcome") != "no_periodic_observed":
                n_unavailable += 1
            continue
        n_periodic += 1
        # Preserve the existing output selection while recording unresolved identity.
        # A missing symbol is unavailable evidence, never proof of nontrading.
        ticker = str(probe.get("ticker", "") or "").strip()
        if not ticker:
            n_dropped_no_ticker += 1
            work.append(stage_work("symbol_identity", cik, status="unavailable",
                                   reason="symbol_evidence_unavailable"))
            continue
        if not identity.get("pit_proven", False):
            n_unproved += 1
            work.append(stage_work("symbol_identity", cik, status="unavailable",
                                   reason="historical_identity_unproved"))
        row = dict(probe)
        row["ticker"] = ticker.upper()
        # Preserve the recall channel the seed carried (sic_reverse today; the union
        # semantics from filter_by_sic make "fts"/"both" possible with a future seed).
        row["recall_channel"] = str(s.get("recall_channel", "") or "sic_reverse")
        # Seed name is a reasonable fallback if submissions name was blank.
        if not row.get("name"):
            row["name"] = str(s.get("name", "") or "")
        out.append(row)
    out = StageRows(out, stage="pit_universe", work=work,
                    upstream=[rows_completion(seeds)],
                    reasons=["historical_seed_coverage_unproved"])
    out.completion["asof"] = asof
    out.completion["identities"] = identities
    out.completion["coverage_scope"] = "current_sic_seed_and_observed_submissions"
    if return_stats:
        stats = {
            "seeds": n_seeds,
            "periodic_filers": n_periodic,
            "dropped_no_asof_ticker": n_dropped_no_ticker,
            "kept": len(out),
            "unavailable_probes": n_unavailable,
            "unproved_historical_symbols": n_unproved,
            "completion": out.completion,
        }
        return out, stats
    return out


def _selftest() -> None:
    """Offline (mock/guarded) PIT-universe unit assertions. No network."""
    from make_fixtures import source36_pit_submissions
    submissions = source36_pit_submissions()

    # ----- _is_periodic: periodic-form prefix matcher --------------------------
    assert _is_periodic("10-K") and _is_periodic("10-Q"), "10-K/10-Q are periodic"
    assert _is_periodic("10-K/A") and _is_periodic("20-F/A"), "amendments are periodic"
    assert _is_periodic("20-F") and _is_periodic("40-F"), "foreign annuals are periodic"
    assert not _is_periodic("8-K"), "8-K is NOT periodic"
    assert not _is_periodic("4"), "Form 4 (insider) is NOT periodic"
    assert not _is_periodic(""), "blank form is NOT periodic"

    # ----- _scan_recent_block: date/form filtering on a parallel-array block ----
    blk = {
        "form":       ["8-K", "10-K",      "4",          "10-Q",      "10-K"],
        "filingDate": ["2019-01-01", "2019-03-15", "2020-02-01", "2020-08-10", "2021-03-15"],
    }
    ok, earliest, latest = _scan_recent_block(blk, "2020-06-30")
    assert ok, "must find a periodic filing <= 2020-06-30"
    assert earliest == "2019-03-15", f"earliest periodic <= asof: {earliest}"
    assert latest == "2020-08-10" or latest == "2019-03-15", f"latest sanity: {latest}"
    # latest must be the MAX periodic filingDate <= asof (10-Q 2020-08-10 is AFTER asof,
    # so it must NOT count; the 2021 10-K is after asof too) -> latest == 2019-03-15.
    assert latest == "2019-03-15", f"latest periodic <= asof must exclude post-asof filings: {latest}"
    # A block whose only periodic filing is AFTER asof -> not a filer yet.
    blk_future = {"form": ["10-K"], "filingDate": ["2025-03-15"]}
    okf, _, _ = _scan_recent_block(blk_future, "2020-06-30")
    assert not okf, "a first 10-K filed AFTER asof must NOT qualify the CIK"
    # Malformed block degrades, never raises.
    assert _scan_recent_block({}, "2020-06-30") == (False, None, None), "empty block guard"

    # ----- cik_periodic_asof: per-CIK submissions probe (mock fetch) -----------
    class _Resp:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status
        def json(self):
            return self._payload

    asof = "2020-06-30"

    # (A) A CIK whose ONLY filing is a single 10-K BEFORE asof -> INCLUDED. It also
    #     has no periodic filing after asof -> delisted_after_asof flag True (kept).
    sub_only_before = submissions['sub_only_before']
    def _fetch_A(url, params=None, timeout=20):
        return _Resp(sub_only_before)
    rA = cik_periodic_asof("0000111111", asof, fetch=_fetch_A)
    assert rA is not None, "CIK whose only filing is BEFORE asof MUST be included"
    assert rA["cik"] == "111111", f"cik normalized: {rA['cik']}"
    assert rA["earliest_filing_asof"] == "2018-04-01", f"earliest<=asof: {rA}"
    assert rA["delisted_after_asof"] is True, (
        "only-before filer with nothing after asof -> delisted_after_asof True (still KEPT)")

    # (B) A CIK whose FIRST filing is AFTER asof -> EXCLUDED (was not a filer yet).
    sub_only_after = submissions['sub_only_after']
    def _fetch_B(url, params=None, timeout=20):
        return _Resp(sub_only_after)
    rB = cik_periodic_asof("0000222222", asof, fetch=_fetch_B)
    assert rB is None, "CIK whose first periodic filing is AFTER asof MUST be excluded"

    # (C) A later-DELISTED filer: filed before asof, then stopped (last 10-K = 2019)
    #     -> INCLUDED and NOT dropped (delisted_after_asof True). The whole point.
    sub_delisted = submissions['sub_delisted']
    def _fetch_C(url, params=None, timeout=20):
        return _Resp(sub_delisted)
    rC = cik_periodic_asof("0000333333", asof, fetch=_fetch_C)
    assert rC is not None, "a LATER-DELISTED filer (filings persist) MUST NOT be dropped"
    assert rC["delisted_after_asof"] is True, "delisted filer flagged, still kept"
    assert rC["latest_filing_asof"] == "2019-03-01", f"latest<=asof for delisted: {rC}"

    # (D) A still-active filer (kept filing AFTER asof) -> delisted_after_asof False.
    sub_active = submissions['sub_active']
    def _fetch_D(url, params=None, timeout=20):
        return _Resp(sub_active)
    rD = cik_periodic_asof("0000444444", asof, fetch=_fetch_D)
    assert rD is not None and rD["delisted_after_asof"] is False, (
        "a filer that kept filing AFTER asof was still active -> delisted_after_asof False")

    # (E) Overflow "files" shard: the qualifying first 10-K lives ONLY in a shard
    #     (recent has only post-asof + non-periodic forms). Must still be INCLUDED.
    sub_shard_main = submissions['sub_shard_main']
    shard_payload = {"form": ["10-K", "10-Q"], "filingDate": ["2010-03-01", "2011-08-01"]}
    def _fetch_E(url, params=None, timeout=20):
        if "submissions-001" in url:
            return _Resp(shard_payload)
        return _Resp(sub_shard_main)
    rE = cik_periodic_asof("0000555555", asof, fetch=_fetch_E)
    assert rE is not None, "overflow-shard-only pre-asof 10-K must still qualify the CIK"
    assert rE["earliest_filing_asof"] == "2010-03-01", f"shard earliest<=asof: {rE}"
    # recent has a 2022 10-K (after asof) -> still active -> delisted_after_asof False.
    assert rE["delisted_after_asof"] is False, "post-asof shard-main 10-K -> active"

    # (F) Non-200 submissions response -> None (guarded, no crash).
    def _fetch_404(url, params=None, timeout=20):
        return _Resp({}, status=404)
    assert cik_periodic_asof("0000666666", asof, fetch=_fetch_404) is None, "404 -> None"

    # ----- FIX 2: _latest_string_fact_le_asof, PIT string-fact date logic ------
    # dei:TradingSymbol facts live under an arbitrary unit key; iterate all lists.
    # Pick the LATEST-FILED fact with filed<=asof; ignore facts filed AFTER asof.
    units_ts = {
        "USD": [  # (unit key name is irrelevant; the helper scans every list)
            {"val": "OLDSYM", "filed": "2018-03-15", "end": "2017-12-31"},
            {"val": "ASOFSYM", "filed": "2020-03-15", "end": "2019-12-31"},
            {"val": "FUTURESYM", "filed": "2021-03-15", "end": "2020-12-31"},  # after asof
        ],
    }
    assert _latest_string_fact_le_asof(units_ts, asof) == "ASOFSYM", (
        "latest TradingSymbol fact filed<=asof must win, ignoring post-asof facts")
    # Only a future-filed fact -> None (a name that first disclosed its symbol AFTER asof).
    units_future = {"x": [{"val": "LATE", "filed": "2025-01-01", "end": "2024-12-31"}]}
    assert _latest_string_fact_le_asof(units_future, asof) is None, (
        "a TradingSymbol first filed AFTER asof must not resolve (no look-ahead)")
    # Blank/whitespace values and undated facts are skipped; result upper-cased.
    units_msg = {"u": [
        {"val": "  ", "filed": "2019-01-01"},
        {"val": None, "filed": "2019-02-01"},
        {"val": "lc", "filed": "2019-06-01"},
    ]}
    assert _latest_string_fact_le_asof(units_msg, asof) == "LC", "blank/None skipped; upper-cased"
    assert _latest_string_fact_le_asof({}, asof) is None, "empty units -> None"
    assert _latest_string_fact_le_asof("not a dict", asof) is None, "malformed units guard"

    # ----- FIX 2: cik_trading_symbol_asof, PIT ticker resolution (mock fetch) --
    # (G1) PRIMARY: a CIK with a dei:TradingSymbol fact filed<=asof resolves to that
    #      symbol (survivorship-safe; persists even for later-delisted names).
    ts_payload = {"cik": 777777, "taxonomy": "dei", "tag": "TradingSymbol", "units": {"USD": [
        {"val": "KEEP", "filed": "2020-03-15", "end": "2019-12-31"}]}}
    def _fetch_ts(url, params=None, timeout=20):
        if "TradingSymbol" in url:
            return _Resp(ts_payload)
        return _Resp({}, status=404)
    sym = cik_trading_symbol_asof("0000777777", asof, fetch=_fetch_ts)
    assert sym == "KEEP", f"dei:TradingSymbol filed<=asof must resolve: {sym}"

    # (G2) SHELL: a CIK with NO TradingSymbol fact and NO submissions tickers ->
    #      None (a ticker-less shell / financing-sub; the universe drops + counts it).
    def _fetch_ts_none(url, params=None, timeout=20):
        if "TradingSymbol" in url:
            return _Resp({"cik": 888888, "taxonomy": "dei", "tag": "TradingSymbol", "units": {}})  # no facts at all
        return _Resp({}, status=404)
    assert cik_trading_symbol_asof("0000888888", asof, fetch=_fetch_ts_none) is None, (
        "a ticker-less shell (no TradingSymbol, no current ticker) must NOT resolve")

    # (G3) FALLBACK: no TradingSymbol fact <=asof, but submissions has a current
    #      ticker (still-listed name) -> resolves via the current-ticker fallback.
    def _fetch_ts_fallback(url, params=None, timeout=20):
        if "TradingSymbol" in url:
            return _Resp({"cik": 999999, "taxonomy": "dei", "tag": "TradingSymbol", "units": {}})
        return _Resp({}, status=404)
    sym_fb = cik_trading_symbol_asof(
        "0000999999", asof, fetch=_fetch_ts_fallback, submissions_tickers=["nasdaqsym"])
    assert sym_fb == "NASDAQSYM", f"current-ticker fallback for still-listed name: {sym_fb}"

    # (G4) DELISTED-AS-OF-T: dei:TradingSymbol fact present as-of T but the entity
    #      later delisted (current submissions tickers EMPTY). The PRIMARY path still
    #      resolves the as-of symbol -> KEPT. This is the survivorship-safe core.
    ts_delisted = {"cik": 1010101, "taxonomy": "dei", "tag": "TradingSymbol", "units": {"USD": [
        {"val": "GONE", "filed": "2019-03-15", "end": "2018-12-31"}]}}
    def _fetch_ts_delisted(url, params=None, timeout=20):
        if "TradingSymbol" in url:
            return _Resp(ts_delisted)
        return _Resp({}, status=404)
    sym_del = cik_trading_symbol_asof(
        "0001010101", asof, fetch=_fetch_ts_delisted, submissions_tickers=[])
    assert sym_del == "GONE", (
        "a later-delisted name (TradingSymbol present as-of, no current ticker) must KEEP its as-of symbol")

    # ----- pit_universe: end-to-end with injected seed + probe (offline) -------
    # Theme with no dedicated SIC -> [] (opt-in no-op, mirrors live SIC-floor).
    assert pit_universe("ai agents nonexistent theme", asof) == [], (
        "theme with no dedicated SIC must return [] (opt-in)")

    # Build a probe table keyed by CIK exercising every required behavior:
    #   111 only-before, tradable -> INCLUDED; 222 first-after-asof -> EXCLUDED;
    #   333 later-delisted, tradable (as-of ticker) -> INCLUDED (not dropped);
    #   444 periodic filer but TICKER-LESS shell (no as-of ticker) -> DROPPED+counted.
    from make_fixtures import source34_scenarios
    _shell = source34_scenarios()["shell"]
    shell_probe = dict(rA, cik="444", name=_shell["name"], ticker="")
    probe_table = {
        "111": dict(rA, cik="111"),       # ticker resolved via fallback -> "OBC"
        "222": None,
        "333": dict(rC, cik="333"),       # ticker resolved via fallback -> "BUI"
        "444": shell_probe,               # ticker-less financing-sub shell
    }
    seed_rows = [
        {"cik": "111", "name": "ONLY BEFORE CO", "recall_channel": "sic_reverse"},
        {"cik": "222", "name": "FUTURE CO", "recall_channel": "sic_reverse"},
        {"cik": "333", "name": "BLEW UP INC", "recall_channel": "sic_reverse"},
        {"cik": "444", "name": _shell["name"], "recall_channel": "sic_reverse"},
        {"cik": "0000000333", "name": "BLEW UP INC DUPE", "recall_channel": "sic_reverse"},  # dupe of 333
    ]
    uni, stats = pit_universe(
        "deathcare", asof,
        seed_fn=lambda t: seed_rows,
        probe_fn=lambda c, a: probe_table.get(c),
        return_stats=True,
    )
    by_cik = {r["cik"]: r for r in uni}
    assert "111" in by_cik, "INCLUDE a CIK whose only filing is before asof"
    assert "222" not in by_cik, "EXCLUDE a CIK whose first filing is after asof"
    assert "333" in by_cik, "do NOT drop a later-delisted filer (survivorship-safe)"
    assert "444" not in by_cik, "DROP a ticker-less shell / financing-sub (no as-of ticker)"
    assert len(uni) == 2, f"dedupe seed dupes; expect exactly 2 survivors, got {len(uni)}: {sorted(by_cik)}"
    assert by_cik["333"]["delisted_after_asof"] is True, "delisted filer carried, flagged, kept"
    # Every survivor CARRIES a resolved (non-empty) ticker (tradability filter).
    assert all(r.get("ticker") for r in uni), "every survivor must carry a resolved as-of ticker"
    assert by_cik["333"]["ticker"] == "BUI", f"later-delisted survivor keeps its as-of ticker: {by_cik['333']}"
    assert all(r.get("recall_channel") == "sic_reverse" for r in uni), (
        "every PIT-universe row must carry its recall_channel (sic_reverse seed)")
    # Drop count surfaced for the harness (FIX 3): exactly one ticker-less shell dropped.
    assert stats["dropped_no_asof_ticker"] == 1, f"one ticker-less shell dropped: {stats}"
    assert stats["periodic_filers"] == 3 and stats["kept"] == 2, f"stats sanity: {stats}"
    # Default (no return_stats) call still returns a plain list (backward-compatible).
    uni_list = pit_universe(
        "deathcare", asof,
        seed_fn=lambda t: seed_rows,
        probe_fn=lambda c, a: probe_table.get(c),
    )
    assert isinstance(uni_list, list) and len(uni_list) == 2, (
        "default pit_universe must return a plain list (harness len(universe) unchanged)")
    # The look-ahead invariant the harness audit will assert: NO surviving row used a
    # filing after asof to qualify (earliest_filing_asof <= asof for every survivor).
    for r in uni:
        assert r["earliest_filing_asof"] <= asof, (
            f"PIT survivor {r['cik']} qualified on a filing AFTER asof — look-ahead leak!")

    print("_pit_universe selftest PASS (PIT universe survivorship-safe: includes only-before, "
          "excludes first-after-asof, keeps later-delisted; FIX 2 PIT ticker via dei:TradingSymbol "
          "filed<=asof + current-ticker fallback, drops+counts ticker-less shells, keeps delisted-as-of-T; "
          "overflow shards + look-ahead invariant)")


def main():
    ap = argparse.ArgumentParser(
        description="_pit_universe — survivorship-safe PIT universe of theme filers as-of T. "
                    "Library module; CLI supports --selftest only."
    )
    ap.add_argument("--selftest", action="store_true", help="Run offline selftest and exit")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    ap.error(
        "_pit_universe.py is a library module (PIECE 2 of the PIT backtest machinery). "
        "tools/backtest.py imports pit_universe(theme, asof). Use --selftest to verify it."
    )


if __name__ == "__main__":
    main()
