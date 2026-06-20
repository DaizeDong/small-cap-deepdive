"""make_report.py — deterministic report scaffolder (P4 / ergonomics G1, G4).

The report_<ticker>.md deliverable used to be free-hand LLM output written per a prose
runbook step; the 398-file validation run produced ZERO of them (ergonomics G1). This
tool PRE-FILLS report_<ticker>.md deterministically from the deepdive + valuation JSON so
the decision-ready artifact exists regardless of agent diligence, and so the trust-relevant
facts (data_quality flags, buy_ineligible_reasons) are surfaced at the TOP of the report
instead of buried in §8 (ergonomics G4 — "every v0.2.0 BUY was a data artifact").

Two things make it machine-trustworthy:
  1. A FENCED FRONT-MATTER RATING CONTRACT (```rating ... ```) at the very top: a small
     key:value block (rating / confidence / mos_basis / mos_pct / buy_eligible / ...) that
     rank.py and finalize_run.py parse deterministically instead of regexing free prose
     (the old prose regex failed 5/11 — ergonomics G2).
  2. A DATA-QUALITY TRUST BANNER rendered directly under the rating, listing every
     valuation data_quality flag and every buy_ineligible_reason verbatim. These are the
     most decision-relevant facts (is this MoS real?) and were the least reliably surfaced.

The agent then fills the prose sections (§0–§8) of the scaffold. The front-matter block
and banner are pre-filled from hard data and must not be removed.

Usage:
    python tools/make_report.py --json reports/smallcap/deepdive_SIGA_2026-06-19.json
    python tools/make_report.py --json <deepdive_json> --out reports/smallcap/report_SIGA.md
    python tools/make_report.py --selftest
"""
from __future__ import annotations
import argparse
import glob
import json
import re
from pathlib import Path
import sys

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPORTS, today

# Sentinel used in the fenced rating block for fields the agent must finalize.
TBD = "TBD"

# English -> canonical Chinese rating label (reports + rank.py + track_forward speak 中文).
_RATING_NORM = {"buy": "买入", "watch": "观察", "hold": "观察",
                "avoid": "避开", "sell": "避开"}


def read_json_utf8(path: str | Path) -> dict:
    """Read a JSON file as UTF-8 (Windows default codepage is GBK; naive opens raise
    UnicodeDecodeError on the utf-8-written deepdive/valuation files — ergonomics G5)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(v, suffix: str = "", nd: int = 1) -> str:
    """Format a numeric value, or 'N/A' when null."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _killflag_count(deep: dict) -> int:
    """Mechanical kill-flag count: prefer explicit killflag_count, else sum the tenk booleans
    PLUS a concentration 'kill' (P3 concentration_flag is BUY-blocking)."""
    kfc = deep.get("killflag_count")
    if kfc is not None:
        try:
            return int(kfc)
        except (TypeError, ValueError):
            pass
    tk = deep.get("tenk", {}) or {}
    der = deep.get("derived", {}) or {}
    kf = sum([1 if tk.get("has_going_concern") else 0,
              1 if tk.get("has_material_weakness") else 0,
              1 if tk.get("has_death_spiral") else 0])
    if der.get("concentration_flag") == "kill":
        kf += 1
    return kf


def collect_trust_flags(deep: dict, val: dict) -> list[str]:
    """Gather every decision-relevant trust flag for the banner, de-duplicated, in a stable
    order: valuation data_quality, then buy_ineligible_reasons, then the discrete derived
    kill/decline flags (concentration, fundamental decline). Verbatim — no paraphrase."""
    flags: list[str] = []
    seen: set[str] = set()

    def _add(label: str) -> None:
        if label and label not in seen:
            seen.add(label)
            flags.append(label)

    der = deep.get("derived", {}) or {}
    for f in (val.get("data_quality") or []):
        _add(f"data_quality: {f}")
    for r in (val.get("buy_ineligible_reasons") or []):
        _add(f"buy_ineligible: {r}")
    # P3 concentration kill/watch — surface verbatim with its detail.
    cflag = der.get("concentration_flag")
    if cflag in ("kill", "watch"):
        detail = der.get("concentration_detail") or ""
        _add(f"concentration={cflag}: {detail}".rstrip(": ").rstrip())
    # P6 fundamental decline (melting-ice-cube veto).
    if der.get("fundamental_decline_flag"):
        cr = der.get("contamination_ratio")
        _add(f"fundamental_decline: contamination_ratio={_fmt(cr, nd=2)} (latest below trailing avg)")
    return flags


