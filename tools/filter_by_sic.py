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
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, http_get, slug

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
    # Coverage-test recall floors (2026-06-20).
    "water-utilities": ["4941"],          # water supply
    "railcar-leasing": ["3743", "4741"],  # railroad equipment + railcar rental
    "regional-gaming": ["7990", "7011"],  # amusement/recreation + hotels-casinos
    # v0.3.1 backlog #5 (2026-06-20): wire SIC recall floors for the ~30 coverage-test
    # themes that previously rested on FTS alone (unfloored & unmeasured). Canonical
    # dedicated SIC code(s) per theme. Slugs match the coverage-test theme dirs so the
    # substring match in theme_sics() resolves compound run slugs (e.g. "cov-coal-metcoal").
    "coal-metcoal": ["1220", "1221"],         # bituminous coal & lignite mining
    "midstream-mlp": ["4610", "4922", "4924"],  # pipelines + natural gas transmission/distribution
    "gold-silver-miners": ["1040", "1090", "1000"],  # gold mining + misc metal mining + metal mining
    "rare-earths": ["1000", "1040", "1090"],  # metal mining + gold + misc metal ores
    "timber-forest": ["2400", "0800"],        # lumber & wood products + forestry
    "beverages": ["2080", "2082", "2086"],    # beverages + malt beverages + bottled/canned soft drinks
    "tobacco-alternatives": ["2100", "2111"],  # tobacco products + cigarettes
    "local-broadcasting": ["4832", "4833"],   # radio broadcasting + television broadcasting
    "waste-recycling": ["4953", "5093"],      # refuse systems + scrap & waste materials
    "semiconductors": ["3674"],               # semiconductors & related devices
    "biotech-clinical": ["2836", "8731"],     # biological products + commercial physical/biological research
    "machinery": ["3500", "3550", "3559", "3561", "3590"],  # industrial & commercial machinery
    "restaurants": ["5812"],                  # eating places
    "homebuilders-land": ["1531"],            # operative builders (homebuilders / land)
    "refiners": ["2911"],                     # petroleum refining
    "steel-fab": ["3310", "3312", "3317"],    # steel works/blast furnaces + steel pipe & tubes
    "lithium-battery-materials": ["1090", "2890", "3690"],  # misc metal ores + industrial chemicals + electrical equipment
    "auto-parts-dealers": ["3714", "5013", "5531"],  # motor vehicle parts + auto parts wholesale/retail
    "oilsvc": ["1389"],                       # oil & gas field services
    "logistics-3pl": ["4731", "4700"],        # arrangement of transportation + transportation services
    "it-services": ["7370", "7372", "7389"],  # computer/data processing services + prepackaged software + computer services
    "rural-telecom-fiber": ["4813"],          # telephone communications (no radiotelephone)
    "household-personal": ["2840", "2844"],   # soap/detergents + perfumes/cosmetics/toiletries
    "diagnostics": ["8071", "2835"],          # medical laboratories + in-vitro/in-vivo diagnostics
    "building-products-hvac": ["3585", "3430", "3440"],  # refrigeration/heating equipment + heating/plumbing + fabricated metal
    "regbank": ["6020", "6021", "6022", "6035", "6036", "6712"],  # commercial banks + savings institutions + bank holding cos (PIT-universe floor; was missing -> empty backtest universe)
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


# ---------------------------------------------------------------------------
# v0.3.2 backlog #10 — SIC-floor sidecar namespacing.
#
# The dedicated-SIC enumeration is a per-theme RECALL artifact. A previous run
# wrote that sidecar to a FIXED, cross-theme path (e.g. candidates_railcar_leasing.json),
# so a machinery run dir ended up with a stale 63-name railcar-leasing sidecar that
# finalize_run would have falsely demanded reports for. The fix: the sidecar MUST be
# (a) written into the ACTIVE run/batch dir (REPORTS, the SMALLCAP_RUN subdir when set),
# and (b) namespaced by the ACTIVE theme slug — never a fixed cross-theme filename. Two
# concurrent themes therefore write distinct files in distinct run dirs and never collide.
# ---------------------------------------------------------------------------

