"""Deterministic geometry screening for motorcycle tyre alternatives.

This module deliberately does not claim vehicle compatibility. It only ranks tyre
sizes that keep the same rim diameter and remain within configurable overall-
diameter and section-width tolerances. Final fitment still requires vehicle/OEM-
specific validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from urllib.parse import urlparse

from moto_fitment import (
    Fitment,
    TyreSpec,
    diameter_delta_percent,
    find_fitment,
    is_reasonable_alternative,
)


# Service-description speed symbols are normalized at the catalog boundary so the
# safety layer can continue comparing integer km/h capabilities. Deliberately exclude
# ambiguous Z/(Y) forms: they do not represent one finite capability without further
# manufacturer context and therefore must not be guessed by an importer.
_SPEED_SYMBOL_TO_KMH: dict[str, int] = {
    "F": 80,
    "J": 100,
    "K": 110,
    "L": 120,
    "M": 130,
    "N": 140,
    "P": 150,
    "Q": 160,
    "R": 170,
    "S": 180,
    "T": 190,
    "U": 200,
    "H": 210,
    "V": 240,
    "W": 270,
    "Y": 300,
}
_SERVICE_DESCRIPTION_RE = re.compile(r"^(?P<load>\d{1,3})\s*(?P<speed>[A-Za-z])$")


def parse_service_description(value: str) -> tuple[int, int]:
    """Parse a tyre service description such as ``58W`` into numeric safety data.

    Returns ``(load_index, speed_kmh)``. Whitespace and letter case are normalized,
    but malformed, unknown or ambiguous symbols fail closed instead of being guessed.
    This function intentionally parses only the service description, not a full tyre
    size such as ``120/70 ZR17 58W``.
    """
    if not isinstance(value, str):
        raise TypeError("service description must be a string")

    match = _SERVICE_DESCRIPTION_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("service description must look like '<load index><speed symbol>'")

    load_index = int(match.group("load"))
    if load_index <= 0:
        raise ValueError("load index must be positive")

    speed_symbol = match.group("speed").upper()
    try:
        speed_kmh = _SPEED_SYMBOL_TO_KMH[speed_symbol]
    except KeyError as exc:
        raise ValueError(f"unsupported or ambiguous speed symbol: {speed_symbol}") from exc

    return load_index, speed_kmh


@dataclass(frozen=True)
class AlternativeEvaluation:
    """A geometry-only evaluation of one candidate tyre size."""

    tyre: TyreSpec
    diameter_delta_percent: float
    width_delta_mm: int
    aspect_ratio_delta: int


@dataclass(frozen=True)
class CatalogTyre:
    """One sellable tyre catalog item with optional commerce and safety metadata.

    ``load_index`` and ``speed_kmh`` are deliberately numeric. This keeps the core
    screening policy independent from presentation symbols and lets upstream importers
    normalize supplier-specific rating formats before they reach the safety boundary.
    """

    sku: str
    brand: str
    product_name: str
    tyre: TyreSpec
    stock_quantity: int | None = None
    price: Decimal | None = None
    product_url: str | None = None
    load_index: int | None = None
    speed_kmh: int | None = None

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku must not be empty")
        if not self.brand.strip():
            raise ValueError("brand must not be empty")
        if not self.product_name.strip():
            raise ValueError("product_name must not be empty")
        if self.stock_quantity is not None and self.stock_quantity < 0:
            raise ValueError("stock_quantity must be non-negative")
        if self.price is not None and self.price <= 0:
            raise ValueError("price must be positive")
        if self.product_url is not None:
            parsed = urlparse(self.product_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("product_url must be an absolute HTTPS URL")
        if self.load_index is not None and (
            isinstance(self.load_index, bool)
            or not isinstance(self.load_index, int)
            or self.load_index <= 0
        ):
            raise ValueError("load_index must be a positive integer when provided")
        if self.speed_kmh is not None and (
            isinstance(self.speed_kmh, bool)
            or not isinstance(self.speed_kmh, int)
            or self.speed_kmh <= 0
        ):
            raise ValueError("speed_kmh must be a positive integer when provided")

    @property
    def is_in_stock(self) -> bool:
        """Return true only when stock is known and greater than zero."""
        return self.stock_quantity is not None and self.stock_quantity > 0


@dataclass(frozen=True)
class CatalogAlternativeEvaluation:
    """Geometry screening result that preserves the sellable catalog identity."""

    item: CatalogTyre
    diameter_delta_percent: float
    width_delta_mm: int
    aspect_ratio_delta: int


@dataclass(frozen=True)
class FitmentAlternativeResult:
    """Verified OEM fitment plus geometry-screened front and rear candidates.

    The candidate lists are intentionally geometry-only. Their presence does not
    mean that load index, speed rating, rim-width approval, vehicle clearance,
    ABS/TC behavior, homologation, or manufacturer restrictions have been checked.
    """

    fitment: Fitment
    front: tuple[AlternativeEvaluation, ...]
    rear: tuple[AlternativeEvaluation, ...]


@dataclass(frozen=True)
class CatalogFitmentAlternativeResult:
    """Verified OEM fitment plus SKU-preserving front and rear catalog candidates."""

    fitment: Fitment
    front: tuple[CatalogAlternativeEvaluation, ...]
    rear: tuple[CatalogAlternativeEvaluation, ...]


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


def _validate_positive_threshold(value: int | None, name: str) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
    ):
        raise ValueError(f"{name} must be a positive integer when provided")


def rank_catalog_alternatives(
    original: TyreSpec,
    catalog: Iterable[CatalogTyre],
    *,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
    only_in_stock: bool = False,
    minimum_load_index: int | None = None,
    minimum_speed_kmh: int | None = None,
) -> tuple[CatalogAlternativeEvaluation, ...]:
    """Screen sellable catalog rows while keeping SKU/product identity intact.

    Multiple SKUs with the same tyre size are preserved because they can represent
    different brands, patterns or stock records. Duplicate SKU values are rejected.
    When ``only_in_stock`` is true, unknown stock and zero-stock rows are omitted so
    callers can request a commerce-ready list without pretending unknown inventory is
    available.

    When a minimum load index or speed capability is supplied, screening becomes
    fail-closed for that criterion: candidates with missing safety metadata are
    rejected alongside candidates below the required threshold. Callers must source
    those minimums from verified OEM/vehicle data; this function never invents them.
    """
    if max_delta_percent < 0:
        raise ValueError("max_delta_percent must be non-negative")
    if max_width_delta_mm < 0:
        raise ValueError("max_width_delta_mm must be non-negative")
    _validate_positive_threshold(minimum_load_index, "minimum_load_index")
    _validate_positive_threshold(minimum_speed_kmh, "minimum_speed_kmh")

    seen_skus: set[str] = set()
    evaluations: list[CatalogAlternativeEvaluation] = []

    for item in catalog:
        sku_key = item.sku.strip().casefold()
        if sku_key in seen_skus:
            raise ValueError(f"duplicate sku in catalog: {item.sku}")
        seen_skus.add(sku_key)

        if only_in_stock and not item.is_in_stock:
            continue
        if minimum_load_index is not None and (
            item.load_index is None or item.load_index < minimum_load_index
        ):
            continue
        if minimum_speed_kmh is not None and (
            item.speed_kmh is None or item.speed_kmh < minimum_speed_kmh
        ):
            continue
        if item.tyre == original:
            continue

        width_delta_mm = item.tyre.width_mm - original.width_mm
        if abs(width_delta_mm) > max_width_delta_mm:
            continue
        if not is_reasonable_alternative(
            original,
            item.tyre,
            max_delta_percent=max_delta_percent,
        ):
            continue

        evaluations.append(
            CatalogAlternativeEvaluation(
                item=item,
                diameter_delta_percent=diameter_delta_percent(original, item.tyre),
                width_delta_mm=width_delta_mm,
                aspect_ratio_delta=item.tyre.aspect_ratio - original.aspect_ratio,
            )
        )

    evaluations.sort(
        key=lambda result: (
            abs(result.diameter_delta_percent),
            abs(result.width_delta_mm),
            abs(result.aspect_ratio_delta),
            result.item.brand.casefold(),
            result.item.product_name.casefold(),
            result.item.sku.casefold(),
        )
    )
    return tuple(evaluations)


def find_fitment_alternatives(
    make: str,
    model: str,
    year: int,
    candidates: Iterable[TyreSpec],
    records: Iterable[Fitment],
    *,
    require_verified: bool = True,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> FitmentAlternativeResult:
    """Resolve OEM fitment and screen one tyre catalog for both wheel positions.

    Production use is fail-closed by default: the matched fitment must have verified
    provenance. ``require_verified=False`` exists for explicit demo/test scenarios.
    The candidate iterable is materialized once so generators can be safely reused
    for front and rear screening.
    """
    fitment = find_fitment(
        make,
        model,
        year,
        records,
        require_verified=require_verified,
    )
    catalog = tuple(candidates)

    return FitmentAlternativeResult(
        fitment=fitment,
        front=rank_geometry_alternatives(
            fitment.front,
            catalog,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
        rear=rank_geometry_alternatives(
            fitment.rear,
            catalog,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
    )


def _effective_minimum(explicit: int | None, verified_oem: int | None) -> int | None:
    """Return the strictest supplied threshold without permitting OEM downgrades."""
    if verified_oem is None:
        return explicit
    if explicit is None:
        return verified_oem
    return max(explicit, verified_oem)


def find_catalog_fitment_alternatives(
    make: str,
    model: str,
    year: int,
    catalog: Iterable[CatalogTyre],
    records: Iterable[Fitment],
    *,
    require_verified: bool = True,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
    only_in_stock: bool = False,
    front_minimum_load_index: int | None = None,
    rear_minimum_load_index: int | None = None,
    front_minimum_speed_kmh: int | None = None,
    rear_minimum_speed_kmh: int | None = None,
) -> CatalogFitmentAlternativeResult:
    """Resolve a vehicle and return safety- and geometry-screened sellable SKUs.

    Verified axle-specific OEM minimums stored on the matched fitment are applied
    automatically. Optional caller thresholds may only make the policy stricter;
    they can never weaken verified OEM requirements. Records without complete verified
    safety metadata preserve the explicit-threshold/geometry-only legacy behavior.
    """
    fitment = find_fitment(
        make,
        model,
        year,
        records,
        require_verified=require_verified,
    )
    items = tuple(catalog)

    # Validate caller-provided values even when verified OEM values will be stricter.
    _validate_positive_threshold(front_minimum_load_index, "front_minimum_load_index")
    _validate_positive_threshold(rear_minimum_load_index, "rear_minimum_load_index")
    _validate_positive_threshold(front_minimum_speed_kmh, "front_minimum_speed_kmh")
    _validate_positive_threshold(rear_minimum_speed_kmh, "rear_minimum_speed_kmh")

    if fitment.has_verified_safety_requirements:
        front_minimum_load_index = _effective_minimum(
            front_minimum_load_index, fitment.front_minimum_load_index
        )
        rear_minimum_load_index = _effective_minimum(
            rear_minimum_load_index, fitment.rear_minimum_load_index
        )
        front_minimum_speed_kmh = _effective_minimum(
            front_minimum_speed_kmh, fitment.front_minimum_speed_kmh
        )
        rear_minimum_speed_kmh = _effective_minimum(
            rear_minimum_speed_kmh, fitment.rear_minimum_speed_kmh
        )

    # Validate duplicate SKU identity once for the shared catalog before screening.
    sku_keys = [item.sku.strip().casefold() for item in items]
    if len(sku_keys) != len(set(sku_keys)):
        raise ValueError("duplicate sku in catalog")

    return CatalogFitmentAlternativeResult(
        fitment=fitment,
        front=rank_catalog_alternatives(
            fitment.front,
            items,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
            only_in_stock=only_in_stock,
            minimum_load_index=front_minimum_load_index,
            minimum_speed_kmh=front_minimum_speed_kmh,
        ),
        rear=rank_catalog_alternatives(
            fitment.rear,
            items,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
            only_in_stock=only_in_stock,
            minimum_load_index=rear_minimum_load_index,
            minimum_speed_kmh=rear_minimum_speed_kmh,
        ),
    )
