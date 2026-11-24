"""Lossless operational tables for bounded, matched hosted contexts."""
import csv
import io
import json


def csv_table(rows):
    stream=io.StringIO();writer=csv.writer(stream,lineterminator="\n")
    for row in rows:
        writer.writerow([json.dumps(v) if v is None or type(v) is bool else v for v in row])
    return stream.getvalue()


ACTION_SPEC_FIELDS = ('kind','duration_minutes','required_skill','generator_id')
ACTION_FIELDS = ('action_id','spec_index','target_id','location')
SCHEDULE_FIELDS = ('action_id','kind','target_id','crew_id','generator_id','departure_min',
                   'travel_route','work_start_min','work_end_min')


def action_catalog(options):
    specs=[];indices={};rows=[]
    for option in options:
        spec=tuple(getattr(option,k) for k in ACTION_SPEC_FIELDS)
        if spec not in indices:indices[spec]=len(specs);specs.append(list(spec))
        rows.append([option.action_id,indices[spec],option.target_id,option.location])
    return {'spec_fields':list(ACTION_SPEC_FIELDS),'specs':specs,
            'action_fields':list(ACTION_FIELDS),'actions_format':'csv','actions':csv_table(rows)}


def observations_view(observations):
    # ScenarioInput validates full asset coverage before this encoder is used.
    # This is a representation of known values, not an assumption about missing data.
    value={'encoding':'sparse_default_true','default':True}
    for attribute in ('equipment_ok','grid_power_ok'):
        for label,status in (('false',False),('unknown',None)):
            value['site_'+attribute+'_'+label]=[sid for sid,v in observations.sites.items() if getattr(v,attribute) is status]
    for typ,items in (('links',observations.links),('roads',observations.roads)):
        value[typ+'_false']=[key for key,status in items.items() if status is False]
        value[typ+'_unknown']=[key for key,status in items.items() if status is None]
    focus=[sid for sid,v in observations.sites.items() if v.equipment_ok is not True or v.grid_power_ok is not True]
    value['explicit_focus_sites']={sid:observations.sites[sid].model_dump() for sid in focus}
    return value


def plan_view(plan):
    value=plan.model_dump(mode='json')
    value['action_fields']=list(SCHEDULE_FIELDS)
    value['actions']=[[getattr(a,k) for k in SCHEDULE_FIELDS] for a in plan.actions]
    return value


def arithmetic_checks(plan,scenario):
    options={o.action_id:o for o in scenario.action_options}
    return [{'action_id':a.action_id,'departure_min':a.departure_min,
             'work_start_min':a.work_start_min,'work_duration_min':options[a.action_id].duration_minutes,
             'computed_work_end_min':a.work_start_min+options[a.action_id].duration_minutes,
             'recorded_work_end_min':a.work_end_min} for a in plan.actions]
