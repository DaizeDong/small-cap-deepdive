"""
filter_by_sic.py — SIC-code coarse-exclusion library (Gate 1 of the two-stage precision gate)

Library functions:
  sic_ok(sic, hard_exclude) — returns True if the SIC code should NOT be excluded.

run_theme.py imports sic_ok directly; this file is NOT run as a standalone pipeline step.

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


def sic_ok(sic: str, hard_exclude: list[str]) -> bool:
    """粗排除:只剔明显无关大类(医药/软件/金融/零售),其余保留交 LLM 精判。
    SIC 缺失时保留(让 LLM 判),不一刀切剔除。"""
    sic = str(sic).split(".")[0].strip()
    if not sic or sic == "nan":
        return True  # 缺 SIC 不剔,交 LLM 判
    # 按长到短匹配硬排除前缀
    for ex in sorted(hard_exclude, key=len, reverse=True):
        if sic.startswith(ex):
            return False
    return True


def _selftest():
    he = CFG["sic_hard_exclude"]
    assert sic_ok("2810", he) is True, "NL/VHI 2810 must NOT be excluded"
    assert sic_ok("2834", he) is False, "pharma 2834 must be excluded"
    assert sic_ok("8071", he) is False, "medical lab 8071 must be excluded"
    assert sic_ok("3743", he) is True, "railcar 3743 must be kept"
    assert sic_ok("", he) is True, "missing sic must be kept (defer to LLM)"
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
