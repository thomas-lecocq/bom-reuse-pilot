"""Synthetic Valenciennes-style BOM export with planted defects and the ground truth to score them.

The clean catalog is hand-written to stay plausible; the dirt (formatting, language, units,
supplier aliases, typo'd references, bad rows) is applied by a seeded RNG, so the dataset is
reproducible and every defect is listed in `truth.json`.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Part:
    ref: str
    en: str
    fr: str
    supplier: str
    mass_kg: float
    unit: str = "pc"


PARTS: list[Part] = [
    # Fasteners and seals: near-identical refs that are genuinely different parts (decoys).
    Part("FIX-1240", "Hex head screw M12x40", "Vis tete hexagonale M12x40", "Bossard", 0.045),
    Part("FIX-1250", "Hex head screw M12x50", "Vis tete hexagonale M12x50", "Bossard", 0.052),
    Part("FIX-1640", "Hex head screw M16x40", "Vis tete hexagonale M16x40", "Bossard", 0.081),
    Part("FIX-1300", "Nut M12", "Ecrou M12", "Bossard", 0.017),
    Part("FIX-1310", "Washer M12", "Rondelle M12", "Bossard", 0.006),
    Part("FIX-2210", "O-ring seal 22x2 NBR", "Joint torique 22x2 NBR", "Trelleborg", 0.002),
    Part("FIX-2211", "O-ring seal 22x2 FKM", "Joint torique 22x2 FKM", "Trelleborg", 0.002),
    # Bogie
    Part("BOG-1101", "Bogie frame motor", "Chassis bogie moteur", "Alstom Le Creusot", 1850.0),
    Part("BOG-1102", "Bogie frame trailer", "Chassis bogie porteur", "Alstom Le Creusot", 1620.0),
    Part("BOG-1110", "Primary spring", "Ressort primaire", "Sogefi", 38.0),
    Part("BOG-1120", "Secondary air spring", "Ressort pneumatique secondaire", "Continental", 52.0),
    Part("BOG-1130", "Yaw damper", "Amortisseur de lacet", "ZF", 21.5),
    Part("BOG-1140", "Wheelset axle", "Essieu monte", "Lucchini", 1150.0),
    Part("BOG-1150", "Axle bearing unit", "Roulement d essieu", "SKF", 34.0),
    Part("BOG-1160", "Traction motor 340kW", "Moteur de traction 340kW", "Alstom Ornans", 620.0),
    # HVAC
    Part("HVC-2101", "Scroll compressor", "Compresseur scroll", "Bitzer", 38.0),
    Part("HVC-2102", "Condenser fan", "Ventilateur condenseur", "ebm-papst", 9.5),
    Part("HVC-2103", "Evaporator coil", "Evaporateur", "Faiveley", 27.0),
    Part("HVC-2104", "Air filter G4", "Filtre a air G4", "Camfil", 1.2),
    Part("HVC-2105", "Pressure sensor 0-25bar", "Capteur de pression 0-25bar", "Sensata", 0.15),
    Part("HVC-2106", "Cab compressor compact", "Compresseur cabine compact", "Bitzer", 22.0),
    # Doors
    Part(
        "DOR-3101", "Door leaf double glazed", "Vantail de porte double vitrage", "Faiveley", 64.0
    ),
    Part("DOR-3102", "Door actuator electric", "Verin de porte electrique", "Faiveley", 11.0),
    Part("DOR-3103", "Door controller", "Controleur de porte", "Faiveley", 2.4),
    Part("DOR-3104", "Door seal profile", "Profil joint de porte", "Trelleborg", 3.1),
    Part("DOR-3105", "Sliding step", "Marchepied mobile", "Faiveley", 18.0),
    Part("DOR-3106", "PRM access ramp", "Rampe d acces PMR", "Faiveley", 24.0),
    # Brakes
    Part("BRK-4100", "Brake panel frame", "Chassis panneau de frein", "Knorr-Bremse", 25.0),
    Part("BRK-4101", "Brake control unit", "Unite de controle frein", "Knorr-Bremse", 6.5),
    Part("BRK-4102", "Solenoid valve", "Electrovanne", "Knorr-Bremse", 1.1),
    Part("BRK-4103", "Pressure sensor 0-10bar", "Capteur de pression 0-10bar", "Knorr-Bremse", 0.2),
    Part("BRK-4104", "Relay valve", "Vanne relais", "Knorr-Bremse", 2.8),
    Part("BRK-4105", "Brake caliper", "Etrier de frein", "Knorr-Bremse", 31.0),
    Part("BRK-4106", "Brake pad set", "Jeu de garnitures de frein", "Knorr-Bremse", 4.2),
    Part(
        "BRK-4107", "Brake control unit gen2", "Unite de controle frein gen2", "Knorr-Bremse", 6.1
    ),
    # Pantograph and electrical
    Part("PAN-5101", "Pantograph frame", "Chassis pantographe", "Schunk", 95.0),
    Part("PAN-5102", "Pan head carbon strip", "Archet bande carbone", "Schunk", 3.5),
    Part("PAN-5103", "Roof insulator", "Isolateur de toiture", "Lapp", 7.8),
    Part("PAN-5104", "Dual voltage selector", "Selecteur bitension", "Secheron", 41.0),
    Part("ELE-4410", "Power cable 35mm2", "Cable de puissance 35mm2", "Nexans", 0.36, "m"),
    Part("ELE-4416", "Power cable 16mm2", "Cable de puissance 16mm2", "Nexans", 0.18, "m"),
    # Cab
    Part("CAB-6101", "Driver desk structure", "Structure pupitre", "Alstom Villeurbanne", 120.0),
    Part("CAB-6102", "Driver display 12in", "Ecran conducteur 12in", "Alstom Villeurbanne", 3.2),
    Part("CAB-6103", "Traction brake controller", "Manipulateur traction frein", "Schaltbau", 5.5),
    Part("CAB-6104", "Driver display 15in", "Ecran conducteur 15in", "Alstom Villeurbanne", 4.4),
]

SUB_ASSEMBLIES: dict[str, tuple[str, list[tuple[str, float]]]] = {
    "SA-BOG-100": (
        "Motor bogie assembly",
        [
            ("BOG-1101", 1),
            ("BOG-1110", 8),
            ("BOG-1120", 2),
            ("BOG-1130", 2),
            ("BOG-1140", 2),
            ("BOG-1150", 4),
            ("BOG-1160", 2),
            ("FIX-1640", 24),
            ("FIX-1300", 24),
        ],
    ),
    "SA-BOG-110": (
        "Trailer bogie assembly",
        [
            ("BOG-1102", 1),
            ("BOG-1110", 8),
            ("BOG-1120", 2),
            ("BOG-1130", 2),
            ("BOG-1140", 2),
            ("BOG-1150", 4),
            ("FIX-1640", 12),
            ("FIX-1300", 12),
        ],
    ),
    "SA-HVC-200": (
        "Saloon HVAC unit",
        [
            ("HVC-2101", 2),
            ("HVC-2102", 2),
            ("HVC-2103", 1),
            ("HVC-2104", 4),
            ("HVC-2105", 2),
            ("FIX-1240", 16),
            ("FIX-2210", 6),
        ],
    ),
    "SA-HVC-210": (
        "Cab HVAC unit",
        [("HVC-2106", 1), ("HVC-2104", 1), ("FIX-1250", 8), ("FIX-1310", 8)],
    ),
    "SA-DOR-300": (
        "Passenger door module",
        [
            ("DOR-3101", 2),
            ("DOR-3102", 1),
            ("DOR-3103", 1),
            ("DOR-3104", 4),
            ("DOR-3105", 1),
            ("FIX-1240", 12),
            ("FIX-1310", 12),
        ],
    ),
    "SA-DOR-305": (
        "Passenger door module PRM",
        [
            ("DOR-3101", 2),
            ("DOR-3102", 1),
            ("DOR-3103", 1),
            ("DOR-3104", 4),
            ("DOR-3105", 1),
            ("DOR-3106", 1),
            ("FIX-1240", 12),
            ("FIX-1310", 12),
        ],
    ),
    "SA-BRK-400": (
        "Brake control panel",
        [
            ("BRK-4100", 1),
            ("BRK-4101", 1),
            ("BRK-4102", 4),
            ("BRK-4103", 2),
            ("BRK-4104", 2),
            ("FIX-2210", 8),
            ("FIX-1250", 6),
        ],
    ),
    "SA-BRK-401": (
        "Brake control panel (variant D)",
        [
            ("BRK-4100", 1),
            ("BRK-4107", 1),
            ("BRK-4102", 4),
            ("BRK-4103", 2),
            ("BRK-4104", 2),
            ("FIX-2210", 8),
            ("FIX-1250", 6),
        ],
    ),
    "SA-BRK-420": (
        "Bogie brake equipment",
        [("BRK-4105", 4), ("BRK-4106", 4), ("FIX-1640", 16)],
    ),
    "SA-PAN-500": (
        "Pantograph 25kV",
        [("PAN-5101", 1), ("PAN-5102", 2), ("PAN-5103", 4), ("ELE-4410", 12)],
    ),
    "SA-PAN-510": (
        "Pantograph dual voltage",
        [
            ("PAN-5101", 1),
            ("PAN-5102", 2),
            ("PAN-5103", 4),
            ("PAN-5104", 1),
            ("ELE-4410", 18),
            ("ELE-4416", 6),
        ],
    ),
    "SA-CAB-600": (
        "Driver desk",
        [("CAB-6101", 1), ("CAB-6102", 2), ("CAB-6103", 1), ("FIX-1240", 20)],
    ),
    "SA-CAB-610": (
        "Driver desk (large display)",
        [("CAB-6101", 1), ("CAB-6104", 2), ("CAB-6103", 1), ("FIX-1240", 20)],
    ),
}

VARIANTS: dict[str, tuple[str, list[str]]] = {
    "REG-A": (
        "3-car electric",
        [
            "SA-BOG-100",
            "SA-BOG-110",
            "SA-HVC-200",
            "SA-HVC-210",
            "SA-DOR-300",
            "SA-BRK-400",
            "SA-BRK-420",
            "SA-PAN-500",
            "SA-CAB-600",
        ],
    ),
    "REG-B": (
        "4-car electric",
        [
            "SA-BOG-100",
            "SA-BOG-110",
            "SA-HVC-200",
            "SA-HVC-210",
            "SA-DOR-300",
            "SA-DOR-305",
            "SA-BRK-400",
            "SA-BRK-420",
            "SA-PAN-500",
            "SA-CAB-600",
        ],
    ),
    "REG-C": (
        "4-car dual voltage",
        [
            "SA-BOG-100",
            "SA-BOG-110",
            "SA-HVC-200",
            "SA-HVC-210",
            "SA-DOR-305",
            "SA-BRK-400",
            "SA-BRK-420",
            "SA-PAN-510",
            "SA-CAB-610",
        ],
    ),
    "REG-D": (
        "6-car electric",
        [
            "SA-BOG-100",
            "SA-BOG-110",
            "SA-HVC-200",
            "SA-HVC-210",
            "SA-DOR-300",
            "SA-BRK-401",
            "SA-BRK-420",
            "SA-PAN-500",
            "SA-CAB-610",
        ],
    ),
    "REG-E": (
        "4-car bi-mode",
        [
            "SA-BOG-100",
            "SA-BOG-110",
            "SA-HVC-200",
            "SA-DOR-305",
            "SA-BRK-400",
            "SA-BRK-420",
            "SA-CAB-600",
        ],
    ),
}

SUPPLIER_ALIASES: dict[str, list[str]] = {
    "Knorr-Bremse": ["Knorr-Bremse", "KNORR BREMSE GmbH", "Knorr Bremse AG"],
    "Faiveley": ["Faiveley", "FAIVELEY", "Faiveley SA"],
    "Bossard": ["Bossard", "BOSSARD AG"],
    "Trelleborg": ["Trelleborg", "TRELLEBORG AB"],
}

UNIT_ALIASES: dict[str, list[str]] = {"pc": ["PC", "pce", "u", "EA", "pcs"], "m": ["m", "M"]}

# Typo'd references for the same physical part (true duplicates), keyed by the true ref.
TYPO_REFS: dict[str, str] = {
    "DOR-3104": "DOR-3014",
    "HVC-2105": "HVC-2I05",
    "PAN-5102": "PAN-512",
    "BRK-4106": "BRK-41O6",
    "CAB-6103": "CAB-61003",
    "BOG-1130": "BOG-1310",
}
# (variant, sub-assembly) where the typo'd ref is used instead of the true one.
TYPO_SITES: dict[str, tuple[str, str]] = {
    "DOR-3104": ("REG-C", "SA-DOR-305"),
    "HVC-2105": ("REG-D", "SA-HVC-200"),
    "PAN-5102": ("REG-C", "SA-PAN-510"),
    "BRK-4106": ("REG-E", "SA-BRK-420"),
    "CAB-6103": ("REG-D", "SA-CAB-610"),
    "BOG-1130": ("REG-E", "SA-BOG-110"),
}
# A duplicate that string rules cannot settle: wording outside the glossary, unknown supplier alias.
HARD_DUPLICATE = ("BOG-1130", "Amortisseur anti-lacet", "ZF Friedrichshafen")

NOTES: list[tuple[str, str, str, str | None]] = [
    # (ref, text, true kind, true target). Kind "none" means no fact should be extracted.
    (
        "FIX-2210",
        "Remplacé par FIX-2211 (FKM) pour tenue en température.",
        "superseded_by",
        "FIX-2211",
    ),
    ("BRK-4101", "Superseded by BRK-4107 from 2025 tenders.", "superseded_by", "BRK-4107"),
    ("CAB-6102", "Obsolète : écran 12in plus fabriqué par le fournisseur.", "obsolete", None),
    (
        "HVC-2103",
        "Equivalent to HVC-2103B (alternate supplier), interchangeable.",
        "equivalent_to",
        "HVC-2103B",
    ),
    (
        "PAN-5103",
        "Ne plus commander, le fournisseur arrête la production fin 2025.",
        "obsolete",
        None,
    ),
    (
        "ELE-4416",
        "From batch 3 onwards fit ELE-4410 instead, harness simplification.",
        "superseded_by",
        "ELE-4410",
    ),
    (
        "DOR-3105",
        "Peut être monté à la place de DOR-3105B sans modification.",
        "equivalent_to",
        "DOR-3105B",
    ),
    ("FIX-1240", "Ne pas confondre avec FIX-1250, remplacement interdit.", "none", None),
    ("BOG-1130", "Not obsolete - confirmed with supplier in March 2025.", "none", None),
    ("BOG-1110", "Couple de serrage 85 Nm, voir gamme G-112.", "none", None),
    ("HVC-2101", "Checked by JD, OK for 2026 tender.", "none", None),
    ("BRK-4105", "RAS", "none", None),
    ("SA-DOR-300", "Module identique sur REG-A et REG-B, à confirmer pour REG-D.", "none", None),
    ("CAB-6101", "Structure commune à tous les pupitres.", "none", None),
    ("BOG-1160", "EOL announced by Alstom Ornans, last order 2027.", "obsolete", None),
]


def _format_ref(ref: str, rng: random.Random) -> str:
    style = rng.random()
    if style < 0.6:
        return ref
    if style < 0.75:
        return ref.lower()
    if style < 0.9:
        return ref.replace("-", " ")
    prefix, _, number = ref.rpartition("-")
    return f"{prefix}_0{number}"


def _format_number(value: float, rng: random.Random) -> str:
    text = f"{value:g}"
    return text.replace(".", ",") if rng.random() < 0.5 else text


def _format_mass(mass_kg: float, rng: random.Random) -> str:
    if mass_kg < 1 and rng.random() < 0.7:
        return f"{_format_number(round(mass_kg * 1000, 3), rng)} g"
    return f"{_format_number(mass_kg, rng)} kg"


def _format_length(metres: float, rng: random.Random) -> tuple[str, str]:
    roll = rng.random()
    if roll < 0.4:
        return f"{metres * 1000:g}", "mm"
    if roll < 0.55:
        return f"{metres * 100:g}", "cm"
    return _format_number(metres, rng), rng.choice(UNIT_ALIASES["m"])


@dataclass
class _Builder:
    rng: random.Random
    rows: list[dict[str, str]]
    truth_ref: dict[str, str]

    def emit(self, row: dict[str, str], true_ref: str) -> None:
        self.rows.append(row)
        self.truth_ref[row["ref_article"]] = true_ref


def _component_row(
    b: _Builder, variant: str, sa_ref: str, part: Part, qty: float, ref: str
) -> dict[str, str]:
    rng = b.rng
    if part.unit == "m":
        qty_text, unit_text = _format_length(qty, rng)
    else:
        qty_text, unit_text = _format_number(qty, rng), rng.choice(UNIT_ALIASES["pc"])
    aliases = SUPPLIER_ALIASES.get(part.supplier, [part.supplier])
    return {
        "variante": variant,
        "niveau": "2",
        "ref_parent": sa_ref,
        "ref_article": ref,
        "designation": part.fr if rng.random() < 0.45 else part.en,
        "qte": qty_text,
        "unite": unit_text,
        "fournisseur": rng.choice(aliases),
        "masse_unitaire": _format_mass(part.mass_kg, rng),
    }


def _planted_overrides(variant: str, sa_ref: str, ref: str, qty: float) -> tuple[float, str]:
    """Composition drift and supplier conflict planted at fixed sites."""
    if (variant, sa_ref, ref) == ("REG-D", "SA-BOG-110", "FIX-1640"):
        return 16, ""
    if (variant, sa_ref, ref) == ("REG-E", "SA-BRK-420", "BRK-4105"):
        return qty, "Wabtec"
    return qty, ""


def build_rows(seed: int) -> tuple[list[dict[str, str]], dict[str, str]]:
    rng = random.Random(seed)
    parts = {p.ref: p for p in PARTS}
    b = _Builder(rng, [], {})
    for variant, (_, sa_refs) in VARIANTS.items():
        for sa_ref in sa_refs:
            sa_name, lines = SUB_ASSEMBLIES[sa_ref]
            sa_row = {
                "variante": variant,
                "niveau": "1",
                "ref_parent": variant,
                "ref_article": _format_ref(sa_ref, rng),
                "designation": sa_name,
                "qte": "1",
                "unite": "PC",
                "fournisseur": "",
                "masse_unitaire": "",
            }
            b.emit(sa_row, sa_ref)
            for ref, base_qty in lines:
                qty, supplier = _planted_overrides(variant, sa_ref, ref, base_qty)
                use_typo = TYPO_SITES.get(ref) == (variant, sa_ref)
                raw_ref = TYPO_REFS[ref] if use_typo else _format_ref(ref, rng)
                row = _component_row(b, variant, sa_ref, parts[ref], qty, raw_ref)
                row["ref_parent"] = sa_row["ref_article"]
                if supplier:
                    row["fournisseur"] = supplier
                if use_typo and ref == HARD_DUPLICATE[0]:
                    row["designation"], row["fournisseur"] = HARD_DUPLICATE[1:]
                if (variant, ref) == ("REG-B", "HVC-2101"):
                    row["masse_unitaire"] = "38 g"  # unit slip: kg typed as g
                b.emit(row, ref)
    _add_bad_rows(b)
    return b.rows, b.truth_ref


def _add_bad_rows(b: _Builder) -> None:
    bad = [
        ("REG-B", "SA-HVC-200", "HVC-2104", "?", "PC"),
        ("REG-C", "SA-BRK-420", "BRK-4106", "4", "bte"),
        ("REG-E", "SA-CAB-600", "", "1", "PC"),
    ]
    for variant, parent, ref, qty, unit in bad:
        b.rows.append(
            {
                "variante": variant,
                "niveau": "2",
                "ref_parent": parent,
                "ref_article": ref,
                "designation": "",
                "qte": qty,
                "unite": unit,
                "fournisseur": "",
                "masse_unitaire": "",
            }
        )


def build_truth(truth_ref: dict[str, str]) -> dict[str, object]:
    return {
        "raw_ref_to_true_ref": truth_ref,
        "duplicate_refs": [[true, typo] for true, typo in TYPO_REFS.items()],
        "reusable_pairs": [
            ["SA-DOR-300", "SA-DOR-305"],
            ["SA-BRK-400", "SA-BRK-401"],
            ["SA-CAB-600", "SA-CAB-610"],
            ["SA-PAN-500", "SA-PAN-510"],
        ],
        "inconsistencies": [
            {"kind": "composition_drift", "subject": "SA-BOG-110"},
            {"kind": "supplier_conflict", "subject": "BRK-4105"},
            {"kind": "mass_mismatch", "subject": "HVC-2101"},
            {"kind": "superseded_in_use", "subject": "FIX-2210"},
            {"kind": "superseded_in_use", "subject": "BRK-4101"},
            {"kind": "obsolete_in_use", "subject": "CAB-6102"},
            {"kind": "obsolete_in_use", "subject": "PAN-5103"},
            {"kind": "obsolete_in_use", "subject": "BOG-1160"},
            {"kind": "superseded_in_use", "subject": "ELE-4416"},
        ],
        "notes": [
            {"note_id": f"N{i:03d}", "ref": ref, "kind": kind, "target": target}
            for i, (ref, _, kind, target) in enumerate(NOTES, start=1)
        ],
        "bad_rows": 3,
    }


def write_dataset(out_dir: Path, seed: int = 7) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, truth_ref = build_rows(seed)
    with (out_dir / "bom_export.csv").open("w", newline="", encoding="utf-8") as f:
        bom_writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        bom_writer.writeheader()
        bom_writer.writerows(rows)
    with (out_dir / "notes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["note_id", "ref_article", "auteur", "date", "texte"])
        for i, (ref, text, _, _) in enumerate(NOTES, start=1):
            writer.writerow(
                [f"N{i:03d}", ref, f"user{i % 4 + 1}", f"2025-{i % 12 + 1:02d}-15", text]
            )
    truth = build_truth(truth_ref)
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False) + "\n")
