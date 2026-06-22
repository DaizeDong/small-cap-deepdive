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
     shards) and KEEP it iff it has a 10-K OR 10-Q with filingDate <= T. This is
     the per-CIK submissions filter the spec calls for, and it is what makes the
     set point-in-time correct: a CIK whose FIRST 10-K/10-Q is filed AFTER T was
     not yet a theme filer as-of T and is dropped; a CIK that filed before T and
     later delisted is KEPT (its filings persist).

Each surviving row is {cik, name, ticker, recall_channel, first_periodic_filing,
earliest_filing_asof, delisted_after_asof?} — `ticker` is the POINT-IN-TIME symbol
resolved from dei:TradingSymbol (filed<=asof), and survivors are restricted to
entities with such a resolvable as-of ticker (ticker-less shells are dropped +
counted as dropped_no_asof_ticker). recall_channel records how the CIK
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import http_get
from filter_by_sic import theme_sics, sic_reverse_recall

# Periodic ("was a filer") forms that establish theme-filer status as-of T. A
# company is a theme filer as-of T iff it filed one of these on/before T. Foreign
# annual reports (20-F/40-F) count too — they are the foreign-filer analogue of the
# 10-K and a foreign theme member is still a member (it just carries abstain
# downstream). Amendments (…/A) count as well (still a periodic disclosure event).
PERIODIC_FORMS = ("10-K", "10-Q", "20-F", "40-F")

_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
_SUBMISSIONS_SHARD = "https://data.sec.gov/submissions/{name}"
# Point-in-time ticker resolution (FIX 2): dei:TradingSymbol is the cover-page
# trading symbol an entity disclosed on its periodic filings. It is survivorship-
# safe: a name that listed in 2019 and delisted in 2021 STILL carries its
# 2019/2020 TradingSymbol fact in EDGAR (filings are immutable), so we can resolve
# the symbol an investor at as-of T would have traded under — even for names that
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


def _latest_string_fact_le_asof(units: dict, asof: str) -> str | None:
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
            if not filed or filed > asof:  # undated or future-filed -> drop (no look-ahead)
                continue
            raw = v.get("val")
            sym = str(raw or "").strip()
            if not sym:
                continue
            # Latest-filed wins; tie -> later API order (>= keeps last seen at same date).
            if best_filed is None or filed >= best_filed:
                best_filed = filed
                best_val = sym.upper()
    return best_val


