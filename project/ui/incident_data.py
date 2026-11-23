"""Read-only projections of visible inputs. No resolver, model or simulator calls."""
from project.core.schemas import ScenarioInput
from project.core.state import AUTHORITY


def observed_label(value, positive='OK', negative='Fault'):
    if value is True:
        return positive
    if value is False:
        return negative
    return 'Unknown'


def local_site_status(scenario, site_id):
    observation = scenario.observed_state.sites[site_id]
    values = (observation.equipment_ok, observation.grid_power_ok)
    if any(value is False for value in values):
        return 'Local fault'
    if any(value is None for value in values):
        return 'Unknown'
    return 'Local observations OK'


def snapshot_counts(scenario: ScenarioInput):
    values = [value for item in scenario.observed_state.sites.values()
              for value in (item.equipment_ok, item.grid_power_ok)]
    values += list(scenario.observed_state.links.values()) + list(scenario.observed_state.roads.values())
    return {
        'site_flags': sum(local_site_status(scenario, site.site_id) == 'Local fault' for site in scenario.sites),
        'unknowns': sum(value is None for value in values),
        'link_faults': sum(value is False for value in scenario.observed_state.links.values()),
        'critical_services': sum(service.critical for service in scenario.services),
    }


def dependency_path(scenario, site_id):
    parent = {link.child: link.parent for link in scenario.links}
    if site_id not in parent:
        raise ValueError('Select a known site')
    path = [site_id]
    while path[-1] != scenario.core_id:
        path.append(parent[path[-1]])
    return list(reversed(path))


def site_rows(scenario):
    return [{'Site': site.site_id, 'Label': site.label,
             'Equipment': observed_label(scenario.observed_state.sites[site.site_id].equipment_ok),
             'Grid power': observed_label(scenario.observed_state.sites[site.site_id].grid_power_ok, 'Available', 'Unavailable'),
             'Local status': local_site_status(scenario, site.site_id),
             'Upstream parent': next(link.parent for link in scenario.links if link.child == site.site_id)}
            for site in scenario.sites]


def link_rows(scenario):
    return [{'Link': link.link_id, 'Parent': link.parent, 'Child': link.child,
             'Observed backhaul': observed_label(scenario.observed_state.links[link.link_id])}
            for link in scenario.links]


def road_rows(scenario):
    return [{'Road': road.road_id, 'From': road.origin, 'To': road.to,
             'Travel (min)': road.travel_minutes,
             'Observed access': observed_label(scenario.observed_state.roads[road.road_id], 'Open', 'Closed')}
            for road in scenario.roads]


def report_rows(scenario, sources=None, query=''):
    query = query.strip().casefold()
    return [{'Report': report.report_id, 'Source': report.source_type,
             'Source class': 'Recognized authority' if report.source_type in AUTHORITY else 'Unverified source',
             'Observed (min)': report.observed_at_min, 'Received (min)': report.received_at_min,
             'Age (min)': scenario.current_time_min - report.observed_at_min,
             'Receipt lag (min)': report.received_at_min - report.observed_at_min,
             'Text': report.text}
            for report in scenario.reports
            if (sources is None or report.source_type in sources)
            and (not query or query in (report.report_id + ' ' + report.text).casefold())]


def crew_rows(scenario):
    def window(crew):
        if scenario.current_time_min < crew.available_from_min:
            return 'Not yet available'
        if scenario.current_time_min >= crew.available_until_min:
            return 'Window ended'
        return 'In window'
    return [{'Crew': crew.crew_id, 'Location': crew.location, 'Skills': ', '.join(crew.skills) or 'None recorded',
             'Available from (min)': crew.available_from_min, 'Available until (min)': crew.available_until_min,
             'Window status': window(crew)} for crew in scenario.crews]


def generator_rows(scenario):
    return [{'Generator': generator.generator_id, 'Location': generator.location,
             'Inventory availability': 'Available' if generator.available else 'Unavailable',
             'Autonomy (min)': generator.autonomy_minutes, 'Deployment (min)': generator.deployment_minutes,
             'Maximum deployments': generator.max_deployments} for generator in scenario.generators]


def service_rows(scenario, critical_only=False):
    return [{'Service': service.service_id, 'Label': service.label, 'Site': service.site_id,
             'Priority class': 'Critical' if service.critical else 'Standard',
             'Policy weight': service.weight, 'Policy evidence': service.policy_evidence_id}
            for service in scenario.services if not critical_only or service.critical]


def action_rows(scenario):
    return [{'Action': action.action_id, 'Kind': action.kind.replace('_', ' '), 'Target': action.target_id,
             'Location': action.location, 'Work duration (min)': action.duration_minutes,
             'Required skill': action.required_skill, 'Generator': action.generator_id or '—'}
            for action in scenario.action_options]
