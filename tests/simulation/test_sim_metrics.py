import pytest

from project.simulation.metrics import Segment, ServiceRef, compute_metrics, service_intervals

SERVICES = [ServiceRef('A', 5, True), ServiceRef('B', 1, False)]


def seg(a, b, *ids):
    return Segment(a, b, frozenset(ids))


def test_weighted_downtime_formula():
    m = compute_metrics(SERVICES, [seg(0, 10), seg(10, 40, 'A'), seg(40, 100, 'A', 'B')], 100)
    assert m['total_weighted_horizon_min'] == 600
    assert m['weighted_available_min'] == 5 * 90 + 1 * 60
    assert m['weighted_downtime_min'] == 600 - 510
    assert m['unweighted_availability'] == pytest.approx((90 + 60) / 200)
    assert m['critical_service_downtime_min'] == 10
    assert m['first_restoration_min'] == 10
    assert m['services_available_at_horizon_end'] == 2 and m['unmet_needs_count'] == 0


def test_no_restoration_gives_null_first_restoration():
    m = compute_metrics(SERVICES, [seg(0, 50), seg(50, 100)], 100)
    assert m['first_restoration_min'] is None and m['weighted_downtime_min'] == 600


def test_initially_up_service_is_not_a_restoration():
    m = compute_metrics(SERVICES, [seg(0, 100, 'A')], 100)
    assert m['first_restoration_min'] is None


def test_service_interval_merging_and_validation():
    segs = [seg(0, 10, 'A'), seg(10, 20, 'A', 'B'), seg(20, 30)]
    assert service_intervals(segs, 'A') == [[0, 20]] and service_intervals(segs, 'B') == [[10, 20]]
    with pytest.raises(ValueError):
        compute_metrics(SERVICES, [seg(0, 10), seg(11, 30)], 30)       # gap
    with pytest.raises(ValueError):
        compute_metrics(SERVICES, [seg(0, 10)], 30)                    # short
    with pytest.raises(ValueError):
        compute_metrics(SERVICES, [seg(0, 30, 'Z')], 30)               # unknown service
    with pytest.raises(ValueError):
        compute_metrics(SERVICES + [ServiceRef('A', 1, False)], [seg(0, 30)], 30)  # duplicate ID
