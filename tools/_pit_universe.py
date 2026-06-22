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

Each surviving row is {cik, name, ticker?, recall_channel, first_periodic_filing,
earliest_filing_asof, delisted_after_asof?}. recall_channel records how the CIK
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


def cik_periodic_asof(cik: str | int, asof: str, fetch=None,
                      sleep: float = 0.0) -> dict | None:
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
        "ticker": <first current ticker, or ""> ,
        "first_periodic_filing": <MIN periodic filingDate seen, any date>,
        "earliest_filing_asof": <MIN periodic filingDate <= asof>,
        "latest_filing_asof": <MAX periodic filingDate <= asof>,
        "delisted_after_asof": <bool | None>,  # see below
      }
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
    tks = doc.get("tickers") or []
    if tks:
        ticker = str(tks[0] or "")

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
                 sleep: float = 0.0, seed_fn=None, probe_fn=None) -> list[dict]:
    """Survivorship-safe PIT universe of theme filers as-of `asof` (YYYY-MM-DD).

    Returns a list of {cik, name, ticker?, recall_channel, first_periodic_filing,
    earliest_filing_asof, latest_filing_asof, delisted_after_asof} for EVERY entity
    that (a) lives in the theme's dedicated SIC (the recall seed) AND (b) had a
    10-K/10-Q (or 20-F/40-F) with filingDate <= asof — INCLUDING entities that
    later delisted (NOT excluded). Empty list for a theme with no dedicated SIC.

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
        return []

    seeds = seed_fn(theme)
    out: list[dict] = []
    seen: set[str] = set()
    for s in seeds:
        cik = str(s.get("cik", "")).split(".")[0].strip().lstrip("0") or ""
        if not cik or cik in seen:
            continue
        seen.add(cik)
        if sleep:
            time.sleep(sleep)
        probe = probe_fn(cik, asof)
        if probe is None:
            continue  # not a periodic filer on/before asof -> excluded (or fetch failed)
        row = dict(probe)
        # Preserve the recall channel the seed carried (sic_reverse today; the union
        # semantics from filter_by_sic make "fts"/"both" possible with a future seed).
        row["recall_channel"] = str(s.get("recall_channel", "") or "sic_reverse")
        # Seed name is a reasonable fallback if submissions name was blank.
        if not row.get("name"):
            row["name"] = str(s.get("name", "") or "")
        out.append(row)
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

    # ----- pit_universe: end-to-end with injected seed + probe (offline) -------
    # Theme with no dedicated SIC -> [] (opt-in no-op, mirrors live SIC-floor).
    assert pit_universe("ai agents nonexistent theme", asof) == [], (
        "theme with no dedicated SIC must return [] (opt-in)")

    # Build a probe table keyed by CIK exercising all three required behaviors:
    #   111 only-before -> INCLUDED; 222 first-after-asof -> EXCLUDED;
    #   333 later-delisted -> INCLUDED (not dropped).
    probe_table = {
        "111": dict(rA, cik="111"),
        "222": None,
        "333": dict(rC, cik="333"),
    }
    seed_rows = [
        {"cik": "111", "name": "ONLY BEFORE CO", "recall_channel": "sic_reverse"},
        {"cik": "222", "name": "FUTURE CO", "recall_channel": "sic_reverse"},
        {"cik": "333", "name": "BLEW UP INC", "recall_channel": "sic_reverse"},
        {"cik": "0000000333", "name": "BLEW UP INC DUPE", "recall_channel": "sic_reverse"},  # dupe of 333
    ]
    uni = pit_universe(
        "deathcare", asof,
        seed_fn=lambda t: seed_rows,
        probe_fn=lambda c, a: probe_table.get(c),
    )
    by_cik = {r["cik"]: r for r in uni}
    assert "111" in by_cik, "INCLUDE a CIK whose only filing is before asof"
    assert "222" not in by_cik, "EXCLUDE a CIK whose first filing is after asof"
    assert "333" in by_cik, "do NOT drop a later-delisted filer (survivorship-safe)"
    assert len(uni) == 2, f"dedupe seed dupes; expect exactly 2 survivors, got {len(uni)}: {sorted(by_cik)}"
    assert by_cik["333"]["delisted_after_asof"] is True, "delisted filer carried, flagged, kept"
    assert all(r.get("recall_channel") == "sic_reverse" for r in uni), (
        "every PIT-universe row must carry its recall_channel (sic_reverse seed)")
    # The look-ahead invariant the harness audit will assert: NO surviving row used a
    # filing after asof to qualify (earliest_filing_asof <= asof for every survivor).
    for r in uni:
        assert r["earliest_filing_asof"] <= asof, (
            f"PIT survivor {r['cik']} qualified on a filing AFTER asof — look-ahead leak!")

    print("_pit_universe selftest PASS (PIT universe survivorship-safe: includes only-before, "
          "excludes first-after-asof, keeps later-delisted; overflow shards + look-ahead invariant)")


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
