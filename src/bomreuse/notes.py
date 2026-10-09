"""Turn free-text FR/EN engineering notes into facts the analysis can check against the BOM.

Two extractors with the same output type, so they can be scored against each other.
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import ValidationError

from bomreuse.ingest import Note
from bomreuse.llm import InvalidOutputs, LlmClient, NoteFactsOut, extract_json, render
from bomreuse.model import NoteFact
from bomreuse.normalize import canonical_ref

_REF = r"([A-Z]{2,4}[-_ .]?\d{3,8}[A-Z]?)"
_SUPERSEDED = re.compile(rf"(?:remplac[ée]e?s? par|superseded by|replaced by)\s+{_REF}", re.I)
_EQUIVALENT = re.compile(
    rf"(?:[ée]quivalent [àa]|equivalent to|interchangeable with)\s+{_REF}", re.I
)
_WITHDRAWN = re.compile(r"\b(?:annul\w*|abandonn\w*|withdrawn|cancel\w*|revoked)\b", re.I)
_OBSOLETE = re.compile(r"\b(?:obsol[eè]te|EOL|end of life|plus fabriqu[ée])", re.I)


class NoteExtractor(Protocol):
    name: str

    def extract(self, note: Note) -> list[NoteFact]: ...


class RuleExtractor:
    name = "rules"

    def extract(self, note: Note) -> list[NoteFact]:
        if _WITHDRAWN.search(note.text):
            return [NoteFact(note.note_id, note.ref_key, "withdrawn", None, self.name, note.date)]
        if match := _SUPERSEDED.search(note.text):
            target = canonical_ref(match.group(1))
            return [
                NoteFact(note.note_id, note.ref_key, "superseded_by", target, self.name, note.date)
            ]
        if match := _EQUIVALENT.search(note.text):
            target = canonical_ref(match.group(1))
            return [
                NoteFact(note.note_id, note.ref_key, "equivalent_to", target, self.name, note.date)
            ]
        if _OBSOLETE.search(note.text):
            return [NoteFact(note.note_id, note.ref_key, "obsolete", None, self.name, note.date)]
        return []


class LlmExtractor:
    name = "llm"

    def __init__(self, client: LlmClient, invalid: InvalidOutputs) -> None:
        self.client = client
        self.invalid = invalid

    def extract(self, note: Note) -> list[NoteFact]:
        raw = self.client.complete(render("note_facts.md", ref=note.ref_key, text=note.text))
        try:
            parsed = NoteFactsOut.model_validate_json(extract_json(raw))
        except ValidationError:
            self.invalid.add(raw)
            return []
        return [
            NoteFact(
                note.note_id,
                note.ref_key,
                fact.kind,
                canonical_ref(fact.target) if fact.target else None,
                self.name,
                note.date,
            )
            for fact in parsed.facts
        ]


def extract_all(notes: list[Note], extractor: NoteExtractor) -> list[NoteFact]:
    return [fact for note in notes for fact in extractor.extract(note)]
