"""Generate C_cluster1.json validation report for Phase C insider cluster batch 1."""
import json
import os

def load_json_safe(path):
    for enc in ['utf-8', 'utf-8-sig', 'latin-1']:
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except Exception:
            continue
    return None

tickers = ['WHF', 'PSUS', 'VTS', 'SPOK', 'VRA', 'LODE', 'LOGC', 'RMT', 'VIRC', 'PICS', 'MBC', 'EVTC', 'ESEA', 'BETR', 'MOBI']

n_insiders_map = {
    'WHF': 2, 'PSUS': 7, 'VTS': 3, 'SPOK': 2, 'VRA': 2,
    'LODE': 4, 'LOGC': 3, 'RMT': 2, 'VIRC': 2, 'PICS': 4,
    'MBC': 4, 'EVTC': 5, 'ESEA': 2, 'BETR': 5, 'MOBI': 7
}
value_usd_map = {
    'WHF': 838455, 'PSUS': 70735390, 'VTS': 2038036, 'SPOK': 473525, 'VRA': 204821,
    'LODE': 4243906, 'LOGC': 3793895, 'RMT': 225641, 'VIRC': 124275, 'PICS': 3356398,
    'MBC': 696390, 'EVTC': 2251252, 'ESEA': 104410, 'BETR': 6129458, 'MOBI': 19088949
}

ticker_records = []
n_buy = 0
n_avoid = 0
n_watch = 0
n_abstain = 0

for ticker in tickers:
    dd = load_json_safe(f'reports/smallcap/deepdive_{ticker}_2026-06-19.json')
    if dd is None:
        ticker_records.append({
            'ticker': ticker, 'error': 'load_failed', 'trigger': 'error',
            'note': 'load_failed', 'mos_basis': None, 'mos_pct': None,
            'kill_flags': [], 'n_insiders': n_insiders_map.get(ticker, 0)
        })
        continue

    tenk = dd.get('tenk', {}) or {}
    going_concern = tenk.get('has_going_concern', None)
    material_weakness = tenk.get('has_material_weakness', None)
    death_spiral = tenk.get('has_death_spiral', None)

    kill_flags_list = []
    if going_concern is True:
        kill_flags_list.append('going_concern')
    if material_weakness is True:
        kill_flags_list.append('material_weakness')
    if death_spiral is True:
        kill_flags_list.append('death_spiral')
    kill_flag_count = len(kill_flags_list)

    val = dd.get('valuation', {}) or {}
    mos_basis = val.get('mos_basis', 'unknown')
    mos_raw = val.get('margin_of_safety_pct', None)
    nav_mos_raw = val.get('nav_margin_of_safety_pct', None)
    mos_pct = round(mos_raw * 100, 1) if mos_raw is not None else None
    nav_mos_pct = round(nav_mos_raw * 100, 1) if nav_mos_raw is not None else None
    data_quality = val.get('data_quality', [])

    n_insiders = n_insiders_map.get(ticker, 0)
    value_usd = value_usd_map.get(ticker, None)

    trigger = 'WATCH'
    note = ''

    if mos_basis == 'fcf_cap':
        if mos_pct is not None and mos_pct >= 30:
            if kill_flag_count == 0:
                trigger = 'BUY'
                dq_penalty = len(data_quality)
                conf = max(30, 100 - dq_penalty * 10)
                note = (
                    'fcf_cap MoS=' + str(mos_pct) + '%>=30%, 0 kill-flags; '
                    + str(dq_penalty) + ' data_quality flags -> confidence=' + str(conf) + '%'
                )
                n_buy += 1
            else:
                trigger = 'AVOID'
                note = 'MoS=' + str(mos_pct) + '%>=30% blocked by kill_flags=' + str(kill_flags_list)
                n_avoid += 1
        elif mos_pct is None:
            trigger = 'abstain'
            note = 'MoS null (neg/unavail FCF); kill_flags=' + str(kill_flags_list)
            n_abstain += 1
        else:
            if kill_flag_count > 0:
                trigger = 'AVOID'
                n_avoid += 1
            else:
                trigger = 'WATCH'
                n_watch += 1
            note = 'MoS=' + str(mos_pct) + '%<30%; kill_flags=' + str(kill_flags_list)
    elif mos_basis == 'nav':
        if nav_mos_pct is not None and nav_mos_pct >= 30:
            if kill_flag_count == 0:
                trigger = 'BUY(nav,0.6conf)'
                note = 'NAV MoS=' + str(nav_mos_pct) + '%>=30%, 0 kill-flags'
                n_buy += 1
            else:
                trigger = 'AVOID'
                note = 'NAV kill_flags block: ' + str(kill_flags_list)
                n_avoid += 1
        else:
            nav_str = str(nav_mos_pct) + '%' if nav_mos_pct is not None else 'null'
            if kill_flag_count > 0:
                trigger = 'AVOID'
                n_avoid += 1
            else:
                trigger = 'WATCH'
                n_watch += 1
            note = 'NAV MoS=' + nav_str + '<30%; kill_flags=' + str(kill_flags_list)
    elif mos_basis == 'abstain':
        trigger = 'abstain'
        note = 'abstain basis'
        n_abstain += 1
    else:
        trigger = 'abstain'
        note = 'no valuation data (mos_basis=' + str(mos_basis) + ')'
        n_abstain += 1

    ticker_records.append({
        'ticker': ticker,
        'mos_basis': mos_basis,
        'mos_pct': mos_pct,
        'nav_mos_pct': nav_mos_pct,
        'kill_flags': kill_flags_list,
        'n_insiders': n_insiders,
        'value_usd': value_usd,
        'trigger': trigger,
        'note': note,
        'data_quality_flags': data_quality
    })

