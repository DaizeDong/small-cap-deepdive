"""
run_theme.py — Single-theme end-to-end driver

Orchestrates: discover → cheap_pass → SIC filter → handoff message.

Stages:
  1. discover.py  — SEC FTS recall + market-cap filter → universe_<slug>_<date>.csv
  2. cheap_pass.py — mechanical health check → cheappass_<slug>_<date>.csv
  3. (inline) SIC filter: join universe for cik/sic, apply filter_by_sic.sic_ok,
     write REPORTS/candidates_<slug>.json
  4. Print "Next steps" handoff — LLM stages are SKILL.md-orchestrated, not auto-run.

Usage:
    python tools/run_theme.py --theme "railcar,railcar leasing" --slug railcar
    python tools/run_theme.py --theme "refractory,refractory materials" --slug refractory --micro
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, slug as _slug, today

import pandas as pd

from filter_by_sic import sic_ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str) -> None:
    """Shell a sibling tool, streaming its output; abort on non-zero exit."""
    print(f"\n{'='*72}\n[{label}] {' '.join(cmd[2:])}\n{'='*72}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[ERROR] {label} exited with code {result.returncode} — aborting.", flush=True)
        sys.exit(result.returncode)


def _find_csv(pattern: str) -> Path | None:
    """Return the most recent file matching a glob pattern, or None."""
    matches = sorted(glob.glob(pattern))
    return Path(matches[-1]) if matches else None


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_discover(theme_kw: str, out_slug: str, max_mcap: float) -> Path:
    """Run discover.py; return the universe CSV path."""
    py = CFG["python_cmd"]
    tools_dir = Path(__file__).resolve().parent
    cmd = [
        py, str(tools_dir / "discover.py"),
        "--theme", theme_kw,
        "--forms", "10-K,10-Q",
        "--max-mcap", str(max_mcap),
        "--out-slug", out_slug,
    ]
    _run(cmd, "DISCOVER")

    # Locate the output — prefer today's date, fall back to any matching file.
    date = today()
    uni = REPORTS / f"universe_{out_slug}_{date}.csv"
    if not uni.exists():
        uni = _find_csv(str(REPORTS / f"universe_{out_slug}_*.csv"))
    if uni is None or not uni.exists():
        print(f"[ERROR] universe CSV not found for slug '{out_slug}'.", flush=True)
        sys.exit(1)
    print(f"[DISCOVER] output: {uni}", flush=True)
    return uni


def stage_cheap_pass(universe_csv: Path, out_slug: str) -> Path:
    """Run cheap_pass.py; return the cheappass CSV path."""
    py = CFG["python_cmd"]
    tools_dir = Path(__file__).resolve().parent
    cmd = [
        py, str(tools_dir / "cheap_pass.py"),
        "--universe", str(universe_csv),
        "--out-slug", out_slug,
    ]
    _run(cmd, "CHEAP_PASS")

    date = today()
    cp = REPORTS / f"cheappass_{out_slug}_{date}.csv"
    if not cp.exists():
        cp = _find_csv(str(REPORTS / f"cheappass_{out_slug}_*.csv"))
    if cp is None or not cp.exists():
        print(f"[ERROR] cheappass CSV not found for slug '{out_slug}'.", flush=True)
        sys.exit(1)
    print(f"[CHEAP_PASS] output: {cp}", flush=True)
    return cp


def stage_sic_filter(cheappass_csv: Path, universe_csv: Path, out_slug: str) -> Path:
    """Inline: join cheappass with universe for cik/sic, apply SIC filter, write candidates JSON."""
    hard_exclude: list[str] = CFG["sic_hard_exclude"]

    cdf = pd.read_csv(cheappass_csv)
    udf = pd.read_csv(universe_csv)[["ticker", "cik", "sic", "mktcap"]]

    # Join to obtain cik/sic for cheappass rows
    merged = cdf.merge(udf, on="ticker", how="left", suffixes=("", "_u"))

    # Keep only survivors (not rejected by cheap_pass)
    survivors = merged[~merged["rejected"]].copy()

    # Apply SIC filter
    survivors["sic_ok"] = survivors["sic"].apply(lambda x: sic_ok(str(x), hard_exclude))
    candidates = survivors[survivors["sic_ok"]].copy()

    print(
        f"\n[SIC_FILTER] cheappass survivors: {len(survivors)} → "
        f"after SIC filter: {len(candidates)}",
        flush=True,
    )

    # Build candidate records
    records = []
    for _, r in candidates.iterrows():
        cik_raw = r.get("cik")
        # business_blurb: extracted by cheap_pass.py from Item 1 of the 10-K.
        # Used by theme-fit-gate.js as PRIMARY basis for classification, eliminating
        # redundant WebSearch for each candidate (Fix 3).
        blurb_raw = r.get("business_blurb", "")
        records.append({
            "ticker": r["ticker"],
            "cik": str(int(cik_raw)) if pd.notna(cik_raw) else None,
            "name": r.get("name", ""),
            "theme_slug": out_slug,
            "sic": str(r.get("sic", "")).split(".")[0],
            "mktcap": float(r["mktcap"]) if pd.notna(r.get("mktcap")) else None,
            "health_score": float(r["health_score"]) if pd.notna(r.get("health_score")) else None,
            "killflag_count": int(r["killflag_count"]) if pd.notna(r.get("killflag_count")) else None,
            "avg_dollar_vol": float(r["avg_dollar_vol"]) if pd.notna(r.get("avg_dollar_vol")) else None,
            "business_blurb": str(blurb_raw) if pd.notna(blurb_raw) else "",
        })

    out = REPORTS / f"candidates_{out_slug}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SIC_FILTER] candidates written → {out} ({len(records)} tickers)", flush=True)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Single-theme end-to-end driver: discover → cheap_pass → SIC filter.",
    )
    ap.add_argument(
        "--theme", required=True,
        help='Comma-separated FTS keywords, e.g. "railcar,railcar leasing"',
    )
    ap.add_argument(
        "--slug", required=True,
        help="Short identifier used in output filenames, e.g. railcar",
    )
    ap.add_argument(
        "--micro", action="store_true",
        help=f"Use micro-cap limit ({CFG['micro_cap_max']/1e6:.0f}M) instead of "
             f"standard small-cap limit ({CFG['market_cap_max']/1e9:.1f}B)",
    )
    args = ap.parse_args()

    out_slug = _slug(args.slug)
    max_mcap = CFG["micro_cap_max"] if args.micro else CFG["market_cap_max"]
    cap_label = f"${max_mcap/1e6:.0f}M (micro)" if args.micro else f"${max_mcap/1e9:.1f}B"

    print(
        f"\n{'#'*72}\n"
        f"  run_theme  slug={out_slug}  cap={cap_label}\n"
        f"  theme keywords: {args.theme}\n"
        f"{'#'*72}",
        flush=True,
    )

    # Stage 1 — discover
    universe_csv = stage_discover(args.theme, out_slug, max_mcap)

    # Stage 2 — cheap pass
    cheappass_csv = stage_cheap_pass(universe_csv, out_slug)

    # Stage 3 — inline SIC filter → candidates JSON
    candidates_json = stage_sic_filter(cheappass_csv, universe_csv, out_slug)

    # Stage 4 — handoff message
    print(
        f"\n{'='*72}\n"
        f"  DONE — mechanical pipeline complete.\n"
        f"\n"
        f"  Next steps (SKILL.md-orchestrated, not auto-run by this script):\n"
        f"    1. Run LLM theme-fit gate:\n"
        f"         node workflows/theme-fit-gate.js {candidates_json}\n"
        f"    2. Batch deep-dive data collection:\n"
        f"         python tools/deepdive_data.py --candidates {candidates_json}\n"
        f"    3. Rank survivors:\n"
        f"         python tools/rank.py --slug {out_slug}\n"
        f"{'='*72}",
        flush=True,
    )


if __name__ == "__main__":
    main()
