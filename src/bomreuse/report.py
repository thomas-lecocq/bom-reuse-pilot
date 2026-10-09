"""Single self-contained HTML report: a sponsor view on top, an engineering view below.

The data is embedded as JSON and rendered by vanilla JS, so the file works offline, by email,
and stays byte-identical for identical input.
"""

from __future__ import annotations

import json
from pathlib import Path

from bomreuse.analyze import REDESIGN_COST_EUR, REUSABLE_FROM
from bomreuse.model import Evidence
from bomreuse.pipeline import RunResult
from bomreuse.resolve import AUTO_MERGE_AT, REVIEW_FROM

TEMPLATE = Path(__file__).parent / "templates" / "report.html"
BLOCKING = {
    "superseded_in_use",
    "obsolete_in_use",
    "supplier_conflict",
    "composition_drift",
    "mass_mismatch",
}


def _evidence(items: tuple[Evidence, ...]) -> list[dict[str, str]]:
    return [{"signal": e.signal, "detail": e.detail} for e in items]


def _headline(r: RunResult) -> dict[str, object]:
    uses = r.analysis.sub_assemblies
    reused = [u for u in uses if len(u.variants) > 1]
    blocking = [f for f in r.analysis.findings if f.kind in BLOCKING]
    variants = sorted({line.variant for line in r.ingested.lines})
    return {
        "variants": variants,
        "sub_assemblies": len(uses),
        "reused": len(reused),
        "reusable_pairs": len(r.analysis.reusable),
        "savings_eur": len(r.analysis.reusable) * REDESIGN_COST_EUR,
        "blocking": len(blocking),
        "rows": r.ingested.row_count,
        "rejects": len(r.ingested.rejects),
        "raw_spellings": sum(len(x.raw_refs) for x in r.resolution.records.values()),
        "components": len(set(r.resolution.cluster_of.values())),
    }


def build_payload(r: RunResult) -> dict[str, object]:
    names = {u.key: u.name for u in r.analysis.sub_assemblies}
    variants_of = {u.key: u.variants for u in r.analysis.sub_assemblies}
    return {
        "headline": _headline(r),
        "assumptions": {
            "redesign_cost_eur": REDESIGN_COST_EUR,
            "reusable_from": REUSABLE_FROM,
            "auto_merge_at": AUTO_MERGE_AT,
            "review_from": REVIEW_FROM,
        },
        "sub_assemblies": [
            {
                "key": u.key,
                "name": u.name,
                "variants": u.variants,
                "consistent": u.consistent,
                "parts": len(u.composition),
            }
            for u in r.analysis.sub_assemblies
        ],
        "reusable": [
            {
                "a": p.key_a,
                "b": p.key_b,
                "a_name": names[p.key_a],
                "b_name": names[p.key_b],
                "a_variants": variants_of[p.key_a],
                "b_variants": variants_of[p.key_b],
                "similarity": p.similarity,
                "only_a": p.only_a,
                "only_b": p.only_b,
            }
            for p in r.analysis.reusable
        ],
        "findings": [
            {
                "kind": f.kind,
                "severity": f.severity,
                "subject": f.subject,
                "message": f.message,
                "variants": f.variants,
            }
            for f in r.analysis.findings
        ],
        "merges": [
            {"a": m.key_a, "b": m.key_b, "score": m.score, "evidence": _evidence(m.evidence)}
            for m in r.resolution.merges
        ],
        "review": [
            {
                "a": i.key_a,
                "b": i.key_b,
                "score": i.score,
                "evidence": _evidence(i.evidence),
                "llm": None
                if i.llm_opinion is None
                else {"same_part": i.llm_opinion.same_part, "reason": i.llm_opinion.reason},
            }
            for i in r.resolution.review
        ],
        "facts": [
            {
                "note_id": f.note_id,
                "ref": f.ref_key,
                "kind": f.kind,
                "target": f.target_key,
                "source": f.source,
            }
            for f in r.facts
        ],
        "evaluation": r.evaluation,
        "llm": {"model": r.llm_model, "invalid_outputs": r.llm_invalid.count},
    }


def render_html(payload: dict[str, object]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data)


def write_report(r: RunResult, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(build_payload(r)), encoding="utf-8")
