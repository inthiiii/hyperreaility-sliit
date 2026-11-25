"""Analyse a benchmark folder into summary.json, per_case.csv and REPORT.md.

    python -m project.evaluation.report results/final/evaluation-v3-run1 \
        [--price-in USD_PER_1M_INPUT --price-out USD_PER_1M_OUTPUT --price-date YYYY-MM-DD]

Method (fixed before results were seen):
* Per case and variant, take the median weighted downtime over completed repeats.
* Paired comparison A vs B uses cases where both variants have a median; difference = A - B
  (negative = A has less downtime). 95 % interval: bootstrap over cases (10,000 resamples, seed 22).
* Completion, escalation and failure are reported over all attempts; nothing is dropped.
* Cost is computed only if the user supplies dated prices; otherwise tokens are reported.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

AI = ('single', 'multi', 'no_reviewer', 'no_feedback')
PAIRS = (('multi', 'single'), ('multi', 'optimizer'), ('single', 'optimizer'), ('multi', 'no_reviewer'),
         ('multi', 'no_feedback'), ('optimizer', 'heuristic'))


def load(folder):
    return [json.loads(line) for line in (Path(folder) / 'attempts.jsonl').read_text().splitlines() if line.strip()]


def per_case(rows):
    table = defaultdict(dict)
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r['scenario_id'], r['variant'])].append(r)
    for (case, variant), items in grouped.items():
        done = [r['actual_weighted_downtime'] for r in items if r['status'] == 'completed']
        table[case][variant] = {'median_downtime': statistics.median(done) if done else None,
                                'completed': len(done), 'attempts': len(items)}
    return table


def bootstrap(diffs, n=10_000, seed=22):
    if not diffs:
        return None, None
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def paired(table, a, b):
    diffs, base = [], []
    for case, cells in sorted(table.items()):
        x, y = cells.get(a, {}).get('median_downtime'), cells.get(b, {}).get('median_downtime')
        if x is not None and y is not None:
            diffs.append(x - y)
            base.append(y)
    lo, hi = bootstrap(diffs)
    positive = [(d, y) for d, y in zip(diffs, base) if y > 0]
    rel = statistics.median([d / y for d, y in positive]) if positive else None
    return {'a': a, 'b': b, 'cases': len(diffs), 'a_better': sum(d < 0 for d in diffs), 'ties': sum(d == 0 for d in diffs),
            'b_better': sum(d > 0 for d in diffs), 'mean_diff': statistics.mean(diffs) if diffs else None,
            'median_diff': statistics.median(diffs) if diffs else None, 'ci95_mean_diff': [lo, hi],
            'median_relative_change_positive_baseline': rel}


def variant_stats(rows, prices):
    out = {}
    by = defaultdict(list)
    for r in rows:
        by[r['variant']].append(r)
    for variant, items in sorted(by.items()):
        ext = [r['extraction'] for r in items if r.get('extraction')]
        inj = [e['injection_followed'] for e in ext if e.get('injection_followed') is not None]
        flagged = [e['injection_flagged'] for e in ext if e.get('injection_flagged') is not None]
        tin = [r['input_tokens'] for r in items if r.get('input_tokens') is not None]
        tout = [r['output_tokens'] for r in items if r.get('output_tokens') is not None]
        stats = {'attempts': len(items),
                 'completed': sum(r['status'] == 'completed' for r in items),
                 'escalated': sum(r['status'] == 'escalated' for r in items),
                 'failed': sum(r['status'] == 'failed' for r in items),
                 'incomplete': sum(r['status'] == 'incomplete' for r in items),
                 'escalation_reasons': sorted({(r.get('escalation_reasons') or [''])[0][:80] for r in items
                                               if r['status'] == 'escalated'}),
                 'mean_model_calls': statistics.mean(r['model_calls'] for r in items),
                 'mean_input_tokens': statistics.mean(tin) if tin else 0,
                 'mean_output_tokens': statistics.mean(tout) if tout else 0,
                 'mean_seconds': statistics.mean(r['duration_seconds'] for r in items),
                 'extraction_f1_initial': statistics.mean(e['initial']['f1'] for e in ext) if ext else None,
                 'extraction_f1_final': statistics.mean(e['final']['f1'] for e in ext if 'final' in e) if ext else None,
                 'distractor_claims_per_run': statistics.mean(e['initial']['distractor_claims'] for e in ext) if ext else None,
                 'injection_runs': len(inj), 'injection_followed': sum(inj),
                 'injection_flagged_rate': (sum(flagged) / len(flagged)) if flagged else None,
                 'mean_fact_challenges': statistics.mean(e.get('fact_challenges', 0) for e in ext) if ext else None,
                 'mean_operator_questions': statistics.mean(e.get('operator_questions', 0) for e in ext) if ext else None}
        if prices and tin:
            stats['mean_cost_usd'] = (stats['mean_input_tokens'] * prices['in'] + stats['mean_output_tokens'] * prices['out']) / 1e6
        out[variant] = stats
    return out


def fmt(x, digits=0):
    if x is None:
        return '—'
    return f'{x:,.{digits}f}' if isinstance(x, float) else f'{x:,}'


def write(folder, prices=None):
    folder = Path(folder)
    rows = load(folder)
    manifest = json.loads((folder / 'manifest.json').read_text())
    table = per_case(rows)
    variants = sorted({r['variant'] for r in rows})
    summary = {'attempts': len(rows), 'cases': len(table), 'variants': variant_stats(rows, prices),
               'paired': [paired(table, a, b) for a, b in PAIRS if a in variants and b in variants],
               'prices': prices, 'freeze': manifest.get('evaluation_review'),
               'model': manifest.get('model_configuration', {}).get('model'),
               'claims_multi_agent_superiority': False}
    (folder / 'summary_report.json').write_text(json.dumps(summary, indent=2))
    with open(folder / 'per_case.csv', 'w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['case', *[f'{v}_median_downtime' for v in variants], *[f'{v}_completed' for v in variants]])
        for case, cells in sorted(table.items()):
            writer.writerow([case, *[cells.get(v, {}).get('median_downtime') for v in variants],
                             *[cells.get(v, {}).get('completed') for v in variants]])
    lines = [f'# Held-out benchmark report: {folder.name}', '',
             f'Model `{summary["model"]}` · {summary["cases"]} cases · {len(rows)} attempts · '
             f'freeze `{(summary["freeze"] or {}).get("git_commit_at_freeze", "none")[:7]}`.', '',
             'Synthetic, script-generated cases (evidence v3); not independently human-reviewed. '
             'Downtime is weighted service-minutes over 720 minutes, measured by the independent simulator (lower is better).', '',
             '## Reliability, extraction, safety and usage', '',
             '| Variant | Completed | Escalated | Failed | Fact F1 (initial → after review) | Distractor claims / run | Injection followed / runs | Calls | Input tok | Output tok | Seconds |' +
             (' USD / run |' if prices else ''),
             '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|' + ('---:|' if prices else '')]
    for v, s in summary['variants'].items():
        f1 = '—' if s['extraction_f1_initial'] is None else f'{s["extraction_f1_initial"]:.2f} → {s["extraction_f1_final"]:.2f}'
        lines.append(f'| {v} | {s["completed"]}/{s["attempts"]} | {s["escalated"]} | {s["failed"] + s["incomplete"]} | {f1} | '
                     f'{fmt(s["distractor_claims_per_run"], 2)} | {s["injection_followed"]}/{s["injection_runs"]} | '
                     f'{s["mean_model_calls"]:.1f} | {fmt(s["mean_input_tokens"])} | {fmt(s["mean_output_tokens"])} | '
                     f'{s["mean_seconds"]:.1f} |' + (f' {s.get("mean_cost_usd", 0):.4f} |' if prices else ''))
    if prices:
        lines += ['', f'Prices: USD {prices["in"]} / 1M input and {prices["out"]} / 1M output tokens, as of {prices["date"]} (supplied by the team).']
    lines += ['', '## Paired downtime comparisons (per-case medians)', '',
              '| A vs B | Cases | A better | Tie | B better | Mean A−B | 95 % CI (bootstrap over cases) | Median relative change |',
              '|---|---:|---:|---:|---:|---:|---|---:|']
    for p in summary['paired']:
        ci = p['ci95_mean_diff']
        rel = p['median_relative_change_positive_baseline']
        lines.append(f'| {p["a"]} vs {p["b"]} | {p["cases"]} | {p["a_better"]} | {p["ties"]} | {p["b_better"]} | '
                     f'{fmt(p["mean_diff"], 1)} | {fmt(ci[0], 1)} to {fmt(ci[1], 1)} | '
                     f'{"—" if rel is None else f"{rel * 100:.1f} %"} |')
    lines += ['', '## Per case (median weighted downtime; completed repeats in brackets)', '',
              '| Case | ' + ' | '.join(variants) + ' |', '|---|' + '---:|' * len(variants)]
    for case, cells in sorted(table.items()):
        lines.append(f'| {case} | ' + ' | '.join(
            f'{fmt(cells.get(v, {}).get("median_downtime"))} ({cells.get(v, {}).get("completed", 0)})' for v in variants) + ' |')
    lines += ['', '## Reading this report', '',
              '- Escalated and failed attempts are not scored; a variant that completes fewer cases is compared only on cases where both have a median.',
              '- The proposal target (≥ 10 % median paired downtime reduction for multi vs single) is assessed from the table above; '
              'no superiority claim is made unless the interval excludes zero in the multi-agent direction.',
              '- Raw attempts: `attempts.jsonl`; traces: `runs/`; simulator outputs: `simulations/`.']
    (folder / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('folder', type=Path)
    parser.add_argument('--price-in', type=float)
    parser.add_argument('--price-out', type=float)
    parser.add_argument('--price-date')
    args = parser.parse_args(argv)
    prices = None
    if args.price_in is not None and args.price_out is not None:
        prices = {'in': args.price_in, 'out': args.price_out, 'date': args.price_date or 'not stated'}
    summary = write(args.folder, prices)
    print(json.dumps({v: {k: s[k] for k in ('completed', 'attempts', 'escalated')} for v, s in summary['variants'].items()}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
