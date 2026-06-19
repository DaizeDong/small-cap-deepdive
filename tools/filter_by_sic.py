"""
filter_by_sic.py — SIC-code coarse-exclusion library (Gate 1 of the two-stage precision gate)

Library functions:
  sic_classify(sic, hard_exclude) — returns "keep" | "review" | "drop".
    "keep"   — SIC is not in the hard-exclude list; include in candidates normally.
    "review" — SIC is in the hard-exclude list BUT the company was a theme-keyword hit;
               let the LLM gate decide (e.g. TITN SIC 5990, SNFCA SIC 6199).
    "drop"   — reserved for future explicit-drop logic; currently unused (same as old False).
  sic_ok(sic, hard_exclude) — legacy bool wrapper: True iff classify returns "keep".
    Kept for backward compatibility; callers that only need a binary pass/fail can
    still use this. run_theme.py uses sic_classify directly for tri-state tagging.

run_theme.py imports both; this file is NOT run as a standalone pipeline step.

CLI: --selftest only (runs unit assertions and exits).

Reference: reference/discovery-engine.md §Gate 1.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG

# 硬排除的 SIC 前缀:医药/医疗器械/医疗服务/软件/金融/保险/房产/零售/餐饮/玩具
HARD_EXCLUDE = CFG["sic_hard_exclude"]


def sic_classify(sic: str, hard_exclude: list[str]) -> str:
    """Tri-state SIC classifier for Phase-4 recall improvement.

    Returns:
      "keep"   — SIC is NOT in the hard-exclude list; candidate passes Gate 1 normally.
      "review" — SIC IS in the hard-exclude list but the company matched theme keywords;
                 carry it forward with sic_tier="review" so the LLM gate can decide.
                 Examples: TITN (SIC 5990 retail — farm equipment dealer),
                            SNFCA (SIC 6199 finance — real deathcare segment).
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
    """Legacy bool wrapper: True iff sic_classify returns 'keep'.
    'review' now returns True so SIC-excluded theme-hits still pass Gate 1.
    Use sic_classify directly when you need the tri-state tier."""
    tier = sic_classify(sic, hard_exclude)
    return tier != "drop"


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
        "filter_by_sic.py is a library module; run_theme.py calls sic_ok() directly.\n"
        "Use --selftest to verify the function."
    )


if __name__ == "__main__":
    main()