by_mos_basis = {}
for r in ticker_records:
    b = r.get('mos_basis') or 'unknown'
    by_mos_basis[b] = by_mos_basis.get(b, 0) + 1

output = {
    'phase': 'C',
    'label': 'insider_cluster_batch1',
    'run_date': '2026-06-19',
    'summary': (
        'Phase C batch 1: 57 small-cap insider-cluster candidates found (band=deep/watch/unknown, mktcap<2B). '
        'First 15 processed. '
        '1 BUY (WHF, fcf_cap MoS=137.9%, 0 kill-flags, but heavy data_quality caveats: BDC structure, '
        'revenue=null, fcf=ocf_proxy, confidence floor ~50%). '
        '1 AVOID (ESEA, MoS=86.6% but going_concern kill-flag). '
        '8 WATCH (MoS<30%, clean kill-flags), 5 abstain (missing/neg FCF or no valuation). '
        'openinsider cluster signal present for all 15; deepdive_data insider counts diverge for some '
        'due to different lookback windows. No crashes.'
    ),
    'tickers': ticker_records,
    'metrics': {
        'n_processed': 15,
        'n_buy': n_buy,
        'n_avoid': n_avoid,
        'n_watch': n_watch,
        'n_abstain': n_abstain,
        'by_mos_basis': by_mos_basis
    },
    'findings': [
        (
            'WHF (Whitehorse Finance, BDC): BUY on fcf_cap MoS=137.9%, 0 kill-flags. '
            'CRITICAL CAVEAT: revenue=null (BDC has no standard GAAP revenue in XBRL), '
            'OCF is proxy (loan portfolio cash flows), 5 data_quality flags. '
            'Per rubric confidence = max(30%, 100%-5*10%) = 50%. '
            'Catalyst: 2 insiders $838K open-market buy (T2-quality from openinsider; '
            'EDGAR Form 4 verification required before crediting as T1). '
            'FCF model may be structurally unsuitable for BDC -- human judgment advised before acting.'
        ),
        (
            'ESEA (Euroseas Ltd, containership): MoS=86.6% but going_concern=True in 20-F. '
            'Kill-flag blocks BUY per zero-tolerance rule. Trigger=AVOID.'
        ),
        (
            'LODE (Comstock Inc): going_concern=True, neg FCF, MoS null. '
            '4 insiders bought $4.2M -- strong conviction signal, but fundamentals too distressed. abstain.'
        ),
        (
            'LOGC (ContextLogic Holdings): going_concern=True + material_weakness (2 kill-flags), '
            'neg FCF, MoS null. 3 insiders bought $3.8M. abstain.'
        ),
        (
            'PICS (N.V.): material_weakness, no financial data accessible from SEC XBRL, '
            'MoS null. 4 insiders bought $3.4M. abstain.'
        ),
        (
            'PSUS (Pershing Square USA): Closed-end fund structure, '
            'yfinance returned null market cap. valuation errored, mos_basis=unknown. '
            '7 insiders bought $70.7M. abstain.'
        ),
        (
            'RMT (Royce Micro-Cap Trust): Closed-end fund, no revenue/OCF in SEC XBRL. '
            'MoS null. abstain.'
        ),
        (
            'openinsider data quality: tool encounters "header row not found" warning on some pulls '
            '(falls back to hardcoded column indices -- not a crash, just layout detection fallback). '
            'Insider buy counts in deepdive_data diverge from openinsider for WHF/PSUS/RMT '
            'because deepdive_data uses 12-month EDGAR Form 4 scan while openinsider uses '
            'a rolling cluster window. Expected per event-driven.md caveat #5. '
            'Large-dollar cluster buys should be verified directly in EDGAR Form 4 before treating as T1.'
        ),
        (
            'VTS (Vitesse Energy): MoS=10.4%<30%, cyclical E&P, 3 insiders $2.0M buy. '
            'Insider catalyst(b) present but MoS threshold not cleared. WATCH.'
        ),
        (
            'BETR (Better Home & Finance): nav basis, NAV MoS=-100%, debt_to_assets=0.9945. '
            '5 insiders bought $6.1M -- notable conviction but company is effectively insolvent on NAV. WATCH.'
        )
    ]
}

os.makedirs('reports/smallcap/validation', exist_ok=True)
out_path = 'reports/smallcap/validation/C_cluster1.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print('Written: ' + out_path)
print()
print('=== FINAL SUMMARY ===')
print('Processed: ' + str(len(ticker_records)) +
      ' | BUY: ' + str(n_buy) +
      ' | AVOID: ' + str(n_avoid) +
      ' | WATCH: ' + str(n_watch) +
      ' | abstain: ' + str(n_abstain))
for r in ticker_records:
    mos_val = r.get('mos_pct')
    mos_str = (str(mos_val) + '%') if mos_val is not None else 'null'
    print('  ' + r['ticker'].ljust(6) +
          ' | ' + (r.get('mos_basis') or 'N/A').ljust(8) +
          ' | MoS=' + mos_str.ljust(8) +
          ' | kf=' + str(r['kill_flags']) +
          ' | => ' + r['trigger'])
