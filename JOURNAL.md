# How this was built with AI

One Claude Code session (Claude Opus 5.5) on 2026-10-09, from about 9:30 to 12:00, plus one
separate agent for the blind datasets. Tom made the design decisions in discussion before any
code and steered the second half; Claude Code wrote the code, the generators' prompts, the tests
and the documents, and ran them. The commit history follows the build order; the tags
`pre-holdout` and `post-holdout-fixes` mark the two measurement points.

## Setup used

- **Global instructions** (`~/.claude/CLAUDE.md`, not in this repo): uv, ruff/mypy --strict/pytest
  clean before every commit, type hints everywhere, "design first in discussion, then a project
  CLAUDE.md with numbered invariants that the code enforces and the tests check, before the
  first module".
- **Project `CLAUDE.md`**, written before the first module: 7 invariants, each with a test in
  `tests/test_invariants.py`.
- **One quality gate**, `scripts/check.sh`, run by the git pre-commit hook (`.githooks/`), by CI
  (`.github/workflows/ci.yml`) and by a Claude Code Stop hook (`.claude/settings.json`) for the
  next sessions opened in this repo (this session was started from the parent folder, so the
  Stop hook did not apply to it; the pre-commit hook did, and refused two commits).
- **`claude -p` headless** as the LLM backend, because no API key was available; the Anthropic
  API and Ollama adapters sit behind the same `LlmClient` protocol.

## The prompts that shaped it (Tom → Claude, translated from French)

1. The case brief, pasted as-is.
2. *"For normalization, how do you plan to do it? Regex only? LLM? An embedding model only?"*
   Adopted: regex canonicalization, string similarity, a small FR/EN glossary, a veto on
   variant attributes; the LLM only on the grey zone, as advice. No embeddings for now.
3. *"The most important rules should not be guaranteed by prose but structurally."* This turned
   the invariants into types (`MergeDecision` refuses empty evidence, `decide()` only takes a
   deterministic score), an architecture test (`resolve.py` does not import `llm.py`), and the
   gate in pre-commit and CI.
4. *"Data and tool were written in the same session; it would have been better with two agents
   that do not share context."* This led to the blind-dataset protocol below.
5. *"If Sonnet is not at 100%, test Opus too; comparing them can be a result."* This led to
   `bomreuse bench` and the switch of the default live model to Opus.

## Blind-dataset protocol

1. A separate agent, told never to open this repository, wrote `blind/generate.py` from the CSV
   contract and the list of defect kinds only, and generated seeds 1 and 2.
2. **Seed 1, first contact, before any fix:** the ingestion crashed (rows with extra separators).
   Once that was fixed, rules only: auto-merge precision 27%, inconsistencies precision 33%,
   reusable precision 30% (`docs/blind_seed1_first_contact_rules.json`).
3. Failures on seed 1 were read, and fixed by family: separator-blind keys, supplier
   abbreviations and acronyms, a veto on size/side/material/class, references that lost their
   prefix, notes without a reference column, `withdrawn` notes in date order.
   `blind/DEFECTS.md` and the generator code were not read until all scoring was done.
4. **Seed 2, held out, scored once** at tag `pre-holdout`, with no change afterwards to that
   result (`docs/holdout_seed2_*.json`): with Opus, inconsistencies recall 100%, precision 88%;
   reusable 2/3; 10/11 duplicates merged automatically, the 11th in the review queue with a
   correct model opinion.
5. Diagnosis of seed 2 showed two more generic gaps (repeated lines, interchangeable parts), fixed
   at tag `post-holdout-fixes`. Seed 2 cannot measure those fixes, so a **fresh seed 3** was
   generated and scored once: 100% on every measure with Opus (`docs/fresh_seed3_*.json`).

## What the AI got wrong, and how it was caught

| Error | Caught by |
|---|---|
| Generator formatted sub-assembly references as `SA_0BOG-110`: fake duplicate sub-assemblies | reading the analysis output |
| Dimension regex split `35mm2` into `35` and `2` | calibration run |
| Supplier suffix `AB` missing, then `ZF` vs `ZF Friedrichshafen` | reading findings; feeding a review decision back |
| Equivalence regex case-sensitive | rules-vs-truth score |
| Clusters named after the typo'd reference | reading the findings |
| `DictWriter` reused for `csv.writer`; protocol attribute vs property | mypy, in the pre-commit hook (commit refused) |
| Crash on rows with more fields than columns | blind seed 1, first contact |
| Identity keys split on letter/digit boundaries (`SECAB-624` ≠ `SE-CAB-624`) | blind seed 1 |
| Note-reference regex limited to 5 digits | blind seed 1 |
| JSON extraction picked a nested object instead of the last top-level one, so the model read 0 notes | the seed 1 score dropping to 0/15; a regression test now pins it |

## The LLM is not deterministic, so it does not decide

On the planted dataset, the one real duplicate in the review queue (`BOG-1130` vs `BOG-1310`)
got opposite verdicts from Sonnet 5.5 in two runs with the same prompt: "different parts, the
transposed digits more likely indicate distinct variants" (`docs/llm_run1_responses.json`), then
"same part, the transposed digits suggest a data-entry error". Over 10 runs Sonnet was wrong on
one pair in 4 runs; Opus 5.5 was right in all 10 (`docs/llm_bench_v1.json`). The prompt was not
tuned to pass that case. The model reads and advises, the deterministic score and an engineer
decide, and the cache makes every run reproducible.

## Limits I know about

- All data is synthetic; seeds 2 and 3 come from the generator whose seed 1 shaped the fixes.
- Thresholds (0.85 / 0.65 / 0.6) and the €60k redesign cost were set by hand.
- Two levels only (variant → sub-assembly → part); real PLM trees are deeper.

## Time

- Tom: about 30 minutes of design discussion before the build, then steering and reviews.
- Claude Code: about 2.5 hours of wall-clock build, including the blind-dataset agent (~20 min,
  in parallel) and live model calls.
