"""Incident views preserve uncertainty, visible-only data and no-inference browsing."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from streamlit.testing.v1 import AppTest

from project.core.schemas import ScenarioInput
from project.core.state import digest
from project.llm.client import HostedAdapter
from project.ui.catalog import load_catalog
from project.ui.incident_data import (
    action_rows, crew_rows, dependency_path, generator_rows, link_rows,
    local_site_status, observed_label, report_rows, road_rows, service_rows,
    site_rows, snapshot_counts,
)
from project.ui.session import SESSION_KEY
from project.ui.topology import render_topology_svg, schematic_positions

ROOT = Path(__file__).resolve().parents[2]
NS = {'s': 'http://www.w3.org/2000/svg'}


@pytest.fixture
def case():
    return ScenarioInput.model_validate_json((ROOT / 'tests/core/fixtures/DEMO-005.json').read_text())


@pytest.fixture
def ui_root(tmp_path):
    directory = tmp_path / 'tests/core/fixtures';directory.mkdir(parents=True)
    for path in (ROOT / 'tests/core/fixtures').glob('*.json'):
        (directory / path.name).write_bytes(path.read_bytes())
    return tmp_path


def incident_app(monkeypatch, ui_root):
    import project.ui.app as views
    monkeypatch.setattr(views, 'load_catalog', lambda root: load_catalog(ui_root))
    def forbidden(*args, **kwargs):
        raise AssertionError('Incident browsing must never construct an adapter or invoke models')
    monkeypatch.setattr(HostedAdapter, '__init__', forbidden)
    monkeypatch.setattr(HostedAdapter, 'complete', forbidden)
    at = AppTest.from_file(ROOT / 'project/main.py', default_timeout=15).run()
    return at.radio(key='workspace_page').set_value('Incident').run()


def test_snapshot_does_not_silently_resolve_reported_faults(case):
    assert snapshot_counts(case) == {'site_flags': 0, 'unknowns': 3, 'link_faults': 0, 'critical_services': 1}
    assert local_site_status(case, 'S02') == 'Unknown'
    assert site_rows(case)[1]['Grid power'] == 'Unknown'
    assert link_rows(case)[0]['Observed backhaul'] == 'Unknown'
    assert 'unavailable' in report_rows(case)[1]['Text']


def test_local_healthy_is_not_upstream_connectivity(case):
    case.observed_state.sites['S01'].equipment_ok = False
    case.observed_state.sites['S01'].grid_power_ok = None
    assert local_site_status(case, 'S01') == 'Local fault'
    assert local_site_status(case, 'S03') == 'Local observations OK'
    assert dependency_path(case, 'S03') == ['CORE', 'S01', 'S03']
    assert snapshot_counts(case)['site_flags'] == 1


def test_tri_state_labels_and_road_closure(case):
    assert [observed_label(v) for v in (True, False, None)] == ['OK', 'Fault', 'Unknown']
    case.observed_state.roads['R01'] = False
    assert road_rows(case)[0]['Observed access'] == 'Closed'
    case.observed_state.roads['R01'] = None
    assert road_rows(case)[0]['Observed access'] == 'Unknown'


def test_report_filtering_keeps_provenance_and_never_marks_facts_verified(case):
    report = case.reports[0];report.source_type = 'unconfirmed_message'
    report.observed_at_min = -15;report.received_at_min = -5
    rows = report_rows(case, ['unconfirmed_message'], 's01')
    assert len(rows) == 1 and rows[0]['Age (min)'] == 15 and rows[0]['Receipt lag (min)'] == 10
    assert rows[0]['Source class'] == 'Unverified source'
    assert report_rows(case, [], '') == []
    assert report_rows(case, query='REP-002')[0]['Report'] == 'REP-002'
    assert report_rows(case, query='not-present') == []


def test_crew_window_bounds_and_generator_inventory(case):
    assert crew_rows(case)[0]['Window status'] == 'In window'
    case.crews[0].available_from_min = 1
    assert crew_rows(case)[0]['Window status'] == 'Not yet available'
    case.crews[0].available_from_min = 0;case.crews[0].available_until_min = 1
    case.current_time_min = 1
    assert crew_rows(case)[0]['Window status'] == 'Window ended'
    case.generators[0].available = False
    assert generator_rows(case)[0]['Inventory availability'] == 'Unavailable'
    assert generator_rows(case)[0]['Autonomy (min)'] == 120


def test_priorities_and_action_catalogue_are_not_rewritten(case):
    original = digest(case)
    rows = service_rows(case, critical_only=True)
    assert len(rows) == 1 and rows[0]['Site'] == 'S02' and rows[0]['Policy weight'] == 5
    assert all(row['Policy evidence'] == case.policy.evidence_id for row in rows)
    assert action_rows(case)[0]['Work duration (min)'] == case.action_options[0].duration_minutes
    assert digest(case) == original


def test_svg_has_every_dependency_direction_and_optional_road(case):
    svg = ET.fromstring(render_topology_svg(case))
    assert len(svg.findall('.//s:g[@data-site-id]', NS)) == len(case.sites)
    paths = svg.findall('.//s:path[@data-link-id]', NS)
    assert {path.attrib['data-link-id'] for path in paths} == {link.link_id for link in case.links}
    assert all(path.attrib['marker-end'] == 'url(#relink-arrow)' for path in paths)
    assert not svg.findall('.//s:line[@data-road-id]', NS)
    roads = ET.fromstring(render_topology_svg(case, show_roads=True)).findall('.//s:line[@data-road-id]', NS)
    assert len(roads) == len(case.roads)
    assert all('marker-end' not in road.attrib for road in roads)


def test_svg_unknowns_critical_ring_focus_and_safe_strings(case):
    case.sites[1].label = '</title><script>alert("unsafe")</script>'
    before = digest(case)
    raw = render_topology_svg(case, selected_site='S02')
    svg = ET.fromstring(raw)
    assert not svg.findall('.//s:script', NS)
    target = svg.find('.//s:g[@data-site-id="S02"]', NS)
    assert target.attrib['data-local-status'] == 'Unknown' and target.attrib['opacity'] == '1'
    assert len(target.findall('s:circle', NS)) == 3  # critical ring, site, status badge
    assert svg.find('.//s:g[@data-site-id="S01"]', NS).attrib['opacity'] != '1'
    assert '&lt;script&gt;' in raw and 'service is restored' in raw
    assert digest(case) == before
    with pytest.raises(ValueError):render_topology_svg(case, selected_site='NOT-A-SITE')


def test_schematic_handles_collinear_coordinates_and_all_fixtures():
    for path in (ROOT / 'tests/core/fixtures').glob('*.json'):
        scenario = ScenarioInput.model_validate_json(path.read_text())
        positions, width, height = schematic_positions(scenario)
        assert len(positions) == len(scenario.sites) + 2
        assert all(0 < x < width and 0 < y < height for x, y in positions.values())
        assert len(set(positions.values())) == len(positions)
        assert ET.fromstring(render_topology_svg(scenario)) is not None


def test_incident_widgets_and_filters_do_not_change_core_session(monkeypatch, ui_root):
    at = incident_app(monkeypatch, ui_root)
    assert not at.exception
    assert len(at.get('image')) == 1  # SVG must use the image renderer, not HTML sanitization.
    session = at.session_state[SESSION_KEY];core = session.core;revision = session.selection_revision
    at.selectbox(key='incident_site').select('S02').run()
    at.checkbox(key='incident_roads').check().run()
    at.text_input(key='incident_query').input('REP-002').run()
    at.checkbox(key='incident_critical_only').check().run()
    assert not at.exception
    assert at.session_state[SESSION_KEY].core is core
    assert at.session_state[SESSION_KEY].selection_revision == revision
    assert core.current is None and core.approval is None
    reports = next(item.value for item in at.dataframe if 'Report' in item.value.columns)
    services = next(item.value for item in at.dataframe if 'Service' in item.value.columns)
    assert list(reports['Report']) == ['REP-002'] and len(services) == 1


def test_no_matching_reports_is_a_visible_empty_state(monkeypatch, ui_root):
    at = incident_app(monkeypatch, ui_root)
    at.multiselect(key='incident_sources').set_value([]).run()
    assert not at.exception
    assert any('No reports match' in item.value for item in at.info)
    assert not any(widget.key == 'incident_report' for widget in at.selectbox)


def test_scenario_change_resets_incident_filters(monkeypatch, ui_root):
    at = incident_app(monkeypatch, ui_root)
    at.selectbox(key='incident_site').select('S02').run()
    at.text_input(key='incident_query').input('not-present').run()
    at.checkbox(key='incident_critical_only').check().run()
    at.selectbox(key='scenario_picker').select('tests/core/fixtures/DEV-004.json').run()
    assert not at.exception
    assert at.selectbox(key='incident_site').value == 'All sites'
    assert at.text_input(key='incident_query').value == ''
    assert not at.checkbox(key='incident_critical_only').value


def test_empty_inventory_and_unapproved_policy_render_without_crash(monkeypatch, ui_root):
    path = ui_root / 'tests/core/fixtures/DEMO-005.json'
    payload = json.loads(path.read_text())
    for key in ('crews', 'generators', 'services', 'reports', 'action_options'):
        payload[key] = []
    payload['policy']['approved_for_simulation'] = False
    path.write_text(json.dumps(payload))
    at = incident_app(monkeypatch, ui_root)
    assert not at.exception
    assert any('No crews' in item.value for item in at.info)
    assert any('No generators' in item.value for item in at.info)
    assert any('No visible incident reports' in item.value for item in at.info)
    assert any('not approved' in item.value for item in at.warning)
