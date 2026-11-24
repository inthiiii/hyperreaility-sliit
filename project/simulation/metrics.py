"""Deterministic restoration metrics.

Units are fictional services and incident minutes, not customers. Time is
integrated exactly over half-open integer-minute segments ``[start, end)``; no
sampling is used, so there is no discretisation error beyond the one-minute
resolution of the inputs. Weighted downtime is
``sum(weight) * horizon - weighted available service-minutes``.
"""
from __future__ import annotations

from typing import Iterable, NamedTuple


class ServiceRef(NamedTuple):
    service_id: str
    weight: int
    critical: bool


class Segment(NamedTuple):
    """Constant service availability over the half-open interval [start, end)."""
    start: int
    end: int
    available: frozenset


def check_segments(segments: list[Segment], horizon_min: int) -> None:
    cursor = 0
    for seg in segments:
        if seg.start != cursor or seg.end <= seg.start:
            raise ValueError('Segments must be contiguous, positive length and start at minute 0')
        cursor = seg.end
    if cursor != horizon_min:
        raise ValueError('Segments must cover exactly [0, horizon)')


def service_intervals(segments: Iterable[Segment], service_id: str) -> list[list[int]]:
    """Merged half-open availability intervals for one service."""
    out: list[list[int]] = []
    for seg in segments:
        if service_id in seg.available:
            if out and out[-1][1] == seg.start:
                out[-1][1] = seg.end
            else:
                out.append([seg.start, seg.end])
    return out


def compute_metrics(services: list[ServiceRef], segments: list[Segment], horizon_min: int) -> dict:
    ids = [s.service_id for s in services]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate service IDs; each service is counted once')
    known = set(ids)
    check_segments(segments, horizon_min)
    for seg in segments:
        if not seg.available <= known:
            raise ValueError('Segment names unknown services')
    weight = {s.service_id: s.weight for s in services}
    crit = {s.service_id for s in services if s.critical}

    available_min = {sid: 0 for sid in ids}
    weighted_available = 0
    for seg in segments:
        length = seg.end - seg.start
        for sid in seg.available:
            available_min[sid] += length
            weighted_available += weight[sid] * length

    total_weighted = sum(weight.values()) * horizon_min
    n = len(ids)
    first_restoration = None
    for prev, seg in zip(segments, segments[1:]):
        if seg.available - prev.available:
            first_restoration = seg.start
            break
    final = segments[-1].available
    return {
        'horizon_min': horizon_min,
        'services_total': n,
        'total_weighted_horizon_min': total_weighted,
        'weighted_available_min': weighted_available,
        'weighted_downtime_min': total_weighted - weighted_available,
        'unweighted_available_min': sum(available_min.values()),
        'unweighted_downtime_min': n * horizon_min - sum(available_min.values()),
        'unweighted_availability': (sum(available_min.values()) / (n * horizon_min)) if n else None,
        'critical_service_downtime_min': sum(horizon_min - available_min[sid] for sid in crit),
        'first_restoration_min': first_restoration,
        'services_available_at_horizon_end': len(final),
        'unmet_needs_count': n - len(final),
    }
