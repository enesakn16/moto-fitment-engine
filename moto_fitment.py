"""Minimal motorcycle tyre fitment engine.

The module intentionally ships with a tiny example dataset. Real-world fitment data
should be sourced and verified before production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.parse import urlparse


@dataclass(frozen=True)
class TyreSpec:
    width_mm: int
    aspect_ratio: int
    rim_in: int

    @property
    def diameter_mm(self) -> float:
        sidewall = self.width_mm * (self.aspect_ratio / 100)
        return self.rim_in * 25.4 + 2 * sidewall

    @property
    def circumference_mm(self) -> float:
        return self.diameter_mm * 3.141592653589793

    @classmethod
    def parse(cls, value: str) -> "TyreSpec":
        try:
            size, rim = value.strip().upper().replace("ZR", "-").replace("R", "-").split("-")
            width, aspect = size.split("/")
            return cls(int(width), int(aspect), int(rim))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Unsupported tyre size: {value!r}") from exc

    def __str__(self) -> str:
        return f"{self.width_mm}/{self.aspect_ratio}-{self.rim_in}"


@dataclass(frozen=True)
class Fitment:
    make: str
    model: str
    year_from: int
    year_to: int
    front: TyreSpec
    rear: TyreSpec
    source_note: str
    source_url: str | None = None
    verified_on: str | None = None

    def supports_year(self, year: int) -> bool:
        return self.year_from <= year <= self.year_to

    @property
    def is_verified(self) -> bool:
        """Return whether the record carries minimally trustworthy provenance.

        Verification deliberately requires both an HTTPS source URL and an ISO date.
        This does not prove that the source itself is authoritative; it prevents demo or
        undocumented records from being silently treated as production-grade data.
        """
        if not self.source_url or not self.verified_on:
            return False

        parsed_url = urlparse(self.source_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            return False

        try:
            verified_date = date.fromisoformat(self.verified_on)
        except ValueError:
            return False

        return verified_date <= date.today()


# Deliberately small demo dataset. Values are examples and are not a substitute
# for manufacturer documentation. The engine is designed so verified records can
# later be loaded from CSV/JSON/SQLite without changing the matching API.
_DEMO_FITMENTS: tuple[Fitment, ...] = (
    Fitment(
        make="Honda",
        model="PCX 125",
        year_from=2021,
        year_to=2024,
        front=TyreSpec.parse("110/70-14"),
        rear=TyreSpec.parse("130/70-13"),
        source_note="Demo record — verify against manufacturer documentation.",
    ),
    Fitment(
        make="Yamaha",
        model="NMAX 125",
        year_from=2021,
        year_to=2024,
        front=TyreSpec.parse("110/70-13"),
        rear=TyreSpec.parse("130/70-13"),
        source_note="Demo record — verify against manufacturer documentation.",
    ),
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def find_fitment(
    make: str,
    model: str,
    year: int,
    records: Iterable[Fitment] = _DEMO_FITMENTS,
    *,
    require_verified: bool = False,
) -> Fitment:
    """Find a make/model/year match, optionally requiring provenance verification.

    ``require_verified=True`` is the intended production mode. It skips matching
    records that lack a valid HTTPS source and verification date instead of silently
    returning demo or undocumented data.
    """
    make_key = _normalize(make)
    model_key = _normalize(model)
    matched_unverified = False

    for record in records:
        if (
            _normalize(record.make) == make_key
            and _normalize(record.model) == model_key
            and record.supports_year(year)
        ):
            if require_verified and not record.is_verified:
                matched_unverified = True
                continue
            return record

    if matched_unverified:
        raise LookupError(
            f"Fitment record exists for {make} {model} ({year}) but has no verified provenance."
        )
    raise LookupError(f"No verified fitment record found for {make} {model} ({year}).")


def diameter_delta_percent(original: TyreSpec, alternative: TyreSpec) -> float:
    """Return signed overall-diameter difference as a percentage."""
    return ((alternative.diameter_mm / original.diameter_mm) - 1) * 100


def is_reasonable_alternative(original: TyreSpec, alternative: TyreSpec, max_delta_percent: float = 3.0) -> bool:
    """Basic geometry screen; this does NOT prove vehicle compatibility."""
    if original.rim_in != alternative.rim_in:
        return False
    return abs(diameter_delta_percent(original, alternative)) <= max_delta_percent


def _self_test() -> None:
    pcx = find_fitment(" honda ", "PCX 125", 2023)
    assert str(pcx.front) == "110/70-14"
    assert str(pcx.rear) == "130/70-13"
    assert not pcx.is_verified

    try:
        find_fitment("Honda", "PCX 125", 2023, require_verified=True)
    except LookupError:
        pass
    else:
        raise AssertionError("Demo records must not pass verified-production lookup")

    verified = Fitment(
        make="Example",
        model="Verified 125",
        year_from=2026,
        year_to=2026,
        front=TyreSpec.parse("100/80-17"),
        rear=TyreSpec.parse("120/70-17"),
        source_note="Self-test fixture",
        source_url="https://example.com/fitment",
        verified_on="2026-01-01",
    )
    assert verified.is_verified
    assert find_fitment(
        "Example", "Verified 125", 2026, (verified,), require_verified=True
    ) == verified

    original = TyreSpec.parse("150/70-17")
    alternative = TyreSpec.parse("150/60-17")
    delta = diameter_delta_percent(original, alternative)
    assert round(delta, 1) == -4.7
    assert not is_reasonable_alternative(original, alternative)

    close_alt = TyreSpec.parse("140/70-17")
    assert is_reasonable_alternative(original, close_alt)

    try:
        TyreSpec.parse("bad-size")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid tyre size must raise ValueError")


if __name__ == "__main__":
    _self_test()
    sample = find_fitment("Honda", "PCX 125", 2023)
    print(f"{sample.make} {sample.model} ({sample.year_from}-{sample.year_to})")
    print(f"Front: {sample.front} | Rear: {sample.rear}")
    print(sample.source_note)
