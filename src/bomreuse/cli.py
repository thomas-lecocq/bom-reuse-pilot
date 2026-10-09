"""Command line: `bomreuse generate`, `bomreuse report`, `bomreuse eval`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bomreuse.bench import write_bench
from bomreuse.evaluate import dump
from bomreuse.generate import write_dataset
from bomreuse.llm import CacheMissError
from bomreuse.pipeline import LLM_MODES, run
from bomreuse.report import write_report

DEFAULT_CACHE = Path("cache/llm_responses.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bomreuse")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write a synthetic export with planted defects")
    gen.add_argument("--out", type=Path, default=Path("data"))
    gen.add_argument("--seed", type=int, default=7)
    for name, help_text in (("report", "build the HTML report"), ("eval", "score against truth")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--data", type=Path, default=Path("data"))
        cmd.add_argument(
            "--llm",
            choices=LLM_MODES,
            default="replay",
            help="replay = committed cache only, offline (default); none = rules only",
        )
        cmd.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
        cmd.add_argument("--out", type=Path, default=Path("out/report.html"))
    bench = sub.add_parser("bench", help="compare models over repeated runs (live calls)")
    bench.add_argument("--data", type=Path, default=Path("data"))
    bench.add_argument("--models", default="sonnet,opus")
    bench.add_argument("--runs", type=int, default=5)
    bench.add_argument("--out", type=Path, default=Path("docs/llm_bench.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "generate":
        write_dataset(args.out, args.seed)
        print(f"wrote {args.out}/bom_export.csv, notes.csv, truth.json")
        return 0
    if args.command == "bench":
        write_bench(args.data, args.models.split(","), args.runs, args.out)
        print(f"wrote {args.out}")
        return 0
    try:
        result = run(args.data, args.llm, args.cache)
    except CacheMissError as exc:
        print(f"{exc}\nRun once with --llm claude-cli, anthropic or ollama.", file=sys.stderr)
        return 2
    if args.command == "eval":
        print(dump(result.evaluation or {}))
        return 0
    write_report(result, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
