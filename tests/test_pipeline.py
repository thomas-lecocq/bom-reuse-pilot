"""Regression floor on the planted dataset: these numbers may only go up."""

from pathlib import Path

from bomreuse.ingest import read_bom
from bomreuse.pipeline import run
from bomreuse.resolve import Action, build_records, decide, score_pair

from .conftest import CACHE


def test_dimension_decoys_are_never_merged(data_dir: Path) -> None:
    records = build_records(read_bom(data_dir / "bom_export.csv").lines)
    for a, b in [("FIX1240", "FIX1250"), ("ELE4410", "ELE4416"), ("FIX1240", "FIX1640")]:
        assert decide(score_pair(records[a], records[b])) is Action.SEPARATE


def test_rules_only_floor(data_dir: Path) -> None:
    evaluation = run(data_dir, "none", CACHE).evaluation
    assert evaluation is not None
    auto = evaluation["resolution"]["auto_merge"]  # type: ignore[index]
    assert auto["precision"] == 1.0
    assert auto["recall"] >= 0.8
    assert evaluation["reusable"]["recall"] == 1.0  # type: ignore[index]


def test_replayed_llm_reads_notes_better_than_rules(data_dir: Path) -> None:
    evaluation = run(data_dir, "replay", CACHE).evaluation
    assert evaluation is not None
    rules = evaluation["notes_rules"]["recall"]  # type: ignore[index]
    llm = evaluation["notes_llm"]["recall"]  # type: ignore[index]
    assert llm > rules


def test_repeated_line_is_read_like_the_other_variants() -> None:
    from bomreuse.analyze import _resolve_repeats

    modal = {"P1": 8.0}
    split = _resolve_repeats({"V1": {"P1": 8.0}}, {"V1": {"P1": 4.0}}, modal)
    exported_twice = _resolve_repeats({"V1": {"P1": 2.0}}, {"V1": {"P1": 1.0}}, {"P1": 1.0})
    assert split == {"V1": {"P1": 8.0}}
    assert exported_twice == {"V1": {"P1": 1.0}}
