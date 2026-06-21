"""
filter_by_sic.py — SIC-code coarse-exclusion library (Gate 1 of the two-stage precision gate)
                   + P8 SIC reverse-recall (the recall FLOOR)

P8 (SIC reverse-recall): for a theme whose dedicated SIC code(s) are known, SIC is
not just a coarse precision *exclude* — it is also a recall *floor*. We ENUMERATE every
registrant in the theme's dedicated SIC(s) directly from EDGAR (browse-edgar
getcompany?SIC=...) and UNION that set with the FTS keyword recall. A true small-cap
that FTS missed — low keyword density, or buried past the FTS top-1000 page cap — is
still recalled because it lives in the dedicated SIC. Each surviving row is tagged with
its recall_channel:
    "fts"          — recalled only by the full-text keyword search
    "sic_reverse"  — recalled only by the dedicated-SIC enumeration (the FTS blind spot)
    "both"         — recalled by both channels (the strongest signal)
This is OPT-IN per theme (THEME_SIC must have an entry, and discover must pass
--sic-reverse) so we don't enumerate a giant generic SIC on every run.

Library functions:
  sic_classify(sic, hard_exclude) — returns "keep" | "review" | "drop".
    "keep"   — SIC is not in the hard-exclude list; include in candidates normally.
    "review" — SIC IS in the hard-exclude list; the company will be forwarded for LLM
               review (e.g. TITN SIC 5990, SNFCA SIC 6199).
               IMPORTANT: "review" is safe to forward ONLY because the caller (run_theme)
               ensures every company reaching sic_classify has already passed FTS keyword
               filtering. sic_classify itself does NOT check theme-keyword membership.
               If called on a pre-FTS universe, "review" would be an over-recall hole.
    "drop"   — reserved for future explicit-drop logic; currently unused (classify never
               returns "drop").
  sic_ok(sic, hard_exclude) — legacy bool wrapper: returns True for "keep" OR "review"
    (i.e., True for any result that is not "drop"). Kept for backward compatibility.
    NOTE: sic_ok now returns True for "review" as well as "keep" — the old docstring
    saying "True iff classify returns 'keep'" was incorrect after the Phase-4 tri-state
    change. run_theme.py uses sic_classify directly for tri-state tagging.

CALLER CONTRACT: run_theme.py calls sic_classify on a post-FTS universe (every company
has already matched theme keywords). Any other caller MUST apply the same FTS pre-filter
before treating "review" as safe to forward — otherwise the over-recall hole reopens.

run_theme.py imports both; this file is NOT run as a standalone pipeline step.

CLI: --selftest only (runs unit assertions and exits).

Reference: reference/discovery-engine.md §Gate 1.
"""
from __future__ import annotations
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, http_get

# 硬排除的 SIC 前缀:医药/医疗器械/医疗服务/软件/金融/保险/房产/零售/餐饮/玩具
HARD_EXCLUDE = CFG["sic_hard_exclude"]

# ---------------------------------------------------------------------------
# P8 SIC reverse-recall — the dedicated-SIC recall FLOOR.
#
# THEME_SIC maps a theme slug (the discover.py --out-slug / first-phrase slug) to the
# theme's dedicated SIC code(s). This is the "SIC->keep mapping" that filter_by_sic owns:
# the SIC(s) that, for this theme, are not coarse-excludes but the OPPOSITE — a member
# of these SIC(s) is presumptively in-theme and must not be dropped just because FTS
# keyword density was low. Keys are matched case-insensitively and as a substring of the
# theme slug (so "deathcare", "funeral_deathcare", etc. all resolve).
#
# Seeded with the deathcare gold cohort (assessment §P8): SCI/CSV are SIC 7200
# (Services-Personal Services) — the dedicated deathcare operator SIC. MATW (3360,
# castings) and SNFCA (6199, finance) are cross-SIC by design and are NOT a dedicated
# deathcare SIC, so they are deliberately NOT floored here — track_forward's recall@gold
# is what measures that residual FTS-only gap.
THEME_SIC: dict[str, list[str]] = {
    "deathcare": ["7200"],
    "funeral": ["7200"],
    "cemetery": ["7200"],
}

