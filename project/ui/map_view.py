"""Incident map: fictional sites placed in real Western Province towns.

Pure helpers build the layer rows so they can be tested without a browser.
Rendering uses pydeck. The default view draws only district outlines (works
offline); a street basemap is optional and needs internet access.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CORE_POINT = (6.934, 79.843)    # Colombo Fort: fictional core switch location
DEPOT_POINT = (6.944, 79.879)   # Orugodawatta: fictional regional depot
LAT_RANGE, LON_RANGE = (6.45, 7.22), (79.84, 80.20)
COLORS = {'OK': [105, 227, 198], 'Fault': [255, 120, 128], 'Unknown': [241, 203, 120],
          'Up': [105, 227, 198], 'Down': [255, 120, 128], 'Not served': [150, 160, 175]}
DISTRICTS = Path(__file__).resolve().parents[2] / 'data' / 'processed' / 'context' / 'western_district_context.geojson'


def positions(scenario):
    """{node_id: (lat, lon)}; falls back to mapping the synthetic grid into the province box."""
    xs = [s.x for s in scenario.sites]
    ys = [s.y for s in scenario.sites]
    span_x, span_y = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    out = {scenario.core_id: CORE_POINT, scenario.depot_id: DEPOT_POINT}
    for s in scenario.sites:
        if s.lat is not None and s.lon is not None:
            out[s.site_id] = (s.lat, s.lon)
        else:
            out[s.site_id] = (LAT_RANGE[0] + (s.y - min(ys)) / span_y * (LAT_RANGE[1] - LAT_RANGE[0]),
                              LON_RANGE[0] + (s.x - min(xs)) / span_x * (LON_RANGE[1] - LON_RANGE[0]))
    return out


def _site_state(observations, site_id):
    o = observations.sites[site_id]
    values = (o.equipment_ok, o.grid_power_ok)
    if any(v is False for v in values):
        return 'Fault'
    if any(v is None for v in values):
        return 'Unknown'
    return 'OK'


def available_at(trajectory, minute, intervals=None, horizon=None):
    """Service IDs available at ``minute``.

    Prefers the simulator's per-service availability intervals (complete from the
    incident start); falls back to availability events in the trajectory.
    """
    if intervals:
        up = set()
        for service_id, data in intervals.items():
            for start, end in (data or {}).get('intervals', []):
                if start <= minute < end or (minute == end == horizon):
                    up.add(service_id)
        return up
    current = None
    for event in trajectory:
        if event.get('type') == 'availability' and event.get('t', 0) <= minute:
            current = set(event.get('available_services', []))
    return current


def crew_positions(scenario, plan, minute):
    """Where each crew is at ``minute`` according to the approved plan (prediction, not GPS)."""
    pos = positions(scenario)
    out = []
    for crew in scenario.crews:
        place, doing = crew.location, 'waiting'
        for action in sorted((a for a in (plan.actions if plan else []) if a.crew_id == crew.crew_id),
                             key=lambda a: a.departure_min):
            if minute < action.departure_min:
                break
            if minute < action.work_start_min:
                place, doing = action.travel_route[-1], f'travelling to {action.travel_route[-1]}'
                break
            target = action.travel_route[-1]
            if minute < action.work_end_min:
                place, doing = target, f'working on {action.action_id}'
                break
            place, doing = target, f'finished {action.action_id}'
        lat, lon = pos[place]
        out.append({'crew_id': crew.crew_id, 'lat': lat + 0.006, 'lon': lon + 0.006, 'doing': doing,
                    'color': crew_color(scenario, crew.crew_id),
                    'label': f'{crew.crew_id}: {doing}'})
    return out


def layer_rows(scenario, observations=None, trajectory=None, minute=None, plan=None, intervals=None):
    """Rows for sites, links and roads. With a trajectory, colours show measured service at ``minute``."""
    observations = observations or scenario.observed_state
    pos = positions(scenario)
    services = {}
    for v in scenario.services:
        services.setdefault(v.site_id, []).append(v)
    up = (available_at(trajectory, minute, intervals, scenario.horizon_min)
          if trajectory is not None and minute is not None else None)
    sites = []
    for s in scenario.sites:
        here = services.get(s.site_id, [])
        if up is not None:
            status = ('Up' if any(v.service_id in up for v in here) else 'Down') if here else 'Not served'
        else:
            status = _site_state(observations, s.site_id)
        critical = any(v.critical for v in here)
        lat, lon = pos[s.site_id]
        sites.append({'site_id': s.site_id, 'name': s.label, 'code': s.code or s.site_id, 'district': s.district or '',
                      'lat': lat, 'lon': lon, 'status': status, 'color': COLORS[status],
                      'radius': 1400 if critical else 900, 'critical': critical,
                      'label': f'{s.label} ({s.code or s.site_id})' + (' · critical' if critical else '')})
    links = []
    for l in scenario.links:
        state = observations.links[l.link_id]
        status = 'OK' if state is True else 'Fault' if state is False else 'Unknown'
        links.append({'link_id': l.link_id, 'path': [[pos[l.parent][1], pos[l.parent][0]], [pos[l.child][1], pos[l.child][0]]],
                      'status': status, 'color': COLORS[status], 'label': f'Backhaul {l.link_id}: {status}'})
    roads = []
    for r in scenario.roads:
        state = observations.roads[r.road_id]
        status = 'Open' if state is True else 'Closed' if state is False else 'Unknown'
        color = [120, 130, 150, 120] if status == 'Open' else [255, 80, 80, 230] if status == 'Closed' else [241, 203, 120, 200]
        roads.append({'road_id': r.road_id, 'path': [[pos[r.origin][1], pos[r.origin][0]], [pos[r.to][1], pos[r.to][0]]],
                      'status': status, 'color': color, 'label': f'Road {r.road_id}: {status}, {r.travel_minutes} min'})
    hubs = [{'name': 'Core (fictional)', 'lat': CORE_POINT[0], 'lon': CORE_POINT[1], 'label': 'Core switch (fictional)'},
            {'name': 'Depot (fictional)', 'lat': DEPOT_POINT[0], 'lon': DEPOT_POINT[1], 'label': 'Crew depot (fictional)'}]
    crews = crew_positions(scenario, plan, minute) if plan is not None and minute is not None else []
    return {'sites': sites, 'links': links, 'roads': roads, 'hubs': hubs, 'crews': crews,
            'routes': route_rows(scenario, plan)}


CREW_COLORS = [[120, 170, 255], [255, 170, 90], [200, 140, 255], [90, 220, 255]]


def crew_color(scenario, crew_id):
    ids = sorted(c.crew_id for c in scenario.crews)
    return CREW_COLORS[ids.index(crew_id) % len(CREW_COLORS)] if crew_id in ids else CREW_COLORS[0]


def route_rows(scenario, plan):
    """Planned travel of each crew, one path per action, coloured per crew."""
    if plan is None:
        return []
    pos = positions(scenario)
    rows = []
    for a in sorted(plan.actions, key=lambda x: (x.crew_id, x.departure_min)):
        path = [[pos[n][1], pos[n][0]] for n in a.travel_route if n in pos]
        if len(path) < 2:
            continue
        rows.append({'crew_id': a.crew_id, 'path': path, 'color': crew_color(scenario, a.crew_id),
                     'label': f'{a.crew_id}: {a.action_id} (leave {a.departure_min}, work {a.work_start_min}–{a.work_end_min})'})
    return rows


@lru_cache(maxsize=1)
def district_geojson():
    try:
        return json.loads(DISTRICTS.read_text())
    except OSError:
        return None


def render_map(scenario, *, observations=None, trajectory=None, minute=None, plan=None, basemap=False, highlight=(),
               height=520, intervals=None):
    import pydeck as pdk
    import streamlit as st

    rows = layer_rows(scenario, observations, trajectory, minute, plan, intervals)
    layers = []
    districts = district_geojson()
    if districts:
        layers.append(pdk.Layer('GeoJsonLayer', districts, stroked=True, filled=True,
                                get_fill_color=[70, 90, 130, 40], get_line_color=[140, 160, 200, 160],
                                line_width_min_pixels=1, pickable=False))
    layers += [
        pdk.Layer('PathLayer', rows['roads'], get_path='path', get_color='color', width_min_pixels=2,
                  get_dash_array=[4, 3], pickable=True),
        pdk.Layer('PathLayer', rows['links'], get_path='path', get_color='color', width_min_pixels=3, pickable=True),
        pdk.Layer('ScatterplotLayer', rows['hubs'], get_position='[lon, lat]', get_radius=1100,
                  get_fill_color=[200, 200, 255], pickable=True),
        pdk.Layer('ScatterplotLayer', rows['sites'], get_position='[lon, lat]', get_radius='radius',
                  get_fill_color='color', get_line_color=[255, 255, 255], line_width_min_pixels=1,
                  stroked=True, pickable=True),
        pdk.Layer('TextLayer', rows['sites'], get_position='[lon, lat]', get_text='name', get_size=12,
                  get_color=[230, 235, 245], get_pixel_offset=[0, -16]),
    ]
    rings = [s for s in rows['sites'] if s['site_id'] in set(highlight)]
    if rings:
        layers.append(pdk.Layer('ScatterplotLayer', rings, get_position='[lon, lat]', get_radius=2600, filled=False,
                                stroked=True, get_line_color=[241, 203, 120], line_width_min_pixels=2, pickable=False))
    if rows['routes']:
        layers.append(pdk.Layer('PathLayer', rows['routes'], get_path='path', get_color='color', width_min_pixels=4,
                                pickable=True, opacity=0.8))
    if rows['crews']:
        layers.append(pdk.Layer('ScatterplotLayer', rows['crews'], get_position='[lon, lat]', get_radius=900,
                                get_fill_color='color', get_line_color=[255, 255, 255], stroked=True,
                                line_width_min_pixels=2, pickable=True))
        layers.append(pdk.Layer('TextLayer', rows['crews'], get_position='[lon, lat]', get_text='crew_id',
                                get_size=13, get_color='color', get_pixel_offset=[0, 16]))
    lats = [s['lat'] for s in rows['sites']] + [CORE_POINT[0]]
    lons = [s['lon'] for s in rows['sites']] + [CORE_POINT[1]]
    view = pdk.ViewState(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lons) + max(lons)) / 2, zoom=8.6)
    deck = pdk.Deck(layers=layers, initial_view_state=view, tooltip={'text': '{label}'},
                    map_style='light' if basemap else None, map_provider='carto' if basemap else None)
    st.pydeck_chart(deck, height=height)
    return rows


# ---------------------------------------------------------------------- guided map story
def _word(value, yes='OK', no='fault'):
    return 'unknown' if value is None else yes if value else no


def evidence_changes(scenario, resolved):
    """What the agents established compared with the initial snapshot."""
    before, names, rows = scenario.observed_state, {s.site_id: s.label for s in scenario.sites}, []
    for site_id, after in resolved.sites.items():
        old = before.sites.get(site_id)
        for field, label in (('equipment_ok', 'equipment'), ('grid_power_ok', 'grid power')):
            a, b = getattr(old, field) if old else None, getattr(after, field)
            if a != b:
                rows.append({'Where': f'{names.get(site_id, site_id)} ({site_id})', 'What': label,
                             'Before': _word(a), 'Now': _word(b), 'site_id': site_id})
    for kind, table, yes, no in (('backhaul', 'links', 'OK', 'fault'), ('road', 'roads', 'open', 'closed')):
        for key, b in getattr(resolved, table).items():
            a = getattr(before, table).get(key)
            if a != b:
                rows.append({'Where': key, 'What': kind, 'Before': _word(a, yes, no), 'Now': _word(b, yes, no),
                             'site_id': None})
    return rows


def itineraries(scenario, plan):
    """Ordered stops per crew, for the plan chapter."""
    names = {s.site_id: s.label for s in scenario.sites}
    out = {}
    for a in sorted(plan.actions if plan else [], key=lambda x: (x.crew_id, x.departure_min)):
        out.setdefault(a.crew_id, []).append(
            {'job': a.action_id, 'what': a.kind.replace('_', ' '), 'where': names.get(a.target_id, a.target_id),
             'leave': a.departure_min, 'start': a.work_start_min, 'end': a.work_end_min})
    return out


def replay_kpis(scenario, trajectory, minute, intervals=None):
    up = available_at(trajectory, minute, intervals, scenario.horizon_min) or set()
    critical = [v for v in scenario.services if v.critical]
    weight = sum(v.weight for v in scenario.services) or 1
    return {'up': sum(v.service_id in up for v in scenario.services), 'total': len(scenario.services),
            'critical_up': sum(v.service_id in up for v in critical), 'critical_total': len(critical),
            'weighted_pct': 100 * sum(v.weight for v in scenario.services if v.service_id in up) / weight}


def replay_events(scenario, trajectory, plan, minute, intervals=None):
    """Readable timeline up to ``minute``: job completions/failures and services coming back or dropping."""
    crews = {a.action_id: a.crew_id for a in (plan.actions if plan else [])}
    site_of = {v.service_id: v.site_id for v in scenario.services}
    names = {s.site_id: s.label for s in scenario.sites}
    rows, previous = [], None
    for event in trajectory:
        t = event.get('t', 0)
        if t > minute:
            break
        kind = event.get('type')
        who = crews.get(event.get('action_id'))
        prefix = f'{who} ' if who else ''
        if kind == 'action_completed':
            rows.append((t, '✅', f"{prefix}finished {event['action_id']}"))
        elif kind in ('action_failed', 'action_skipped', 'action_cancelled'):
            rows.append((t, '⛔', f"{event['action_id']} {kind.split('_')[1]}: {event.get('reason', '')}".strip()))
        elif kind == 'action_paused':
            rows.append((t, '⏸️', f"{event['action_id']} paused: {event.get('reason', '')}"))
        elif kind == 'generator_expired':
            rows.append((t, '🪫', f"generator {event.get('generator_id')} ran out of fuel"))
        elif kind == 'availability' and not intervals:
            now = set(event.get('available_services', []))
            if previous is not None:
                for sid, word, icon in ((now - previous, 'back up', '🟢'), (previous - now, 'went down', '🔴')):
                    sites = sorted({names.get(site_of.get(s), s) for s in sid})
                    if sites:
                        rows.append((t, icon, f"{', '.join(sites)} {word}"))
            previous = now
    if intervals:
        changes = {}
        for service_id, data in intervals.items():
            for start, end in (data or {}).get('intervals', []):
                if scenario.current_time_min < start <= minute:
                    changes.setdefault((start, 'back up', '🟢'), set()).add(names.get(site_of.get(service_id), service_id))
                if end < scenario.horizon_min and end <= minute:
                    changes.setdefault((end, 'went down', '🔴'), set()).add(names.get(site_of.get(service_id), service_id))
        rows += [(t, icon, f"{', '.join(sorted(sites))} {word}") for (t, word, icon), sites in changes.items()]
        rows.sort(key=lambda r: r[0])
    return rows
