"""Forecast is a visible-state mathematical tool, not measured evaluation."""
import csv
import io
from project.core.forecast import service_forecast
from project.core.state import build_verified_state
from project.core.planner import plan


def test_demo_generator_forecast_accounts_for_downstream_services(load_case):
    s=load_case();state=build_verified_state(s,[]);candidate=plan(state)
    result=service_forecast(state,candidate)
    assert result['total_weighted_available_minutes']==720
    assert result['agrees_with_scheduler'] is True
    rows=list(csv.reader(io.StringIO(result['services_csv'])))
    assert sum(int(row[3]) for row in rows)==720
    assert len([r for r in rows if int(r[2])>0])==2
    assert 'not simulator measurement' in result['scope']


def test_forecast_uses_public_inventory_not_hidden_generator_labels(load_case):
    s=load_case();s.generators[0].autonomy_minutes=60
    state=build_verified_state(s,[]);candidate=plan(state);result=service_forecast(state,candidate)
    assert result['total_weighted_available_minutes']==360
    assert result['agrees_with_scheduler'] is True


def test_healthy_services_contribute_without_any_repair_or_generator(load_case):
    s=load_case('DEV-007');state=build_verified_state(s,[]);candidate=plan(state)
    result=service_forecast(state,candidate)
    assert not candidate.actions
    assert result['total_weighted_available_minutes']==sum(v.weight for v in s.services)*(s.horizon_min-s.current_time_min)
    assert result['agrees_with_scheduler'] is True