def build_rating_block(deep: dict, val: dict) -> str:
    """The fenced FRONT-MATTER RATING CONTRACT. Machine-parseable; pre-filled from hard data
    where deterministic (mos_basis / mos_pct / buy_eligible / kill-flags / concentration /
    decline), TBD where the agent must decide (rating / confidence / hold_period). rank.py and
    finalize_run.py read THIS block, not the prose."""
    der = deep.get("derived", {}) or {}
    ticker = deep.get("ticker") or val.get("ticker") or "UNKNOWN"

    mos_basis = val.get("mos_basis") or "abstain"
    # MoS shown is the one that matches the basis (fcf MoS for fcf_cap, nav MoS for nav).
    if mos_basis == "nav":
        mos_pct = val.get("nav_margin_of_safety_pct")
    elif mos_basis == "fcf_cap":
        mos_pct = val.get("margin_of_safety_pct")
    else:
        mos_pct = None
    # nav_margin_of_safety_pct is reported on a 0..1 ratio in some valuations; pass through verbatim.

    buy_eligible = val.get("buy_eligible")
    be_str = "true" if buy_eligible is True else ("false" if buy_eligible is False else TBD)

    lines = [
        "```rating",
        f"ticker: {ticker}",
        f"rating: {TBD}          # 买入 / 观察 / 避开 — agent decides per judgment-rubric BUY trigger",
        f"confidence: {TBD}      # 0-100 integer",
        f"hold_period: {TBD}",
        f"mos_basis: {mos_basis}",
        f"mos_pct: {_mos_field(mos_pct)}",
        f"buy_eligible: {be_str}",
        f"killflag_count: {_killflag_count(deep)}",
        f"concentration_flag: {der.get('concentration_flag') if der.get('concentration_flag') else 'null'}",
        f"fundamental_decline_flag: {'true' if der.get('fundamental_decline_flag') else 'false'}",
        "```",
    ]
    return "\n".join(lines)


def _mos_field(v) -> str:
    if v is None:
        return "null"
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return "null"


# P-E — a prose `<...>` token (e.g. "<One sentence ...>", "<e.g. ...>") that the agent never
# filled. Non-greedy, no nested '<', so the `—` em-dashes and inline quotes inside a placeholder
# are tolerated. The fenced rating block uses ' # ' comments (not angle brackets) and the trust
# banner has no '<...>', so this NEVER touches the machine-decision layer.
_PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
_PLACEHOLDER_FILLER = "_(待补)_"  # neutral "to be filled" marker — never a literal <...> token


def strip_placeholders(md: str) -> str:
    """Replace every unfilled prose `<...>` placeholder with a neutral '_(待补)_' marker so a PM
    never reads a literal angle-bracket template token (P-E), then tidy lines that became just a
    label + marker or an empty list bullet.

    The machine-decision block (fenced ```rating``` contract + DATA-QUALITY TRUST BANNER) carries
    no `<...>` tokens, so it is preserved byte-for-byte. Idempotent: a report with no placeholders
    is returned unchanged.
    """
    out_lines: list[str] = []
    for line in md.splitlines():
        new = _PLACEHOLDER_RE.sub(_PLACEHOLDER_FILLER, line)
        # A bullet/line that is now ONLY the filler (the entire content was a placeholder) is
        # noise — drop a bare "- _(待补)_" but keep "Label: _(待补)_" (the label is informative).
        stripped = new.strip()
        if stripped in ("- " + _PLACEHOLDER_FILLER, _PLACEHOLDER_FILLER):
            continue
        out_lines.append(new)
    return "\n".join(out_lines)


def build_trust_banner(flags: list[str]) -> str:
    """The DATA-QUALITY TRUST BANNER rendered under the rating. Always present (even when
    clean) so a PM knows the check ran — an empty banner is itself a signal."""
    head = "> ⚠️ **DATA-QUALITY TRUST BANNER** — read before the rating below."
    if not flags:
        return (head + "\n>\n"
                "> No valuation data_quality flags, no BUY-ineligibility reasons, no "
                "concentration/decline kill-flags. MoS inputs are clean.")
    body = "\n".join(f"> - {f}" for f in flags)
    return (head + "\n>\n"
            "> The following were raised by the data layer and MUST be weighed at the "
            "decision point (every v0.2.0 BUY was a data artifact):\n>\n" + body)


