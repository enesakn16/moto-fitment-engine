"""Deterministic geometry screening for motorcycle tyre alternatives.

This module deliberately does not claim vehicle compatibility. It only ranks tyre
sizes that keep the same rim diameter and remain within configurable overall-
diameter and section-width tolerances. Final fitment still requires vehicle/OEM-
specific validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from moto_fitment import TyreSpec, diameter_delta_percent, is_reasonable_alternative


@dataclass(frozen=True)
class AlternativeEvaluation:
    """A geometry-only evaluation of one candidate tyre size."""

    tyre: TyreSpec
    diameter_delta_percent: float
    width_delta_mm: int
    aspect_ratio_delta: int


def rank_geometry_alternatives(
    original: TyreSpec,
    candidates: Iterable[TyreSpec],
    *,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> tuple[AlternativeEvaluation, ...]:
    """Return deterministic geometry-screened candidates ordered by closeness.

    Exact duplicates of the OEM size are omitted, repeated candidate sizes are
    collapsed, different rim diameters are rejected, and candidates outside the
    requested overall-diameter or section-width tolerances are rejected.

    ``max_width_delta_mm`` is deliberately conservative. Similar rolling diameter
    alone is not enough to make a tyre a credible candidate: a much wider or
    narrower section may require a different rim width or create clearance issues.

    The result is a *screening list*, not a compatibility guarantee. Load index,
    speed rating, approved rim-width range, physical clearance, ABS/TC calibration,
    homologation and manufacturer restrictions remain outside this geometry-only
    calculation and must still be verified before a tyre is described as compatible.
    """
    if max_delta_percent < 0:
        raise ValueError("max_delta_percent must be non-negative")
    if max_width_delta_mm < 0:
        raise ValueError("max_width_delta_mm must be non-negative")

    seen: set[TyreSpec] = set()
    evaluations: list[AlternativeEvaluation] = []

    for candidate in candidates:
        if candidate == original or candidate in seen:
            continue
        seen.add(candidate)

        width_delta_mm = candidate.width_mm - original.width_mm
        if abs(width_delta_mm) > max_width_delta_mm:
            continue

        if not is_reasonable_alternative(
            original,
            candidate,
            max_delta_percent=max_delta_percent,
        ):
            continue

        evaluations.append(
            AlternativeEvaluation(
                tyre=candidate,
                diameter_delta_percent=diameter_delta_percent(original, candidate),
                width_delta_mm=width_delta_mm,
                aspect_ratio_delta=candidate.aspect_ratio - original.aspect_ratio,
            )
        )

    evaluations.sort(
        key=lambda item: (
            abs(item.diameter_delta_percent),
            abs(item.width_delta_mm),
            abs(item.aspect_ratio_delta),
            item.tyre.width_mm,
            item.tyre.aspect_ratio,
            item.tyre.rim_in,
        )
    )
    return tuple(evaluations)
