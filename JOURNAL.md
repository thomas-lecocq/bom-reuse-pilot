# How this was built with AI

One Claude Code session (Claude Opus 5.5), on 2026-10-09, morning. Tom made the design decisions
in a discussion before any code; Claude Code wrote the code, the data generator and the tests,
and ran them. The commit history follows the build order.

## Setup used

- **Global instructions** (`~/.claude/CLAUDE.md`, not in this repo): uv, ruff/mypy --strict/pytest
  clean before every commit, type hints everywhere, "design first in discussion, then a project
  CLAUDE.md with numbered invariants that the code enforces and the tests check, before the
  first module".
- **Project `CLAUDE.md`**, written before the first module: 7 invariants, each with a test in
  `tests/test_invariants.py`.
- **One quality gate**, `scripts/check.sh`, run by the git pre-commit hook (`.githooks/`), by CI
  (`.github/workflows/ci.yml`) and by a Claude Code Stop hook (`.claude/settings.json`) for the
  next sessions opened in this repo. It blocked two commits in this session (mypy errors below).
- **`claude -p` headless** as the LLM backend, because no API key was available; the Anthropic
  API and Ollama adapters exist behind the same `LlmClient` protocol.

## The prompts that shaped it (Tom → Claude, translated from French)

1. The case brief, pasted as-is.
2. *"For normalization, how do you plan to do it? Regex only? LLM? An embedding model only?"*
   Answer adopted: regex canonicalization, string similarity with rapidfuzz, a small FR/EN
   glossary, a dimension veto; the LLM only on the grey zone, as advice. No embeddings: torch and
   a model download for a gain the glossary already captures on this data; a week-2 option.
3. *"The most important rules should not be guaranteed by prose but structurally, if possible."*
   This turned the CLAUDE.md invariants into types (`MergeDecision` refuses empty evidence,
   `decide()` only takes a deterministic score), an architecture test (`resolve.py` does not
   import `llm.py`), and the gate in pre-commit and CI.
4. *"Yes to everything"* on the synthetic data with planted ground truth, so every claim in the
   report is a measurement.

## What the AI got wrong, and how it was caught

| Error | Caught by |
|---|---|
| Sub-assembly references formatted as `SA_0BOG-110` by the generator: fake duplicate sub-assemblies | reading the analysis output (`SA0BOG110` next to `SABOG110`) |
| Dimension regex split `35mm2` into `35` and `2`: the 35 mm² and 16 mm² cables escaped the veto | calibration run, the pair landed in the review queue |
| Supplier suffix `AB` missing: `TRELLEBORG AB` vs `Trelleborg` reported as a supplier conflict | reading the findings |
| Equivalence regex case-sensitive: `Equivalent to …` missed | the rules-vs-truth score |
| Clusters named after the typo'd reference (`DOR-3014` instead of `DOR-3104`) | reading the findings |
| `DictWriter` variable reused for `csv.writer`; protocol attribute vs property | mypy, in the pre-commit hook (commit refused) |

## The LLM is not deterministic, so it does not decide

The review-queue prompt was run twice (the cache was regenerated after a change of key format).
On the one real duplicate in the queue (`BOG-1130` vs `BOG-1310`, a transposed-digit typo with a
French description and a different supplier spelling):

- run 1 (kept in `docs/llm_run1_responses.json`): **different parts**, "the references differ by
  transposed digits, which more likely indicates distinct variants";
- run 2 (the committed cache): **same part**, "the references differ only by a transposed digit
  pair, which suggests a data-entry error".

Same evidence, opposite verdicts. The prompt was not tuned to pass this case; that would be
fitting the test. This is the argument for the design: the model reads and advises, the
deterministic score and an engineer decide, and the cache makes the demo reproducible.

## Limits I know about

- Data, defects and tool were written in the same session: the scores are a regression floor,
  not a measure of performance on Alstom data.
- Thresholds (0.85 / 0.65 / 0.6) and the €60k redesign cost were set by hand.
- Two levels only (variant → sub-assembly → part); real PLM trees are deeper.

## Time

- Tom: design discussion and reviews, about 30 minutes before the build, plus review of the report.
- Claude Code: build, generator, tests and documentation in the same session.