# EDGAR browse-by-SIC enumeration endpoint (the recall-floor channel). The structured
# data.sec.gov/full-text endpoints require a query term; browse-edgar getcompany?SIC= is
# the only channel that enumerates an entire SIC. HTML rows are:
#   <td>...CIK=<10digit>&...>CIK</a></td><td scope="row">COMPANY NAME</td>
_BROWSE_EDGAR = "https://www.sec.gov/cgi-bin/browse-edgar"
_SIC_ROW_RE = re.compile(
    r"CIK=(\d{10})&amp;owner=include[^>]*>(\d{10})</a></td>\s*<td[^>]*>([^<]+)</td>",
    re.I,
)


def sic_classify(sic: str, hard_exclude: list[str]) -> str:
    """Tri-state SIC classifier for Phase-4 recall improvement.

    Returns:
      "keep"   — SIC is NOT in the hard-exclude list; candidate passes Gate 1 normally.
      "review" — SIC IS in the hard-exclude list; forward with sic_tier="review" for
                 LLM gate decision. Examples: TITN (SIC 5990 retail — farm equipment
                 dealer), SNFCA (SIC 6199 finance — real deathcare segment).
                 IMPORTANT: this function does NOT itself check theme-keyword membership.
                 Safety comes from the pipeline: run_theme calls sic_classify on a
                 post-FTS universe, so every company here is already a keyword hit.
                 A caller that skips FTS pre-filtering would get over-recall on "review".
      "drop"   — explicit future use; currently unused (classify never returns "drop").
    SIC missing → "keep": defer to LLM, do not auto-exclude.
    """
    sic = str(sic).split(".")[0].strip()
    if not sic or sic == "nan":
        return "keep"  # 缺 SIC 不剔,交 LLM 判
    # 按长到短匹配硬排除前缀
    for ex in sorted(hard_exclude, key=len, reverse=True):
        if sic.startswith(ex):
            return "review"  # was a theme-keyword hit → let LLM decide
    return "keep"


def sic_ok(sic: str, hard_exclude: list[str]) -> bool:
    """Legacy bool wrapper: True for "keep" OR "review" (anything that is not "drop").
    Note: the old docstring said "True iff classify returns 'keep'" — that was incorrect
    after the Phase-4 tri-state change; sic_ok now also returns True for "review".
    Use sic_classify directly when you need the tri-state tier.
    # DEPRECATED: kept for backward-compat; prefer sic_classify
    """
    tier = sic_classify(sic, hard_exclude)
    return tier != "drop"


def theme_sics(theme: str, mapping: dict[str, list[str]] | None = None) -> list[str]:
    """Return the dedicated SIC code(s) for a theme, or [] if none are known.

    P8: only themes present in THEME_SIC get a SIC recall floor. Matching is
    case-insensitive and substring-based against the theme slug, so "deathcare",
    "funeral", and compound slugs like "deathcare_2026" all resolve. [] means the
    theme has no dedicated SIC — reverse-recall is a no-op and discover falls back to
    FTS-only recall (the existing behavior; opt-in by construction).
    """
    if mapping is None:
        mapping = THEME_SIC
    t = str(theme).lower()
    sics: list[str] = []
    for key, codes in mapping.items():
        if key in t:
            for c in codes:
                if c not in sics:
                    sics.append(c)
    return sics


