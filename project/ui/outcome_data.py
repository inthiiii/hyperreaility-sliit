"""Result projections preserve nulls and evaluator field names/units."""
import math
from project.core.schemas import SimulationResult
from project.core.state import digest
from project.ui.history_data import public_payload


def current_outcome(session):
    if session.simulation_result is None:
        return None, None
    try:
        result = SimulationResult.model_validate(session.simulation_result)
        run = session.core.current;attempt = session.simulation_attempt
        if run is None or run.plan is None or not attempt or attempt.get('status') != 'completed':
            raise ValueError('No matching completed attempt')
        if (result.scenario_id, result.plan_id, result.state_version) != (run.state.scenario_id, run.plan.plan_id, run.state.state_version):
            raise ValueError('Result and current run differ')
        if attempt.get('plan_hash') != digest(run.plan) or attempt.get('result_hash') != digest(result):
            raise ValueError('Result or plan changed')
        binding = digest({'run': run.run_id, 'input': run.state.source_hash,
                          'plan': digest(run.plan), 'state': digest(run.state)})
        if attempt.get('binding') != binding:
            raise ValueError('Result state binding changed')
        def finite_tree(value):
            if isinstance(value, float) and not math.isfinite(value):raise ValueError('Non-finite output')
            if isinstance(value, dict):
                for item in value.values():finite_tree(item)
            if isinstance(value, list):
                for item in value:finite_tree(item)
        finite_tree(result.model_dump(mode='python'))
        return result, None
    except (ValueError, TypeError, AttributeError):
        return None, 'Stored output no longer matches the current run; it is not presented as the current outcome.'


def metric_rows(result):
    units = result.run_metadata.get('metric_units', {})
    if not isinstance(units, dict):units = {}
    return [{'Metric': key, 'Value': value, 'Unit': units[key] if isinstance(units.get(key), str) else 'Not specified'}
            for key, value in result.metrics.items()]


def trajectory_rows(result):
    rows = []
    for item in public_payload(result.trajectory):
        rows.append({key: value if value is None or isinstance(value, (str, int, float, bool)) else '[nested output omitted]'
                     for key, value in item.items()})
    return rows


def numeric_fields(rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    return [key for key in keys if any(row.get(key) is not None for row in rows)
            and all(row.get(key) is None or (type(row[key]) in (int, float) and math.isfinite(row[key])) for row in rows)]


def plot_rows(rows, time_field, series):
    valid = numeric_fields(rows)
    if time_field not in valid or not series or any(key not in valid or key == time_field for key in series):
        raise ValueError('Select numeric time and series fields')
    times = [row.get(time_field) for row in rows]
    if any(value is None for value in times) or any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError('Time values must be present and strictly increasing; raw rows remain available')
    return [{'Time': row[time_field], 'Series': key, 'Value': row.get(key)} for row in rows for key in series]
