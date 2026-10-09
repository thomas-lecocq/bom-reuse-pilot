"""Entity resolution of component references: same physical part under different references?

Decisions come from a deterministic score only. The LLM, when used, annotates the review queue
afterwards (see `pipeline.py`); this module must not import `llm.py`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import combinations
from statistics import median

from rapidfuzz.distance import OSA
from rapidfuzz.fuzz import token_set_ratio

from bomreuse.model import BomLine, Evidence, MergeDecision, ReviewItem
from bomreuse.normalize import (
    dimension_tokens,
    english_tokens,
    ref_family,
    same_supplier,
    variant_markers,
)

AUTO_MERGE_AT = 0.85
REVIEW_FROM = 0.65


class Action(StrEnum):
    MERGE = "merge"
    REVIEW = "review"
    SEPARATE = "separate"


@dataclass
class ComponentRecord:
    key: str
    raw_refs: set[str] = field(default_factory=set)
    descriptions: set[str] = field(default_factory=set)
    suppliers: set[str] = field(default_factory=set)
    masses: list[float] = field(default_factory=list)
    variants: set[str] = field(default_factory=set)

    @property
    def mass_kg(self) -> float | None:
        return median(self.masses) if self.masses else None


@dataclass(frozen=True)
class PairScore:
    score: float
    evidence: tuple[Evidence, ...]
    vetoed: bool


@dataclass
class Resolution:
    records: dict[str, ComponentRecord]
    cluster_of: dict[str, str]
    merges: list[MergeDecision]
    review: list[ReviewItem]

    def members(self, cluster: str) -> list[str]:
        return sorted(k for k, c in self.cluster_of.items() if c == cluster)


def build_records(lines: list[BomLine]) -> dict[str, ComponentRecord]:
    records: dict[str, ComponentRecord] = {}
    for line in lines:
        if line.level != 2:
            continue
        rec = records.setdefault(line.key, ComponentRecord(line.key))
        rec.raw_refs.add(line.raw_ref)
        rec.descriptions.add(line.description)
        if line.supplier:
            rec.suppliers.add(line.supplier)
        if line.mass_kg is not None:
            rec.masses.append(line.mass_kg)
        rec.variants.add(line.variant)
    return records


def _description_similarity(a: ComponentRecord, b: ComponentRecord) -> tuple[float, str, str]:
    best = (0.0, "", "")
    for da in sorted(a.descriptions):
        for db in sorted(b.descriptions):
            sim = token_set_ratio(english_tokens(da), english_tokens(db)) / 100
            if sim > best[0]:
                best = (sim, da, db)
    return best


def _mass_agreement(a: ComponentRecord, b: ComponentRecord) -> float:
    ma, mb = a.mass_kg, b.mass_kg
    if ma is None or mb is None:
        return 0.5
    return 1.0 if abs(ma - mb) <= 0.05 * max(ma, mb) else 0.0


def _markers(rec: ComponentRecord) -> dict[str, frozenset[str]]:
    merged: dict[str, frozenset[str]] = {}
    for d in rec.descriptions:
        for category, values in variant_markers(d).items():
            merged[category] = merged.get(category, frozenset()) | values
    return merged


def _variant_veto(a: ComponentRecord, b: ComponentRecord) -> Evidence | None:
    """Different size, side, material or class: two parts, however similar the rest."""
    dims_a = frozenset().union(*(dimension_tokens(d) for d in a.descriptions))
    dims_b = frozenset().union(*(dimension_tokens(d) for d in b.descriptions))
    if dims_a and dims_b and not (dims_a <= dims_b or dims_b <= dims_a):
        return Evidence("dimension veto", f"{sorted(dims_a)} vs {sorted(dims_b)}")
    ma, mb = _markers(a), _markers(b)
    for category in sorted(ma.keys() & mb.keys()):
        if not ma[category] & mb[category]:
            detail = f"{sorted(ma[category])} vs {sorted(mb[category])}"
            return Evidence(f"{category} veto", detail)
    return None


def _reference_similarity(ka: str, kb: str) -> tuple[float, str]:
    if ref_family(ka) and ref_family(kb):
        return OSA.normalized_similarity(ka, kb), f"{ka} ~ {kb}"
    digits_a, digits_b = re.sub(r"\D", "", ka), re.sub(r"\D", "", kb)
    return OSA.normalized_similarity(digits_a, digits_b), f"{ka} ~ {kb} (prefix missing)"


def score_pair(a: ComponentRecord, b: ComponentRecord) -> PairScore:
    ref_sim, ref_detail = _reference_similarity(a.key, b.key)
    desc_sim, da, db = _description_similarity(a, b)
    supplier = 1.0 if any(same_supplier(x, y) for x in a.suppliers for y in b.suppliers) else 0.0
    mass = _mass_agreement(a, b)
    evidence = (
        Evidence("reference", f"{ref_detail}: {ref_sim:.2f}"),
        Evidence("description", f"{da!r} ~ {db!r}: {desc_sim:.2f}"),
        Evidence("supplier", "shared" if supplier else "different"),
        Evidence("mass", {1.0: "agrees", 0.0: "differs", 0.5: "unknown"}[mass]),
    )
    veto = _variant_veto(a, b)
    if veto is not None:
        return PairScore(0.0, (*evidence, veto), vetoed=True)
    score = 0.35 * ref_sim + 0.4 * desc_sim + 0.1 * supplier + 0.15 * mass
    return PairScore(round(score, 3), evidence, vetoed=False)


def decide(pair: PairScore) -> Action:
    if pair.vetoed or pair.score < REVIEW_FROM:
        return Action.SEPARATE
    return Action.MERGE if pair.score >= AUTO_MERGE_AT else Action.REVIEW


def _candidate_pairs(by_family: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Pairs within a reference family; a reference that lost its prefix meets every family."""
    pairs = [p for keys in by_family.values() for p in combinations(keys, 2)]
    bare = by_family.get("", [])
    others = sorted(k for family, keys in by_family.items() if family for k in keys)
    pairs += [(b, k) for b in bare for k in others]
    return pairs


