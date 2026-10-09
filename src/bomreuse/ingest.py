"""Boundary between the raw PLM/ERP export and the entity model.

Every row leaves this module either as a `BomLine` or as a `Reject` with its reason.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from bomreuse.model import BomLine, Reject
from bomreuse.normalize import canonical_ref, canonical_supplier, parse_mass_kg, parse_quantity

BOM_COLUMNS = (
    "variante",
    "niveau",
    "ref_parent",
    "ref_article",
    "designation",
    "qte",
    "unite",
    "fournisseur",
    "masse_unitaire",
)


@dataclass(frozen=True)
class Note:
    note_id: str
    ref_key: str
    text: str


@dataclass(frozen=True)
class Ingested:
    lines: list[BomLine]
    rejects: list[Reject]
    row_count: int


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        missing = set(BOM_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def _to_line(number: int, row: dict[str, str]) -> BomLine | Reject:
    if not row["ref_article"]:
        return Reject(number, "missing reference", row)
    if row["niveau"] not in {"1", "2"}:
        return Reject(number, f"unknown level {row['niveau']!r}", row)
    quantity = parse_quantity(row["qte"], row["unite"])
    if quantity is None:
        return Reject(number, f"unparsable quantity {row['qte']!r} {row['unite']!r}", row)
    return BomLine(
        row_number=number,
        variant=row["variante"],
        level=int(row["niveau"]),
        parent_key=canonical_ref(row["ref_parent"]),
        key=canonical_ref(row["ref_article"]),
        raw_ref=row["ref_article"],
        description=row["designation"],
        quantity=quantity,
        supplier=canonical_supplier(row["fournisseur"]),
        supplier_raw=row["fournisseur"],
        mass_kg=parse_mass_kg(row["masse_unitaire"]),
    )


def read_bom(path: Path) -> Ingested:
    rows = _read_rows(path)
    lines: list[BomLine] = []
    rejects: list[Reject] = []
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        result = _to_line(number, row)
        if isinstance(result, Reject):
            rejects.append(result)
        else:
            lines.append(result)
    return Ingested(lines, rejects, len(rows))


def read_notes(path: Path) -> list[Note]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Note(row["note_id"], canonical_ref(row["ref_article"]), row["texte"])
            for row in csv.DictReader(f, delimiter=";")
        ]
