"""Visible-state service forecast, never evaluator truth or measured restoration."""
from project.agents.context import csv_table


def service_forecast(state,plan):
    s=state.scenario;obs=state.resolved_observations
    parents={link.child:(link.parent,link.link_id) for link in s.links}
    generators={g.generator_id:g for g in s.generators}
    equipment={sid:v.equipment_ok is True for sid,v in obs.sites.items()}
    links={key:value is True for key,value in obs.links.items()}
    deployments=[(g.site_id,s.current_time_min,g.expires_at_min) for g in s.active_generators]
    for action in plan.actions:
        if action.kind=='generator_deploy':
            deployments.append((action.target_id,action.work_end_min,
                                action.work_end_min+generators[action.generator_id].autonomy_minutes))
    boundaries={s.current_time_min,s.horizon_min}
    boundaries.update(a.work_end_min for a in plan.actions)
    boundaries.update(t for _,start,end in deployments for t in (start,end) if s.current_time_min<t<s.horizon_min)
    boundaries=sorted(t for t in boundaries if s.current_time_min<=t<=s.horizon_min)
    minutes={service.service_id:0 for service in s.services}
    for start,end in zip(boundaries,boundaries[1:]):
        for action in plan.actions:
            if action.work_end_min<=start:
                if action.kind=='equipment_repair':equipment[action.target_id]=True
                elif action.kind=='link_repair':links[action.target_id]=True
        available={s.core_id:True}
        def connected(site):
            if site in available:return available[site]
            parent,link=parents[site]
            power=obs.sites[site].grid_power_ok is True or any(sid==site and a<=start<b for sid,a,b in deployments)
            available[site]=equipment[site] and power and links[link] and connected(parent)
            return available[site]
        for service in s.services:
            if connected(service.site_id):minutes[service.service_id]+=end-start
    rows=[[service.service_id,service.weight,minutes[service.service_id],service.weight*minutes[service.service_id]] for service in s.services]
    total=sum(row[3] for row in rows)
    predicted=plan.planner_config.get('predicted_weighted_available_minutes_remaining')
    return {'scope':'visible static prediction for remaining horizon only; not simulator measurement',
            'assumptions':'No unseen events; public generator autonomy; unknowns unavailable. Includes unaffected and repaired services, not just the generator site.',
            'from_min':s.current_time_min,'until_min':s.horizon_min,
            'service_fields':['service_id','weight','available_minutes','weighted_available_minutes'],
            'services_csv':csv_table(rows),'total_weighted_available_minutes':total,
            'scheduler_prediction':predicted,'agrees_with_scheduler':total==predicted if predicted is not None else None}
