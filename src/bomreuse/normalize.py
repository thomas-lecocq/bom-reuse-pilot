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

_NUMERIC_TOKEN = re.compile(
    r"\d+(?:\.\d+)?(?:[x/-]\d+(?:\.\d+)?)*\s?(?:mm2|mm|kw|kv|bar|in)?(?![a-z0-9])"
)
_ORDINAL = re.compile(r"\b(\d)(?:re|er|e|eme|st|nd|rd|th)\b")
# Attributes that make two otherwise identical designations two different parts.
_MARKERS: dict[str, dict[str, str]] = {
    "side": {
        "gauche": "left",
        "gche": "left",
        "gch": "left",
        "left": "left",
        "lh": "left",
        "droite": "right",
        "droit": "right",
        "drte": "right",
        "drt": "right",
        "dte": "right",
        "right": "right",
        "rh": "right",
    },
    "material": {
        "inox": "stainless",
        "stainless": "stainless",
        "a4": "stainless",
        "a2": "stainless",
        "zinc": "zinc",
        "zn": "zinc",
        "zingue": "zinc",
        "zinguee": "zinc",
        "nbr": "nbr",
        "fkm": "fkm",
        "viton": "fkm",
        "epdm": "epdm",
        "silicone": "silicone",
        "alu": "aluminium",
        "aluminium": "aluminium",
        "aluminum": "aluminium",
    },
}


def display_ref(raw: str) -> str:
    """Readable form: `bog_01101` -> `BOG-1101`. Not an identity: `SECAB-624` keeps its shape."""
    tokens = re.split(r"[^A-Z0-9]+|(?<=[A-Z])(?=\d)", raw.upper())
    return "-".join(t.lstrip("0") or "0" if t.isdigit() else t for t in tokens if t)


def canonical_ref(raw: str) -> str:
    """Identity key, blind to separators: `SE-CAB-624`, `SECAB 624`, `se_cab_0624` -> `SECAB624`."""
    return display_ref(raw).replace("-", "")


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


_SUPPLIER_STOPWORDS = {"de", "du", "des", "et", "and", "la", "le", "les", "&"}


def canonical_supplier(raw: str) -> str:
    """Accent-free lowercase tokens without legal suffixes: `Ateliers Méca. du Hainaut SA` ->
    `ateliers meca hainaut`."""
    words = re.split(r"[\s\-_.,/]+", strip_accents(raw).lower().replace("&", " "))
    return " ".join(w for w in words if w and w not in _LEGAL_SUFFIXES | _SUPPLIER_STOPWORDS)


def _abbreviates(x: str, y: str) -> bool:
    short, long = sorted((x, y), key=len)
    return short == long or (len(short) >= 3 and long.startswith(short))


def same_supplier(a: str, b: str) -> bool:
    """One company under two spellings: abbreviations (`meca`/`mecaniques`), an acronym (`amh`),
    or a name that extends the other (`zf` / `zf friedrichshafen`, `interne` / `fab interne`)."""
    ta, tb = a.split(), b.split()
    if not ta or not tb:
        return False
    short, long = sorted((ta, tb), key=len)
    if len(short) == 1 and 2 <= len(short[0]) <= 5 and short[0] == "".join(w[0] for w in long):
        return True
    for start in range(len(long) - len(short) + 1):
        window = long[start : start + len(short)]
        if all(_abbreviates(x, y) for x, y in zip(short, window, strict=True)):
            return True
    return False


def supplier_groups(names: set[str]) -> int:
    groups: list[str] = []
    for name in sorted(names, key=len, reverse=True):
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
    text = _ORDINAL.sub("", text)
    return frozenset(t.replace(" ", "") for t in _NUMERIC_TOKEN.findall(text))


def variant_markers(description: str) -> dict[str, frozenset[str]]:
    """Side, material and class (1re/2nd...) found in a designation, by category."""
    text = strip_accents(description).lower()
    words = re.findall(r"[a-z0-9]+", text)
    found: dict[str, set[str]] = {}
    for category, table in _MARKERS.items():
        values = {table[w] for w in words if w in table}
        if values:
            found[category] = values
    classes = {f"class {m}" for m in _ORDINAL.findall(text)}
    if classes:
        found["class"] = classes
    return {k: frozenset(v) for k, v in found.items()}
