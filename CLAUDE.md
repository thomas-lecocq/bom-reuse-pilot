# bom-reuse-pilot

Pilot tool: which sub-assemblies are reused or reusable across train variants, and where the BOM
is inconsistent. Input: a dirty multi-variant BOM CSV plus free-text FR/EN notes.

Tooling: uv, Python 3.13, ruff (line 100, C901 max 10), mypy --strict, pytest.
Gate: `scripts/check.sh` (ruff + format check + mypy + pytest). It runs in the git pre-commit hook
(`git config core.hooksPath .githooks`) and in CI. Never `--no-verify`.

## Invariants (each one is enforced by code and checked by a test)

1. No merge without evidence: a `MergeDecision` with empty evidence cannot be built.
2. The LLM never decides a merge: `resolve.decide()` takes only a deterministic score, and
   `resolve.py` does not import `llm.py` (architecture test). LLM opinions annotate the review queue.
3. LLM output is parsed by a pydantic schema at the boundary; invalid output is dropped and counted,
   never cast.
4. Row conservation: every input row becomes a normalized line or a reported reject, none silently lost.
5. Quantities carry a canonical unit (`Unit` enum); analysis never sees a raw unit string.
6. The demo runs offline: the full pipeline passes with sockets disabled, using the committed LLM cache.
7. Deterministic output: same input and cache give a byte-identical report.

## Language
Code, docs, report and commit messages in English (the client audience is English-speaking).

## Needs Tom's approval
New runtime dependency; any paid API call; changing the merge thresholds in `resolve.py`.