def _parse_browse_edgar(html: str) -> list[dict]:
    """Extract {cik, name, sic} rows from a browse-edgar getcompany HTML page.

    Pulled out as a pure function so the selftest can exercise the parser on a fixture
    without any network call. CIK is normalized to the no-leading-zero string used by
    the rest of the pipeline (matches discover.fts_search, which stores CIK as a plain
    digit string).
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for m in _SIC_ROW_RE.finditer(html):
        cik = m.group(1).lstrip("0") or "0"
        if cik in seen:
            continue
        seen.add(cik)
        name = (
            m.group(3)
            .replace("&amp;", "&")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
            .strip()
        )
        rows.append({"cik": cik, "name": name})
    return rows


def enumerate_sic(sic: str, forms: str = "10-K", max_pages: int = 20,
                  count: int = 100, sleep: float = 0.6,
                  fetch=None) -> list[dict]:
    """Enumerate ALL registrants in one SIC via EDGAR browse-by-SIC. P8 recall floor.

    Pages through browse-edgar getcompany?SIC=<sic>&start=<n> until a short page
    (< count rows) is returned. Each row is {cik, name, sic, recall_channel:
    "sic_reverse"}. fetch is injectable (defaults to _common.http_get) so the selftest
    can run offline with a fixture. Network errors break the loop (best-effort floor;
    we never crash the run for a recall add-on).
    """
    if fetch is None:
        fetch = http_get
    sic = str(sic).split(".")[0].strip()
    out: list[dict] = []
    seen: set[str] = set()
    for page in range(max_pages):
        params = {
            "action": "getcompany", "SIC": sic, "type": forms,
            "dateb": "", "owner": "include", "count": count,
            "start": page * count,
        }
        try:
            r = fetch(_BROWSE_EDGAR, params=params, timeout=25)
            html = r.text if hasattr(r, "text") else str(r)
        except Exception as e:  # pragma: no cover - network guard
            print(f"  [warn] enumerate_sic({sic}) page {page}: {e}", file=sys.stderr)
            break
        rows = _parse_browse_edgar(html)
        if not rows:
            break
        new = 0
        for row in rows:
            if row["cik"] in seen:
                continue
            seen.add(row["cik"])
            row["sic"] = sic
            row["recall_channel"] = "sic_reverse"
            out.append(row)
            new += 1
        if len(rows) < count or new == 0:
            break
        time.sleep(sleep)
    return out


def sic_reverse_recall(theme: str, forms: str = "10-K", mapping=None,
                       fetch=None, max_pages: int = 20) -> list[dict]:
    """All registrants in the theme's dedicated SIC(s), tagged recall_channel=sic_reverse.

    Empty list when the theme has no dedicated SIC (theme not in THEME_SIC) — opt-in by
    construction, so a theme with no entry is a clean no-op and discover stays FTS-only.
    """
    sics = theme_sics(theme, mapping)
    if not sics:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for sic in sics:
        for row in enumerate_sic(sic, forms=forms, fetch=fetch, max_pages=max_pages):
            if row["cik"] in seen:
                continue
            seen.add(row["cik"])
            out.append(row)
    return out


def union_recall(fts_rows: list[dict], sic_rows: list[dict]) -> list[dict]:
    """UNION the FTS recall with the SIC-reverse recall on CIK, no dupes. P8 floor merge.

    recall_channel is tagged per surviving row:
      "fts"          present only in fts_rows
      "sic_reverse"  present only in sic_rows (the FTS blind spot the floor recovers)
      "both"         present in both (strongest signal)
    FTS rows win on field content (they carry ticker/form/file_date/matched_phrase from
    the full-text hit); a SIC-only row is added with whatever browse-edgar gave (cik/name/
    sic) and ticker left blank for downstream enrichment to resolve. Returns a new list;
    inputs are not mutated.
    """
    fts_ciks = {str(r.get("cik", "")).strip() for r in fts_rows if r.get("cik")}
    sic_ciks = {str(r.get("cik", "")).strip() for r in sic_rows if r.get("cik")}
    out: list[dict] = []
    for r in fts_rows:
        rr = dict(r)
        cik = str(rr.get("cik", "")).strip()
        rr["recall_channel"] = "both" if cik in sic_ciks else "fts"
        out.append(rr)
    for r in sic_rows:
        cik = str(r.get("cik", "")).strip()
        if cik in fts_ciks:
            continue  # already emitted as "both"
        rr = dict(r)
        rr["recall_channel"] = "sic_reverse"
        rr.setdefault("ticker", "")
        out.append(rr)
    return out


def _selftest():
    he = CFG["sic_hard_exclude"]
    # Legacy sic_ok checks (must not regress)
    assert sic_ok("2810", he) is True, "NL/VHI 2810 must NOT be excluded"
    assert sic_ok("3743", he) is True, "railcar 3743 must be kept"
    assert sic_ok("", he) is True, "missing sic must be kept (defer to LLM)"

    # Phase-4 tri-state checks: sic_classify
    assert sic_classify("2810", he) == "keep", "2810 must be 'keep'"
    assert sic_classify("2834", he) == "review", "pharma 2834 must be 'review' (not 'drop')"
    assert sic_classify("8071", he) == "review", "medical lab 8071 must be 'review'"
    assert sic_classify("3743", he) == "keep", "railcar 3743 must be 'keep'"
    assert sic_classify("", he) == "keep", "missing sic must be 'keep'"

    # Phase-4 recall: TITN (SIC 5990) and SNFCA (SIC 6199) must survive as "review"
    # so the LLM gate can decide their theme membership.
    assert sic_classify("5990", he) == "review", (
        "TITN SIC 5990 must classify as 'review' (farm equipment dealer, theme-keyword hit); "
        "was wrongly silently dropped in run-3."
    )
    assert sic_classify("6199", he) == "review", (
        "SNFCA SIC 6199 must classify as 'review' (real deathcare segment); "
        "was wrongly silently dropped in run-3."
    )
    # Legacy sic_ok for 5990 and 6199 must now return True (they pass to LLM)
    assert sic_ok("5990", he) is True, "sic_ok('5990') must be True after Phase-4 fix"
    assert sic_ok("6199", he) is True, "sic_ok('6199') must be True after Phase-4 fix"

    # -----------------------------------------------------------------------
    # P8 SIC reverse-recall (the recall FLOOR). All offline (fixtures + mock fetch).
    # -----------------------------------------------------------------------
    # theme_sics: dedicated-SIC lookup is opt-in, case-insensitive, substring-matched.
    assert theme_sics("deathcare") == ["7200"], "deathcare must floor to dedicated SIC 7200"
    assert theme_sics("DEATHCARE_2026") == ["7200"], "theme_sics must be case-insensitive + substring"
    assert theme_sics("funeral services") == ["7200"], "funeral synonym must resolve to 7200"
    assert theme_sics("ai agents") == [], "theme with no dedicated SIC -> [] (opt-in no-op)"

    # _parse_browse_edgar: pure parser on a real-shaped browse-edgar fixture.
    fixture = (
        '<tr><td valign="top" scope="row"><a href="/cgi-bin/browse-edgar?action=getcompany'
        '&amp;CIK=0000089089&amp;owner=include&amp;count=100&amp;type=10-K">0000089089</a></td>'
        '<td scope="row">SERVICE CORP INTERNATIONAL</td></tr>'
        '<tr><td valign="top" scope="row"><a href="/cgi-bin/browse-edgar?action=getcompany'
        '&amp;CIK=0001016281&amp;owner=include&amp;count=100&amp;type=10-K">0001016281</a></td>'
        '<td scope="row">Carriage Services &amp; Co, Inc.</td></tr>'
    )
    parsed = _parse_browse_edgar(fixture)
    assert [p["cik"] for p in parsed] == ["89089", "1016281"], f"parse CIKs: {parsed}"
    assert parsed[1]["name"] == "Carriage Services & Co, Inc.", f"HTML entity unescape: {parsed[1]}"

    # enumerate_sic: paginates via injectable fetch, tags recall_channel, dedupes across pages.
    class _Resp:
        def __init__(self, text): self.text = text
    page1 = (
        '<a href="x&amp;CIK=0000089089&amp;owner=include&amp;count=100&amp;type=10-K">0000089089</a></td>'
        '<td scope="row">SERVICE CORP INTERNATIONAL</td>'
        '<a href="x&amp;CIK=0001016281&amp;owner=include&amp;count=100&amp;type=10-K">0001016281</a></td>'
        '<td scope="row">CARRIAGE SERVICES INC</td>'
    )
    page2 = (  # one new + one dupe of page1 -> short page ends pagination
        '<a href="x&amp;CIK=0000063296&amp;owner=include&amp;count=100&amp;type=10-K">0000063296</a></td>'
        '<td scope="row">MATTHEWS INTL CORP</td>'
        '<a href="x&amp;CIK=0001016281&amp;owner=include&amp;count=100&amp;type=10-K">0001016281</a></td>'
        '<td scope="row">CARRIAGE SERVICES INC</td>'
    )
    # Paginating mock (count=2): page1 full, page2 = one new + one dupe, page3 empty.
    def _paging_fetch(url, params=None, timeout=25):
        start = (params or {}).get("start", 0)
        return _Resp({0: page1, 2: page2}.get(start, ""))
    enum = enumerate_sic("7200", count=2, fetch=_paging_fetch, sleep=0)
    enum_ciks = [r["cik"] for r in enum]
    assert enum_ciks == ["89089", "1016281", "63296"], f"enumerate_sic dedupe across pages: {enum_ciks}"
    assert all(r["recall_channel"] == "sic_reverse" for r in enum), "enumerate_sic must tag sic_reverse"
    assert all(r["sic"] == "7200" for r in enum), "enumerate_sic must stamp the SIC on each row"

    # Single-page mock (all 3 distinct rows) for the default-count sic_reverse_recall path.
    all_rows = page1 + (
        '<a href="x&amp;CIK=0000063296&amp;owner=include&amp;count=100&amp;type=10-K">0000063296</a></td>'
        '<td scope="row">MATTHEWS INTL CORP</td>'
    )
    def _onepage_fetch(url, params=None, timeout=25):
        return _Resp(all_rows if (params or {}).get("start", 0) == 0 else "")

    # sic_reverse_recall: no-op for an unmapped theme; full enumeration for a mapped one.
    assert sic_reverse_recall("ai agents", fetch=_onepage_fetch) == [], "unmapped theme -> no enumeration"
    rev = sic_reverse_recall("deathcare", fetch=_onepage_fetch)
    assert {r["cik"] for r in rev} == {"89089", "1016281", "63296"}, f"reverse-recall set: {rev}"

    # union_recall: merges FTS + SIC-reverse on CIK with NO dupes, tags channel correctly.
    fts = [
        {"cik": "89089", "ticker": "SCI", "name": "SERVICE CORP INTERNATIONAL",
         "sic": "7200", "matched_phrase": "deathcare"},     # in both channels -> "both"
        {"cik": "999999", "ticker": "ZZZZ", "name": "FTS Only Co",
         "sic": "7200", "matched_phrase": "cremation"},      # fts only -> "fts"
    ]
    sic = [
        {"cik": "89089", "name": "SERVICE CORP INTERNATIONAL", "sic": "7200",
         "recall_channel": "sic_reverse"},
        {"cik": "1016281", "name": "CARRIAGE SERVICES INC", "sic": "7200",
         "recall_channel": "sic_reverse"},                   # sic only -> the FTS blind spot
    ]
    merged = union_recall(fts, sic)
    by_cik = {r["cik"]: r for r in merged}
    assert len(merged) == 3, f"union must dedupe SCI to ONE row, got {len(merged)}: {[r['cik'] for r in merged]}"
    assert sorted(by_cik) == ["1016281", "89089", "999999"], f"union CIK set: {sorted(by_cik)}"
    assert by_cik["89089"]["recall_channel"] == "both", "CIK in both FTS+SIC must tag 'both'"
    assert by_cik["89089"]["ticker"] == "SCI", "FTS row content (ticker) must survive the merge"
    assert by_cik["999999"]["recall_channel"] == "fts", "FTS-only CIK must tag 'fts'"
    assert by_cik["1016281"]["recall_channel"] == "sic_reverse", (
        "SIC-only CIK (the FTS blind spot the floor recovers) must tag 'sic_reverse'"
    )
    assert by_cik["1016281"]["ticker"] == "", "SIC-only row gets blank ticker for downstream enrichment"
    # idempotence / no-mutation: inputs untouched
    assert "recall_channel" not in fts[0], "union_recall must NOT mutate its inputs"

    print("filter_by_sic selftest PASS")


def main():
    parser = argparse.ArgumentParser(
        description="filter_by_sic — SIC coarse-exclusion library. CLI supports --selftest only."
    )
    parser.add_argument("--selftest", action="store_true", help="Run selftest and exit")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return

    parser.error(
        "filter_by_sic.py is a library module: run_theme.py calls sic_classify()/sic_ok(); "
        "discover.py imports the P8 reverse-recall helpers (theme_sics / sic_reverse_recall / "
        "union_recall).\nUse --selftest to verify the functions."
    )


if __name__ == "__main__":
    main()
