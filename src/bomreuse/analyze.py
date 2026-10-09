"""Answer the pilot question on resolved data: reused, reusable, inconsistent."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from statistics import median

from bomreuse.model import BomLine, Finding, NoteFact, Reject
from bomreuse.normalize import supplier_groups
from bomreuse.resolve import Resolution

REUSABLE_FROM = 0.6
# Invented pilot assumption, shown in the report: engineering + qualification cost of designing
# a sub-assembly again for a tender instead of reusing an existing one.
REDESIGN_COST_EUR = 60_000

Composition = dict[str, float]


@dataclass(frozen=True)
class SubAssemblyUse:
    key: str
    name: str
    variants: tuple[str, ...]
    composition: Composition
    consistent: bool


@dataclass(frozen=True)
class ReusablePair:
    key_a: str
    key_b: str
    similarity: float
    only_a: tuple[str, ...]
    only_b: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    sub_assemblies: list[SubAssemblyUse]
    reusable: list[ReusablePair]
    findings: list[Finding]
    cluster_mass: dict[str, float]
    compositions: dict[str, dict[str, Composition]]


def _compositions(lines: list[BomLine], res: Resolution) -> dict[str, dict[str, Composition]]:
    """sub-assembly key -> variant -> cluster -> quantity."""
    out: dict[str, dict[str, Composition]] = defaultdict(lambda: defaultdict(dict))
    for line in lines:
        if line.level == 2:
            comp = out[line.parent_key][line.variant]
            cluster = res.cluster_of[line.key]
            comp[cluster] = comp.get(cluster, 0.0) + line.quantity.value
    return out


def _modal(by_variant: dict[str, Composition]) -> Composition:
    counts = Counter(tuple(sorted(c.items())) for c in by_variant.values())
    return dict(counts.most_common(1)[0][0])


def weighted_similarity(a: Composition, b: Composition, mass: dict[str, float]) -> float:
    """Share of mass in common (weighted Jaccard): standard hardware barely counts."""
    shared = total = 0.0
    for cluster in a.keys() | b.keys():
        wa = a.get(cluster, 0.0) * mass.get(cluster, 1.0)
        wb = b.get(cluster, 0.0) * mass.get(cluster, 1.0)
        shared += min(wa, wb)
        total += max(wa, wb)
    return shared / total if total else 0.0


def _drift(key: str, by_variant: dict[str, Composition], modal: Composition) -> Finding:
    odd = sorted(v for v, c in by_variant.items() if c != modal)
    diffs = []
    for v in odd:
        changed = sorted(
            k for k in by_variant[v].keys() | modal.keys() if by_variant[v].get(k) != modal.get(k)
        )
        details = ", ".join(
            f"{k} {modal.get(k, 0):g}->{by_variant[v].get(k, 0):g}" for k in changed
        )
        diffs.append(f"{v}: {details}")
    return Finding(
        "composition_drift",
        "high",
        key,
        "Same sub-assembly reference, different content: " + "; ".join(diffs),
        tuple(odd),
    )


def _sub_assemblies(
    lines: list[BomLine], res: Resolution
) -> tuple[list[SubAssemblyUse], list[Finding]]:
    names = {line.key: line.description for line in lines if line.level == 1}
    uses: list[SubAssemblyUse] = []
    findings: list[Finding] = []
    for key, by_variant in sorted(_compositions(lines, res).items()):
        modal = _modal(by_variant)
        consistent = all(c == modal for c in by_variant.values())
        if not consistent:
            findings.append(_drift(key, by_variant, modal))
        variants = tuple(sorted(by_variant))
        uses.append(SubAssemblyUse(key, names.get(key, key), variants, modal, consistent))
    return uses, findings


def _reusable(uses: list[SubAssemblyUse], mass: dict[str, float]) -> list[ReusablePair]:
    pairs = []
    for a, b in combinations(uses, 2):
        sim = weighted_similarity(a.composition, b.composition, mass)
        if sim >= REUSABLE_FROM:
            only_a = tuple(sorted(a.composition.keys() - b.composition.keys()))
            only_b = tuple(sorted(b.composition.keys() - a.composition.keys()))
            pairs.append(ReusablePair(a.key, b.key, round(sim, 3), only_a, only_b))
    return sorted(pairs, key=lambda p: -p.similarity)


def _cluster_findings(lines: list[BomLine], res: Resolution) -> list[Finding]:
    by_cluster: dict[str, list[BomLine]] = defaultdict(list)
    for line in lines:
        if line.level == 2:
            by_cluster[res.cluster_of[line.key]].append(line)
    findings = []
    for cluster, group in sorted(by_cluster.items()):
        variants = tuple(sorted({ln.variant for ln in group}))
        members = res.members(cluster)
        if len(members) > 1:
            msg = f"One part recorded under {len(members)} references: {', '.join(members)}"
            findings.append(Finding("duplicate_reference", "medium", cluster, msg, variants))
        suppliers = Counter(ln.supplier_raw for ln in group if ln.supplier)
        if supplier_groups({ln.supplier for ln in group if ln.supplier}) > 1:
            msg = "Conflicting suppliers: " + ", ".join(f"{s} ({n})" for s, n in suppliers.items())
            findings.append(Finding("supplier_conflict", "high", cluster, msg, variants))
        masses = [ln.mass_kg for ln in group if ln.mass_kg is not None]
        if masses and max(masses) > 1.5 * min(masses):
            odd = sorted({ln.variant for ln in group if ln.mass_kg == min(masses)})
            msg = f"Unit mass ranges {min(masses):g} to {max(masses):g} kg (unit slip?)"
            findings.append(Finding("mass_mismatch", "high", cluster, msg, tuple(odd)))
    return findings


def current_facts(facts: list[NoteFact]) -> list[NoteFact]:
    """Facts still standing: per reference, in note date order, `withdrawn` cancels the
    superseded/obsolete statements made before it."""
    by_ref: dict[str, list[NoteFact]] = defaultdict(list)
    for fact in sorted(facts, key=lambda f: (f.date, f.note_id)):
        if fact.kind == "withdrawn":
            by_ref[fact.ref_key] = [f for f in by_ref[fact.ref_key] if f.kind == "equivalent_to"]
        else:
            by_ref[fact.ref_key].append(fact)
    return [f for ref in sorted(by_ref) for f in by_ref[ref]]


def _note_findings(facts: list[NoteFact], lines: list[BomLine], res: Resolution) -> list[Finding]:
    used_in: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if line.level == 2:
            used_in[res.cluster_of[line.key]].add(line.variant)
    findings: dict[tuple[str, str], Finding] = {}
    for fact in current_facts(facts):
        cluster = res.cluster_of.get(fact.ref_key)
        if cluster is None or fact.kind not in {"superseded_by", "obsolete"}:
            continue
        variants = tuple(sorted(used_in[cluster]))
        if fact.kind == "superseded_by":
            kind, msg = (
                "superseded_in_use",
                f"Superseded by {fact.target_key} (note {fact.note_id})",
            )
        else:
            kind, msg = "obsolete_in_use", f"Declared obsolete (note {fact.note_id})"
        findings.setdefault(
            (kind, cluster), Finding(kind, "high", cluster, msg + " but still used", variants)
        )
    return list(findings.values())


def _reject_findings(rejects: list[Reject]) -> list[Finding]:
    return [
        Finding("unparsable_row", "low", f"row {r.row_number}", r.reason, (r.raw["variante"],))
        for r in rejects
    ]


def analyze(
    lines: list[BomLine], rejects: list[Reject], res: Resolution, facts: list[NoteFact]
) -> Analysis:
    masses: dict[str, list[float]] = defaultdict(list)
    for key, rec in res.records.items():
        masses[res.cluster_of[key]].extend(rec.masses)
    cluster_mass = {c: median(m) for c, m in masses.items() if m}
    uses, drift = _sub_assemblies(lines, res)
    findings = (
        drift
        + _cluster_findings(lines, res)
        + _note_findings(facts, lines, res)
        + _reject_findings(rejects)
    )
    compositions = {k: dict(v) for k, v in _compositions(lines, res).items()}
    return Analysis(uses, _reusable(uses, cluster_mass), findings, cluster_mass, compositions)
