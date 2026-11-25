"""Publish a credential-free aggregate of completed development experiment batches.

Raw traces and evaluator artifacts stay in ignored local result directories.
This summarizes development observations, never independent held-out performance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project.core.state import digest
from project.core.tracing import read_run
from project.evaluation.comparison import paired_summary


def escalation_category(row):
    if row['status']!='escalated':return None
    reasons=row.get('escalation_reasons') or []
    if any('workflow stopped; inspect structured usage' in reason for reason in reasons):
        return 'workflow_exception_or_budget'
    if any(reason.startswith(('site:','link:','road:')) for reason in reasons):
        return 'unresolved_evidence'
    return 'agent_review_or_clarification'


def summarize(experiments, concurrent_batches=1):
    if type(concurrent_batches) is not int or concurrent_batches<1:
        raise ValueError('Concurrency must be a positive integer')
    rows=[];manifests=[];cases={};artifacts=[];seen=set();raw=[];raw_by_variant={};missing_extractions=0
    for directory in map(Path,experiments):
        manifest=json.loads((directory/'manifest.json').read_text())
        if not all(sid.startswith('DEV-') for sid in manifest['cases']):
            raise ValueError('Only explicitly development-labelled cases may enter this report')
        if set(cases)&set(manifest['cases']):raise ValueError('Do not duplicate cases across batches')
        cases.update(manifest['cases']);manifests.append(manifest)
        content=(directory/'attempts.jsonl').read_bytes()
        batch=[json.loads(line) for line in content.splitlines()]
        expected={(sid,v,n) for sid in manifest['cases'] for v in manifest['variants'] for n in range(manifest['repeats'])}
        observed={(r['scenario_id'],r['variant'],r['repeat']) for r in batch}
        if len(observed)!=len(batch) or observed!=expected:raise ValueError('Incomplete or duplicated batch jobs')
        if seen&observed:raise ValueError('Duplicate comparison jobs')
        seen.update(observed);rows.extend(batch)
        artifacts.append({'directory':directory.as_posix(),
            'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
            'attempts_sha256':hashlib.sha256(content).hexdigest()})
        for row in batch:
            if row['model_configuration']!=manifest['model_configuration']:raise ValueError('Row/model manifest mismatch')
            for rid in row.get('run_ids',[]):
                run=read_run(directory/'runs'/(rid+'.json'))
                if run['run_id']!=rid or run['state']['scenario_id']!=row['scenario_id']:
                    raise ValueError('Trace identity mismatch')
                metric=run['metadata'].get('raw_extraction_metrics')
                if metric is None:missing_extractions+=1
                else:
                    raw.append(metric);raw_by_variant.setdefault(row['variant'],[]).append(metric)
    if not manifests:raise ValueError('Provide at least one completed experiment')
    first=manifests[0]
    for manifest in manifests[1:]:
        for field in ('source_sha256','model_configuration','comparison_protocol','whole_incident_limits','variants','repeats'):
            if manifest[field]!=first[field]:raise ValueError('Incomparable experiment protocols: '+field)
    variants={}
    for variant in first['variants']:
        group=[r for r in rows if r['variant']==variant];scored=[r for r in group if r.get('scoring_status')=='scored']
        variants[variant]={'attempts':len(group),'statuses':dict(Counter(r['status'] for r in group)),
            'scored':len(scored),'escalation_categories':dict(Counter(escalation_category(r) for r in group if r['status']=='escalated')),'decision_effect_count':sum(r.get('decision_effect_count',0) for r in group),
            'mean_weighted_downtime_scored_only':statistics.mean(r['actual_weighted_downtime'] for r in scored) if scored else None,
            'mean_duration_seconds':statistics.mean(r['duration_seconds'] for r in group),
            'model_calls':sum(r['model_calls'] for r in group),
            'auxiliary_request_count':sum(r.get('auxiliary_request_count',0) for r in group),
            'input_tokens':sum(r['input_tokens'] for r in group) if all(r['input_tokens'] is not None for r in group) else None,
            'output_tokens':sum(r['output_tokens'] for r in group) if all(r['output_tokens'] is not None for r in group) else None}
    per_variant={}
    for variant in first['variants']:
        metrics=raw_by_variant.get(variant,[])
        a=sum(m['true_positive'] for m in metrics);b=sum(m['false_positive'] for m in metrics);c=sum(m['false_negative'] for m in metrics)
        per_variant[variant]={'run_records_with_metrics':len(metrics),'true_positive':a,'false_positive':b,'false_negative':c,
                              'micro_f1':2*a/(2*a+b+c) if 2*a+b+c else None}
    tp=sum(m['true_positive'] for m in raw);fp=sum(m['false_positive'] for m in raw);fn=sum(m['false_negative'] for m in raw)
    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
    failures=Counter((u.get('error_type') or r.get('error_type') or 'unclassified')
                     for r in rows for u in r.get('model_usage',[]) if u.get('status')!='ok')
    return {'scope':'development only; not independent held-out evaluation',
        'model_configuration':first['model_configuration'],'source_sha256':first['source_sha256'],
        'protocol':first['comparison_protocol'],'whole_incident_limits':first['whole_incident_limits'],
        'case_count':len(cases),'case_hashes':cases,'attempts':len(rows),'variants':variants,
        'concurrent_batches':concurrent_batches,'timing_note':'Observed wall time includes concurrent batch contention; not an isolated latency benchmark.',
        'paired_comparison':paired_summary(rows),
        'raw_extraction':{'label_source':'recognized visible fixture sentences before resolver fill-in',
            'run_records_with_metrics':len(raw),'run_records_without_metrics':missing_extractions,
            'true_positive':tp,'false_positive':fp,'false_negative':fn,'micro_f1':f1,'by_variant':per_variant,
            'unlabelled_reports':sum(m['unlabelled_reports'] for m in raw)},
        'request_error_counts':dict(failures),
        'auxiliary_request_count':sum(r.get('auxiliary_request_count',0) for r in rows),
        'auxiliary_error_counts':dict(Counter(u.get('error_type','unclassified') for r in rows for u in r.get('auxiliary_requests',[]) if u.get('status')!='ok')),
        'artifacts':artifacts,
        'api_cost':None,'claims_multi_agent_superiority':False,
        'jobs':[{key:r.get(key) for key in ('scenario_id','variant','repeat','status','scoring_status',
                 'actual_weighted_downtime','approved_episodes','decision_effect_count','model_calls',
                 'input_tokens','output_tokens','auxiliary_request_count','returned_models','failure_phase','error_type','escalation_reasons')} for r in rows]}


def markdown(report):
    lines=['# Luna development verification','',
        'Development observations only. Independent held-out review and final evaluation remain pending.','',
        f"Model: `{report['model_configuration']['model']}`; reasoning: `{report['model_configuration'].get('reasoning_effort')}`.",
        f"Cases: {report['case_count']}; attempts: {report['attempts']}; concurrent batches: {report['concurrent_batches']}.",'',
        '| Variant | Scored | Escalated | Failed | Incomplete | Model calls |',
        '|---|---:|---:|---:|---:|---:|']
    for variant,item in report['variants'].items():
        counts=item['statuses'];lines.append(f"| {variant} | {item['scored']} | {counts.get('escalated',0)} | {counts.get('failed',0)} | {counts.get('incomplete',0)} | {item['model_calls']} |")
    comparison=report['paired_comparison']
    lines+=['',f"Comparable scored single/multi pairs: {comparison['scored_comparable_pairs']} of {comparison['eligible_pairs']}.",
        f"Multi wins: {comparison['multi_wins']}; single wins: {comparison['single_wins']}; ties: {comparison['ties']}.",
        f"Mean single-minus-multi weighted downtime: {comparison['mean_single_minus_multi']} weighted service-minutes (complete comparable pairs only).",'',
        f"Raw initial extraction micro-F1: {report['raw_extraction']['micro_f1']}; metric-bearing run records: {report['raw_extraction']['run_records_with_metrics']}.",
        'Labels cover recognized fixture sentences, not an independently audited natural-language dataset.','',
        'Escalations include unresolved evidence, agent review/clarification and workflow exceptions or budget stops; they are not all verified-correct safety decisions.',
        'Failures and exclusions remain in the JSON report. Repetitions are not independent new scenarios. Applied action holds are not proof of better restoration. Actual API charges were not measured. No multi-agent superiority claim is made.','',
        'Wall times include concurrent batch contention and must not be presented as an isolated latency benchmark.','',
        f"Source fingerprint: `{report['source_sha256']}`.",'']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiments',nargs='+',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--concurrent-batches',type=int,default=1)
    args=parser.parse_args();report=summarize(args.experiments,args.concurrent_batches)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (args.output/'report.md').write_text(markdown(report))
    print(json.dumps({'cases':report['case_count'],'attempts':report['attempts'],
        'comparable_pairs':report['paired_comparison']['scored_comparable_pairs'],'output':str(args.output)},indent=2))


if __name__=='__main__':main()
