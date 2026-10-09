"""One test per invariant listed in CLAUDE.md."""

import ast
import inspect
import socket
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from bomreuse import resolve as resolve_module
from bomreuse.ingest import Note, read_bom
from bomreuse.llm import InvalidOutputs, annotate_review
from bomreuse.model import BomLine, Evidence, MergeDecision, Quantity, ReviewItem, Unit
from bomreuse.notes import LlmExtractor
from bomreuse.pipeline import run
from bomreuse.report import build_payload, render_html
from bomreuse.resolve import ComponentRecord, decide

from .conftest import CACHE


def test_1_merge_requires_evidence() -> None:
    with pytest.raises(ValueError, match="no evidence"):
        MergeDecision("A-1", "A-2", 0.99, ())
    assert MergeDecision("A-1", "A-2", 0.99, (Evidence("reference", "x"),)).evidence


def test_2_llm_cannot_decide_a_merge() -> None:
    assert list(inspect.signature(decide).parameters) == ["pair"]
    tree = ast.parse(Path(inspect.getfile(resolve_module)).read_text())
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("llm" in name for name in imported)


class _GarbageClient:
    model_id = "garbage"

    def complete(self, prompt: str) -> str:
        return "I think they are probably the same, yes."


def test_3_invalid_llm_output_is_dropped_and_counted() -> None:
    invalid = InvalidOutputs()
    records = {k: ComponentRecord(k, descriptions={"x"}) for k in ("A-1", "A-2")}
    items = [ReviewItem("A-1", "A-2", 0.7, ())]
    annotate_review(items, records, _GarbageClient(), invalid)
    facts = LlmExtractor(_GarbageClient(), invalid).extract(Note("N1", "A-1", "obsolete"))
    assert items[0].llm_opinion is None
    assert facts == []
    assert invalid.count == 2


def test_4_every_row_is_kept_or_rejected(data_dir: Path) -> None:
    ingested = read_bom(data_dir / "bom_export.csv")
    assert ingested.rejects, "the generator plants bad rows"
    assert len(ingested.lines) + len(ingested.rejects) == ingested.row_count


def test_5_quantities_carry_a_canonical_unit(data_dir: Path) -> None:
    lines: list[BomLine] = read_bom(data_dir / "bom_export.csv").lines
    assert all(isinstance(line.quantity, Quantity) for line in lines)
    assert {line.quantity.unit for line in lines} <= set(Unit)


def test_6_demo_runs_offline(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("network or subprocess used during replay")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    result = run(data_dir, "replay", CACHE)
    assert result.llm_facts is not None
    assert all(item.llm_opinion is not None for item in result.resolution.review)


def test_7_report_is_deterministic(data_dir: Path) -> None:
    first = render_html(build_payload(run(data_dir, "replay", CACHE)))
    second = render_html(build_payload(run(data_dir, "replay", CACHE)))
    assert first == second


def test_2b_engineer_decisions_override_the_score(data_dir: Path) -> None:
    lines = read_bom(data_dir / "bom_export.csv").lines
    split = resolve_module.resolve(lines, {frozenset(("DOR-3014", "DOR-3104")): False})
    joined = resolve_module.resolve(lines, {frozenset(("BRK-4102", "BRK-4104")): True})
    assert split.cluster_of["DOR-3014"] != split.cluster_of["DOR-3104"]
    assert joined.cluster_of["BRK-4102"] == joined.cluster_of["BRK-4104"]
    merge = next(m for m in joined.merges if {m.key_a, m.key_b} == {"BRK-4102", "BRK-4104"})
    assert merge.evidence[-1].signal == "engineer decision"
