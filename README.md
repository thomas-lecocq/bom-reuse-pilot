# bom-reuse-pilot

**Question from the Valenciennes pilot:** which sub-assemblies are reused, or reusable, across
train variants, and where are the inconsistencies?

A small CLI reads a dirty multi-variant BOM export and free-text FR/EN notes, normalizes them into
a simple entity model, and writes one self-contained HTML report: a one-minute view for the
sponsor on top, the engineering detail (with the evidence behind every merge) below.

```bash
uv sync
uv run bomreuse generate             # small synthetic export + planted defects -> data/
uv run bomreuse report               # -> out/report.html, offline (copy: docs/sample_report_small.html)
uv run bomreuse eval                 # scores against the planted defects
uv run bomreuse report --llm none    # rules only, no model at all
uv run bomreuse report --llm claude-cli   # live model via `claude -p` (also: anthropic, ollama)
uv run bomreuse report --data blind/seed3 --cache blind/cache_seed3_opus.json   # docs/sample_report.html
uv run bomreuse bench --data blind/seed3 --models sonnet,opus --runs 3          # model comparison
docker build -t bomreuse . && docker run --rm --network none -v "$PWD/out:/out" bomreuse
```

Engineers answer the review queue in the report and export `review_decisions.json`; dropped into
the data folder, it is applied on the next run as confirmed merges or confirmed separations.

## What it does

| Stage | Module | How |
|---|---|---|
| Ingest | `ingest.py` | `;`-separated export; each row becomes a `BomLine` or a `Reject` with its reason (unreadable quantity, unknown unit, extra separators...) |
| Normalize | `normalize.py` | identity keys blind to separators (`SE-CAB-624` = `SECAB 0624`); units (mm/cm/m, g/kg, PC/pce/EA); supplier spellings (abbreviations, acronyms, legal suffixes); FR→EN domain glossary |
| Resolve duplicates | `resolve.py` | pairs within a reference family (or any family if the prefix was lost) scored on reference edit distance, description similarity, supplier, mass. **Veto** when size, side, material or class differ (M8x25 zinc ≠ M8x25 stainless, left ≠ right). ≥ 0.85 merge, 0.65–0.85 review queue |
| Read notes | `notes.py` | facts `superseded_by` / `obsolete` / `equivalent_to` / `withdrawn`, by regex rules or an LLM (same output type); applied in note-date order |
| Model opinions | `llm.py` | the LLM gives an opinion on each review-queue pair; **it never merges anything** |
| Analyze | `analyze.py` | reused = same sub-assembly in ≥ 2 variants; reusable = different sub-assemblies sharing ≥ 60% of their mass (interchangeable parts count as one); inconsistencies = composition drift, supplier conflict, unit slip, superseded/obsolete parts still used, duplicate references, repeated lines, unreadable rows |
| Evaluate | `evaluate.py` | precision/recall against planted defects |
| Report | `report.py`, `templates/report.html` | one HTML file, data embedded, vanilla JS: drill-down per sub-assembly, family comparison, review decisions, CSV export |

## Measured

Every dataset has a ground truth, so these are scores, not impressions. Full outputs in `docs/`.

**Blind datasets.** A separate agent that never saw this code wrote a generator for dirtier
exports (8 variants, ~1,850 rows, ~175 parts, ~60 FR/EN notes): `blind/generate.py`, its
`DEFECTS.md` read only after scoring.

| Inconsistencies found (precision / recall) | Rules only | Rules + Opus 5.5 |
|---|---|---|
| Seed 1, first contact, before any fix | 33% / 76% | — |
| Seed 1 after fixing what it revealed (no longer a test) | 86% / 90% | 100% / 100% |
| Seed 2, held out, scored once (tag `pre-holdout`) | 67% / 93% | 88% / 100% |
| Seed 3, fresh, after the post-holdout fixes (tag `post-holdout-fixes`) | 74% / 85% | **100% / 100%** |

On seed 3: duplicate references 13/13 merged with no false merge, reusable families 5/5, note
facts 21/21 with the model (9/21 with rules), model opinion right on 8/8 review pairs.

**Sonnet 5.5 vs Opus 5.5** (`bomreuse bench`, live calls, no cache):

| | Sonnet 5.5 | Opus 5.5 |
|---|---|---|
| Planted dataset, 10 runs: review queue accuracy | 93% mean (5/6 in 4 runs of 10) | 100% in 10 runs |
| Planted dataset, 10 runs: note facts | 100% | 100% |
| Blind seed 3, 3 runs | see `docs/llm_bench_seed3.json` | |

The same prompt can flip its verdict from one run to the next (`JOURNAL.md`); hence the cache
for reproducible runs, and the engineer as the only one who decides on an ambiguous pair.

**What these numbers do not say.** All datasets are synthetic. The blind generator is
independent of the tool, but seeds 2 and 3 come from the same generator as seed 1, whose defect
families shaped the fixes: seed 3 measures generalization within that generator, not on Alstom
data. The thresholds and the €60k redesign cost are set by hand.

## Design choices

- **Deterministic core, LLM at the edges.** Merges are decided by an explainable score; the model
  reads free text and advises on ambiguous pairs. An engineer confirms. A wrong merge silently
  corrupts every count downstream, so it must be auditable.
- **Mass-weighted similarity for reusability.** Screws and washers are shared by everything;
  sharing the bogie frame is what matters.
- **Ambiguity resolved against the other variants.** A part listed twice under one parent can be
  a split quantity or a line exported twice; the tool keeps the reading the other variants agree
  with and reports the line.
- **Offline by construction.** Every model response is cached, keyed by model + prompt hash, and
  committed. The default run replays it, with a test that disables sockets and subprocesses. The
  container runs with `--network none`; `docker-compose.yml` puts Ollama on an internal network.
- **Invariants enforced by code, not prose.** See `CLAUDE.md`: each invariant has a test in
  `tests/test_invariants.py`; the gate (`scripts/check.sh`: ruff, mypy --strict, pytest) runs in
  the pre-commit hook and in CI.

## Not done (3-week pilot backlog)

1. Connector to the real PLM/ERP export and its column semantics; deeper trees than 2 levels.
2. Thresholds, glossary and markers calibrated on pairs labelled by Alstom engineers.
3. Cost model from Alstom's figures instead of the flat €60k assumption.
4. On-premise model choice measured with `bomreuse bench` against those labels.
5. Multi-user review (today: one exported JSON file).

## How this was built with AI

See [`JOURNAL.md`](JOURNAL.md): the design discussion, the prompts that mattered, what the AI got
wrong, the blind-dataset protocol, and the human time spent.
