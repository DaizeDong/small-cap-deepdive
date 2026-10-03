"""
cheap_pass.py — Stage 0 机械体检 + kill-flag 扫描(无定性叙事)

把发现阶段的小盘候选机械打分,kill-flag>=3 或财务硬伤直接淘汰,把 N 家砍到少数进 deep dive。
体现"agent 优势=规模化机械纪律"(对抗调研结论):不讲故事,只数硬信号。
设计依据:reference/mechanical-checks.md。

数据:SEC EDGAR(companyfacts XBRL + 全文检索 kill-flag) + yfinance(流通股稀释)。
kill-flag(成簇出现≈几乎必暴雷):going concern / material weakness / 重述 /
  death-spiral 可转债(variable conversion) / 审计师更换 / 反向拆股。

Private path setup:
    Initialize a versioned PRIVATE companion with SMALL_CAP_DEEPDIVE_CONFIG_DIR.
    Set REPORTS_ROOT to the absolute path returned by _common.reports_dir():
        python -c "import sys; sys.path.insert(0, 'tools'); from _common import reports_dir; print(reports_dir())"
    The resolver includes SMALLCAP_RUN when set and fails if initialization is missing.

Usage (REPORTS_ROOT is the resolved absolute private path):
    python tools/cheap_pass.py --universe "${REPORTS_ROOT}/universe_synthetic_2000-01-01.csv" --out-slug synthetic
Output: _common.reports_dir()/cheappass_synthetic_<date>.csv, with its stage receipt.
The universe and its receipt remain in the versioned private companion.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from edgar import Company

# Import _common exports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    init_edgar, REPORTS, slug, today, CFG, http_get,
    resolve_mktcap, band_for,  # P5, mktcap fallback + band tagging (resolve ceiling here)
)
# P3, magnitude-based concentration (extractor + flag composer live in deepdive_data,
# the P3 owner). cheap_pass already reads the 10-K full text in killflag_scan, so we reuse
# the same deterministic extractor on that text to surface the kill-flag BEFORE the expensive
# deepdive, rather than duplicating the regex contract here.
from deepdive_data import _extract_concentration, _concentration_flag
from _filing_disclosures import scan_disclosures
from filter_by_sic import (stage_completion, stage_work, read_stage_receipt,
                           write_stage_receipt, prepare_stage_output)

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

# Going-concern and material-weakness entries use local statement evidence.
# The remaining legacy phrase flags are lexical indicators, not semantic findings.
KILL_PHRASES = {
    "going_concern": "going concern",
    "substantial_doubt": "substantial doubt",       # 比 going concern 更特异
    "material_weakness": "material weakness",
    "death_spiral": "variable conversion",
    "reverse_split": "reverse stock split",
}


def _looks_like_toc(text: str) -> bool:
    """Return True if the first ~200 chars look like a table-of-contents entry.

    TOC lines have few alphabetic chars and are dominated by dots, digits, and
    whitespace (e.g. "Business........ 3" or "Item 1. Business ........... 4").
    Also detects page-number-padded TOC entries common in 20-F filings, where
    each entry ends with large whitespace padding and a page number
    (e.g. "ITEM 4A. UNRESOLVED STAFF COMMENTS                    57").
    Prose sections have many alphabetic chars and few dots/digits.
    Threshold: fewer than 50 alpha chars OR dot/digit fraction > 40%
    OR page-number-padded TOC pattern (3+ spaces followed by digit(s) at line end).
    """
    sample = text[:200]
    alpha = sum(1 for c in sample if c.isalpha())
    dot_digit = sum(1 for c in sample if c in "0123456789.")
    if alpha < 50:
        return True
    if len(sample) > 0 and dot_digit / len(sample) > 0.40:
        return True
    # Page-number-padded TOC: lines ending with multiple spaces + a page number.
    # Pattern: 3 or more spaces followed by digits at end-of-line.
    # In a 200-char sample, two or more such occurrences indicates a TOC.
    toc_page_pattern = re.compile(r"\s{3,}\d+\s*(?:\n|$)")
    if len(toc_page_pattern.findall(sample)) >= 2:
        return True
    return False


def _extract_business_blurb(txt: str, max_chars: int = 2000,
                            filing_form: str | None = None) -> str:
    """Extract business description section blurb from annual-report full text.

    Form-aware extraction:
      - 10-K (default): searches for "Item 1. Business" (correct for domestic filers).
      - 20-F / 40-F: searches for "Item 4. Information on the Company" (foreign filers).
        In a 20-F, Item 1 is the directors roster — garbage for theme-fit; the real
        business description lives under Item 4.

    TOC detection: after each match, inspect the first ~200 chars for prose
    density (>= 50 alpha chars and dot/digit fraction <= 40%). If it looks like
    a table-of-contents entry, advance to the next occurrence of the pattern.
    This prevents returning "Business........... 3" noise.

    Returns empty string if no meaningful prose is found — the theme-fit gate
    already falls back to WebSearch on empty blurb (correct degradation).
    """
    low = txt.lower()
    is_foreign = (filing_form or "").upper() in ("20-F", "40-F")

    if is_foreign:
        # 20-F / 40-F: business description is "Item 4. Information on the Company"
        # Also try generic "business overview" as a fallback for variations.
        patterns = [
            r"item\s+4[\.\-\s]+(information on the company|business overview|the business)",
            r"item\s+4\b",  # bare "item 4" fallback
        ]
    else:
        # 10-K: standard "Item 1. Business" heading
        patterns = [
            r"item\s+1[\.\-\s]+business",   # "item 1. business" or "item 1 business"
            r"item\s+1\b",                   # bare "item 1" fallback
        ]

    for pat in patterns:
        start = 0
        while True:
            m = re.search(pat, low[start:])
            if not m:
                break
            idx = start + m.end()
            candidate = txt[idx:idx + max_chars + 200].strip().lstrip("\r\n\t ")
            if not _looks_like_toc(candidate):
                return candidate[:max_chars]
            # TOC hit, advance past this match and try the next occurrence
            start = idx
        # If we exhausted all occurrences for this pattern, try the next pattern.
    return ""


def killflag_scan(ticker: str) -> dict:
    """Read the latest annual filing and retain disclosure evidence with its polarity.

    Going-concern and material-weakness flags distinguish current assertions,
    explicit negatives and completed remediation. Unsupported or conditional
    statements yield None and disclosure_review_required, with original spans.

    Also extracts business_blurb (Item 1 first ~2000 chars) for theme-fit gate reuse,
    avoiding redundant WebSearch in theme-fit-gate.js.

    Phase 4 — 20-F / 40-F graceful fallback:
    If get_filings(form="10-K", amendments=False) returns no results, falls back to
    20-F then 40-F. Foreign-domiciled filers (shipping, some industrials/mining) file
    20-F/40-F; going-concern and material-weakness language is structurally similar.
    The same disclosure rules and business_blurb extraction apply to each form.
    Sets out["filing_form"] to the form type that was actually read.
    """
    out = {f"kf_{k}": 0 for k in KILL_PHRASES}
    out.update(kf_going_concern=None, kf_substantial_doubt=None, kf_material_weakness=None,
               disclosure_evidence={}, disclosure_review_required=True)
    out["kf_scanned"] = False
    out["business_blurb"] = ""
    out["filing_form"] = None
    # P3, concentration fields, surfaced at the cheap-pass stage from the same full text.
    out["top_customer_pct"] = None
    out["top_program_pct"] = None
    out["concentration_flag"] = None
    out["concentration_detail"] = None
    try:
        c = Company(ticker)
        f = None
        form_used = None
        # Primary: 10-K (amendments=False, 10-K/A 修正件常缺 going-concern 全文)
        fl = c.get_filings(form="10-K", amendments=False)
        if fl is not None and len(fl):
            f = fl.latest(1)
            form_used = "10-K"
        # Fallback 1: 20-F (foreign-domiciled filers, Phase 4)
        if f is None:
            fl20 = c.get_filings(form="20-F", amendments=False)
            if fl20 is not None and len(fl20):
                f = fl20.latest(1)
                form_used = "20-F"
        # Fallback 2: 40-F (Canadian filers, Phase 4)
        if f is None:
            fl40 = c.get_filings(form="40-F", amendments=False)
            if fl40 is not None and len(fl40):
                f = fl40.latest(1)
                form_used = "40-F"
        if f is None:
            return out
        out["filing_form"] = form_used
        txt = f.text() if hasattr(f, "text") else str(f.obj())
        if not isinstance(txt, str) or not txt.strip():
            out["error"] = "Annual filing text is unavailable"
            return out
        low = txt.lower()
        evidence = scan_disclosures(txt)
        out["disclosure_evidence"] = evidence
        out["disclosure_review_required"] = any(row["flag"] is None for row in evidence.values())
        for name, phrase in KILL_PHRASES.items():
            topic = "going_concern" if name == "substantial_doubt" else name
            if topic in evidence:
                flag = evidence[topic]["flag"]
                out[f"kf_{name}"] = None if flag is None else int(flag)
            else:
                out[f"kf_{name}"] = int(phrase in low)
        out["kf_scanned"] = True
        # Extract business blurb for theme-fit gate, form-aware (C fix):
        # 20-F/40-F: Item 4 "Information on the Company"; 10-K: Item 1 "Business"
        out["business_blurb"] = _extract_business_blurb(txt, filing_form=form_used)
        # P3, magnitude-based concentration from the same full text. Reuses the P3 owner's
        # deterministic extractor (deepdive_data) so cheap_pass and deepdive agree on the
        # contract; surfacing concentration_flag here lets score() reject a ">60% single-program
        # / >40% single-customer" kill BEFORE the expensive deepdive runs.
        _tc, _tp, _cd = _extract_concentration(txt)
        out["top_customer_pct"] = _tc
        out["top_program_pct"] = _tp
        out["concentration_flag"] = _concentration_flag(_tc, _tp)
        out["concentration_detail"] = _cd
        if _cd and "ambiguous_concentration_clause" in _cd:
            out["disclosure_review_required"] = True
    except Exception as e:
        print(f"  [warn] killflag {ticker}: {e}", file=sys.stderr)
    return out


def get_concept_series(cik: str, concept: str) -> list:
    """拉某 XBRL 概念的时间序列(取 USD 单位的全部值)。"""
    url = FACTS.format(cik=str(cik).zfill(10), concept=concept)
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            return []
        units = r.json().get("units", {})
        vals = units.get("USD") or units.get("USD/shares") or []
        return sorted(vals, key=lambda x: x.get("end", ""))
    except Exception:
        return []


def latest_val(series: list):
    return series[-1]["val"] if series else None


def health_check(row) -> dict:
    """单公司机械体检:runway / 现金流质量 / 稀释 / kill-flag。"""
    cik = str(row.get("cik", "")).strip()
    if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
        raise ValueError("Valid SEC issuer identity required before financial screening")
    out = {"ticker": row["ticker"], "name": row["name"], "mktcap": row.get("mktcap")}

    # --- 财务硬数据(XBRL) ---
    cash = latest_val(get_concept_series(cik, "CashAndCashEquivalentsAtCarryingValue"))
    time.sleep(0.15)
    ni = get_concept_series(cik, "NetIncomeLoss")
    time.sleep(0.15)
    ocf = get_concept_series(cik, "NetCashProvidedByUsedInOperatingActivities")
    time.sleep(0.15)
    rev = get_concept_series(cik, "Revenues") or get_concept_series(
        cik, "RevenueFromContractWithCustomerExcludingAssessedTax")
    time.sleep(0.15)

    out["cash"] = cash
    out["net_income"] = latest_val(ni)
    out["ocf_latest"] = latest_val(ocf)
    out["revenue"] = latest_val(rev)

    # runway:现金 / 季度净烧钱(用最近 OCF 近似;OCF>0 则不烧)
    burn = None
    if ocf:
        recent_ocf = ocf[-1]["val"]
        if recent_ocf < 0 and cash is not None:
            burn = cash / (abs(recent_ocf))  # 单位=该 OCF 期数(粗略,多为年度)
    out["runway_periods"] = round(burn, 1) if burn is not None else None

    # 现金流质量:净利>0 但 OCF<0 = 红旗
    out["flag_ocf_ni_divergence"] = (
        out["net_income"] is not None and out["ocf_latest"] is not None
        and out["net_income"] > 0 and out["ocf_latest"] < 0
    )

    # --- kill-flag 全文扫描(edgartools 读 10-K 全文,精准判定)---
    flags = killflag_scan(row["ticker"])
    out.update(flags)
    # 计数:going_concern+substantial_doubt 同时命中才算"持续经营"1票(避免例行提及误报)
    has_going_concern = (flags.get("kf_going_concern") and flags.get("kf_substantial_doubt"))
    going = 1 if has_going_concern else 0
    out["killflag_count"] = (
        going
        + (flags.get("kf_material_weakness") or 0)
        + flags.get("kf_death_spiral", 0)
        + flags.get("kf_reverse_split", 0)
    )
    time.sleep(0.3)
    return out


def score(df: pd.DataFrame) -> pd.DataFrame:
    """0-100 体检分 + 淘汰判定。"""
    df = df.copy()
    if len(df) == 0:
        numeric = ("mktcap", "cash", "net_income", "ocf_latest", "revenue",
                   "runway_periods", "killflag_count", "health_score",
                   "top_customer_pct", "top_program_pct")
        boolean = ("flag_ocf_ni_divergence", "kf_scanned", "disclosure_review_required",
                   "reject_going_concern", "reject_killflags", "reject_burn",
                   "reject_concentration", "rejected", "health_score_complete")
        for col in numeric:
            df[col] = pd.Series(dtype="float64")
        for col in boolean:
            df[col] = pd.Series(dtype="bool")
        for col in ("ticker", "name", "concentration_flag", "concentration_detail",
                    "business_blurb", "filing_form", "disclosure_evidence"):
            df[col] = pd.Series(dtype="object")
        for key in KILL_PHRASES:
            df[f"kf_{key}"] = pd.Series(dtype="float64")
        return df
    # 淘汰规则(kill-flag 计数已收紧,going concern 需双命中才计1)
    zero = pd.Series(0, index=df.index)
    df["reject_going_concern"] = (df.get("kf_going_concern", zero).fillna(0).astype(bool)
                                  & df.get("kf_substantial_doubt", zero).fillna(0).astype(bool))
    df["reject_killflags"] = df["killflag_count"] >= 2
    # I4: use OCF (cash burn), not GAAP net_income, for burn rejection.
    # net_income < 0 conflates non-cash GAAP losses (impairments, write-offs) with cash distress.
    # A company with positive OCF and a non-cash impairment loss is NOT burning cash.
    # reject_burn = short runway AND negative operating cash flow (actual cash burn).
    df["reject_burn"] = df["runway_periods"].notna() & (df["runway_periods"] < 1.0) & \
                        (df["ocf_latest"].fillna(0) < 0)
    # P3, concentration kill-flag is a hard reject at the cheap-pass stage.
    # concentration_flag=="kill" (>60% single-program OR >40% single-customer) is a
    # BUY-blocking concentration; reject before deepdive.
    # "watch" does NOT reject here, it flows through to the deepdive/rubric WATCH-cap.
    if "concentration_flag" in df.columns:
        df["reject_concentration"] = df["concentration_flag"].fillna("") == "kill"
    else:
        df["reject_concentration"] = False
    df["rejected"] = (df["reject_going_concern"] | df["reject_killflags"]
                      | df["reject_burn"] | df["reject_concentration"])
    # 简单体检分:从100扣
    s = pd.Series(100.0, index=df.index)
    s -= df["killflag_count"].fillna(0) * 20
    s -= df["flag_ocf_ni_divergence"].astype(int) * 15
    s -= (df["revenue"].fillna(0) <= 0).astype(int) * 25
    s -= (df["runway_periods"].fillna(99) < 2).astype(int) * 20
    df["health_score"] = s.clip(0, 100)
    # The numeric score summarizes observed flags. Unknown disclosure evidence
    # remains eligible for further investigation, but cannot be labeled complete.
    unresolved = df.get("disclosure_review_required", pd.Series(True, index=df.index))
    scanned = df.get("kf_scanned", pd.Series(False, index=df.index))
    df["health_score_complete"] = scanned.fillna(False).astype(bool) & ~unresolved.fillna(True).astype(bool)
    return df


def _selftest():
    """Selftest:
    1. IQST — must flag going_concern + substantial_doubt (Guard 2/3: full-text double-hit).
    2. KOP  — amendments=False must NOT return a 10-K/A as the latest filing (Guard 1).
    3. EGAN — must NOT flag kf_material_weakness (FP fix: bare boilerplate must not fire;
               requires affirmative ICFR finding per Guard 3b).
    4. business_blurb — EGAN blurb must be real prose: >100 chars, contains lowercase
               words, not dominated by dots/digits (TOC noise prevention, A4 fix).
    5. KOP  — must NOT flag kf_material_weakness = 0 (Guard 3b anchor test; clean filer).
    """
    init_edgar()
    # Test 1: IQST going-concern double-hit
    r = killflag_scan("IQST")
    assert r["kf_going_concern"] == 1 and r["kf_substantial_doubt"] == 1, (
        f"IQST must flag going concern (amendments=False fix), "
        f"got kf_going_concern={r['kf_going_concern']} kf_substantial_doubt={r['kf_substantial_doubt']}"
    )
    print(f"  IQST: going_concern={r['kf_going_concern']} substantial_doubt={r['kf_substantial_doubt']}  OK")

    # Test 2: KOP amendment exclusion, latest filing must be 10-K, not 10-K/A
    kop_company = Company("KOP")
    fl = kop_company.get_filings(form="10-K", amendments=False)
    f = fl.latest(1) if fl is not None and len(fl) else None
    assert f is not None, "KOP: no 10-K found (amendments=False)"
    form_type = str(getattr(f, "form", "") or getattr(f, "form_type", "")).strip()
    assert form_type != "10-K/A", (
        f"KOP: amendments=False must not return a 10-K/A, got form_type={form_type!r}"
    )
    print(f"  KOP: form_type={form_type!r} (not 10-K/A)  OK")

    # Test 3: EGAN no-material-weakness FP fix (Guard 3b)
    # EGAN (eGain Corp) is a healthy filer that should NOT have an actual ICFR material weakness.
    # The old bare-phrase rule would fire on boilerplate risk-factor language; the new
    # affirmative-finding rule must return 0 for a company with no actual ICFR finding.
    egan_r = killflag_scan("EGAN")
    assert egan_r["kf_material_weakness"] == 0, (
        f"EGAN: kf_material_weakness must be 0 under affirmative-finding rule "
        f"(bare boilerplate must not fire), got {egan_r['kf_material_weakness']}"
    )
    print(f"  EGAN: kf_material_weakness={egan_r['kf_material_weakness']} (FP fix verified)  OK")

    # Test 4: business_blurb is real prose, not TOC noise (A4 fix)
    blurb = egan_r.get("business_blurb", "")
    assert len(blurb) > 100, (
        f"EGAN: business_blurb should be >100 chars (Item 1 extraction), got len={len(blurb)}"
    )
    # Verify prose quality: must contain lowercase words (real prose) and not be dominated by dots.
    sample200 = blurb[:200]
    alpha_count = sum(1 for c in sample200 if c.isalpha())
    dot_digit_count = sum(1 for c in sample200 if c in "0123456789.")
    assert alpha_count >= 50, (
        f"EGAN blurb first 200 chars has only {alpha_count} alpha chars — looks like TOC noise.\n"
        f"First 200 chars: {sample200!r}"
    )
    assert len(sample200) == 0 or dot_digit_count / len(sample200) <= 0.40, (
        f"EGAN blurb first 200 chars is {dot_digit_count/len(sample200):.0%} dots/digits — "
        f"looks like TOC noise.\nFirst 200 chars: {sample200!r}"
    )
    print(f"  EGAN: business_blurb length={len(blurb)} chars, alpha={alpha_count} in first 200 (prose OK)")
    print(f"  EGAN blurb first 200 chars: {sample200!r}")

    # Test 5: KOP material_weakness must be 0 (Guard 3b anchor; clean filer)
    kop_r = killflag_scan("KOP")
    assert kop_r["kf_material_weakness"] == 0, (
        f"KOP: kf_material_weakness must be 0 (clean filer, Guard 3b anchor), "
        f"got {kop_r['kf_material_weakness']}"
    )
    print(f"  KOP: kf_material_weakness={kop_r['kf_material_weakness']} (Guard 3b anchor OK)")

    # Test 6: 20-F fallback, STNG (Scorpio Tankers) is a Marshall Islands domicile
    # that files 20-F (not 10-K). killflag_scan must find the 20-F without crashing,
    # set kf_scanned=True, and filing_form must be exactly "20-F" (not 10-K or 40-F).
    # The business_blurb must be either real Item-4 prose OR empty (not the directors
    # roster from Item 1, which is garbage for theme-fit).
    stng_r = killflag_scan("STNG")
    assert stng_r["kf_scanned"] is True, (
        f"STNG: kf_scanned must be True (20-F fallback should find a filing), "
        f"got kf_scanned={stng_r['kf_scanned']} filing_form={stng_r.get('filing_form')!r}"
    )
    assert stng_r.get("filing_form") == "20-F", (
        f"STNG: filing_form must be exactly '20-F' (STNG is definitively a 20-F filer), "
        f"got {stng_r.get('filing_form')!r}"
    )
    stng_blurb = stng_r.get("business_blurb", "")
    # Blurb must be empty OR real prose (not directors roster from Item 1).
    # Directors roster contains names like "Mr." / "Ms." / "President" with few alpha chars
    # per sentence relative to a real business description.
    # We check: if non-empty, must have >= 50 alpha chars in first 200 and < 40% dots/digits.
    if stng_blurb:
        stng_sample = stng_blurb[:200]
        stng_alpha = sum(1 for c in stng_sample if c.isalpha())
        stng_dotdigit = sum(1 for c in stng_sample if c in "0123456789.")
        assert stng_alpha >= 50, (
            f"STNG blurb non-empty but looks like directors roster / TOC (only {stng_alpha} "
            f"alpha chars in first 200). First 200: {stng_sample!r}"
        )
        assert len(stng_sample) == 0 or stng_dotdigit / len(stng_sample) <= 0.40, (
            f"STNG blurb first 200 chars is {stng_dotdigit/len(stng_sample):.0%} dots/digits "
            f"— looks like TOC. First 200: {stng_sample!r}"
        )
    print(f"  STNG: kf_scanned={stng_r['kf_scanned']} filing_form={stng_r.get('filing_form')!r} "
          f"blurb_len={len(stng_blurb)} (20-F form-aware blurb OK)")
    if stng_blurb:
        print(f"  STNG blurb first 200 chars: {stng_blurb[:200]!r}")
    else:
        print("  STNG blurb: empty (acceptable — theme-fit gate will fall back to WebSearch)")

    # Generated positive-OCF case with a non-cash net loss must survive burn screening.
    from make_fixtures import source34_scenarios
    _cases = source34_scenarios()
    _test_data_positive_ocf = pd.DataFrame([_cases["positive_ocf"]])
    _scored = score(_test_data_positive_ocf)
    assert not _scored["reject_burn"].iloc[0], (
        f"I4: generated positive-OCF company with positive OCF must NOT be rejected by reject_burn "
        f"(runway_periods=None so no burn condition). "
        f"reject_burn={_scored['reject_burn'].iloc[0]}"
    )
    assert not _scored["rejected"].iloc[0], (
        f"I4: generated positive-OCF company must survive cheap_pass (no kill-flags, positive OCF). "
        f"rejected={_scored['rejected'].iloc[0]}"
    )
    print("  I4 reject_burn (OCF not net_income): generated positive-OCF company with positive OCF survives  OK")

    # Also verify the burn logic fires when OCF is negative (real cash-burn scenario):
    _test_data_negative_ocf = pd.DataFrame([{
        "ticker": "FAKE_BURN",
        "name": "Fake Burn Company",
        "mktcap": 10_000_000,
        "cash": 500_000,
        "net_income": -5_000_000,
        "ocf_latest": -2_000_000,   # truly burning cash
        "revenue": 3_000_000,
        "runway_periods": 0.25,     # cash/burn < 1.0 period
        "flag_ocf_ni_divergence": False,
        "killflag_count": 0,
        "kf_going_concern": 0,
        "kf_substantial_doubt": 0,
        "kf_material_weakness": 0,
        "kf_death_spiral": 0,
        "kf_reverse_split": 0,
        "kf_scanned": True,
        "business_blurb": "Startup burning cash.",
    }])
    _scored_burn = score(_test_data_negative_ocf)
    assert _scored_burn["reject_burn"].iloc[0], (
        f"I4: Cash-burning company (runway<1, OCF<0) MUST be rejected. "
        f"reject_burn={_scored_burn['reject_burn'].iloc[0]}"
    )
    print("  I4 reject_burn (OCF negative): cash-burning company correctly rejected  OK")

    # Test 8: P3, concentration_flag composition contract (reused from deepdive_data P3 owner).
    # kill if top_program_pct>60 OR top_customer_pct>40; watch in 40-60; None otherwise.
    assert _concentration_flag(None, 75.0) == "kill", "top_program 75% must be kill"
    assert _concentration_flag(45.0, None) == "kill", "top_customer 45% must be kill"
    assert _concentration_flag(None, 50.0) == "watch", "top_program 50% must be watch"
    assert _concentration_flag(40.0, None) == "watch", "top_customer 40% must be watch"
    assert _concentration_flag(10.0, 10.0) is None, "low concentration must be None"
    assert _concentration_flag(None, None) is None, "no concentration data must be None"
    print("  P3 _concentration_flag contract (kill>60prog/>40cust, watch 40-60): OK")

    # Vary only the concentration label in an otherwise clean generated company.
    def _clean_conc_row(ticker, conc_flag):
        return dict(_cases["concentration_base"], ticker=ticker, concentration_flag=conc_flag)
    _conc_df = pd.DataFrame([
        _clean_conc_row("FAKE_KILL", "kill"),
        _clean_conc_row("FAKE_WATCH", "watch"),
        _clean_conc_row("FAKE_NONE", None),
    ])
    _conc_scored = score(_conc_df).set_index("ticker")
    assert _conc_scored.loc["FAKE_KILL", "reject_concentration"], (
        "P3: concentration_flag=='kill' must set reject_concentration=True")
    assert _conc_scored.loc["FAKE_KILL", "rejected"], (
        "P3: a clean company with concentration 'kill' must be REJECTED before deepdive (generated concentration case)")
    assert not _conc_scored.loc["FAKE_WATCH", "reject_concentration"], (
        "P3: 'watch' concentration must NOT reject at cheap_pass (flows to WATCH-cap)")
    assert not _conc_scored.loc["FAKE_WATCH", "rejected"], (
        "P3: clean 'watch' company must survive cheap_pass")
    assert not _conc_scored.loc["FAKE_NONE", "rejected"], (
        "P3: clean company with no concentration must survive cheap_pass")
    print("  P3 score() concentration kill-reject (kill rejected; watch/none survive): OK")

    # Test 10: P3, score() must not crash when the concentration_flag column is absent
    # (backward-compat with pre-P3 cheap_pass CSVs / event records lacking the field).
    _legacy_df = pd.DataFrame([{
        "ticker": "FAKE_LEGACY", "name": "Legacy", "mktcap": 5e8,
        "cash": 5e7, "net_income": 1e7, "ocf_latest": 2e7, "revenue": 1e8,
        "runway_periods": None, "flag_ocf_ni_divergence": False,
        "killflag_count": 0, "kf_going_concern": 0, "kf_substantial_doubt": 0,
        "kf_material_weakness": 0, "kf_death_spiral": 0, "kf_reverse_split": 0,
        "kf_scanned": True, "business_blurb": "Legacy record, no concentration field.",
    }])
    _legacy_scored = score(_legacy_df)
    assert not _legacy_scored["reject_concentration"].iloc[0], (
        "P3: missing concentration_flag column must default reject_concentration=False (no crash)")
    assert not _legacy_scored["rejected"].iloc[0], (
        "P3: legacy clean row must survive when concentration_flag column is absent")
    print("  P3 score() legacy-record backward-compat (no concentration_flag column): OK")

    # Test 11: P5, resolve_ceiling resolves mktcap via the _common fallback, flows through
    # band='unknown' (null mktcap is NEVER a silent drop), and excludes only 'large'.
    # Use injected ciks/prices: yfinance-null rows are reconstructed from SEC shares x price
    # by resolve_mktcap (called inside resolve_ceiling). To keep the selftest network-free,
    # we cover the band-routing + null-flow-through using already-known mktcaps and a genuinely
    # unresolvable null (no price -> stays None -> band='unknown' -> flows through).
    _ceil_df = pd.DataFrame([
        {"ticker": "DEEPC", "name": "Deep", "cik": "1", "mktcap": 8e8, "price": 10.0,
         "smallcap_candidate": True},
        {"ticker": "WATCHC", "name": "Watch", "cik": "2", "mktcap": 3e9, "price": 20.0,
         "smallcap_candidate": True},
        {"ticker": "BIGC", "name": "Big", "cik": "3", "mktcap": 8e9, "price": 50.0,
         "smallcap_candidate": True},
        {"ticker": "UNKC", "name": "Unknown", "cik": "4", "mktcap": None, "price": None,
         "smallcap_candidate": True},
    ])
    _kept = resolve_ceiling(_ceil_df, max_mcap=2e9, watch_max=5e9).set_index("ticker")
    assert "BIGC" not in _kept.index, (
        "P5: 'large' (>watch_max) must be excluded from cheap_pass candidates")
    assert "UNKC" in _kept.index, (
        "P5: null-mktcap row must FLOW THROUGH as band='unknown', NOT be dropped (the v0.2.0 bug)")
    assert _kept.loc["UNKC", "band"] == "unknown", (
        f"P5: genuinely unresolvable mktcap must band='unknown', got {_kept.loc['UNKC','band']!r}")
    assert _kept.loc["UNKC", "mktcap_source"] == "unresolved", (
        "P5: unresolvable row mktcap_source must be 'unresolved'")
    assert _kept.loc["DEEPC", "band"] == "deep", "P5: 0.8B must band 'deep'"
    assert _kept.loc["WATCHC", "band"] == "watch", "P5: 3B must band 'watch' (kept, surfaced separately)"
    print("  P5 resolve_ceiling (large excluded; unknown flows through; deep/watch banded): OK")

    # Test 12: P5, the SEC-shares x price reconstruction leg (network-free, via resolve_mktcap
    # with an injected shares_fn) feeds the band. resolve_ceiling calls resolve_mktcap internally
    # for null-mktcap rows; here we verify the leg's contract directly so the in-scope-resolution
    # path is asserted deterministically: yfinance-null + price + SEC shares -> a real mktcap whose
    # band routes correctly (a small reconstructed cap stays 'deep' and flows through to deepdive).
    _mc, _src = resolve_mktcap(None, 5.0, "123", shares_fn=lambda c: 1e8)  # 1e8 sh x $5 = 5e8
    assert _mc == 5e8 and _src == "sec_shares_x_price", (
        f"P5: SEC shares x price fallback must reconstruct mktcap, got {_mc},{_src}")
    assert band_for(_mc, 2e9, 5e9) == "deep", (
        "P5: a 0.5B reconstructed mktcap must band 'deep' (in-scope, flows to deepdive)")
    print("  P5 SEC-shares x price reconstruction leg (yfinance-null -> in-scope 'deep'): OK")

    # A generated missing-cap company resolves before size exclusion.
    _cap = _cases["market_cap"]
    _p12_ticker = _cap["ticker"]
    _p12_df = pd.DataFrame([
        {"ticker": _p12_ticker, "name": _cap["name"], "cik": _cap["cik"], "mktcap": None,
         "price": _cap["price"], "smallcap_candidate": True},
        {"ticker": "BIGX", "name": "AcmeCorp Synthetic Oversize", "cik": _cap["large_cik"],
         "mktcap": None, "price": _cap["large_price"], "smallcap_candidate": True},
    ])
    _shares = {_cap["cik"]: _cap["shares"], _cap["large_cik"]: _cap["large_shares"]}
    _p12_kept = resolve_ceiling(
        _p12_df, max_mcap=2e9, watch_max=5e9,
        shares_fn=lambda c: _shares.get(str(c).strip().lstrip("0")),
    ).set_index("ticker")
    assert _p12_ticker in _p12_kept.index, (
        "P12: a yfinance-NaN row with resolvable SEC shares x price must NOT be size-excluded "
        "(resolved market cap must reach cheap_pass)")
    assert _p12_kept.loc[_p12_ticker, "mktcap"] == _cap["value"], (
        f"P12: generated market cap must equal shares times price, "
        f"got {_p12_kept.loc[_p12_ticker,'mktcap']}")
    assert _p12_kept.loc[_p12_ticker, "mktcap_source"] == "sec_shares_x_price", (
        f"P12: generated market cap must use SEC shares times price, "
        f"got {_p12_kept.loc[_p12_ticker,'mktcap_source']!r}")
    assert _p12_kept.loc[_p12_ticker, "band"] == "deep", (
        f"P12: generated in-band reconstruction must band 'deep' (in-scope, NOT 'unknown'), "
        f"got {_p12_kept.loc[_p12_ticker,'band']!r}")
    # BIGX: the SEC reconstruction fires FIRST, THEN the >watch_max exclusion bites ,
    # confirming resolution strictly precedes size-exclusion (not the reverse).
    assert "BIGX" not in _p12_kept.index, (
        "P12: a reconstructed mktcap that is genuinely 'large' is excluded AFTER resolution "
        "(resolve-then-size-exclude ordering)")
    print("  P12 SEC shares x price fires BEFORE size-exclusion "
          "(missing-cap case kept as 'deep'; oversize excluded after reconstruction): OK")

    print("cheap_pass selftest PASS (IQST going-concern + KOP amendment exclusion + EGAN MW FP fix + business_blurb + KOP MW=0 + STNG 20-F form-aware blurb + I4 reject_burn OCF fix + P3 concentration kill-reject + P5 ceiling resolution/unknown flow-through + P12 SEC shares x price before size-exclusion)")


def resolve_ceiling(cand: pd.DataFrame, max_mcap: float,
                    watch_max: float | None = None,
                    shares_fn=None) -> pd.DataFrame:
    """P5/P12 — resolve the market-cap ceiling INSIDE cheap_pass, before the expensive deepdive.

    For each candidate row: resolve mktcap via the _common fallback chain when it is
    null/non-positive (yfinance -> SEC companyfacts shares x price), then tag a band via
    band_for. Only the "large" band (> watch_band_max) is excluded as out-of-scope. The
    "deep", "watch", AND "unknown" bands FLOW THROUGH into the body health check — a null
    mktcap remains explicit as unknown when resolution is unavailable.

    SEC shares times price reconstruction precedes the size filter. An eligible
    reconstruction receives its resolved band before exclusion; unresolved rows
    continue with the unknown band. shares_fn permits isolated acquisition controls.

    Sets/overwrites these columns on the returned frame:
      - mktcap         (resolved, may stay None for unknown)
      - mktcap_source  ("yfinance" / "sec_shares_x_price" / "unresolved")
      - band           ("deep" / "watch" / "large" / "unknown")
    and returns only the rows that are NOT "large".
    """
    if watch_max is None:
        watch_max = CFG.get("watch_band_max", 5_000_000_000)
    cand = cand.copy()
    if "mktcap_source" not in cand.columns:
        cand["mktcap_source"] = None
    resolved, sources, bands = [], [], []
    for _, row in cand.iterrows():
        mc = row.get("mktcap")
        # Treat None / NaN / non-positive as "needs resolution".
        needs = mc is None or (isinstance(mc, float) and mc != mc) or (
            isinstance(mc, (int, float)) and mc <= 0)
        if needs:
            # P12: resolve (incl. SEC shares x price) BEFORE banding/size-exclusion.
            if shares_fn is not None:
                mc, src = resolve_mktcap(None, row.get("price"), row.get("cik"),
                                         shares_fn=shares_fn)
            else:
                mc, src = resolve_mktcap(None, row.get("price"), row.get("cik"))
        else:
            mc = float(mc)
            src = row.get("mktcap_source") or "yfinance"
        band = band_for(mc, max_mcap, watch_max)
        resolved.append(mc)
        sources.append(src)
        bands.append(band)
    cand["mktcap"] = resolved
    cand["mktcap_source"] = sources
    cand["band"] = bands
    # Exclude only out-of-scope large caps; unknown flows through (not dropped).
    return cand[cand["band"] != "large"].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=False)
    ap.add_argument("--max-mcap", type=float, default=CFG["market_cap_max"])
    ap.add_argument("--limit", type=int, default=0, help="只测前N家(调试用)")
    ap.add_argument("--out-slug", default="", help="输出文件名 slug(多主题区分)")
    ap.add_argument(
        "--selftest", action="store_true",
        help="Run legacy checks using live SEC filings; requires configured EDGAR access",
    )
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.universe:
        ap.error("--universe is required when not using --selftest")

    if args.limit < 0 or not 0 < args.max_mcap < float("inf"):
        ap.error("--limit must be nonnegative and --max-mcap finite and positive")
    uni_path = Path(args.universe)
    is_json = uni_path.suffix.lower() == ".json"
    required = {"ticker", "cik", "name"}
    try:
        if is_json:
            records = json.loads(uni_path.read_text(encoding="utf-8"))
            if not isinstance(records, list) or any(
                    not isinstance(row, dict) or not required.issubset(row) for row in records):
                raise ValueError("JSON must be a list of records with ticker, cik and name")
            uni = pd.DataFrame(records) if records else pd.DataFrame(columns=sorted(required))
        elif uni_path.suffix.lower() == ".csv":
            uni = pd.read_csv(uni_path, dtype={"ticker": str, "cik": str, "name": str})
            if not (required | {"smallcap_candidate"}).issubset(uni.columns):
                raise ValueError("CSV requires ticker, cik, name and smallcap_candidate columns")
            if not uni["smallcap_candidate"].isin([True, False]).all():
                raise ValueError("smallcap_candidate must contain boolean values")
        else:
            raise ValueError("--universe must be a JSON or CSV file")
        for col in required:
            if any(isinstance(value, bool) or (not pd.isna(value) and not isinstance(value, (str, int)))
                   for value in uni[col]):
                raise ValueError(f"invalid {col} value")
            uni[col] = uni[col].fillna("").astype(str)
        for col in ("mktcap", "price"):
            if col not in uni:
                uni[col] = None
            uni[col] = pd.to_numeric(uni[col], errors="raise")
    except (OSError, ValueError, TypeError) as exc:
        ap.error(f"invalid --universe: {exc}")
    upstream = read_stage_receipt(uni_path, len(uni))
    if upstream["status"] == "invalid":
        ap.error("--universe has an invalid or mismatched completion receipt")
    event_binding = None
    if upstream.get("stage") in {"event_spinoffs", "event_insider_clusters"}:
        from _event_admission import artifact_binding, write_event_admission
        if Path(REPORTS).resolve() != uni_path.resolve().parent:
            ap.error("Event screening must write to the discovery run directory")
        event_binding = artifact_binding(uni_path)
    cand = uni.copy() if is_json else uni[uni["smallcap_candidate"] == True].copy()
    # Parsing and structural validation finish before provider initialization.
    if not cand.empty:
        init_edgar()
    cand = resolve_ceiling(cand, args.max_mcap)
    selected_count = len(cand)
    eligible_bands = cand["band"].to_dict()
    if args.limit:
        cand = cand.sort_values("mktcap").head(args.limit)
    decisions = {}
    for source_index, row in uni.iterrows():
        input_band = row.get("band")
        if not isinstance(input_band, str) or not input_band:
            input_band = "unknown"
        if not is_json and not row["smallcap_candidate"]:
            decision = "excluded_existing_candidate_flag"
        elif source_index not in eligible_bands:
            decision = "excluded_existing_large_band"
        elif source_index not in cand.index:
            decision = "not_processed_limit"
        else:
            decision = "pending"
        decisions[str(source_index)] = {
            "input_index": int(source_index), "cik": row["cik"], "ticker": row["ticker"],
            "band": eligible_bands.get(source_index, "large" if
                decision == "excluded_existing_large_band" else input_band),
            "screening_decision": decision}
    print(f"对 {len(cand)} 家小盘候选做机械体检...", file=sys.stderr)

    rows, work, scored_indices = [], [], []
    for i, (source_index, r) in enumerate(cand.iterrows()):
        identity = f"{r['cik']}:{r['ticker']}"
        try:
            result = health_check(r)
        except Exception:
            item = stage_work("cheap_health", identity, status="unavailable", reason="health_check_failed")
            decisions[str(source_index)]["screening_decision"] = "unavailable"
        else:
            result.update(input_index=int(source_index), cik=str(r["cik"]))
            rows.append(result)
            scored_indices.append(source_index)
            complete = (bool(result.get("kf_scanned"))
                        and not result.get("disclosure_review_required", True)
                        and all(pd.notna(result.get(key)) for key in
                                ("cash", "net_income", "ocf_latest", "revenue")))
            item = stage_work("cheap_health", identity,
                              status="complete" if complete else "unavailable",
                              reason="" if complete else "missing_health_evidence")
        item["band"] = r.get("band", "unknown")
        item["input_index"] = int(source_index)
        decisions[str(source_index)]["evidence_complete"] = item["status"] == "complete"
        work.append(item)
        if (i + 1) % 10 == 0:
            print(f"  体检 {i+1}/{len(cand)}", file=sys.stderr)
    df = pd.DataFrame(rows)
    df = score(df)
    for score_index, scored in df.iterrows():
        decisions[str(scored_indices[score_index])]["screening_decision"] = (
            "rejected_existing_policy" if scored["rejected"] else "retained")
    df = df.sort_values(["rejected", "health_score"], ascending=[True, False])

    date = today()
    tag = f"{args.out_slug}_" if args.out_slug else ""
    out = prepare_stage_output(REPORTS / f"cheappass_{tag}{date}.csv")
    df.to_csv(out, index=False)
    reasons = ["limit_truncated"] if len(cand) < selected_count else []
    completion = stage_completion("cheap_pass", len(df), work=work,
                                  upstream=[upstream], reasons=reasons)
    completion["selected_count"] = selected_count
    completion["input_count"] = len(uni)
    completion["input_artifact"] = str(uni_path.resolve())
    completion["attempted_count"] = len(cand)
    completion["scored_count"] = len(df)
    completion["decisions"] = list(decisions.values())
    if event_binding is not None:
        if artifact_binding(uni_path) != event_binding:
            raise ValueError("Event discovery changed during screening")
        completion["input"] = event_binding
    write_stage_receipt(out, completion)
    event_completion = None
    if event_binding is not None:
        admitted, event_completion = write_event_admission(uni_path, out)
        print(f"Event admission: {admitted}; status: {event_completion['status']}")

    survivors = df[~df["rejected"]]
    print(f"\n=== Cheap pass 结果 ===")
    print(f"体检 {len(df)} 家 | 淘汰 {df['rejected'].sum()} 家 | 幸存 {len(survivors)} 家")
    print(f"\n幸存者(按体检分,进 deep dive 候选):")
    for _, r in survivors.head(15).iterrows():
        rev = f"${r['revenue']/1e6:.0f}M" if pd.notna(r['revenue']) else "无营收"
        print(f"  {r['ticker']:8} 分{r['health_score']:5.0f}  kill-flag {int(r['killflag_count'])}  营收{rev:>8}  {r['name'][:32]}")
    print(f"\n被淘汰(kill-flag>=3 或烧钱):")
    for _, r in df[df["rejected"]].head(12).iterrows():
        print(f"  {r['ticker']:8} kill-flag {int(r['killflag_count'])}  {r['name'][:36]}")
    print(f"\n清单: {out}")
    print(f"Stage status: {completion['status']}")
    return 0 if (completion["status"] == "complete"
                 and (event_completion is None or event_completion["status"] == "complete")) else 2


if __name__ == "__main__":
    sys.exit(main())
