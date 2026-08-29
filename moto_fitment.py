"""Minimal motorcycle tyre fitment engine.

The module intentionally ships with a tiny example dataset. Real-world fitment data
should be sourced and verified before production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
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
        if not isinstance(value, str):
            raise ValueError(f"Unsupported tyre size: {value!r}")

        normalized = value.strip().upper().replace(" ", "")
        match = re.fullmatch(r"(\d{2,3})/(\d{2,3})(?:-?(?:ZR|R)-?|-)(\d{2})", normalized)
        if not match:
            raise ValueError(f"Unsupported tyre size: {value!r}")

        width, aspect, rim = match.groups()
        return cls(int(width), int(aspect), int(rim))

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


_MAX_JSON_BYTES = 1_000_000
_JSON_FIELDS = {
    "make",
    "model",
    "year_from",
    "year_to",
    "front",
    "rear",
    "source_note",
    "source_url",
    "verified_on",
}


def load_fitments_json(path: str | Path) -> tuple[Fitment, ...]:
    """Load strictly validated fitment records from a JSON array.

    The loader refuses unknown fields, oversized files, invalid year ranges,
    malformed tyre sizes, overlapping make/model/year ranges, and records without
    verified provenance. Production data therefore cannot silently downgrade to
    the permissive demo-data behavior or become lookup-order dependent.
    """
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Fitment JSON file does not exist: {source}")

    size = source.stat().st_size
    if size > _MAX_JSON_BYTES:
        raise ValueError(f"Fitment JSON exceeds {_MAX_JSON_BYTES} byte safety limit")

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read fitment JSON: {source}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Fitment JSON must contain a non-empty array of records")

    records: list[Fitment] = []
    identities: set[tuple[str, str, int, int]] = set()
    ranges_by_model: dict[tuple[str, str], list[tuple[int, int]]] = {}

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Fitment record {index} must be a JSON object")

        unknown = set(item) - _JSON_FIELDS
        missing = _JSON_FIELDS - set(item)
        if unknown:
            raise ValueError(
                f"Fitment record {index} has unknown fields: {', '.join(sorted(unknown))}"
            )
        if missing:
            raise ValueError(
                f"Fitment record {index} is missing fields: {', '.join(sorted(missing))}"
            )

        make = item["make"]
        model = item["model"]
        source_note = item["source_note"]
        source_url = item["source_url"]
        verified_on = item["verified_on"]
        if not all(isinstance(value, str) and value.strip() for value in (make, model, source_note)):
            raise ValueError(f"Fitment record {index} has blank make/model/source_note")
        if not isinstance(source_url, str) or not isinstance(verified_on, str):
            raise ValueError(f"Fitment record {index} provenance fields must be strings")

        year_from = item["year_from"]
        year_to = item["year_to"]
        if (
            isinstance(year_from, bool)
            or isinstance(year_to, bool)
            or not isinstance(year_from, int)
            or not isinstance(year_to, int)
            or year_from < 1900
            or year_to < year_from
            or year_to > date.today().year + 2
        ):
            raise ValueError(f"Fitment record {index} has an invalid year range")

        front_value = item["front"]
        rear_value = item["rear"]
        if not isinstance(front_value, str) or not isinstance(rear_value, str):
            raise ValueError(f"Fitment record {index} tyre sizes must be strings")

        record = Fitment(
            make=make.strip(),
            model=model.strip(),
            year_from=year_from,
            year_to=year_to,
            front=TyreSpec.parse(front_value),
            rear=TyreSpec.parse(rear_value),
            source_note=source_note.strip(),
            source_url=source_url.strip(),
            verified_on=verified_on.strip(),
        )
        if not record.is_verified:
            raise ValueError(f"Fitment record {index} does not have verified provenance")

        make_key = _normalize(record.make)
        model_key = _normalize(record.model)
        identity = (make_key, model_key, record.year_from, record.year_to)
        if identity in identities:
            raise ValueError(f"Fitment record {index} duplicates an existing fitment range")

        range_key = (make_key, model_key)
        for existing_from, existing_to in ranges_by_model.get(range_key, ()):
            if record.year_from <= existing_to and existing_from <= record.year_to:
                raise ValueError(
                    f"Fitment record {index} overlaps an existing fitment range for "
                    f"{record.make} {record.model}"
                )

        identities.add(identity)
        ranges_by_model.setdefault(range_key, []).append((record.year_from, record.year_to))
        records.append(record)

    return tuple(records)


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
