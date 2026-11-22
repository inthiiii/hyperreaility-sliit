"""Explicitly labelled template baseline, for offline development only."""
import re
from project.core.schemas import EvidenceFact
from project.core.state import AUTHORITY

PHRASES={
 'equipment is operational':('site','equipment_ok',True),
 'equipment has failed':('site','equipment_ok',False),
 'grid power is available':('site','grid_power_ok',True),
 'grid power is unavailable':('site','grid_power_ok',False),
 'backhaul link is operational':('link','backhaul_ok',True),
 'backhaul link has failed':('link','backhaul_ok',False),
 'access road is open':('road','open',True),
 'access road is closed':('road','open',False),
}

def template_facts(scenario):
    facts=[]
    for r in scenario.reports:
        match=re.fullmatch(r'([A-Za-z0-9_-]+): (.+)\.',r.text.strip())
        if not match or match[2] not in PHRASES:continue
        typ,attr,value=PHRASES[match[2]]
        facts.append(EvidenceFact(target_type=typ,target_id=match[1],attribute=attr,value=value,
          evidence_ids=[r.report_id],observed_at_min=r.observed_at_min,received_at_min=r.received_at_min,status='verified' if r.source_type in AUTHORITY else 'unverified',
          reason='Exact fixture-template match; not LLM inference'))
    return facts