def render_report(deep: dict, val: dict, date: str | None = None) -> str:
    """Compose the full pre-filled report markdown: fenced rating contract + trust banner +
    the §0–§8 template scaffold with hard numbers pre-filled."""
    date = date or today()
    der = deep.get("derived", {}) or {}
    tk = deep.get("tenk", {}) or {}
    ticker = deep.get("ticker") or val.get("ticker") or "UNKNOWN"

    rating_block = build_rating_block(deep, val)
    banner = build_trust_banner(collect_trust_flags(deep, val))

    rev = der.get("latest_revenue")
    rev_M = round(rev / 1e6, 1) if rev else None
    ni = der.get("latest_net_income")
    ni_M = round(ni / 1e6, 1) if ni else None
    ocf = der.get("latest_ocf")
    ocf_M = round(ocf / 1e6, 1) if ocf else None

    parts = [
        f"# {ticker} Deep Dive — {date} (timestamp-locked)",
        "",
        rating_block,
        "",
        banner,
        "",
        "---",
        "",
        "## 0. One-line thesis + base-rate anchor",
        "<One sentence stating the core thesis.>",
        "Reference class: <e.g. \"pre-revenue micro-cap with AI exposure\"> — base rates: "
        "~X% zero/wipeout within 5 years, ~Y% mediocre, ~Z% acquisition/upside.",
        "",
        "## 1. Scorecard",
        "",
        "| Dimension | Score (1–5) | Tier | Basis (one line) |",
        "|---|---|---|---|",
        "| 1. Financial quality |  |  | "
        f"latest rev {_fmt(rev_M, 'M')}, NI {_fmt(ni_M, 'M')}, OCF {_fmt(ocf_M, 'M')} |",
        "| 2. Business model / moat |  |  |  |",
        "| 3. Growth / unit economics |  |  | "
        f"rev growth {_fmt(der.get('revenue_growth_pct'), '%')} |",
        "| 4. Management |  |  |  |",
        "| 5. Theme fit / timing |  |  |  |",
        "| 6. Valuation |  |  | "
        f"EV/Sales {_fmt(val.get('ev_sales'), 'x')}, EV/EBITDA {_fmt(val.get('ev_ebitda'), 'x')} |",
        "| 7. Risk / counterargument |  |  |  |",
        "| **Weighted total** | **/35** |  |  |",
        "",
        f"Kill-flag count: {_killflag_count(deep)} (from mechanical-checks layer)",
        "",
        "## 2. Bull case (falsifiable)",
        "- Claim: <specific claim>",
        "  Trigger to flip: <if X does not happen by Q__, this argument is falsified>",
        "",
        "## 3. Bear case (falsifiable) + disconfirmation search results",
        "- Claim: <specific claim>",
        "  Trigger to flip: <if X happens by Q__, this argument is falsified>",
        "",
        "Disconfirmation search: [results or \"searched, nothing found\"]",
        "",
        "## 4. Pre-mortem: most likely path to -80%",
        "<Two or three sentences. Assume you are already wrong — what happened?>",
        "",
        "## 5. Kill-flag review",
        f"- has_going_concern: {bool(tk.get('has_going_concern'))} — <one line>",
        f"- has_material_weakness: {bool(tk.get('has_material_weakness'))} — <one line>",
        f"- has_death_spiral: {bool(tk.get('has_death_spiral'))} — <one line>",
        f"- customer_concentration_flag: {der.get('concentration_flag') or 'null'} — "
        f"{der.get('concentration_detail') or '<one line on largest customer/program %>'}",
        "",
        "## 6. Valuation: implied assumptions",
        f"Current EV/Sales: {_fmt(val.get('ev_sales'), 'x')}   "
        f"EV/EBITDA: {_fmt(val.get('ev_ebitda'), 'x')}   Peer median EV/Sales: __x",
        f"EBIT source: {val.get('ebit_source') or 'N/A'}",
        f"Reverse DCF implied growth (5-yr): {_fmt(val.get('reverse_dcf_implied_growth'), '%')}   "
        f"Actual trailing growth: {_fmt(der.get('revenue_growth_pct'), '%')}",
        "Assessment: <credible / stretched / heroic>",
        f"MoS basis: {val.get('mos_basis') or 'abstain'}   "
        f"MoS: {_fmt(val.get('margin_of_safety_pct'), '%')}   "
        f"[NAV MoS: {_fmt(val.get('nav_margin_of_safety_pct'))}]   "
        f"data_quality flags: {', '.join(val.get('data_quality') or []) or 'none'}",
        "Catalyst: <one sentence with dated trigger, or \"none\">",
        "BUY trigger fires: <YES — state basis | NO — state which condition fails>",
        "",
        "## 7. Monitor triggers (which 8-Ks / data points change the rating)",
        "- <trigger 1>",
        "- <trigger 2>",
        "",
        "## 8. Known gaps and unverified items",
        "- <data point that could not be obtained, with reason>",
        "- <assumption that is load-bearing but unverified>",
        "",
    ]
    # P-E: strip unfilled prose `<...>` placeholders (the machine-decision block has none, so it
    # is preserved). A PM never sees literal template tokens; numbers already pre-filled remain.
    return strip_placeholders("\n".join(parts))


