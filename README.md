# bom-reuse-pilot

**Question from the Valenciennes pilot:** which sub-assemblies are reused, or reusable, across
train variants, and where are the inconsistencies?

A small CLI reads a dirty multi-variant BOM export and free-text FR/EN notes, normalizes them into
a simple entity model, and writes one self-contained HTML report: a one-minute view for the
sponsor on top, the engineering detail (with the evidence behind every merge) below.

```bash
uv sync
uv run bomreuse generate             # synthetic export + planted defects + truth.json -> data/
uv run bomreuse report               # -> out/report.html, offline (copy: docs/sample_report.html)
uv run bomreuse eval                 # scores against the planted defects
uv run bomreuse report --llm none    # rules only, no model at all
uv run bomreuse report --llm claude-cli   # live model via `claude -p` (also: anthropic, ollama)
```

## What it does

| Stage | Module | How |
|---|---|---|
| Ingest | `ingest.py` | `;`-separated export; each row becomes a `BomLine` or a `Reject` with its reason |
| Normalize | `normalize.py` | references (`bog_01101` → `BOG-1101`), units (mm/cm/m, g/kg, PC/pce/EA), supplier legal suffixes, FR→EN domain glossary |
| Resolve duplicates | `resolve.py` | pairs within a reference family scored on reference edit distance, description similarity (after glossary), supplier, mass; **veto when dimensions differ** (M12x40 ≠ M12x50). ≥ 0.85 merge, 0.65–0.85 review queue, below: separate |
| Read notes | `notes.py` | facts `superseded_by` / `obsolete` / `equivalent_to`; regex rules or an LLM, same output type |
| Model opinions | `llm.py` | the LLM gives an opinion on each review-queue pair; **it never merges anything** |
| Analyze | `analyze.py` | reused = same sub-assembly in ≥ 2 variants; reusable = different sub-assemblies sharing ≥ 60% of their mass; inconsistencies = composition drift, supplier conflict, unit slip, superseded/obsolete parts still used, duplicate references, unreadable rows |
| Evaluate | `evaluate.py` | precision/recall against the defects the generator planted |
| Report | `report.py`, `templates/report.html` | one HTML file, data embedded, vanilla JS (filters, sorting, review decisions exported as JSON) |

## Measured on the planted dataset

5 variants, 13 sub-assemblies, 316 rows, 15 notes. Every defect was planted on purpose and is
listed in `data/truth.json`, so these are scores, not impressions.

| | Rules only | Rules + LLM (replayed cache) |
|---|---|---|
| Reference spellings collapsed | 112 raw spellings → 50 references | same |
| Duplicate references merged automatically | 5/6, no false merge | same (the LLM does not merge) |
| Review queue: 6 pairs, 1 real duplicate | engineer decides alone | model opinion right on 6/6 |
| Facts read from notes | 5/8, 1 false positive ("Not obsolete") | 8/8, no false positive |
| Planted inconsistencies found | 7/9 | 9/9 |
| Reusable families found | 4/4 | 4/4 |

Caveats, said plainly: the data, the defects and the tool were written in the same session, so
these numbers are a regression floor (`tests/test_pipeline.py`), not evidence of performance on
Alstom data. The LLM numbers are one sample: a first run of the same prompt judged the real
duplicate to be two different parts (see `JOURNAL.md`).

## Design choices

- **Deterministic core, LLM at the edges.** Merges are decided by an explainable score; the model
  reads free text and advises on ambiguous pairs. An engineer confirms. Reason: Thomas must be
  able to audit why two references were merged, and a wrong merge silently corrupts every count
  downstream.
- **Mass-weighted similarity for reusability.** Screws and washers are shared by everything;
  sharing the bogie frame is what matters.
- **Offline by construction.** Every model response is cached (`cache/llm_responses.json`,
  keyed by model + prompt hash) and committed. The default run replays it, with a test that
  disables sockets and subprocesses. The `ollama` backend is the on-premise answer.
- **Invariants enforced by code, not prose.** See `CLAUDE.md`: each invariant has a test in
  `tests/test_invariants.py`; the gate (`scripts/check.sh`: ruff, mypy --strict, pytest) runs in
  the pre-commit hook and in CI.

## Not done (3-week pilot backlog)

1. Connector to the real PLM/ERP export, and its real column semantics (with Thomas).
2. Review decisions fed back as confirmed merges / separations on the next run.
3. Glossary and thresholds calibrated on a sample labelled by Alstom engineers, not on our own data.
4. Cost model from Alstom's figures instead of the flat €60k assumption.
5. On-premise deployment: container, local model through Ollama, no outbound network.

## How this was built with AI

See [`JOURNAL.md`](JOURNAL.md): the design discussion, the prompts that mattered, what the AI got
wrong, and the human time spent.
