"""Boundary between the raw PLM/ERP export and the entity model.

Every row leaves this module either as a `BomLine` or as a `Reject` with its reason.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter

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
    date: str = ""


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
        return [_clean(row) for row in reader]


def _clean(row: dict[str | None, str | list[str] | None]) -> dict[str, str]:
    """Extra separators land under the key None; keep them visible so the row is rejected."""
    out = {k: v.strip() if isinstance(v, str) else "" for k, v in row.items() if k is not None}
    extra = row.get(None)
    if isinstance(extra, list):
        out[_EXTRA] = ";".join(extra)
    return out


_EXTRA = "_extra_fields"


def _to_line(number: int, row: dict[str, str]) -> BomLine | Reject:
    if _EXTRA in row:
        return Reject(number, f"more fields than columns (unquoted ';'?): {row[_EXTRA]!r}", row)
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


_REF_IN_TEXT = re.compile(r"\b[A-Z]{2,4}[-_ .]?\d{3,8}[A-Z]?\b", re.I)


def iso_date(raw: str) -> str:
    """`13/01/2025` and `2025-01-13` -> `2025-01-13`; anything else -> empty."""
    if match := re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", raw.strip()):
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return raw.strip() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw.strip()) else ""


def _note_subject(row: dict[str, str]) -> str:
    """The note's reference column, or the first reference written in its text."""
    if row["ref_article"].strip():
        return canonical_ref(row["ref_article"])
    match = _REF_IN_TEXT.search(row["texte"])
    return canonical_ref(match.group(0)) if match else ""


def read_notes(path: Path) -> list[Note]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Note(row["note_id"], _note_subject(row), row["texte"], iso_date(row["date"]))
            for row in csv.DictReader(f, delimiter=";")
        ]


class _Decision(BaseModel):
    a: str
    b: str
    decision: Literal["same", "different"]


def read_decisions(path: Path) -> dict[frozenset[str], bool]:
    """Review-queue decisions exported from the report; absent file means no decision yet."""
    if not path.exists():
        return {}
    parsed = TypeAdapter(list[_Decision]).validate_json(path.read_text(encoding="utf-8"))
    return {
        frozenset((canonical_ref(d.a), canonical_ref(d.b))): d.decision == "same" for d in parsed
    }
