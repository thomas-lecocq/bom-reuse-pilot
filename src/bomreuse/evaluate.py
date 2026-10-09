"""Score the pipeline against the defects planted by the generator (`truth.json`).

This is what lets us say "the tool finds X of Y planted problems" instead of "it looks right".
"""

from __future__ import annotations

import json
from collections.abc import Set as AbstractSet
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel

from bomreuse.model import Finding, NoteFact, ReviewItem
from bomreuse.normalize import canonical_ref
from bomreuse.resolve import Resolution


class _TruthNote(BaseModel):
    note_id: str
    ref: str
    kind: str
    target: str | None


class _TruthFinding(BaseModel):
    kind: str
    subject: str


class Truth(BaseModel):
    raw_ref_to_true_ref: dict[str, str]
    reusable_pairs: list[tuple[str, str]]
    inconsistencies: list[_TruthFinding]
    notes: list[_TruthNote]


def load_truth(path: Path) -> Truth:
    return Truth.model_validate_json(path.read_text(encoding="utf-8"))


def _prf(
    found: AbstractSet[tuple[str, ...]], expected: AbstractSet[tuple[str, ...]]
) -> dict[str, object]:
    tp = len(found & expected)
    return {
        "expected": len(expected),
        "found": len(found),
        "correct": tp,
        "precision": round(tp / len(found), 3) if found else None,
        "recall": round(tp / len(expected), 3) if expected else None,
        "missed": sorted(" / ".join(t) for t in expected - found),
        "wrong": sorted(" / ".join(t) for t in found - expected),
    }


def _true_ref_of_key(res: Resolution, truth: Truth) -> dict[str, str]:
    out = {}
    for key, rec in res.records.items():
        refs = {
            truth.raw_ref_to_true_ref[r] for r in rec.raw_refs if r in truth.raw_ref_to_true_ref
        }
        if len(refs) == 1:
            out[key] = refs.pop()
    return out


def score_resolution(res: Resolution, truth: Truth) -> dict[str, object]:
    true_ref = _true_ref_of_key(res, truth)
    keys = sorted(true_ref)
    expected = {(a, b) for a, b in combinations(keys, 2) if true_ref[a] == true_ref[b]}
    found = {(a, b) for a, b in combinations(keys, 2) if res.cluster_of[a] == res.cluster_of[b]}
    raw_spellings = sum(len(r.raw_refs) for r in res.records.values())
    return {
        "raw_spellings": raw_spellings,
        "canonical_keys": len(res.records),
        "auto_merge": _prf(found, expected),
        "review": score_review(res.review, true_ref),
    }


def score_review(items: list[ReviewItem], true_ref: dict[str, str]) -> dict[str, object]:
    with_opinion = [i for i in items if i.llm_opinion is not None]
    agree = sum(
        1
        for i in with_opinion
        if i.llm_opinion is not None
        and i.llm_opinion.same_part == (true_ref.get(i.key_a) == true_ref.get(i.key_b))
    )
    true_dups = sum(1 for i in items if true_ref.get(i.key_a) == true_ref.get(i.key_b))
    return {
        "items": len(items),
        "true_duplicates": true_dups,
        "llm_opinions": len(with_opinion),
        "llm_correct": agree,
    }


def score_notes(facts: list[NoteFact], truth: Truth) -> dict[str, object]:
    expected = {
        (n.note_id, n.kind, canonical_ref(n.target) if n.target else "-")
        for n in truth.notes
        if n.kind != "none"
    }
    found = {(f.note_id, f.kind, f.target_key or "-") for f in facts}
    return _prf(found, expected)


def score_findings(
    findings: list[Finding], reusable: list[tuple[str, str]], truth: Truth
) -> dict[str, object]:
    expected = {(t.kind, canonical_ref(t.subject)) for t in truth.inconsistencies}
    found = {(f.kind, f.subject) for f in findings if f.kind in {k for k, _ in expected}}
    exp_pairs = {tuple(sorted(canonical_ref(r) for r in p)) for p in truth.reusable_pairs}
    found_pairs = {tuple(sorted(p)) for p in reusable}
    return {"inconsistencies": _prf(found, expected), "reusable": _prf(found_pairs, exp_pairs)}


def dump(score: dict[str, object]) -> str:
    return json.dumps(score, indent=2, sort_keys=True)
