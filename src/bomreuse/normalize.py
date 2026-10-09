"""Deterministic canonical forms: references, units, suppliers and FR/EN descriptions.

Everything here is a pure function so that each merge can be explained by the rule that fired.
"""

from __future__ import annotations

import re
import unicodedata

from bomreuse.model import Quantity, Unit

_UNIT_ALIASES: dict[str, tuple[Unit, float]] = {
    "pc": (Unit.PIECE, 1.0),
    "pcs": (Unit.PIECE, 1.0),
    "pce": (Unit.PIECE, 1.0),
    "u": (Unit.PIECE, 1.0),
    "un": (Unit.PIECE, 1.0),
    "ea": (Unit.PIECE, 1.0),
    "m": (Unit.METRE, 1.0),
    "cm": (Unit.METRE, 0.01),
    "mm": (Unit.METRE, 0.001),
    "kg": (Unit.KILOGRAM, 1.0),
    "g": (Unit.KILOGRAM, 0.001),
    "l": (Unit.LITRE, 1.0),
    "ml": (Unit.LITRE, 0.001),
}

_LEGAL_SUFFIXES = {
    "gmbh",
    "ag",
    "ab",
    "sa",
    "sas",
    "spa",
    "ltd",
    "corp",
    "corporation",
    "inc",
    "srl",
}

# Domain glossary: French token -> English token. Small on purpose; week 2 grows it from real data.
GLOSSARY: dict[str, str] = {
    "vis": "screw",
    "tete": "head",
    "hexagonale": "hex",
    "ecrou": "nut",
    "rondelle": "washer",
    "joint": "seal",
    "torique": "o-ring",
    "cable": "cable",
    "puissance": "power",
    "frein": "brake",
    "etrier": "caliper",
    "garniture": "pad",
    "chassis": "frame",
    "ressort": "spring",
    "amortisseur": "damper",
    "essieu": "axle",
    "roue": "wheel",
    "roulement": "bearing",
    "compresseur": "compressor",
    "ventilateur": "fan",
    "filtre": "filter",
    "porte": "door",
    "vantail": "leaf",
    "moteur": "motor",
    "capteur": "sensor",
    "pression": "pressure",
    "electrovanne": "solenoid-valve",
    "vanne": "valve",
    "pupitre": "desk",
    "ecran": "screen",
    "manipulateur": "controller",
    "archet": "pan-head",
    "isolateur": "insulator",
    "verin": "actuator",
    "rampe": "ramp",
    "marchepied": "step",
    "condenseur": "condenser",
    "evaporateur": "evaporator",
    "de": "",
    "du": "",
    "a": "",
    "pour": "",
    "en": "",
}

_NUMERIC_TOKEN = re.compile(r"\d+(?:\.\d+)?(?:[x-]\d+(?:\.\d+)?)*(?:mm2|mm|kw|kv|bar|in)?(?![a-z])")


def canonical_ref(raw: str) -> str:
    """`bog-01101`, `BOG 1101`, `BOG_1101` and `BOG1101` all map to `BOG-1101`."""
    tokens = re.split(r"[^A-Z0-9]+|(?<=[A-Z])(?=\d)", raw.upper())
    return "-".join(t.lstrip("0") or "0" if t.isdigit() else t for t in tokens if t)


def ref_family(key: str) -> str:
    match = re.match(r"[A-Z]+", key)
    return match.group(0) if match else ""


def parse_number(raw: str) -> float | None:
    text = raw.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_quantity(raw_qty: str, raw_unit: str) -> Quantity | None:
    value = parse_number(raw_qty)
    alias = _UNIT_ALIASES.get(raw_unit.strip().lower())
    if value is None or alias is None or value <= 0:
        return None
    unit, factor = alias
    return Quantity(round(value * factor, 6), unit)


def parse_mass_kg(raw: str) -> float | None:
    match = re.fullmatch(r"\s*([\d\s.,]+)\s*(kg|g)\s*", raw.lower())
    if match is None:
        return None
    value = parse_number(match.group(1))
    if value is None:
        return None
    return round(value / 1000 if match.group(2) == "g" else value, 6)


def canonical_supplier(raw: str) -> str:
    tokens = re.split(r"[\s\-_.]+", strip_accents(raw).lower())
    return "".join(t for t in tokens if t and t not in _LEGAL_SUFFIXES)


def same_supplier(a: str, b: str) -> bool:
    """Canonical names where one extends the other (`zf`, `zffriedrichshafen`) are one company."""
    short, long = sorted((a, b), key=len)
    return len(short) >= 2 and long.startswith(short)


def supplier_groups(names: set[str]) -> int:
    groups: list[str] = []
    for name in sorted(names, key=len):
        if not any(same_supplier(g, name) for g in groups):
            groups.append(name)
    return len(groups)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def english_tokens(description: str) -> str:
    """Lowercase, accent-free, French words mapped to English through the glossary."""
    text = strip_accents(description).lower().replace("²", "2")
    words = re.findall(r"[a-z0-9.,x\-]+", text)
    mapped = (GLOSSARY.get(w, w) for w in words)
    return " ".join(w for w in mapped if w)


def dimension_tokens(description: str) -> frozenset[str]:
    text = strip_accents(description).lower().replace("²", "2").replace(",", ".")
    return frozenset(_NUMERIC_TOKEN.findall(text))
