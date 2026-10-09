"""Wire the stages together: ingest, resolve, (LLM annotations), analyze, evaluate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bomreuse.analyze import Analysis, analyze
from bomreuse.evaluate import load_truth, score_findings, score_notes, score_resolution
from bomreuse.ingest import Ingested, read_bom, read_decisions, read_notes
from bomreuse.llm import (
    AnthropicClient,
    CachedClient,
    ClaudeCliClient,
    InvalidOutputs,
    LlmClient,
    OllamaClient,
    annotate_review,
)
from bomreuse.model import NoteFact
from bomreuse.notes import LlmExtractor, RuleExtractor, extract_all
from bomreuse.resolve import Resolution, resolve

LLM_MODES = ("none", "replay", "claude-cli", "anthropic", "ollama")
REPLAY_MODEL_ID = ClaudeCliClient().model_id


@dataclass
class RunResult:
    ingested: Ingested
    resolution: Resolution
    facts: list[NoteFact]
    rule_facts: list[NoteFact]
    llm_facts: list[NoteFact] | None
    analysis: Analysis
    evaluation: dict[str, object] | None
    llm_model: str | None
    llm_invalid: InvalidOutputs


def make_client(mode: str, cache_path: Path) -> CachedClient | None:
    backends: dict[str, LlmClient] = {
        "claude-cli": ClaudeCliClient(),
        "anthropic": AnthropicClient(),
        "ollama": OllamaClient(),
    }
    if mode == "none":
        return None
    if mode == "replay":
        return CachedClient(cache_path, REPLAY_MODEL_ID)
    backend = backends[mode]
    return CachedClient(cache_path, backend.model_id, backend)


def run(data_dir: Path, llm_mode: str, cache_path: Path) -> RunResult:
    ingested = read_bom(data_dir / "bom_export.csv")
    notes = read_notes(data_dir / "notes.csv")
    resolution = resolve(ingested.lines, read_decisions(data_dir / "review_decisions.json"))
    client = make_client(llm_mode, cache_path)
    invalid = InvalidOutputs()
    rule_facts = extract_all(notes, RuleExtractor())
    llm_facts = None
    if client is not None:
        annotate_review(resolution.review, resolution.records, client, invalid)
        llm_facts = extract_all(notes, LlmExtractor(client, invalid))
    facts = llm_facts if llm_facts is not None else rule_facts
    analysis = analyze(ingested.lines, ingested.rejects, resolution, facts)
    evaluation = None
    truth_path = data_dir / "truth.json"
    if truth_path.exists():
        truth = load_truth(truth_path)
        pairs = [(p.key_a, p.key_b) for p in analysis.reusable]
        evaluation = {
            "resolution": score_resolution(resolution, truth),
            "notes_rules": score_notes(rule_facts, truth),
            "notes_llm": score_notes(llm_facts, truth) if llm_facts is not None else None,
            **score_findings(analysis.findings, pairs, truth),
        }
    model = client.model_id if client is not None else None
    return RunResult(
        ingested, resolution, facts, rule_facts, llm_facts, analysis, evaluation, model, invalid
    )