def _find(parent: dict[str, str], key: str) -> str:
    while parent[key] != key:
        parent[key] = parent[parent[key]]
        key = parent[key]
    return key


EngineerDecisions = dict[frozenset[str], bool]  # pair of keys -> same part?


def resolve(lines: list[BomLine], decisions: EngineerDecisions | None = None) -> Resolution:
    """Engineer decisions override the score; a model opinion never reaches this function."""
    decisions = decisions or {}
    records = build_records(lines)
    by_family: dict[str, list[str]] = defaultdict(list)
    for key in sorted(records):
        by_family[ref_family(key)].append(key)
    parent = {k: k for k in records}
    merges: list[MergeDecision] = []
    review: list[ReviewItem] = []
    for ka, kb in _candidate_pairs(by_family):
        pair = score_pair(records[ka], records[kb])
        action = decide(pair)
        engineer = decisions.get(frozenset((ka, kb)))
        if engineer is not None:
            verdict = "same part" if engineer else "different parts"
            note = Evidence("engineer decision", f"{verdict}, from the review queue")
            pair = PairScore(pair.score, (*pair.evidence, note), pair.vetoed)
            action = Action.MERGE if engineer else Action.SEPARATE
        if action is Action.MERGE:
            merges.append(MergeDecision(ka, kb, pair.score, pair.evidence))
            parent[_find(parent, kb)] = _find(parent, ka)
        elif action is Action.REVIEW:
            review.append(ReviewItem(ka, kb, pair.score, pair.evidence))
    return Resolution(records, _name_clusters(records, parent), merges, review)


def _name_clusters(records: dict[str, ComponentRecord], parent: dict[str, str]) -> dict[str, str]:
    """A cluster is named after its most widely used reference, not after a typo."""
    groups: dict[str, list[str]] = defaultdict(list)
    for key in records:
        groups[_find(parent, key)].append(key)
    cluster_of = {}
    for members in groups.values():
        name = max(members, key=lambda k: (len(records[k].variants), k))
        cluster_of.update(dict.fromkeys(members, name))
    return cluster_of
