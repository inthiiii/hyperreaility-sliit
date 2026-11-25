"""Summarise a benchmark output folder: per-variant status, downtime, extraction and usage.

    python scripts/summarize_run.py results/development/v14-dev-tuning-20261127/run1
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def main(folder):
    rows = [json.loads(line) for line in (Path(folder) / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    by = defaultdict(list)
    for r in rows:
        by[r['variant']].append(r)
    print(f'{"variant":12} {"n":>3} {"done":>4} {"esc":>4} {"fail":>4} {"med down":>9} {"F1":>5} {"inj ok":>6} {"calls":>5} {"in tok":>7} {"sec":>5}')
    for variant, items in sorted(by.items()):
        done = [r for r in items if r['status'] == 'completed']
        f1 = [r['extraction']['initial']['f1'] for r in items if r.get('extraction')]
        inj = [r['extraction']['injection_followed'] for r in items if r.get('extraction') and r['extraction'].get('injection_followed') is not None]
        tok = [r['input_tokens'] for r in items if r.get('input_tokens') is not None]
        print(f'{variant:12} {len(items):3} {len(done):4} {sum(r["status"]=="escalated" for r in items):4} '
              f'{sum(r["status"]=="failed" for r in items):4} '
              f'{statistics.median([r["actual_weighted_downtime"] for r in done]) if done else float("nan"):9.0f} '
              f'{statistics.mean(f1) if f1 else float("nan"):5.2f} '
              f'{(sum(not x for x in inj)/len(inj)) if inj else float("nan"):6.2f} '
              f'{statistics.mean(r["model_calls"] for r in items):5.1f} '
              f'{statistics.mean(tok) if tok else 0:7.0f} {statistics.mean(r["duration_seconds"] for r in items):5.1f}')
    print()
    cases = sorted({r['scenario_id'] for r in rows})
    variants = sorted(by)
    print('case        ' + ' '.join(f'{v:>10}' for v in variants))
    for c in cases:
        cells = []
        for v in variants:
            r = next((x for x in by[v] if x['scenario_id'] == c), None)
            cells.append(f'{(r["actual_weighted_downtime"] if r and r["status"]=="completed" else (r["status"][:4] if r else "-")):>10}')
        print(f'{c:11} ' + ' '.join(cells))
    for r in rows:
        if r['status'] != 'completed':
            print('NOT COMPLETED', r['scenario_id'], r['variant'], r['status'], r.get('escalation_reasons') or r.get('error_type'))


if __name__ == '__main__':
    main(sys.argv[1])
