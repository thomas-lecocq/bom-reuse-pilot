import pytest

from bomreuse.model import Quantity, Unit
from bomreuse.normalize import (
    canonical_ref,
    canonical_supplier,
    dimension_tokens,
    english_tokens,
    parse_mass_kg,
    parse_quantity,
)


@pytest.mark.parametrize("raw", ["BOG-1101", "bog-1101", "BOG 1101", "BOG_01101", "BOG1101"])
def test_reference_spellings_collapse(raw: str) -> None:
    assert canonical_ref(raw) == "BOG-1101"


def test_typo_is_not_collapsed() -> None:
    assert canonical_ref("DOR-3014") != canonical_ref("DOR-3104")


@pytest.mark.parametrize(
    ("qty", "unit", "expected"),
    [
        ("2500", "mm", Quantity(2.5, Unit.METRE)),
        ("250", "cm", Quantity(2.5, Unit.METRE)),
        ("2,5", "M", Quantity(2.5, Unit.METRE)),
        ("4", "pce", Quantity(4, Unit.PIECE)),
        ("4,0", "EA", Quantity(4, Unit.PIECE)),
    ],
)
def test_quantities_are_converted(qty: str, unit: str, expected: Quantity) -> None:
    assert parse_quantity(qty, unit) == expected


@pytest.mark.parametrize(("qty", "unit"), [("?", "PC"), ("4", "bte"), ("0", "PC"), ("", "PC")])
def test_bad_quantities_are_refused(qty: str, unit: str) -> None:
    assert parse_quantity(qty, unit) is None


def test_mass() -> None:
    assert parse_mass_kg("45 g") == 0.045
    assert parse_mass_kg("12,5 kg") == 12.5
    assert parse_mass_kg("12.5") is None


def test_supplier_aliases() -> None:
    names = {"Knorr-Bremse", "KNORR BREMSE GmbH", "Knorr Bremse AG"}
    assert {canonical_supplier(n) for n in names} == {"knorrbremse"}
    assert canonical_supplier("Wabtec") != canonical_supplier("Knorr-Bremse")


def test_french_description_maps_to_english() -> None:
    assert english_tokens("Vis tête hexagonale M12x40") == "screw head hex m12x40"


def test_dimensions() -> None:
    assert dimension_tokens("Hex head screw M12x40") == {"12x40"}
    assert dimension_tokens("Câble de puissance 35mm²") == {"35mm2"}
