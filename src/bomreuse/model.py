"""Entity model shared by every stage: what a normalized BOM line, a merge and a finding are."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Unit(StrEnum):
    PIECE = "pc"
    METRE = "m"
    KILOGRAM = "kg"
    LITRE = "l"


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: Unit


@dataclass(frozen=True)
class Reject:
    row_number: int
    reason: str
    raw: dict[str, str]


@dataclass(frozen=True)
class BomLine:
    """One input row after normalization. `key` is the canonical form of `raw_ref`."""

    row_number: int
    variant: str
    level: int
    parent_key: str
    key: str
    raw_ref: str
    description: str
    quantity: Quantity
    supplier: str
    supplier_raw: str
    mass_kg: float | None


@dataclass(frozen=True)
class Evidence:
    signal: str
    detail: str


@dataclass(frozen=True)
class MergeDecision:
    """Two component keys judged to be the same part. Cannot exist without evidence."""

    key_a: str
    key_b: str
    score: float
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError(f"merge {self.key_a}={self.key_b} has no evidence")


@dataclass(frozen=True)
class LlmOpinion:
    same_part: bool
    reason: str


@dataclass
class ReviewItem:
    key_a: str
    key_b: str
    score: float
    evidence: tuple[Evidence, ...]
    llm_opinion: LlmOpinion | None = None


@dataclass(frozen=True)
class NoteFact:
    note_id: str
    ref_key: str
    kind: str  # superseded_by | obsolete | equivalent_to
    target_key: str | None
    source: str  # rules | llm


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str  # high | medium | low
    subject: str
    message: str
    variants: tuple[str, ...] = field(default=())
