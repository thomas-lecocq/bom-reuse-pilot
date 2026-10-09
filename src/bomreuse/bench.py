"""Compare models on the two LLM tasks over repeated runs, bypassing the cache.

One run gives one sample; the same prompt can flip its verdict between runs, so the report
gives min / mean / max per model.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from bomreuse.evaluate import load_truth, score_notes, score_review, true_ref_of_key
from bomreuse.ingest import read_bom, read_notes
from bomreuse.llm import ClaudeCliClient, InvalidOutputs, PromptRecorder, annotate_review
from bomreuse.notes import LlmExtractor, extract_all
from bomreuse.resolve import resolve


@dataclass
class _Answers:
    answers: dict[str, str]
    model_id: str = "answers"

    def complete(self, prompt: str) -> str:
        return self.answers[prompt]


@dataclass(frozen=True)
class RunScore:
    review_correct: int
    review_total: int
    notes_precision: float
    notes_recall: float
    notes_wrong: list[str]
    notes_missed: list[str]
    invalid: int


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _strings(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _one_run(data_dir: Path, model: str, workers: int) -> RunScore:
    ingested = read_bom(data_dir / "bom_export.csv")
    notes = read_notes(data_dir / "notes.csv")
    truth = load_truth(data_dir / "truth.json")
    recorder = PromptRecorder()
    dry = resolve(ingested.lines)
    annotate_review(dry.review, dry.records, recorder, InvalidOutputs())
    extract_all(notes, LlmExtractor(recorder, InvalidOutputs()))
    client = ClaudeCliClient(model)
    with ThreadPoolExecutor(workers) as pool:
        answers = dict(
            zip(recorder.prompts, pool.map(client.complete, recorder.prompts), strict=True)
        )
    replay = _Answers(answers)
    invalid = InvalidOutputs()
    resolution = resolve(ingested.lines)
    annotate_review(resolution.review, resolution.records, replay, invalid)
    facts = extract_all(notes, LlmExtractor(replay, invalid))
    review = score_review(resolution.review, true_ref_of_key(resolution, truth))
    note_score = score_notes(facts, truth)
    return RunScore(
        int(_num(review["llm_correct"])),
        int(_num(review["items"])),
        _num(note_score["precision"]),
        _num(note_score["recall"]),
        _strings(note_score["wrong"]),
        _strings(note_score["missed"]),
        invalid.count,
    )


def _spread(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 3),
        "mean": round(mean(values), 3),
        "max": round(max(values), 3),
    }


def _summary(runs: list[RunScore]) -> dict[str, object]:
    return {
        "runs": len(runs),
        "review_accuracy": _spread([r.review_correct / max(r.review_total, 1) for r in runs]),
        "notes_precision": _spread([r.notes_precision for r in runs]),
        "notes_recall": _spread([r.notes_recall for r in runs]),
        "invalid_outputs": sum(r.invalid for r in runs),
    }


def bench(data_dir: Path, models: list[str], runs: int, workers: int = 6) -> dict[str, object]:
    result: dict[str, object] = {"dataset": str(data_dir)}
    for model in models:
        samples = [_one_run(data_dir, model, workers) for _ in range(runs)]
        result[model] = {"summary": _summary(samples), "samples": [asdict(x) for x in samples]}
    return result


def write_bench(data_dir: Path, models: list[str], runs: int, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bench(data_dir, models, runs), indent=2) + "\n", encoding="utf-8")
