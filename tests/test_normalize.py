import pytest

from bomreuse.model import Quantity, Unit
from bomreuse.normalize import (
    canonical_ref,
    canonical_supplier,
    dimension_tokens,
    display_ref,
    english_tokens,
    parse_mass_kg,
    parse_quantity,
    same_supplier,
    supplier_groups,
    variant_markers,
)


@pytest.mark.parametrize("raw", ["BOG-1101", "bog-1101", "BOG 1101", "BOG_01101", "BOG1101"])
def test_reference_spellings_collapse(raw: str) -> None:
    assert canonical_ref(raw) == "BOG1101"


def test_separators_do_not_split_identity() -> None:
    assert canonical_ref("SECAB-624") == canonical_ref("SE-CAB-624") == canonical_ref("se_cab_0624")
    assert display_ref("se_cab_0624") == "SE-CAB-624"


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
    assert {canonical_supplier(n) for n in names} == {"knorr bremse"}


def test_french_description_maps_to_english() -> None:
    assert english_tokens("Vis tête hexagonale M12x40") == "screw head hex m12x40"


def test_dimensions() -> None:
    assert dimension_tokens("Hex head screw M12x40") == {"12x40"}
    assert dimension_tokens("Câble de puissance 35mm²") == {"35mm2"}


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ZF", "ZF Friedrichshafen"),
        ("Ateliers Méca. du Hainaut", "AMH"),
        ("Ressorts et Susp. des Alpes", "RESSORTS & SUSPENSIONS DES ALPES"),
        ("FAB. INTERNE", "Interne"),
    ],
)
def test_supplier_spellings_of_one_company(a: str, b: str) -> None:
    assert same_supplier(canonical_supplier(a), canonical_supplier(b))


def test_different_suppliers_stay_apart() -> None:
    names = {canonical_supplier(n) for n in ("Knorr-Bremse", "Wabtec", "KNORR BREMSE GmbH")}
    assert supplier_groups(names) == 2


def test_variant_markers() -> None:
    assert variant_markers("VIS H M8X25 INOX A4") == {"material": frozenset({"stainless"})}
    assert variant_markers("Porte côté gauche")["side"] == {"left"}
    assert variant_markers("Upholstery fabric, 2nd class")["class"] == {"class 2"}