def sic_floor_sidecar_path(theme_slug: str, run_dir: Path | None = None) -> Path:
    """Path for a theme's SIC-floor sidecar — under the active run dir, slug-namespaced.

    `run_dir` defaults to _common.REPORTS (the active SMALLCAP_RUN batch dir, or the
    flat output dir when no run is active). The filename is ALWAYS derived from the
    ACTIVE theme's slug — `_sic_floor_<slug>.json` — so a machinery run can never be
    handed a fixed `candidates_railcar_leasing.json`. The `_sic_floor_` prefix also
    keeps it out of finalize_run's `candidates_*.json` completeness glob (it is a recall
    diagnostic, not a deep-dive demand list).
    """
    if run_dir is None:
        run_dir = REPORTS
    return Path(run_dir) / f"_sic_floor_{slug(theme_slug)}.json"


def write_sic_floor_sidecar(theme_slug: str, sic_rows: list[dict],
                            run_dir: Path | None = None) -> Path:
    """Write the SIC-floor recall rows to the active-run, slug-namespaced sidecar.

    Returns the path written. The destination is computed by sic_floor_sidecar_path,
    so it is guaranteed to live under the active run dir and to carry the ACTIVE theme's
    slug — never a fixed cross-theme path. Creates the run dir if missing.
    """
    path = sic_floor_sidecar_path(theme_slug, run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(sic_rows), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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
    # Coverage-test recall floors (2026-06-20).
    assert theme_sics("cov-water-utilities") == ["4941"], "water-utilities must floor to SIC 4941"
    assert theme_sics("railcar-leasing run") == ["3743", "4741"], "railcar must floor to 3743/4741"
    assert theme_sics("regional-gaming") == ["7990", "7011"], "regional-gaming must floor to 7990/7011"
    assert theme_sics("ai agents") == [], "theme with no dedicated SIC -> [] (opt-in no-op)"

    # v0.3.1 backlog #5: every previously-unfloored coverage-test theme must now resolve to
    # its canonical dedicated SIC(s). Slugs prefixed with "cov-" exercise the substring match.
    assert theme_sics("cov-coal-metcoal") == ["1220", "1221"], "coal-metcoal must floor to 1220/1221"
    assert theme_sics("cov-midstream-mlp") == ["4610", "4922", "4924"], "midstream-mlp must floor to 4610/4922/4924"
    assert theme_sics("cov-gold-silver-miners") == ["1040", "1090", "1000"], "gold-silver-miners must floor to 1040/1090/1000"
    assert theme_sics("cov-rare-earths") == ["1000", "1040", "1090"], "rare-earths must floor to 1000/1040/1090"
    assert theme_sics("cov-timber-forest") == ["2400", "0800"], "timber-forest must floor to 2400/0800"
    assert theme_sics("cov-beverages") == ["2080", "2082", "2086"], "beverages must floor to 2080/2082/2086"
    assert theme_sics("cov-tobacco-alternatives") == ["2100", "2111"], "tobacco-alternatives must floor to 2100/2111"
    assert theme_sics("cov-local-broadcasting") == ["4832", "4833"], "local-broadcasting must floor to 4832/4833"
    assert theme_sics("cov-waste-recycling") == ["4953", "5093"], "waste-recycling must floor to 4953/5093"
    assert theme_sics("cov-semiconductors") == ["3674"], "semiconductors must floor to 3674"
    assert theme_sics("cov-biotech-clinical") == ["2836", "8731"], "biotech-clinical must floor to 2836/8731"
    assert theme_sics("cov-machinery") == ["3500", "3550", "3559", "3561", "3590"], "machinery must floor to 3500-series"
    assert theme_sics("cov-restaurants") == ["5812"], "restaurants must floor to 5812"
    assert theme_sics("cov-homebuilders-land") == ["1531"], "homebuilders-land must floor to 1531"
    assert theme_sics("cov-refiners") == ["2911"], "refiners must floor to 2911"
    assert theme_sics("cov-steel-fab") == ["3310", "3312", "3317"], "steel-fab must floor to 3310/3312/3317"
    assert theme_sics("cov-lithium-battery-materials") == ["1090", "2890", "3690"], "lithium-battery-materials must floor to 1090/2890/3690"
    assert theme_sics("cov-auto-parts-dealers") == ["3714", "5013", "5531"], "auto-parts-dealers must floor to 3714/5013/5531"
    assert theme_sics("cov-oilsvc") == ["1389"], "oilsvc must floor to 1389"
    assert theme_sics("cov-logistics-3pl") == ["4731", "4700"], "logistics-3pl must floor to 4731/4700"
    assert theme_sics("cov-it-services") == ["7370", "7372", "7389"], "it-services must floor to 7370/7372/7389"
    assert theme_sics("cov-rural-telecom-fiber") == ["4813"], "rural-telecom-fiber must floor to 4813"
    assert theme_sics("cov-household-personal") == ["2840", "2844"], "household-personal must floor to 2840/2844"
    assert theme_sics("cov-diagnostics") == ["8071", "2835"], "diagnostics must floor to 8071/2835"
    assert theme_sics("cov-building-products-hvac") == ["3585", "3430", "3440"], "building-products-hvac must floor to 3585/3430/3440"
    assert theme_sics("regbank") == ["6020", "6021", "6022", "6035", "6036", "6712"], "regbank must floor to bank SICs (PIT universe was empty without this)"

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

    # -----------------------------------------------------------------------
    # v0.3.2 #10 — SIC-floor sidecar must be namespaced under the ACTIVE run dir
    # and the ACTIVE theme slug, never a fixed cross-theme path. Two distinct
    # slugs/runs must NOT clobber each other.
    # -----------------------------------------------------------------------
    import tempfile
    with tempfile.TemporaryDirectory() as _td:
        run_machinery = Path(_td) / "2026-06-20_cov-machinery"
        run_railcar = Path(_td) / "2026-06-20_cov-railcar-leasing"
        # The sidecar filename derives from the ACTIVE theme slug — never a fixed cross-theme name.
        p_mach = sic_floor_sidecar_path("cov-machinery", run_dir=run_machinery)
        p_rail = sic_floor_sidecar_path("railcar-leasing", run_dir=run_railcar)
        assert p_mach.name == "_sic_floor_cov_machinery.json", f"#10: slug-namespaced sidecar name: {p_mach.name}"
        assert p_mach != p_rail, "#10: distinct slugs/runs must give distinct sidecar paths (no clobber)"
        # The machinery run must NEVER be handed a fixed candidates_railcar_leasing.json.
        assert "railcar" not in p_mach.name, "#10: machinery sidecar must not carry a cross-theme (railcar) name"
        assert "candidates_" not in p_mach.name, "#10: sidecar must stay out of the candidates_*.json glob"
        assert p_mach.parent == run_machinery, "#10: sidecar must land under the ACTIVE run dir"
        # Actually write two distinct sidecars and confirm they coexist without clobbering.
        sic_rows_a = [{"cik": "111", "name": "MACHINE CO", "recall_channel": "sic_reverse"}]
        sic_rows_b = [{"cik": "222", "name": "RAILCAR CO", "recall_channel": "sic_reverse"}]
        w_a = write_sic_floor_sidecar("cov-machinery", sic_rows_a, run_dir=run_machinery)
        w_b = write_sic_floor_sidecar("railcar-leasing", sic_rows_b, run_dir=run_railcar)
        assert w_a == p_mach and w_b == p_rail, "#10: writer must use the namespaced path"
        assert w_a.exists() and w_b.exists(), "#10: both sidecars must exist (no clobber)"
        loaded_a = json.loads(w_a.read_text(encoding="utf-8"))
        loaded_b = json.loads(w_b.read_text(encoding="utf-8"))
        assert loaded_a[0]["cik"] == "111" and loaded_b[0]["cik"] == "222", (
            "#10: each run's sidecar must hold ITS OWN rows, not a cross-theme stale file")

    print("filter_by_sic selftest PASS (+ #10 sidecar namespacing isolation)")


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