def cik_trading_symbol_asof(cik: str | int, asof: str, fetch=None,
                            submissions_tickers=None) -> str | None:
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
    Returns an upper-cased symbol string, or None when NEITHER path yields one
    (a ticker-less shell / financing-sub -> the caller drops + counts it).
    `fetch` and `submissions_tickers` are injectable for the offline selftest.
    """
    if fetch is None:
        fetch = http_get
    cik10 = str(cik).split(".")[0].strip().lstrip("0").zfill(10) or "0".zfill(10)

    # PRIMARY: dei:TradingSymbol, latest fact filed <= asof.
    try:
        r = fetch(_DEI_CONCEPT.format(cik10=cik10, concept="TradingSymbol"), timeout=20)
        if getattr(r, "status_code", 200) == 200:
            units = (r.json() or {}).get("units", {}) or {}
            sym = _latest_string_fact_le_asof(units, asof)
            if sym:
                return sym
    except Exception:
        pass

    # FALLBACK: current submissions tickers (still-listed names only).
    if submissions_tickers:
        for t in submissions_tickers:
            s = str(t or "").strip()
            if s:
                return s.upper()
    return None


def cik_periodic_asof(cik: str | int, asof: str, fetch=None,
                      sleep: float = 0.0, resolve_ticker: bool = True) -> dict | None:
    """PIT submissions probe for ONE CIK: was it a periodic filer on/before asof?

    Reads the per-CIK submissions index (and any older "files" overflow shards, so
    pre-2015 history is not missed for early as-of dates) and scans every periodic
    report (10-K/10-Q/20-F/40-F, incl. /A) for filingDate <= asof.

    Returns None when the CIK has NO periodic filing on/before asof — i.e. it was
    NOT yet a theme filer as-of asof (e.g. a company whose first 10-K is filed
    AFTER asof is correctly excluded). Otherwise returns:
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
    `ticker` is resolved POINT-IN-TIME (FIX 2): the dei:TradingSymbol fact filed
    on/before asof (survivorship-safe — persists for later-delisted names), falling
    back to the current submissions tickers only for still-listed names. "" when the
    CIK is a ticker-less shell/financing-sub (the universe builder drops + counts
    those). Set resolve_ticker=False to skip the extra companyconcept fetch (used by
    callers that resolve the symbol themselves).
    `delisted_after_asof` is a best-effort flag derived from whether ANY periodic
    filing exists AFTER asof: if the entity kept filing periodic reports after asof
    it was clearly still active (False); if its last periodic report is on/before
    asof it MAY have delisted (True) — survivorship-safe either way, because we KEEP
    the row regardless (the realized return / last-close logic lives in PIECE 3).
    None when undeterminable. fetch is injectable for offline selftests.
    """
    if fetch is None:
        fetch = http_get
    cik_plain = str(cik).split(".")[0].strip().lstrip("0") or "0"
    cik10 = cik_plain.zfill(10)

    blocks: list[dict] = []
    name = ""
    ticker = ""
    first_periodic_any: str | None = None
    has_periodic_after_asof = False

    try:
        r = fetch(_SUBMISSIONS.format(cik10=cik10), timeout=20)
        if getattr(r, "status_code", 200) != 200:
            return None
        doc = r.json()
    except Exception:
        return None

    name = str(doc.get("name", "") or "")
    current_tickers = doc.get("tickers") or []
    # POINT-IN-TIME ticker (FIX 2): dei:TradingSymbol filed<=asof (survivorship-safe),
    # falling back to current submissions tickers only for still-listed names.
    if resolve_ticker:
        ticker = cik_trading_symbol_asof(
            cik_plain, asof, fetch=fetch, submissions_tickers=current_tickers) or ""

    filings = doc.get("filings") or {}
    recent = filings.get("recent") or {}
    if recent:
        blocks.append(recent)

    # Older filings spill into "files" overflow shards (each a {form,filingDate,...}
    # block). For early as-of dates (e.g. 2020) the qualifying first 10-K may live
    # ONLY in a shard, so we must read them — otherwise we'd wrongly exclude a
    # long-tenured filer. Best-effort: a shard fetch failure is skipped, not fatal.
    for shard in (filings.get("files") or []):
        sname = str(shard.get("name", "") or "")
        if not sname:
            continue
        if sleep:
            time.sleep(sleep)
        try:
            sr = fetch(_SUBMISSIONS_SHARD.format(name=sname), timeout=20)
            if getattr(sr, "status_code", 200) != 200:
                continue
            blocks.append(sr.json())
        except Exception:
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
        return None  # not yet a theme filer as-of asof -> excluded

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
    """Survivorship-safe PIT universe of theme filers as-of `asof` (YYYY-MM-DD).

    Returns a list of {cik, name, ticker, recall_channel, first_periodic_filing,
    earliest_filing_asof, latest_filing_asof, delisted_after_asof} for EVERY entity
    that (a) lives in the theme's dedicated SIC (the recall seed), (b) had a
    10-K/10-Q (or 20-F/40-F) with filingDate <= asof — INCLUDING entities that
    later delisted (NOT excluded) — AND (c) has a RESOLVABLE point-in-time ticker
    (dei:TradingSymbol filed<=asof, or current submissions ticker for still-listed).
    Empty list for a theme with no dedicated SIC.

    TRADABILITY FILTER (FIX 2): a periodic filer with NO as-of ticker is a
    ticker-less shell / financing-sub (e.g. "155 East Tropicana Finance Corp" —
    a financing subsidiary that files 10-Ks for its bonds but never trades equity).
    Those have no priceable security, would yield null returns, and are DROPPED.
    Every surviving row is a tradable issuer (incl. later-delisted ones, which the
    survivorship-safe dei:TradingSymbol path keeps resolvable) and CARRIES its
    resolved `ticker`.

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
    if probe_fn is None:
        def probe_fn(c, a):
            return cik_periodic_asof(c, a, fetch=fetch, sleep=sleep)

    if not theme_sics(theme):
        # No dedicated SIC -> no SIC seed. (FTS-as-of seed is a future add per spec.)
        return ([], {"seeds": 0, "periodic_filers": 0,
                     "dropped_no_asof_ticker": 0, "kept": 0}) if return_stats else []

    seeds = seed_fn(theme)
    out: list[dict] = []
    seen: set[str] = set()
    n_seeds = 0
    n_periodic = 0
    n_dropped_no_ticker = 0
    for s in seeds:
        cik = str(s.get("cik", "")).split(".")[0].strip().lstrip("0") or ""
        if not cik or cik in seen:
            continue
        seen.add(cik)
        n_seeds += 1
        if sleep:
            time.sleep(sleep)
        probe = probe_fn(cik, asof)
        if probe is None:
            continue  # not a periodic filer on/before asof -> excluded (or fetch failed)
        n_periodic += 1
        # TRADABILITY FILTER: drop + count ticker-less shells / financing-subs.
        # The as-of ticker is survivorship-safe (dei:TradingSymbol persists for
        # later-delisted names), so a missing ticker means a genuinely non-trading
        # entity, not just a since-delisted one.
        ticker = str(probe.get("ticker", "") or "").strip()
        if not ticker:
            n_dropped_no_ticker += 1
            continue
        row = dict(probe)
        row["ticker"] = ticker.upper()
        # Preserve the recall channel the seed carried (sic_reverse today; the union
        # semantics from filter_by_sic make "fts"/"both" possible with a future seed).
        row["recall_channel"] = str(s.get("recall_channel", "") or "sic_reverse")
        # Seed name is a reasonable fallback if submissions name was blank.
        if not row.get("name"):
            row["name"] = str(s.get("name", "") or "")
        out.append(row)
    if return_stats:
        stats = {
            "seeds": n_seeds,
            "periodic_filers": n_periodic,
            "dropped_no_asof_ticker": n_dropped_no_ticker,
            "kept": len(out),
        }
        return out, stats
    return out


