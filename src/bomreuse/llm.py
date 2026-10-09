"""Pluggable LLM backends behind one cache, plus the two places the pipeline asks a model.

Backends: `claude -p` headless (no API key needed), Anthropic API, Ollama (on-premise). Every
response is cached by hash of (backend model, prompt) and committed, so the demo replays offline.
Model output is validated by pydantic; invalid output is counted and dropped.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

from bomreuse.model import LlmOpinion, ReviewItem
from bomreuse.resolve import ComponentRecord

PROMPT_DIR = Path(__file__).parent / "prompts"


class LlmClient(Protocol):
    @property
    def model_id(self) -> str: ...

    def complete(self, prompt: str) -> str: ...


class CacheMissError(RuntimeError):
    pass


class _CliEnvelope(BaseModel):
    result: str


@dataclass
class ClaudeCliClient:
    model: str = "sonnet"

    @property
    def model_id(self) -> str:
        return f"claude-cli:{self.model}"

    def complete(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory() as cwd:  # keep any project CLAUDE.md out of the prompt
            proc = subprocess.run(
                ["claude", "-p", "--model", self.model, "--output-format", "json", "--tools", ""]
                + ["--no-session-persistence"],
                input=prompt,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=180,
                check=True,
            )
        return _CliEnvelope.model_validate_json(proc.stdout).result


@dataclass
class AnthropicClient:
    model: str = "claude-sonnet-5-5"

    @property
    def model_id(self) -> str:
        return f"anthropic:{self.model}"

    def complete(self, prompt: str) -> str:
        import anthropic  # optional dependency: `uv sync --extra anthropic`

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        message = client.messages.create(
            model=self.model, max_tokens=1024, messages=[{"role": "user", "content": prompt}]
        )
        return "".join(block.text for block in message.content if block.type == "text")


class _OllamaReply(BaseModel):
    response: str


@dataclass
class OllamaClient:
    """On-premise backend: nothing leaves the network."""

    model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen3:14b"))
    host: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )

    @property
    def model_id(self) -> str:
        return f"ollama:{self.model}"

    def complete(self, prompt: str) -> str:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(
            f"{self.host}/api/generate", body, {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=300) as reply:
            return _OllamaReply.model_validate_json(reply.read()).response


@dataclass
class CachedClient:
    """Replays committed responses; calls `backend` only on a miss (if one is configured)."""

    path: Path
    model_id: str
    backend: LlmClient | None = None
    entries: dict[str, str] = field(default_factory=dict)
    misses: int = 0

    def __post_init__(self) -> None:
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def _key(self, prompt: str) -> str:
        return hashlib.sha256(f"{self.model_id}\n{prompt}".encode()).hexdigest()[:16]

    def complete(self, prompt: str) -> str:
        key = self._key(prompt)
        if key not in self.entries:
            if self.backend is None:
                raise CacheMissError(f"no cached response for prompt {key} ({self.model_id})")
            self.misses += 1
            self.entries[key] = self.backend.complete(prompt)
            self.save()
        return self.entries[key]

    def save(self) -> None:
        text = json.dumps(dict(sorted(self.entries.items())), indent=2, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text + "\n", encoding="utf-8")


def extract_json(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def render(template: str, **values: str) -> str:
    text = (PROMPT_DIR / template).read_text(encoding="utf-8")
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return text


class PairVerdict(BaseModel):
    same_part: bool
    reason: str


class NoteFactOut(BaseModel):
    kind: Literal["superseded_by", "obsolete", "equivalent_to"]
    target: str | None = None


class NoteFactsOut(BaseModel):
    facts: list[NoteFactOut]


@dataclass
class InvalidOutputs:
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, raw: str) -> None:
        self.count += 1
        if len(self.examples) < 3:
            self.examples.append(raw[:200])


def _describe(rec: ComponentRecord) -> str:
    mass = f"{rec.mass_kg:g} kg" if rec.mass_kg is not None else "unknown"
    return (
        f"reference {rec.key}; descriptions {sorted(rec.descriptions)}; "
        f"suppliers {sorted(rec.suppliers)}; unit mass {mass}"
    )


def annotate_review(
    items: list[ReviewItem],
    records: dict[str, ComponentRecord],
    client: LlmClient,
    invalid: InvalidOutputs,
) -> None:
    """Attach an LLM opinion to each review item. The opinion is advice; it changes no merge."""
    for item in items:
        prompt = render(
            "pair_review.md", a=_describe(records[item.key_a]), b=_describe(records[item.key_b])
        )
        raw = client.complete(prompt)
        try:
            verdict = PairVerdict.model_validate_json(extract_json(raw))
        except ValidationError:
            invalid.add(raw)
            continue
        item.llm_opinion = LlmOpinion(verdict.same_part, verdict.reason)
