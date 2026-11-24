"""Paired engineering summaries; incomplete jobs never receive invented scores."""
from collections import Counter
import random
import statistics


def paired_summary(rows):
    agents=[r for r in rows if r['variant'] in ('single','multi')]
    groups={}
    for row in agents:groups.setdefault((row['scenario_id'],row['repeat']),{})[row['variant']]=row
    differences=[];excluded=[]
    for key,pair in sorted(groups.items()):
        if set(pair)!= {'single','multi'}:
            excluded.append({'case':list(key),'reason':'missing_variant'});continue
        left,right=pair['single'],pair['multi']
        if left.get('scoring_status')!='scored' or right.get('scoring_status')!='scored':
            excluded.append({'case':list(key),'reason':'unscored_pair'});continue
        if left.get('model_configuration')!=right.get('model_configuration'):
            excluded.append({'case':list(key),'reason':'configuration_mismatch'});continue
        # Alias routing can produce different returned snapshots. Do not pool them.
        if left.get('returned_models')!=right.get('returned_models') or len(left.get('returned_models',[]))!=1:
            excluded.append({'case':list(key),'reason':'returned_model_mismatch_or_missing'});continue
        differences.append(left['actual_weighted_downtime']-right['actual_weighted_downtime'])
    interval=None
    if len(differences)>=2:
        rng=random.Random(22)
        means=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(2000))
        interval=[means[49],means[1949]]
    return {'comparison':'single versus multi; same four-stage tool-assisted workflow',
        'eligible_pairs':len(groups),'scored_comparable_pairs':len(differences),'excluded_pairs':excluded,
        'conditioning':'Downtime differences use complete comparable pairs only; assess failure coverage alongside them.',
        'difference_unit':'weighted service-minutes; positive favors multi',
        'mean_single_minus_multi':statistics.mean(differences) if differences else None,
        'median_single_minus_multi':statistics.median(differences) if differences else None,
        'multi_wins':sum(d>0 for d in differences),'single_wins':sum(d<0 for d in differences),
        'ties':sum(d==0 for d in differences),'paired_bootstrap_95pct_interval':interval,
        'uncertainty':'Exploratory paired resampling; repeats within a scenario are not independent new scenarios.',
        'status_counts':{v:dict(Counter(r['status'] for r in agents if r['variant']==v)) for v in ('single','multi')},
        'decision_effect_counts':{v:sum(r.get('decision_effect_count',0) for r in agents if r['variant']==v) for v in ('single','multi')},
        'api_cost':None,'claims_multi_agent_superiority':False}