def _selftest() -> None:
    """Offline (mock/guarded) PIT-universe unit assertions. No network."""

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
    sub_only_before = {
        "name": "ONLY BEFORE CO", "tickers": ["OBC"],
        "filings": {"recent": {"form": ["10-K"], "filingDate": ["2018-04-01"]}, "files": []},
    }
    def _fetch_A(url, params=None, timeout=20):
        return _Resp(sub_only_before)
    rA = cik_periodic_asof("0000111111", asof, fetch=_fetch_A)
    assert rA is not None, "CIK whose only filing is BEFORE asof MUST be included"
    assert rA["cik"] == "111111", f"cik normalized: {rA['cik']}"
    assert rA["earliest_filing_asof"] == "2018-04-01", f"earliest<=asof: {rA}"
    assert rA["delisted_after_asof"] is True, (
        "only-before filer with nothing after asof -> delisted_after_asof True (still KEPT)")

    # (B) A CIK whose FIRST filing is AFTER asof -> EXCLUDED (was not a filer yet).
    sub_only_after = {
        "name": "FUTURE CO", "tickers": ["FUT"],
        "filings": {"recent": {"form": ["10-K", "10-Q"],
                               "filingDate": ["2021-03-15", "2021-08-10"]}, "files": []},
    }
    def _fetch_B(url, params=None, timeout=20):
        return _Resp(sub_only_after)
    rB = cik_periodic_asof("0000222222", asof, fetch=_fetch_B)
    assert rB is None, "CIK whose first periodic filing is AFTER asof MUST be excluded"

    # (C) A later-DELISTED filer: filed before asof, then stopped (last 10-K = 2019)
    #     -> INCLUDED and NOT dropped (delisted_after_asof True). The whole point.
    sub_delisted = {
        "name": "BLEW UP INC", "tickers": ["BUI"],
        "filings": {"recent": {"form": ["10-K", "10-Q", "10-K"],
                               "filingDate": ["2017-03-01", "2018-08-01", "2019-03-01"]},
                    "files": []},
    }
    def _fetch_C(url, params=None, timeout=20):
        return _Resp(sub_delisted)
    rC = cik_periodic_asof("0000333333", asof, fetch=_fetch_C)
    assert rC is not None, "a LATER-DELISTED filer (filings persist) MUST NOT be dropped"
    assert rC["delisted_after_asof"] is True, "delisted filer flagged, still kept"
    assert rC["latest_filing_asof"] == "2019-03-01", f"latest<=asof for delisted: {rC}"

    # (D) A still-active filer (kept filing AFTER asof) -> delisted_after_asof False.
    sub_active = {
        "name": "STILL HERE CORP", "tickers": ["SHC"],
        "filings": {"recent": {"form": ["10-K", "10-K", "10-K"],
                               "filingDate": ["2019-03-01", "2021-03-01", "2023-03-01"]},
                    "files": []},
    }
    def _fetch_D(url, params=None, timeout=20):
        return _Resp(sub_active)
    rD = cik_periodic_asof("0000444444", asof, fetch=_fetch_D)
    assert rD is not None and rD["delisted_after_asof"] is False, (
        "a filer that kept filing AFTER asof was still active -> delisted_after_asof False")

    # (E) Overflow "files" shard: the qualifying first 10-K lives ONLY in a shard
    #     (recent has only post-asof + non-periodic forms). Must still be INCLUDED.
    sub_shard_main = {
        "name": "OLD TIMER CO", "tickers": ["OTC"],
        "filings": {
            "recent": {"form": ["8-K", "10-K"], "filingDate": ["2020-01-05", "2022-03-01"]},
            "files": [{"name": "CIK0000555555-submissions-001.json"}],
        },
    }
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

    # ----- FIX 2: _latest_string_fact_le_asof — PIT string-fact date logic ------
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

    # ----- FIX 2: cik_trading_symbol_asof — PIT ticker resolution (mock fetch) --
    # (G1) PRIMARY: a CIK with a dei:TradingSymbol fact filed<=asof resolves to that
    #      symbol (survivorship-safe; persists even for later-delisted names).
    ts_payload = {"units": {"USD": [
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
            return _Resp({"units": {}})  # no facts at all
        return _Resp({}, status=404)
    assert cik_trading_symbol_asof("0000888888", asof, fetch=_fetch_ts_none) is None, (
        "a ticker-less shell (no TradingSymbol, no current ticker) must NOT resolve")

    # (G3) FALLBACK: no TradingSymbol fact <=asof, but submissions has a current
    #      ticker (still-listed name) -> resolves via the current-ticker fallback.
    def _fetch_ts_fallback(url, params=None, timeout=20):
        if "TradingSymbol" in url:
            return _Resp({"units": {}})
        return _Resp({}, status=404)
    sym_fb = cik_trading_symbol_asof(
        "0000999999", asof, fetch=_fetch_ts_fallback, submissions_tickers=["nasdaqsym"])
    assert sym_fb == "NASDAQSYM", f"current-ticker fallback for still-listed name: {sym_fb}"

    # (G4) DELISTED-AS-OF-T: dei:TradingSymbol fact present as-of T but the entity
    #      later delisted (current submissions tickers EMPTY). The PRIMARY path still
    #      resolves the as-of symbol -> KEPT. This is the survivorship-safe core.
    ts_delisted = {"units": {"USD": [
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
    shell_probe = dict(rA, cik="444", name="155 EAST TROPICANA FINANCE CORP", ticker="")
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
        {"cik": "444", "name": "155 EAST TROPICANA FINANCE CORP", "recall_channel": "sic_reverse"},
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