def _find_deepdive(ticker: str, reports_dir: Path) -> Path | None:
    files = glob.glob(str(reports_dir / f"deepdive_{ticker}_*.json"))
    return Path(sorted(files)[-1]) if files else None


def _load_deep_and_val(deepdive_path: Path) -> tuple[dict, dict]:
    """Load the deepdive JSON and its embedded/sidecar valuation block."""
    deep = read_json_utf8(deepdive_path)
    val = deep.get("valuation") or {}
    if not val:
        # try a sidecar valuation_<ticker>_<date>.json next to the deepdive
        ticker = deep.get("ticker", "")
        sidecars = glob.glob(str(deepdive_path.parent / f"valuation_{ticker}_*.json"))
        if sidecars:
            val = read_json_utf8(sorted(sidecars)[-1])
    return deep, val


def main() -> None:
    ap = argparse.ArgumentParser(
        description="make_report.py — deterministically pre-fill report_<ticker>.md "
                    "(fenced rating contract + data-quality trust banner) from deepdive JSON."
    )
    ap.add_argument("--json", default="",
                    help="path to deepdive_<ticker>_<date>.json (valuation read from its "
                         "embedded 'valuation' block, or a sidecar valuation_*.json)")
    ap.add_argument("--out", default="",
                    help="output path (default: <reports_dir>/report_<ticker>.md)")
    ap.add_argument("--selftest", action="store_true",
                    help="Run self-test (synthetic JSON -> banner + parseable rating) and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.json:
        ap.error("--json <deepdive_json> is required (or use --selftest)")

    deepdive_path = Path(args.json)
    if not deepdive_path.exists():
        ap.error(f"deepdive JSON not found: {deepdive_path}")

    deep, val = _load_deep_and_val(deepdive_path)
    ticker = deep.get("ticker") or val.get("ticker") or "UNKNOWN"
    md = render_report(deep, val)

    out = Path(args.out) if args.out else (deepdive_path.parent / f"report_{ticker}.md")
    out.write_text(md, encoding="utf-8")
    print(f"report scaffolded: {out}")


# ---------------------------------------------------------------------------
# Selftest — synthetic JSON -> report has banner + rating block parses + flags surfaced.
# Imports the SAME parser finalize_run.py / rank.py use, so the contract is verified end-to-end.
# ---------------------------------------------------------------------------

def _selftest() -> None:
    # SIGA-like synthetic: BUY-ineligible by concentration kill + decline + data_quality flags.
    deep = {
        "ticker": "TST",
        "derived": {
            "latest_revenue": 1.2e8, "latest_net_income": 1.0e7, "latest_ocf": 2.0e7,
            "revenue_growth_pct": -31.8,
            "concentration_flag": "kill",
            "concentration_detail": "single program 90% of revenue (BARDA)",
            "fundamental_decline_flag": True, "contamination_ratio": 0.68,
            "rev_slope_sign": -1, "latest_below_avg": True,
        },
        "tenk": {"has_going_concern": False, "has_material_weakness": False,
                 "has_death_spiral": False},
    }
    val = {
        "ticker": "TST", "mos_basis": "fcf_cap", "margin_of_safety_pct": 76.0,
        "nav_margin_of_safety_pct": None, "ev_sales": 1.1, "ev_ebitda": 4.2,
        "ebit_source": "OperatingIncomeLoss",
        "reverse_dcf_implied_growth": -12.0,
        "data_quality": ["capex_unavailable_fcf_uses_ocf_proxy",
                         "rdcf_implied_growth_very_negative:market_pricing_in_decline"],
        "buy_eligible": False,
        "buy_ineligible_reasons": ["concentration_flag=kill", "fundamental_decline_flag"],
    }

    md = render_report(deep, val, date="2026-06-20")

    # 1. Trust banner present and surfaces flags verbatim (G4).
    assert "DATA-QUALITY TRUST BANNER" in md, "trust banner must be present"
    assert "capex_unavailable_fcf_uses_ocf_proxy" in md, "data_quality flag must be verbatim in banner"
    assert "buy_ineligible: concentration_flag=kill" in md, "buy_ineligible reason must be in banner"
    assert "concentration=kill" in md, "concentration kill must be in banner"
    assert "fundamental_decline" in md, "decline flag must be in banner"

    # 2. Fenced rating contract present and parseable by the shared parser.
    assert md.lstrip().splitlines()[0].startswith("# TST Deep Dive"), "title first"
    assert "```rating" in md, "fenced rating block must be present"
    parsed = parse_rating_block(md)
    assert parsed["mos_basis"] == "fcf_cap", f"mos_basis parse: {parsed}"
    assert parsed["buy_eligible"] is False, f"buy_eligible parse: {parsed}"
    assert parsed["killflag_count"] == 1, f"killflag_count (concentration kill) parse: {parsed}"
    assert parsed["concentration_flag"] == "kill", f"concentration_flag parse: {parsed}"
    assert parsed["fundamental_decline_flag"] is True, f"decline parse: {parsed}"
    # rating/confidence pre-filled as TBD (agent decides) — must be recognized as unset.
    assert parsed["rating"] in (None, TBD), f"rating should be TBD pre-fill: {parsed}"

    # 3. Clean company -> banner says clean, no spurious flags, killflag_count 0.
    deep_clean = {"ticker": "CLN", "derived": {"concentration_flag": None,
                  "fundamental_decline_flag": False}, "tenk": {}}
    val_clean = {"ticker": "CLN", "mos_basis": "fcf_cap", "margin_of_safety_pct": 35.0,
                 "buy_eligible": True, "data_quality": [], "buy_ineligible_reasons": []}
    md_clean = render_report(deep_clean, val_clean, date="2026-06-20")
    assert "MoS inputs are clean" in md_clean, "clean banner must say clean"
    parsed_clean = parse_rating_block(md_clean)
    assert parsed_clean["buy_eligible"] is True, "clean buy_eligible true"
    assert parsed_clean["killflag_count"] == 0, "clean killflag_count 0"

    # P-E: rendered report must contain NO literal `<...>` prose placeholder tokens — a PM never
    # sees template skeletons. The machine-decision block (rating contract + trust banner) must
    # still be intact and parseable after stripping.
    assert _PLACEHOLDER_RE.search(md) is None, "no literal <...> placeholder may survive (P-E)"
    assert "<One sentence" not in md and "<e.g." not in md, "specific placeholders stripped"
    assert "```rating" in md and "DATA-QUALITY TRUST BANNER" in md, \
        "machine-decision block survives placeholder stripping"
    assert parse_rating_block(md)["mos_basis"] == "fcf_cap", "rating block still parses after strip"
    # strip_placeholders is idempotent and surgical: a clean line is untouched; a bare bullet drops.
    assert strip_placeholders("plain line") == "plain line", "clean line unchanged"
    assert strip_placeholders("- <foo>") == "", "bare placeholder bullet dropped"
    assert strip_placeholders("Catalyst: <x>") == "Catalyst: " + _PLACEHOLDER_FILLER, \
        "labelled placeholder keeps label + marker"
    assert _PLACEHOLDER_RE.search(md_clean) is None, "clean-company report also placeholder-free"

    # 4. UTF-8 read helper round-trips (GBK friction — G5).
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(p).write_text(json.dumps({"ticker": "中文", "x": 1}, ensure_ascii=False), encoding="utf-8")
    assert read_json_utf8(p)["ticker"] == "中文", "utf-8 read helper round-trip"
    os.unlink(p)

    print("make_report selftest PASS (trust banner surfaces flags + fenced rating contract parses "
          "+ clean-banner + killflag count incl. concentration + utf-8 read + P-E no literal "
          "<...> placeholders survive while machine-decision block preserved)")


# parse_rating_block is defined in finalize_run; import lazily for selftest reuse to keep a
# single parser definition (DRY — the report producer verifies the consumer's parser).
def parse_rating_block(md: str) -> dict:  # noqa: E302 (kept adjacent to selftest)
    from finalize_run import parse_rating_block as _p
    return _p(md)


if __name__ == "__main__":
    main()
