"""Blind, held-out test data for a multi-variant rail BOM reuse and consistency tool.

Why this exists: the tool must be scored on data its authors never saw. This script invents a
regional-train catalogue, assembles eight variants from it, plants scored defects and unscored
noise, then writes a dirty PLM/ERP export, free-text engineering notes and a ground-truth file.
Everything is deterministic per seed; the seed changes which parts and sites carry each defect.

Usage: python3 generate.py --seed N --out DIR   (also: --check DIR to re-run the self-check)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

HEADER = [
    "variante",
    "niveau",
    "ref_parent",
    "ref_article",
    "designation",
    "qte",
    "unite",
    "fournisseur",
    "masse_unitaire",
]
NOTES_HEADER = ["note_id", "ref_article", "auteur", "date", "texte"]
PC_UNITS = ["PC", "pc", "pce", "pcs", "u", "un", "EA"]

SUPPLIERS: dict[str, list[str]] = {
    "BR": [
        "Boulonnerie Rhodanienne",
        "BOULONNERIE RHODANIENNE",
        "Boulonnerie Rhodanienne SAS",
        "Boulonnerie Rhodan.",
    ],
    "VIN": [
        "Visserie Industrielle du Nord",
        "VISSERIE INDUSTRIELLE DU NORD",
        "Visserie Ind. du Nord SARL",
    ],
    "PJ": [
        "Polyjoint Industrie",
        "POLYJOINT INDUSTRIE",
        "Polyjoint Industrie SA",
        "PolyJoint Ind.",
    ],
    "EP": ["Étanche Pro", "ETANCHE PRO", "Etanche Pro SAS"],
    "CN": [
        "Câbleries de Normandie",
        "Cableries de Normandie",
        "CABLERIES DE NORMANDIE",
        "Câbleries de Normandie SA",
    ],
    "CX": ["Connectique Alpes", "CONNECTIQUE ALPES", "Connectique Alpes SARL"],
    "AMH": [
        "Ateliers Mécaniques du Hainaut",
        "ATELIERS MECANIQUES DU HAINAUT",
        "AMH",
        "Ateliers Méca. du Hainaut",
    ],
    "RP": ["Roulements de Picardie", "ROULEMENTS DE PICARDIE", "Roulements de Picardie SAS"],
    "RSA": [
        "Ressorts et Suspensions des Alpes",
        "RESSORTS & SUSPENSIONS DES ALPES",
        "Ressorts et Susp. des Alpes",
    ],
    "FS": ["Freinrail Systèmes", "FREINRAIL SYSTEMES", "Freinrail Systemes SAS", "Freinrail"],
    "PF": ["Pneumatica Ferroviaria", "PNEUMATICA FERROVIARIA", "Pneumatica Ferroviaria S.p.A."],
    "CAP": ["Captelec", "CAPTELEC", "Captelec SA"],
    "ET": ["Elektra Traktion AG", "ELEKTRA TRAKTION AG", "Elektra Traktion"],
    "TRF": ["Transfo Ouest", "TRANSFO OUEST", "Transfo Ouest SA"],
    "MDL": ["Moteurs Diesel Lorrains", "MOTEURS DIESEL LORRAINS", "Moteurs Diesel Lorrains SAS"],
    "CR": ["Climatic Rail", "CLIMATIC RAIL", "Climatic Rail GmbH", "Climatic-Rail"],
    "PS": ["Portéo Systems", "PORTEO SYSTEMS", "Porteo Systems", "Portéo Systems SAS"],
    "VTE": [
        "Vitrages Techniques de l'Est",
        "VITRAGES TECHNIQUES DE L'EST",
        "Vitrages Tech. de l'Est",
    ],
    "PC": ["Pupitres et Commandes", "PUPITRES ET COMMANDES", "Pupitres & Commandes SARL"],
    "SCF": ["Sièges Confort Ferroviaire", "SIEGES CONFORT FERROVIAIRE", "Sièges Confort Ferro."],
    "LUM": ["Lumirail", "LUMIRAIL", "Lumirail SAS"],
    "HRM": ["Hygiène Rail Modules", "HYGIENE RAIL MODULES", "Hygiene Rail Modules SA"],
    "ASD": ["Attelages Scharf-Durand", "ATTELAGES SCHARF-DURAND", "Attelages Scharf Durand"],
    "IB": ["InfoBord", "INFOBORD", "Infobord SAS"],
    "SR": ["Signalis Rail", "SIGNALIS RAIL", "Signalis Rail SA"],
    "CHI": [
        "Chimie Maintenance Industrie",
        "CHIMIE MAINTENANCE INDUSTRIE",
        "Chimie Maint. Industrie",
    ],
    "KR": ["Kabelwerk Rhein GmbH", "KABELWERK RHEIN"],
    "CPR": ["Connecteurs Pro", "CONNECTEURS PRO"],
    "FGC": ["Freins et Garnitures du Centre", "FREINS ET GARNITURES DU CENTRE"],
    "RL": ["Roulements Lyonnais", "ROULEMENTS LYONNAIS"],
    "ST": ["Suspensions Techniques", "SUSPENSIONS TECHNIQUES"],
    "DIS": ["Distrifer Négoce", "DISTRIFER NEGOCE"],
}
ALT_SUPPLIER = {
    "BR": "VIN",
    "VIN": "BR",
    "PJ": "EP",
    "EP": "PJ",
    "CN": "KR",
    "CX": "CPR",
    "FS": "FGC",
    "RP": "RL",
    "RSA": "ST",
}
INTERNAL = ["INTERNE", "Interne", "Fabrication interne", "FAB. INTERNE", ""]

ABBR = {
    "RESERVOIR": "RESERV.",
    "RESSORT": "RESS.",
    "AMORTISSEUR": "AMORT.",
    "SUSPENSION": "SUSP.",
    "SECONDAIRE": "SEC.",
    "PRIMAIRE": "PRIM.",
    "CLIMATISATION": "CLIM.",
    "CALCULATEUR": "CALC.",
    "TEMPERATURE": "TEMP.",
    "CHAUFFAGE": "CHAUFF.",
    "VENTILATEUR": "VENTIL.",
    "HEXAGONALE": "H",
    "HEXAGONAL": "H",
    "CLASSE": "CL",
    "ZINGUEE": "ZN",
    "ZINGUE": "ZN",
    "AUTOFREINE": "AUTOFR.",
    "PLATE": "PL.",
    "GAUCHE": "GCHE",
    "DROIT": "DRT",
    "DROITE": "DRT",
    "PORTE": "PTE",
    "VANTAIL": "VANT.",
    "ACCES": "ACC.",
    "GUIDAGE": "GUID.",
    "SUPERIEUR": "SUP.",
    "MECANISME": "MECA.",
    "HABILLAGE": "HAB.",
    "CAPTEUR": "CAPT.",
    "PRESSION": "PRESS.",
    "DISPOSITIF": "DISP.",
    "FREIN": "FR.",
    "MOTEUR": "MOT.",
    "TRACTION": "TRACT.",
    "ALIMENTATION": "ALIM.",
    "ECLAIRAGE": "ECL.",
    "SECOURS": "SECOURS",
    "ESSIEU": "ESS.",
    "BOGIE": "BOG.",
    "PORTEUR": "PORT.",
    "SOUDE": "SOUD.",
    "REFROIDISSEMENT": "REFROID.",
    "INFORMATION": "INFO.",
    "VOYAGEURS": "VOY.",
    "CONDUITE": "COND.",
    "CONDUCTEUR": "COND.",
    "AMENAGEMENT": "AMENAG.",
    "EQUIPEMENT": "EQUIP.",
    "UNIPOLAIRE": "UNIP.",
    "HALOGENE": "HAL.",
    "AVEUGLE": "AV.",
    "SIGNALISATION": "SIGNAL.",
    "CONVERTISSEUR": "CONV.",
    "TRANSFORMATEUR": "TRANSFO",
    "ATTELAGE": "ATTEL.",
    "AUTOMATIQUE": "AUTO.",
    "HELICOIDAL": "HELIC.",
    "PNEUMATIQUE": "PNEU.",
    "PNEUMATIQUES": "PNEU.",
    "TRANSVERSAL": "TRANSV.",
    "VERTICAL": "VERT.",
    "GARNITURE": "GARNIT.",
    "ORGANIQUE": "ORGA.",
    "FRITTEE": "FRITT.",
    "PRINCIPAL": "PPAL",
    "AUXILIAIRE": "AUX.",
    "SECURITE": "SECU.",
    "ASPIRATION": "ASPI.",
    "COMPRESSEUR": "COMPR.",
    "CONDENSATS": "COND.",
    "TOITURE": "TOIT.",
    "COMPOSITE": "COMPO.",
    "ISOLATEUR": "ISOL.",
    "DISJONCTEUR": "DISJ.",
    "DETECTION": "DETECT.",
    "ABAISSEMENT": "ABAISS.",
    "CONTACTEUR": "CONTACT.",
    "REFRIGERANT": "REFRIG.",
    "FRIGORIGENE": "FRIGO.",
    "SOUFFLAGE": "SOUFFL.",
    "REGULATEUR": "REGUL.",
    "RESISTANCE": "RESIST.",
    "CONVECTEUR": "CONVECT.",
    "PLANCHER": "PLANCH.",
    "OPERATEUR": "OPERAT.",
    "ELECTRIQUE": "ELEC.",
    "VERROUILLAGE": "VERROU.",
    "INTERCIRCULATION": "INTERCIRC.",
    "COULISSANTE": "COUL.",
    "MANIPULATEUR": "MANIP.",
    "AVERTISSEUR": "AVERT.",
    "RETROVISION": "RETRO.",
    "FEUILLETE": "FEUILL.",
    "CHAUFFANT": "CHAUFF.",
    "REGLABLE": "REGL.",
    "RABATTABLE": "RABATT.",
    "GARNISSAGE": "GARNISS.",
    "ALUMINIUM": "ALU",
    "REGLETTE": "REGL.",
    "UNIVERSEL": "UNIV.",
    "DEPRESSION": "DEPRESS.",
    "COMMANDE": "CDE",
    "COUPLEUR": "COUPL.",
    "ADAPTATEUR": "ADAPT.",
    "AFFICHEUR": "AFFICH.",
    "LATERAL": "LAT.",
    "VIDEOPROTECTION": "VIDEO",
    "COMPTAGE": "COMPT.",
    "INTERPHONE": "INTERPH.",
    "ODOMETRIQUE": "ODOM.",
    "MAINTENANCE": "MAINT.",
    "SIGNALETIQUE": "SIGNAL.",
    "IDENTIFICATION": "IDENT.",
    "GRAVEE": "GRAV.",
    "POLYURETHANE": "PU",
    "ACCROCHAGE": "ACCROCH.",
    "REFROIDISSEMENT,": "REFROID.",
    "IMMOBILISATION": "IMMOB.",
    "CONNECTEUR": "CONNECT.",
    "CIRCULAIRE": "CIRC.",
    "BROCHES": "BR.",
    "SERTIR": "SERT.",
    "BORNIER": "BORN.",
    "ETHERNET": "ETH.",
    "FERROVIAIRE": "FERRO.",
    "ANNELEE": "ANN.",
    "COLLIER": "COLL.",
    "SERRAGE": "SERR.",
    "BLINDE": "BLIND.",
    "PROFILE": "PROF.",
    "CELLULAIRE": "CELL.",
    "DISTRIBUTEUR": "DISTRIB.",
    "BOISSEAU": "BOISS.",
    "SPHERIQUE": "SPHER.",
    "FLEXIBLE": "FLEX.",
    "ENRAYAGE": "ENRAY.",
    "ETRIER": "ETR.",
    "CYLINDRE": "CYL.",
}
SMALL_WORDS = {"DE", "D'", "DU", "DES", "LA", "LE", "A", "EN", "SUR", "POUR", "AVEC", "ET", "L'"}

VARIANTS = [
    ("RGX-2C-TH", 2, "TH", False),
    ("RGX-3C-TH", 3, "TH", True),
    ("RGX-3C-AC", 3, "AC", True),
    ("RGX-4C-AC", 4, "AC", False),
    ("RGX-4C-BM", 4, "BM", True),
    ("RGX-5C-AC", 5, "AC", True),
    ("RGX-5C-BT", 5, "BT", True),
    ("RGX-6C-DC", 6, "DC", False),
]


@dataclass
class Part:
    key: str
    fam: str
    fr: str
    en: str
    kind: str  # pc | len | mass | vol
    mass: float | None
    sup: str
    group: str | None
    ref: str = ""
    abbr: str = ""


@dataclass
class SADesign:
    slot: str
    fam: str
    fr: str
    en: str
    lines: list[tuple[str, float]]
    ref: str = ""
    base_slot: str = ""


@dataclass
class Inst:
    variant: str
    slot: str
    sa: SADesign
    count: int
    lines: list[tuple[str, float]]
    sa_raw: str = ""


def _sig3(x: float) -> float:
    return float(f"{x:.3g}")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _abbr(fr: str) -> str:
    words = _strip_accents(fr).upper().replace("(", "").replace(")", "").split()
    out: list[str] = []
    for w in words:
        if w in SMALL_WORDS:
            continue
        if w.startswith(("D'", "L'")):
            w = w[2:]
        out.append(ABBR.get(w, w))
    return " ".join(out).replace("VIS TETE H", "VIS H").replace(";", "")


def _catalogue() -> list[Part]:
    c: list[Part] = []

    def p(
        key: str,
        fam: str,
        fr: str,
        en: str,
        kind: str,
        mass: float | None,
        sup: str,
        group: str | None = None,
    ) -> None:
        c.append(Part(key, fam, fr, en, kind, None if mass is None else _sig3(mass), sup, group))

    for d, ln in [(6, 20), (8, 25), (10, 30), (12, 40), (12, 50), (16, 40), (16, 60), (20, 80)]:
        m = 7.85e-6 * (0.785 * d * d * ln + 0.9 * d**3)
        p(
            f"screw_M{d}x{ln}",
            "FIX",
            f"Vis à tête hexagonale M{d}x{ln} classe 8.8 zinguée",
            f"Hex head screw M{d}x{ln} grade 8.8 zinc plated",
            "pc",
            m,
            "BR",
            "screw",
        )
    for d, ln in [(8, 25), (10, 30)]:
        m = 7.85e-6 * (0.785 * d * d * ln + 0.9 * d**3)
        p(
            f"screwA4_M{d}x{ln}",
            "FIX",
            f"Vis à tête hexagonale M{d}x{ln} inox A4",
            f"Hex head screw M{d}x{ln} stainless A4",
            "pc",
            m,
            "BR",
            "screw",
        )
    for d in [6, 8, 10, 12, 16, 20]:
        p(
            f"nut_M{d}",
            "FIX",
            f"Écrou hexagonal M{d} classe 8 zingué",
            f"Hex nut M{d} grade 8 zinc plated",
            "pc",
            7.85e-6 * 0.8 * d**3,
            "VIN",
            "nut",
        )
    for d in [10, 12, 16]:
        p(
            f"nutl_M{d}",
            "FIX",
            f"Écrou autofreiné M{d} classe 8 zingué",
            f"Self-locking nut M{d} grade 8 zinc plated",
            "pc",
            7.85e-6 * 0.95 * d**3,
            "BR",
            "nut",
        )
    for d in [6, 8, 10, 12, 16, 20]:
        m = 7.85e-6 * 0.785 * ((2.1 * d) ** 2 - (1.1 * d) ** 2) * 0.15 * d
        p(
            f"wash_M{d}",
            "FIX",
            f"Rondelle plate M{d} zinguée",
            f"Flat washer M{d} zinc plated",
            "pc",
            m,
            "BR",
            "washer",
        )
    p(
        "rivet_48",
        "FIX",
        "Rivet aveugle inox 4,8x12",
        "Blind rivet stainless 4.8x12",
        "pc",
        0.0018,
        "BR",
        "rivet",
    )
    p(
        "rivet_40",
        "FIX",
        "Rivet aveugle inox 4,0x10",
        "Blind rivet stainless 4.0x10",
        "pc",
        0.0012,
        "BR",
        "rivet",
    )

    p("oring_25", "JNT", "Joint torique 25x3 NBR", "O-ring 25x3 NBR", "pc", 0.0012, "PJ", "oring")
    p("oring_40", "JNT", "Joint torique 40x3 NBR", "O-ring 40x3 NBR", "pc", 0.0019, "PJ", "oring")
    p(
        "oring_40fkm",
        "JNT",
        "Joint torique 40x3 FKM",
        "O-ring 40x3 FKM (Viton)",
        "pc",
        0.0024,
        "EP",
        "oring",
    )
    p(
        "oring_63",
        "JNT",
        "Joint torique 63x3,5 NBR",
        "O-ring 63x3.5 NBR",
        "pc",
        0.0038,
        "PJ",
        "oring",
    )
    p(
        "seal_door",
        "JNT",
        "Joint de porte EPDM; profil creux 24x18",
        "Door seal EPDM hollow profile 24x18",
        "len",
        None,
        "PJ",
    )
    p(
        "seal_window",
        "JNT",
        "Joint de vitre EPDM en H 12 mm",
        "Window H-seal EPDM 12 mm",
        "len",
        None,
        "PJ",
    )
    p(
        "seal_roof",
        "JNT",
        "Joint de toiture CVC EPDM cellulaire",
        "HVAC roof seal, cellular EPDM",
        "len",
        None,
        "PJ",
    )
    p("gasket_dn50", "JNT", "Joint plat DN50 fibre", "Flat gasket DN50 fibre", "pc", 0.015, "PJ")

    for s in ["1,5", "2,5", "4", "16", "95"]:
        p(
            f"cab_{s.replace(',', '_')}",
            "CBL",
            f"Câble unipolaire {s} mm² 0,6/1 kV sans halogène",
            f"Single-core cable {s.replace(',', '.')} mm2 0.6/1 kV halogen-free",
            "len",
            None,
            "CN",
            "cable",
        )
    p(
        "cab_mvb",
        "CBL",
        "Câble blindé 2x0,75 mm² bus MVB",
        "Shielded cable 2x0.75 mm2 MVB bus",
        "len",
        None,
        "CN",
    )
    p(
        "cab_eth",
        "CBL",
        "Câble Ethernet Cat5e ferroviaire 4 paires",
        "Railway Ethernet cable Cat5e 4 pairs",
        "len",
        None,
        "CN",
    )
    p(
        "cab_ht",
        "CBL",
        "Câble haute tension 25 kV toiture",
        "25 kV roof high-voltage cable",
        "len",
        None,
        "CN",
    )
    p(
        "conduit",
        "CBL",
        "Gaine annelée PA12 NW23",
        "Corrugated conduit PA12 NW23",
        "len",
        None,
        "CX",
    )
    p(
        "tie_s",
        "CBL",
        "Collier de serrage PA 4,8x200",
        "Cable tie PA 4.8x200",
        "pc",
        0.002,
        "CX",
        "tie",
    )
    p(
        "tie_l",
        "CBL",
        "Collier de serrage PA 7,6x300",
        "Cable tie PA 7.6x300",
        "pc",
        0.004,
        "CX",
        "tie",
    )
    p(
        "conn_19",
        "CNX",
        "Connecteur circulaire 19 broches",
        "Circular connector 19 pins",
        "pc",
        0.12,
        "CX",
        "conn",
    )
    p(
        "conn_37",
        "CNX",
        "Connecteur circulaire 37 broches",
        "Circular connector 37 pins",
        "pc",
        0.21,
        "CX",
        "conn",
    )
    p(
        "conn_m12",
        "CNX",
        "Connecteur M12 4 points codage D",
        "M12 connector 4-pin D-coded",
        "pc",
        0.03,
        "CX",
    )
    p("lug_16", "CNX", "Cosse à sertir 16 mm² M8", "Crimp lug 16 mm2 M8", "pc", 0.008, "CX", "lug")
    p(
        "lug_95",
        "CNX",
        "Cosse à sertir 95 mm² M12",
        "Crimp lug 95 mm2 M12",
        "pc",
        0.045,
        "CX",
        "lug",
    )
    p("tblock", "CNX", "Bornier 10 voies", "Terminal block 10 ways", "pc", 0.09, "CX")

    p(
        "frame_m",
        "BOG",
        "Châssis de bogie moteur soudé",
        "Motor bogie frame, welded",
        "pc",
        1850,
        "AMH",
        "frame",
    )
    p(
        "frame_t",
        "BOG",
        "Châssis de bogie porteur soudé",
        "Trailer bogie frame, welded",
        "pc",
        1620,
        "AMH",
        "frame",
    )
    p(
        "ws_m",
        "BOG",
        "Essieu monté moteur roues Ø850",
        "Motor wheelset, Ø850 wheels",
        "pc",
        1380,
        "AMH",
        "ws",
    )
    p(
        "ws_t",
        "BOG",
        "Essieu monté porteur roues Ø850",
        "Trailer wheelset, Ø850 wheels",
        "pc",
        1160,
        "AMH",
        "ws",
    )
    p(
        "axlebox",
        "BOG",
        "Boîte d'essieu fonte GS",
        "Axle box housing, ductile iron",
        "pc",
        86,
        "AMH",
    )
    p(
        "bearing",
        "BOG",
        "Roulement cartouche TBU 130x230",
        "Tapered bearing unit TBU 130x230",
        "pc",
        32.5,
        "RP",
    )
    p(
        "spring_p",
        "BOG",
        "Ressort hélicoïdal de suspension primaire",
        "Primary suspension coil spring",
        "pc",
        47,
        "RSA",
    )
    p(
        "airspring_1",
        "BOG",
        "Ressort pneumatique de suspension secondaire gén. 1",
        "Secondary air spring gen. 1",
        "pc",
        62,
        "RSA",
        "airspring",
    )
    p(
        "airspring_2",
        "BOG",
        "Ressort pneumatique de suspension secondaire gén. 2",
        "Secondary air spring gen. 2",
        "pc",
        57.5,
        "RSA",
        "airspring",
    )
    p(
        "damp_v",
        "BOG",
        "Amortisseur vertical secondaire",
        "Secondary vertical damper",
        "pc",
        12.5,
        "RSA",
        "damp",
    )
    p("damp_l", "BOG", "Amortisseur transversal", "Lateral damper", "pc", 9.8, "RSA", "damp")
    p("damp_y", "BOG", "Amortisseur anti-lacet", "Yaw damper", "pc", 21, "RSA", "damp")
    p("arb", "BOG", "Barre anti-roulis", "Anti-roll bar", "pc", 146, "AMH")
    p("trod", "BOG", "Bielle de traction", "Traction rod", "pc", 38, "AMH")
    p("gearbox", "BOG", "Réducteur d'essieu", "Axle gearbox", "pc", 615, "ET")
    p(
        "motbracket",
        "BOG",
        "Support de suspension moteur",
        "Motor suspension bracket",
        "pc",
        54,
        "AMH",
    )
    p(
        "ebrush",
        "BOG",
        "Dispositif de retour courant (balai de terre)",
        "Earthing brush device",
        "pc",
        6.2,
        "CAP",
    )
    p("sandbox", "BOG", "Sablière avec réservoir 30 l", "Sander with 30 l sand box", "pc", 28, "PF")
    p("flangelub", "BOG", "Graisseur de boudin", "Wheel flange lubricator", "pc", 14, "PF")

    p(
        "disc_wheel",
        "FRN",
        "Disque de frein sur roue",
        "Wheel-mounted brake disc",
        "pc",
        108,
        "FS",
        "disc",
    )
    p(
        "disc_axle",
        "FRN",
        "Disque de frein sur essieu Ø640",
        "Axle-mounted brake disc Ø640",
        "pc",
        124,
        "FS",
        "disc",
    )
    p(
        "caliper",
        "FRN",
        "Étrier de frein à disque compact",
        "Compact disc brake caliper",
        "pc",
        68,
        "FS",
    )
    p(
        "pad_org",
        "FRN",
        "Garniture de frein organique",
        "Brake pad, organic",
        "pc",
        4.2,
        "FS",
        "pad",
    )
    p(
        "pad_sint",
        "FRN",
        "Garniture de frein frittée",
        "Brake pad, sintered",
        "pc",
        4.6,
        "FS",
        "pad",
    )
    p(
        "cyl_park",
        "FRN",
        "Cylindre de frein d'immobilisation à ressort",
        "Spring-applied parking brake cylinder",
        "pc",
        22,
        "FS",
    )
    p(
        "panel_frame",
        "FRN",
        "Châssis de panneau pneumatique de frein",
        "Brake pneumatic panel frame",
        "pc",
        95,
        "FS",
    )
    p("relay_valve", "FRN", "Valve relais de frein", "Brake relay valve", "pc", 6.8, "FS")
    p("distributor", "FRN", "Distributeur de frein UIC", "UIC brake distributor", "pc", 9.4, "FS")
    p(
        "ptrans",
        "FRN",
        "Capteur de pression 0-10 bar",
        "Pressure transducer 0-10 bar",
        "pc",
        0.32,
        "FS",
    )
    p("ballvalve", "FRN", "Robinet à boisseau sphérique DN15", "Ball valve DN15", "pc", 0.85, "PF")
    p("hose", "FRN", "Flexible de frein DN25 L=600", "Brake hose DN25 L=600", "pc", 1.9, "PF")
    p("antiskid", "FRN", "Capteur anti-enrayage", "Wheel slide protection sensor", "pc", 0.6, "FS")
    p("bcu", "FRN", "Calculateur de frein (BCU)", "Brake control unit (BCU)", "pc", 8.5, "FS")

    p(
        "compressor",
        "PAR",
        "Compresseur à vis 1500 l/min",
        "Screw compressor 1500 l/min",
        "pc",
        310,
        "PF",
    )
    p("dryer", "PAR", "Dessiccateur bi-colonne", "Twin-tower air dryer", "pc", 42, "PF")
    p(
        "res100",
        "PAR",
        "Réservoir d'air principal 100 l",
        "Main air reservoir 100 l",
        "pc",
        58,
        "PF",
        "res",
    )
    p(
        "res50",
        "PAR",
        "Réservoir d'air auxiliaire 50 l",
        "Auxiliary air reservoir 50 l",
        "pc",
        34,
        "PF",
        "res",
    )
    p("safetyvalve", "PAR", "Soupape de sécurité 10 bar", "Safety valve 10 bar", "pc", 0.9, "PF")
    p(
        "intakefilter",
        "PAR",
        "Filtre d'aspiration compresseur",
        "Compressor intake filter",
        "pc",
        3.1,
        "PF",
    )
    p(
        "drain",
        "PAR",
        "Purgeur automatique de condensats",
        "Automatic condensate drain",
        "pc",
        1.4,
        "PF",
    )

    p(
        "panto_ac",
        "PTG",
        "Pantographe unijambiste 25 kV",
        "Single-arm pantograph 25 kV",
        "pc",
        195,
        "CAP",
        "panto",
    )
    p(
        "panto_dc",
        "PTG",
        "Pantographe unijambiste 1,5 kV continu",
        "Single-arm pantograph 1.5 kV DC",
        "pc",
        228,
        "CAP",
        "panto",
    )
    p(
        "insulator",
        "PTG",
        "Isolateur de toiture composite",
        "Composite roof insulator",
        "pc",
        14,
        "CAP",
    )
    p(
        "vcb",
        "PTG",
        "Disjoncteur principal sous vide 25 kV",
        "Vacuum circuit breaker 25 kV",
        "pc",
        182,
        "CAP",
    )
    p("arrester", "PTG", "Parafoudre 25 kV", "Surge arrester 25 kV", "pc", 11, "CAP")
    p("carbon", "PTG", "Bande de frottement carbone", "Carbon contact strip", "pc", 3.2, "CAP")
    p(
        "addvalve",
        "PTG",
        "Valve ADD de détection d'abaissement",
        "Automatic dropping device (ADD) valve",
        "pc",
        1.1,
        "CAP",
    )
    p("busbar", "PTG", "Barre de liaison toiture cuivre", "Copper roof busbar", "pc", 22, "CAP")

    p(
        "converter",
        "TRC",
        "Convertisseur de traction IGBT",
        "IGBT traction converter",
        "pc",
        1450,
        "ET",
    )
    p(
        "tmotor",
        "TRC",
        "Moteur de traction asynchrone 400 kW",
        "Asynchronous traction motor 400 kW",
        "pc",
        720,
        "ET",
    )
    p(
        "transformer",
        "TRC",
        "Transformateur principal 25 kV",
        "Main transformer 25 kV",
        "pc",
        3200,
        "TRF",
    )
    p(
        "coolfan",
        "TRC",
        "Motoventilateur de refroidissement traction",
        "Traction cooling fan unit",
        "pc",
        48,
        "ET",
    )
    p("inductance", "TRC", "Self de ligne", "Line inductor", "pc", 210, "TRF")
    p("contactor", "TRC", "Contacteur de ligne 1500 A", "Line contactor 1500 A", "pc", 7.5, "ET")
    p("speedsensor", "TRC", "Capteur de vitesse moteur", "Motor speed sensor", "pc", 0.45, "ET")
    p(
        "coolant",
        "TRC",
        "Liquide de refroidissement glycol 35 %",
        "Glycol coolant 35 %",
        "vol",
        None,
        "CHI",
    )
    p(
        "ventgrid",
        "TRC",
        "Grille de ventilation moteur",
        "Motor ventilation grille",
        "pc",
        2.3,
        "ET",
    )

    p(
        "engine",
        "GEN",
        "Moteur diesel 390 kW Stage V",
        "Diesel engine 390 kW Stage V",
        "pc",
        1250,
        "MDL",
    )
    p("alternator", "GEN", "Alternateur de traction", "Traction alternator", "pc", 680, "MDL")
    p("fueltank", "GEN", "Réservoir de carburant 1000 l", "Fuel tank 1000 l", "pc", 240, "MDL")
    p("silencer", "GEN", "Silencieux d'échappement", "Exhaust silencer", "pc", 85, "MDL")
    p(
        "radiator",
        "GEN",
        "Radiateur de refroidissement moteur",
        "Engine cooling radiator",
        "pc",
        160,
        "MDL",
    )
    p("engineoil", "GEN", "Huile moteur 10W40", "Engine oil 10W40", "vol", None, "CHI")
    p("ppframe", "GEN", "Châssis de groupe motopropulseur", "Power pack frame", "pc", 420, "AMH")
    p("fuelfilter", "GEN", "Filtre à gazole", "Diesel fuel filter", "pc", 1.2, "MDL")

    p(
        "hvac_sal",
        "CVC",
        "Groupe de climatisation salle 35 kW",
        "Saloon HVAC roof unit 35 kW",
        "pc",
        720,
        "CR",
        "hvac",
    )
    p(
        "hvac_cab",
        "CVC",
        "Groupe de climatisation cabine 6 kW",
        "Cab HVAC unit 6 kW",
        "pc",
        140,
        "CR",
        "hvac",
    )
    p("evapfan", "CVC", "Ventilateur d'évaporateur", "Evaporator fan", "pc", 18, "CR")
    p("condfan", "CVC", "Ventilateur de condenseur", "Condenser fan", "pc", 21, "CR")
    p(
        "refrigerant",
        "CVC",
        "Fluide frigorigène R1234ze",
        "Refrigerant R1234ze",
        "mass",
        None,
        "CHI",
    )
    p("duct", "CVC", "Gaine de soufflage isolée", "Insulated supply air duct", "len", None, "CR")
    p("filterg4", "CVC", "Filtre à air G4 592x287x48", "Air filter G4 592x287x48", "pc", 0.9, "CR")
    p("tsensor", "CVC", "Sonde de température PT100", "PT100 temperature sensor", "pc", 0.08, "CR")
    p("hvacctrl", "CVC", "Régulateur CVC", "HVAC controller", "pc", 4.6, "CR")
    p("heater", "CVC", "Résistance de chauffage 3 kW", "Heating element 3 kW", "pc", 2.8, "CR")
    p(
        "floorheater",
        "CVC",
        "Convecteur de chauffage au plancher",
        "Floor convector heater",
        "pc",
        6.5,
        "CR",
    )

    p(
        "leaf_l",
        "POR",
        "Vantail de porte d'accès gauche",
        "Access door leaf, left-hand",
        "pc",
        78,
        "PS",
        "leaf",
    )
    p(
        "leaf_r",
        "POR",
        "Vantail de porte d'accès droit",
        "Access door leaf, right-hand",
        "pc",
        78,
        "PS",
        "leaf",
    )
    p("drive", "POR", "Opérateur de porte électrique", "Electric door operator", "pc", 36, "PS")
    p(
        "rail_l",
        "POR",
        "Rail de guidage supérieur gauche",
        "Upper guide rail, left-hand",
        "pc",
        9.5,
        "PS",
        "rail",
    )
    p(
        "rail_r",
        "POR",
        "Rail de guidage supérieur droit",
        "Upper guide rail, right-hand",
        "pc",
        9.5,
        "PS",
        "rail",
    )
    p(
        "cover_l",
        "POR",
        "Capot d'habillage mécanisme gauche",
        "Mechanism cover, left-hand",
        "pc",
        4.2,
        "PS",
        "cover",
    )
    p(
        "cover_r",
        "POR",
        "Capot d'habillage mécanisme droit",
        "Mechanism cover, right-hand",
        "pc",
        4.2,
        "PS",
        "cover",
    )
    p("step", "POR", "Marche mobile", "Sliding step", "pc", 54, "PS")
    p(
        "pushbtn",
        "POR",
        "Bouton poussoir d'ouverture lumineux",
        "Illuminated door open push button",
        "pc",
        0.25,
        "PS",
    )
    p(
        "emhandle",
        "POR",
        "Poignée d'ouverture d'urgence",
        "Emergency release handle",
        "pc",
        0.9,
        "PS",
    )
    p("dcu", "POR", "Calculateur de porte (DCU)", "Door control unit (DCU)", "pc", 2.1, "PS")
    p("lock", "POR", "Dispositif de verrouillage", "Door locking device", "pc", 3.4, "PS")
    p(
        "interdoor",
        "POR",
        "Porte d'intercirculation coulissante",
        "Sliding gangway door",
        "pc",
        48,
        "PS",
    )

    p("desk", "CAB", "Pupitre de conduite", "Driver desk", "pc", 240, "PC")
    p("dseat", "CAB", "Siège conducteur réglable", "Adjustable driver seat", "pc", 38, "SCF")
    p(
        "windscreen",
        "CAB",
        "Pare-brise chauffant feuilleté",
        "Heated laminated windscreen",
        "pc",
        95,
        "VTE",
    )
    p("wiper", "CAB", "Moteur d'essuie-glace", "Wiper motor", "pc", 7.8, "PC")
    p(
        "mastercontroller",
        "CAB",
        "Manipulateur traction/freinage",
        "Master controller",
        "pc",
        12,
        "PC",
    )
    p("horn", "CAB", "Avertisseur sonore deux tons", "Two-tone horn", "pc", 4.5, "PC")
    p("headlight", "CAB", "Phare LED", "LED headlight", "pc", 6.2, "LUM")
    p("markerlight", "CAB", "Feu de position LED", "LED marker light", "pc", 1.6, "LUM")
    p("camera", "CAB", "Caméra de rétrovision", "Rear-view camera", "pc", 0.9, "IB")
    p("sunblind", "CAB", "Store pare-soleil", "Sun blind", "pc", 2.4, "PC")

    p("seat1", "AME", "Siège double 1re classe", "Double seat, 1st class", "pc", 58, "SCF", "seat")
    p("seat2", "AME", "Siège double 2e classe", "Double seat, 2nd class", "pc", 44, "SCF", "seat")
    p("foldseat", "AME", "Strapontin", "Tip-up seat", "pc", 12, "SCF")
    p("armrest", "AME", "Accoudoir", "Armrest", "pc", 1.3, "SCF")
    p("table", "AME", "Tablette rabattable", "Fold-down table", "pc", 4.8, "SCF")
    p(
        "fabric1",
        "AME",
        "Tissu de garnissage 1re classe",
        "Upholstery fabric, 1st class",
        "len",
        None,
        "SCF",
        "fabric",
    )
    p(
        "fabric2",
        "AME",
        "Tissu de garnissage 2e classe",
        "Upholstery fabric, 2nd class",
        "len",
        None,
        "SCF",
        "fabric",
    )
    p(
        "seatrail",
        "AME",
        "Rail de fixation sièges aluminium",
        "Aluminium seat fixing rail",
        "len",
        None,
        "SCF",
    )

    p("led1200", "ECL", "Réglette LED 1200 mm", "LED strip light 1200 mm", "pc", 1.8, "LUM", "led")
    p("led1500", "ECL", "Réglette LED 1500 mm", "LED strip light 1500 mm", "pc", 2.2, "LUM", "led")
    p("leddriver", "ECL", "Alimentation LED 110 V", "LED driver 110 V", "pc", 0.6, "LUM")
    p("emlight", "ECL", "Bloc d'éclairage de secours", "Emergency lighting unit", "pc", 1.1, "LUM")
    p("readlight", "ECL", "Liseuse LED", "LED reading light", "pc", 0.35, "LUM")

    p(
        "wc_pmr",
        "SAN",
        "Module WC universel PMR",
        "Universal access toilet module (PRM)",
        "pc",
        680,
        "HRM",
        "wc",
    )
    p("wc_std", "SAN", "Module WC standard", "Standard toilet module", "pc", 410, "HRM", "wc")
    p("vacbowl", "SAN", "Cuvette WC à dépression", "Vacuum toilet bowl", "pc", 28, "HRM")
    p("basin", "SAN", "Lave-mains inox", "Stainless wash basin", "pc", 14, "HRM")
    p(
        "cleantank",
        "SAN",
        "Réservoir d'eau propre 200 l",
        "Fresh water tank 200 l",
        "pc",
        46,
        "HRM",
        "tank",
    )
    p(
        "wastetank",
        "SAN",
        "Réservoir d'eaux usées 300 l",
        "Waste water tank 300 l",
        "pc",
        72,
        "HRM",
        "tank",
    )
    p("handdryer", "SAN", "Sèche-mains", "Hand dryer", "pc", 3.9, "HRM")
    p("grabbar", "SAN", "Barre d'appui inox", "Stainless grab bar", "pc", 2.7, "HRM")
    p("wcctrl", "SAN", "Automate de commande WC", "Toilet control PLC", "pc", 2.2, "HRM")

    p(
        "couplerhead",
        "ATT",
        "Tête d'attelage automatique type 10",
        "Automatic coupler head type 10",
        "pc",
        420,
        "ASD",
    )
    p("draftgear", "ATT", "Appareil de choc et traction", "Draft gear", "pc", 180, "ASD")
    p(
        "ecoupler",
        "ATT",
        "Coupleur électrique automatique",
        "Automatic electrical coupler",
        "pc",
        95,
        "ASD",
    )
    p("couplercover", "ATT", "Capot d'attelage avant", "Front coupler cover", "pc", 24, "ASD")
    p(
        "emadapter",
        "ATT",
        "Adaptateur d'attelage de secours",
        "Emergency coupling adapter",
        "pc",
        65,
        "ASD",
    )

    p(
        "frontdisp",
        "PIS",
        "Girouette frontale LED",
        "Front LED destination display",
        "pc",
        8.5,
        "IB",
    )
    p("sidedisp", "PIS", "Afficheur latéral", "Side destination display", "pc", 5.2, "IB")
    p("tft", "PIS", "Écran TFT 18,5 pouces", "TFT screen 18.5 inch", "pc", 3.6, "IB")
    p("speaker", "PIS", "Haut-parleur", "Loudspeaker", "pc", 0.8, "IB")
    p("cctv", "PIS", "Caméra de vidéoprotection", "CCTV camera", "pc", 0.7, "IB")
    p(
        "pisctrl",
        "PIS",
        "Calculateur information voyageurs",
        "Passenger information controller",
        "pc",
        4.1,
        "IB",
    )
    p(
        "counter",
        "PIS",
        "Capteur de comptage voyageurs",
        "Passenger counting sensor",
        "pc",
        0.5,
        "IB",
    )
    p("intercom", "PIS", "Interphone d'urgence", "Emergency intercom", "pc", 1.3, "IB")

    p("kvb", "SIG", "Antenne KVB", "KVB antenna", "pc", 11, "SR")
    p("evc", "SIG", "Calculateur ETCS (EVC)", "ETCS on-board computer (EVC)", "pc", 38, "SR")
    p("radar", "SIG", "Radar odométrique", "Odometry radar", "pc", 2.9, "SR")
    p("balise", "SIG", "Antenne de lecture balise", "Balise transmission antenna", "pc", 24, "SR")
    p("dmi", "SIG", "Écran DMI conducteur", "Driver DMI screen", "pc", 6.8, "SR")
    p("gsmr", "SIG", "Radio sol-train GSM-R", "GSM-R cab radio", "pc", 7.5, "SR")

    p("grease", "CON", "Graisse lithium EP2", "Lithium grease EP2", "mass", None, "CHI")
    p("threadlock", "CON", "Frein filet moyen", "Threadlocker, medium strength", "vol", None, "CHI")
    p("primer", "CON", "Primaire d'accrochage époxy", "Epoxy primer", "vol", None, "CHI")
    p("sealant", "CON", "Mastic polyuréthane", "Polyurethane sealant", "vol", None, "CHI")
    p("labelset", "CON", "Jeu d'étiquettes de signalétique", "Signage label set", "pc", 0.05, "IB")
    p(
        "idplate",
        "CON",
        "Plaque d'identification gravée",
        "Engraved identification plate",
        "pc",
        0.04,
        "IB",
    )
    for part in c:
        part.abbr = _abbr(part.fr)
    return c


SA_SPECS: dict[str, tuple[str, str, str, list[tuple[str, float]]]] = {
    "BOG_M": (
        "BOG",
        "Bogie moteur équipé",
        "Motor bogie assembly",
        [
            ("frame_m", 1),
            ("ws_m", 2),
            ("axlebox", 4),
            ("bearing", 4),
            ("spring_p", 8),
            ("airspring_1", 2),
            ("damp_v", 2),
            ("damp_l", 2),
            ("damp_y", 2),
            ("arb", 1),
            ("trod", 1),
            ("gearbox", 2),
            ("disc_wheel", 4),
            ("screw_M16x60", 24),
            ("grease", 1.2),
        ],
    ),
    "BOG_T": (
        "BOG",
        "Bogie porteur équipé",
        "Trailer bogie assembly",
        [
            ("frame_t", 1),
            ("ws_t", 2),
            ("axlebox", 4),
            ("bearing", 4),
            ("spring_p", 8),
            ("airspring_1", 2),
            ("damp_v", 2),
            ("damp_l", 2),
            ("arb", 1),
            ("trod", 1),
            ("disc_axle", 6),
            ("flangelub", 1),
            ("screw_M16x60", 16),
            ("nutl_M16", 16),
        ],
    ),
    "FRN_UNIT": (
        "FRN",
        "Ensemble frein à disque bogie",
        "Bogie disc brake set",
        [
            ("caliper", 4),
            ("pad_org", 8),
            ("cyl_park", 2),
            ("hose", 4),
            ("antiskid", 2),
            ("screw_M12x50", 16),
            ("threadlock", 0.02),
        ],
    ),
    "FRN_PANEL": (
        "FRN",
        "Panneau pneumatique de frein",
        "Brake pneumatic panel",
        [
            ("panel_frame", 1),
            ("relay_valve", 1),
            ("distributor", 1),
            ("ptrans", 3),
            ("ballvalve", 4),
            ("bcu", 1),
            ("oring_25", 8),
            ("screw_M10x30", 12),
        ],
    ),
    "PAR": (
        "PAR",
        "Production d'air comprimé",
        "Compressed air supply unit",
        [
            ("compressor", 1),
            ("dryer", 1),
            ("res100", 1),
            ("res50", 2),
            ("safetyvalve", 2),
            ("intakefilter", 1),
            ("drain", 2),
            ("gasket_dn50", 4),
            ("screw_M16x40", 8),
        ],
    ),
    "PTG_AC": (
        "PTG",
        "Équipement de toiture 25 kV",
        "25 kV roof equipment",
        [
            ("panto_ac", 1),
            ("insulator", 4),
            ("vcb", 1),
            ("arrester", 1),
            ("carbon", 2),
            ("addvalve", 1),
            ("transformer", 1),
            ("cab_ht", 8.5),
            ("busbar", 2),
            ("screw_M12x40", 16),
        ],
    ),
    "PTG_DC": (
        "PTG",
        "Équipement de toiture 1,5 kV",
        "1.5 kV DC roof equipment",
        [
            ("panto_dc", 1),
            ("insulator", 4),
            ("carbon", 2),
            ("addvalve", 1),
            ("busbar", 2),
            ("cab_95", 12),
            ("lug_95", 4),
            ("screw_M12x40", 16),
        ],
    ),
    "TRC_CONV": (
        "TRC",
        "Coffre de traction",
        "Traction converter box",
        [
            ("converter", 1),
            ("inductance", 1),
            ("coolfan", 2),
            ("contactor", 4),
            ("coolant", 18),
            ("cab_95", 24),
            ("conn_37", 4),
            ("screw_M12x50", 12),
        ],
    ),
    "TRC_MOT": (
        "TRC",
        "Ensemble moteur de traction",
        "Traction motor set",
        [
            ("tmotor", 1),
            ("speedsensor", 2),
            ("ventgrid", 2),
            ("lug_95", 3),
            ("conn_m12", 2),
            ("screw_M20x80", 8),
        ],
    ),
    "GEN": (
        "GEN",
        "Groupe motopropulseur diesel",
        "Diesel power pack",
        [
            ("engine", 1),
            ("alternator", 1),
            ("fueltank", 1),
            ("silencer", 1),
            ("radiator", 1),
            ("engineoil", 42),
            ("ppframe", 1),
            ("fuelfilter", 2),
            ("coolant", 45),
            ("screw_M20x80", 12),
            ("wash_M20", 12),
        ],
    ),
    "CVC_SAL": (
        "CVC",
        "Climatisation salle voyageurs",
        "Saloon HVAC",
        [
            ("hvac_sal", 1),
            ("evapfan", 2),
            ("condfan", 2),
            ("refrigerant", 7.5),
            ("duct", 14),
            ("filterg4", 4),
            ("tsensor", 3),
            ("hvacctrl", 1),
            ("heater", 4),
            ("floorheater", 6),
            ("seal_roof", 9.2),
            ("screw_M10x30", 16),
        ],
    ),
    "CVC_CAB": (
        "CVC",
        "Climatisation cabine de conduite",
        "Driver cab HVAC",
        [
            ("hvac_cab", 1),
            ("evapfan", 1),
            ("condfan", 1),
            ("refrigerant", 1.8),
            ("duct", 3.5),
            ("filterg4", 1),
            ("tsensor", 2),
            ("hvacctrl", 1),
            ("heater", 1),
            ("seal_roof", 3.2),
            ("screw_M8x25", 8),
        ],
    ),
    "POR_G": (
        "POR",
        "Porte d'accès voyageurs côté gauche",
        "Passenger access door, left-hand",
        [
            ("leaf_l", 1),
            ("drive", 1),
            ("rail_l", 1),
            ("cover_l", 1),
            ("step", 1),
            ("seal_door", 6.8),
            ("pushbtn", 2),
            ("emhandle", 1),
            ("dcu", 1),
            ("lock", 1),
            ("screw_M8x25", 12),
        ],
    ),
    "POR_D": (
        "POR",
        "Porte d'accès voyageurs côté droit",
        "Passenger access door, right-hand",
        [
            ("leaf_r", 1),
            ("drive", 1),
            ("rail_r", 1),
            ("cover_r", 1),
            ("step", 1),
            ("seal_door", 6.8),
            ("pushbtn", 2),
            ("emhandle", 1),
            ("dcu", 1),
            ("lock", 1),
            ("screw_M8x25", 12),
        ],
    ),
    "CAB": (
        "CAB",
        "Aménagement cabine de conduite",
        "Driver cab fit-out",
        [
            ("desk", 1),
            ("dseat", 1),
            ("windscreen", 1),
            ("wiper", 1),
            ("mastercontroller", 1),
            ("horn", 1),
            ("headlight", 2),
            ("markerlight", 4),
            ("camera", 2),
            ("sunblind", 1),
            ("seal_window", 7.4),
            ("cab_mvb", 22),
        ],
    ),
    "AME_1": (
        "AME",
        "Aménagement sièges 1re classe",
        "1st class seating",
        [
            ("seat1", 12),
            ("armrest", 12),
            ("table", 6),
            ("fabric1", 14),
            ("seatrail", 22),
            ("screw_M10x30", 48),
        ],
    ),
    "AME_2": (
        "AME",
        "Aménagement sièges 2e classe",
        "2nd class seating",
        [
            ("seat2", 20),
            ("foldseat", 4),
            ("armrest", 8),
            ("fabric2", 28),
            ("seatrail", 36),
            ("screw_M10x30", 80),
        ],
    ),
    "ECL": (
        "ECL",
        "Éclairage salle voyageurs",
        "Saloon lighting",
        [
            ("led1200", 24),
            ("led1500", 6),
            ("leddriver", 15),
            ("emlight", 6),
            ("readlight", 12),
            ("cab_1_5", 60),
            ("rivet_40", 40),
        ],
    ),
    "WC_PMR": (
        "SAN",
        "Toilettes universelles PMR",
        "Universal access toilet (PRM)",
        [
            ("wc_pmr", 1),
            ("vacbowl", 1),
            ("basin", 1),
            ("cleantank", 1),
            ("wastetank", 1),
            ("handdryer", 1),
            ("grabbar", 4),
            ("wcctrl", 1),
            ("oring_40", 6),
            ("screwA4_M8x25", 12),
            ("sealant", 0.3),
        ],
    ),
    "WC_STD": (
        "SAN",
        "Toilettes standard",
        "Standard toilet",
        [
            ("wc_std", 1),
            ("vacbowl", 1),
            ("basin", 1),
            ("wastetank", 1),
            ("handdryer", 1),
            ("grabbar", 1),
            ("wcctrl", 1),
            ("oring_40", 6),
            ("screwA4_M10x30", 8),
            ("sealant", 0.2),
        ],
    ),
    "ATT_AUTO": (
        "ATT",
        "Attelage automatique d'extrémité",
        "End automatic coupler",
        [
            ("couplerhead", 1),
            ("draftgear", 1),
            ("ecoupler", 1),
            ("couplercover", 1),
            ("screw_M20x80", 8),
            ("nut_M20", 8),
            ("cab_mvb", 10),
            ("grease", 0.5),
        ],
    ),
    "CBL": (
        "CBL",
        "Câblage de caisse",
        "Carbody wiring harness",
        [
            ("cab_1_5", 450),
            ("cab_2_5", 220),
            ("cab_4", 120),
            ("cab_16", 40),
            ("cab_mvb", 85),
            ("cab_eth", 60),
            ("conduit", 140),
            ("tie_s", 800),
            ("conn_19", 24),
            ("conn_m12", 18),
            ("lug_16", 20),
            ("tblock", 30),
        ],
    ),
    "PIS": (
        "PIS",
        "Information voyageurs et vidéo",
        "Passenger information & CCTV",
        [
            ("frontdisp", 1),
            ("sidedisp", 4),
            ("tft", 6),
            ("speaker", 10),
            ("cctv", 6),
            ("pisctrl", 1),
            ("counter", 4),
            ("intercom", 4),
            ("cab_eth", 45),
            ("conn_m12", 30),
        ],
    ),
    "SIG": (
        "SIG",
        "Équipement de signalisation embarquée",
        "On-board signalling equipment",
        [
            ("kvb", 1),
            ("evc", 1),
            ("radar", 1),
            ("balise", 1),
            ("dmi", 1),
            ("gsmr", 1),
            ("conn_37", 4),
            ("cab_mvb", 18),
            ("screw_M12x40", 8),
        ],
    ),
}
DISTRACTOR_SLOTS = [
    ("BOG_M", "BOG_T"),
    ("PTG_AC", "PTG_DC"),
    ("CVC_SAL", "CVC_CAB"),
    ("POR_G", "POR_D"),
    ("AME_1", "AME_2"),
    ("WC_PMR", "WC_STD"),
]
CLONE_CANDIDATES = [
    "CVC_SAL",
    "POR_G",
    "AME_2",
    "ECL",
    "CBL",
    "PIS",
    "WC_PMR",
    "FRN_PANEL",
    "ATT_AUTO",
    "SIG",
    "CAB",
    "PAR",
    "FRN_UNIT",
    "TRC_MOT",
    "BOG_T",
]
CLONE_SUFFIX = [
    (" - version B", " - version B"),
    (" (programme Grand Est)", " (Grand Est programme)"),
    (" ind. 2", " rev. 2"),
    (" - variante longue", " - long variant"),
    (" série 2", " batch 2"),
    (" (projet AURA)", " (AURA project)"),
]


def _slots_for(cars: int, power: str, first: bool) -> list[tuple[str, int]]:
    motor = 2 if cars <= 3 else 3
    s = [
        ("BOG_M", motor),
        ("BOG_T", cars + 1 - motor),
        ("FRN_UNIT", cars + 1),
        ("FRN_PANEL", cars),
        ("PAR", 1 if cars <= 3 else 2),
    ]
    if power in ("AC", "BM", "BT"):
        s.append(("PTG_AC", 1 if cars <= 4 else 2))
    if power in ("DC", "BT"):
        s.append(("PTG_DC", 1 if cars <= 4 else 2))
    s += [("TRC_CONV", motor), ("TRC_MOT", motor * 2)]
    if power in ("TH", "BM"):
        s.append(("GEN", 1 if cars <= 2 else 2))
    s += [("CVC_SAL", cars), ("CVC_CAB", 2), ("POR_G", cars * 2), ("POR_D", cars * 2), ("CAB", 2)]
    if first:
        s.append(("AME_1", 1))
    s += [("AME_2", cars), ("ECL", cars), ("WC_PMR", 1)]
    if cars >= 4:
        s.append(("WC_STD", 1 if cars < 6 else 2))
    s += [("ATT_AUTO", 2), ("CBL", cars), ("PIS", 1), ("SIG", 2)]
    return s


# ---------------------------------------------------------------- formatting helpers


def _num(x: float, dec: int, comma: bool, strip: bool = True) -> str:
    s = f"{x:.{dec}f}"
    if strip and "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",") if comma else s


class Gen:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.parts: dict[str, Part] = {}
        self.used_numbers: set[int] = set()
        self.raw_map: dict[str, str] = {}
        self.inconsistencies: list[dict[str, object]] = []
        self.meta: dict[str, object] = {"seed": seed}

    # ------------------------------------------------------------ references
    def _alloc(self, n: int) -> int:
        while True:
            base = self.rng.randint(100000, 999999 - n)
            if all(b not in self.used_numbers for b in range(base, base + n)):
                self.used_numbers.update(range(base, base + n))
                return base

    def _new_part(
        self, proto: Part, key: str, fr: str, en: str, sup: str, mass: float | None
    ) -> Part:
        part = Part(key, proto.fam, fr, en, proto.kind, mass, sup, None)
        part.abbr = _abbr(fr)
        part.ref = f"{proto.fam}-{self._alloc(1)}"
        self.parts[key] = part
        return part

    def build_parts(self) -> None:
        cat = _catalogue()
        groups: dict[str, list[Part]] = {}
        for part in cat:
            self.parts[part.key] = part
            if part.group:
                groups.setdefault(part.group, []).append(part)
        for members in groups.values():
            base = self._alloc(len(members))
            for i, part in enumerate(members):
                part.ref = f"{part.fam}-{base + i}"
        for part in cat:
            if not part.ref:
                part.ref = f"{part.fam}-{self._alloc(1)}"

    def build_sas(self) -> dict[str, SADesign]:
        used: set[int] = set()

        def alloc(n: int) -> int:
            while True:
                b = self.rng.randint(100, 999 - n)
                if all(x not in used for x in range(b, b + n)):
                    used.update(range(b, b + n))
                    return b

        sas: dict[str, SADesign] = {}
        for slot, (fam, fr, en, lines) in SA_SPECS.items():
            sas[slot] = SADesign(slot, fam, fr, en, list(lines), base_slot=slot)
        for a, b in DISTRACTOR_SLOTS:
            n = alloc(2)
            sas[a].ref = f"SE-{sas[a].fam}-{n}"
            sas[b].ref = f"SE-{sas[b].fam}-{n + 1}"
        for sa in sas.values():
            if not sa.ref:
                sa.ref = f"SE-{sa.fam}-{alloc(1)}"
        self._sa_alloc = alloc
        return sas

    # ------------------------------------------------------------ structure
    def build_instances(self, sas: dict[str, SADesign]) -> list[Inst]:
        rng = self.rng
        insts: list[Inst] = []
        for code, cars, power, first in VARIANTS:
            for slot, count in _slots_for(cars, power, first):
                insts.append(Inst(code, slot, sas[slot], count, list(sas[slot].lines)))
        # reusable clones
        n_clones = rng.randint(3, 5)
        clone_slots = rng.sample(CLONE_CANDIDATES, n_clones)
        self.reusable_pairs: list[list[str]] = []
        self.clone_slots = clone_slots
        self.equiv_swaps: list[tuple[str, str]] = []
        mods = ["identical", "qty", "equiv", "extra"]
        rng.shuffle(mods)
        while len(mods) < n_clones:
            mods.append(rng.choice(["identical", "qty", "equiv", "extra"]))
        self.clone_details: list[dict[str, object]] = []
        for slot, mod in zip(clone_slots, mods):
            base = sas[slot]
            lines = list(base.lines)
            detail = mod
            if mod == "qty":
                cands = [
                    i for i, (k, q) in enumerate(lines) if self.parts[k].fam == "FIX" and q >= 4
                ]
                if not cands:
                    cands = [
                        i for i, (k, q) in enumerate(lines) if self.parts[k].kind == "pc" and q >= 4
                    ]
                i = rng.choice(cands)
                k, q = lines[i]
                lines[i] = (k, q + rng.choice([2, 4]))
                detail = f"qty {k} {q}->{lines[i][1]}"
            elif mod == "equiv":
                cands = [
                    i
                    for i, (k, _) in enumerate(lines[1:], start=1)
                    if self.parts[k].kind == "pc"
                    and self.parts[k].fam != "FIX"
                    and self.parts[k].mass is not None
                ]
                i = rng.choice(cands)
                k, q = lines[i]
                proto = self.parts[k]
                alt = ALT_SUPPLIER.get(proto.sup, "DIS")
                newp = self._new_part(
                    proto,
                    f"{k}_eq",
                    proto.fr + " (2e source)",
                    proto.en + " (second source)",
                    alt,
                    _sig3((proto.mass or 0) * rng.uniform(0.97, 1.03)),
                )
                lines[i] = (newp.key, q)
                self.equiv_swaps.append((k, newp.key))
                detail = f"equivalent swap {proto.ref} -> {newp.ref}"
            elif mod == "extra":
                extra = "idplate" if all(k != "idplate" for k, _ in lines) else "labelset"
                lines.append((extra, 1))
                detail = f"extra {extra}"
            sfx_fr, sfx_en = rng.choice(CLONE_SUFFIX)
            clone = SADesign(
                slot + "_CL",
                base.fam,
                base.fr + sfx_fr,
                base.en + sfx_en,
                lines,
                ref=f"SE-{base.fam}-{self._sa_alloc(1)}",
                base_slot=slot,
            )
            users = [i for i, inst in enumerate(insts) if inst.slot == slot]
            k_clone = rng.randint(2, max(2, len(users) - 2))
            for i in rng.sample(users, k_clone):
                insts[i].sa = clone
                insts[i].lines = list(clone.lines)
            self.reusable_pairs.append(sorted([base.ref, clone.ref]))
            self.clone_details.append({"base": base.ref, "clone": clone.ref, "mod": detail})
        rng.shuffle(insts)
        insts.sort(key=lambda x: [v[0] for v in VARIANTS].index(x.variant))
        return insts

    def plant_drift(self, insts: list[Inst]) -> set[int]:
        rng = self.rng
        uses: dict[str, list[int]] = {}
        for i, inst in enumerate(insts):
            uses.setdefault(inst.sa.ref, []).append(i)
        cands = sorted(
            r
            for r, idx in uses.items()
            if len(idx) >= 3
            and insts[idx[0]].slot not in self.clone_slots
            and not insts[idx[0]].slot.endswith("_CL")
            and insts[idx[0]].sa.slot == insts[idx[0]].sa.base_slot
        )
        n = rng.randint(3, 5)
        chosen = rng.sample(cands, n)
        types = ["qty", "missing", "extra", "swap_near"]
        rng.shuffle(types)
        while len(types) < n:
            types.append(rng.choice(["qty", "missing", "extra", "swap_near"]))
        drifted: set[int] = set()
        self.drift_parts: set[str] = set()
        for ref, kind in zip(chosen, types):
            ii = rng.choice(uses[ref])
            inst = insts[ii]
            lines = inst.lines
            keys = {k for k, _ in lines}
            if kind == "swap_near":
                opts = []
                for li, (k, _) in enumerate(lines):
                    g = self.parts[k].group
                    if g:
                        sib = [
                            p.key
                            for p in self.parts.values()
                            if p.group == g and p.key != k and p.key not in keys
                        ]
                        if sib:
                            opts.append((li, sib))
                if not opts:
                    kind = "qty"
                else:
                    li, sib = rng.choice(opts)
                    old = lines[li][0]
                    new = rng.choice(sib)
                    lines[li] = (new, lines[li][1])
                    detail = f"{self.parts[old].ref} replaced by {self.parts[new].ref}"
                    self.drift_parts.update({old, new})
            if kind == "qty":
                opts2 = [
                    li
                    for li, (k, q) in enumerate(lines)
                    if (self.parts[k].kind == "pc" and q >= 2) or self.parts[k].kind == "len"
                ]
                li = rng.choice(opts2)
                k, q = lines[li]
                if self.parts[k].kind == "pc":
                    newq = rng.choice([v for v in (q // 2, q + 2, q * 2) if v != q and v > 0])
                else:
                    newq = round(q * rng.choice([0.6, 1.5]), 1)
                lines[li] = (k, newq)
                detail = f"qty of {self.parts[k].ref} {q:g} -> {newq:g}"
                self.drift_parts.add(k)
            elif kind == "missing":
                li = rng.randrange(1, len(lines))
                k, _ = lines.pop(li)
                detail = f"{self.parts[k].ref} missing"
                self.drift_parts.add(k)
            elif kind == "extra":
                fam = self.parts[lines[0][0]].fam
                pool = [
                    p.key
                    for p in self.parts.values()
                    if p.fam == fam and p.key not in keys and not p.key.endswith("_eq")
                ]
                if not pool:
                    pool = [
                        k
                        for k in ("idplate", "primer", "tie_l", "wash_M10", "nut_M12")
                        if k not in keys
                    ]
                k = rng.choice(pool)
                kindp = self.parts[k].kind
                q = {"pc": rng.choice([1, 2, 4]), "len": 2.5, "vol": 0.25, "mass": 0.2}[kindp]
                lines.insert(rng.randrange(1, len(lines) + 1), (k, q))
                detail = f"extra {self.parts[k].ref}"
                self.drift_parts.add(k)
            drifted.add(ii)
            self.inconsistencies.append(
                {
                    "kind": "composition_drift",
                    "subject": ref,
                    "detail": f"variant {inst.variant}: {detail}",
                }
            )
        return drifted

    def plant_splits(self, insts: list[Inst], drifted: set[int]) -> None:
        rng = self.rng
        opts = [
            (ii, li)
            for ii, inst in enumerate(insts)
            if ii not in drifted
            for li, (k, q) in enumerate(inst.lines)
            if self.parts[k].kind == "pc" and q >= 4 and q % 2 == 0
        ]
        self.splits = []
        for ii, li in rng.sample(opts, rng.randint(1, 2)):
            k, q = insts[ii].lines[li]
            insts[ii].lines[li] = (k, q // 2)
            insts[ii].lines.insert(li + 1, (k, q // 2))
            self.splits.append(
                f"{insts[ii].variant} {insts[ii].sa.ref} {self.parts[k].ref} {q} split in two lines"
            )

    # ------------------------------------------------------------ defects on parts
    def plant_part_defects(self, insts: list[Inst]) -> None:
        rng = self.rng
        occ: dict[str, list[tuple[int, int]]] = {}
        for ii, inst in enumerate(insts):
            for li, (k, _) in enumerate(inst.lines):
                occ.setdefault(k, []).append((ii, li))
        self.occ = occ
        excluded = set(self.drift_parts)
        for a, b in self.equiv_swaps:
            excluded.update({a, b})

        def nvar(k: str) -> int:
            return len({insts[ii].variant for ii, _ in occ[k]})

        in_use = sorted(occ)
        multi = [
            k
            for k in in_use
            if k not in excluded
            and nvar(k) >= 2
            and len(occ[k]) >= 3
            and self.parts[k].kind == "pc"
        ]
        rng.shuffle(multi)
        taken: set[str] = set()

        def take(pool: list[str], n: int) -> list[str]:
            out = []
            for k in pool:
                if k not in taken and len(out) < n:
                    out.append(k)
                    taken.add(k)
            return out

        self.supplier_conflict: dict[tuple[str, str], str] = {}
        for k in take([k for k in multi if self.parts[k].sup in SUPPLIERS], rng.randint(3, 5)):
            part = self.parts[k]
            variants = sorted({insts[ii].variant for ii, _ in occ[k]})
            v = rng.choice(variants)
            alt = ALT_SUPPLIER.get(part.sup, "DIS")
            self.supplier_conflict[(v, k)] = alt
            self.inconsistencies.append(
                {
                    "kind": "supplier_conflict",
                    "subject": part.ref,
                    "detail": f"{SUPPLIERS[part.sup][0]} elsewhere, {SUPPLIERS[alt][0]} on {v}",
                }
            )
        self.mass_slip: dict[tuple[int, int], str] = {}
        self.force_mass: set[str] = set()
        mass_pool = [k for k in multi if (self.parts[k].mass or 0) >= 0.05]
        for k in take(mass_pool, rng.randint(3, 5)):
            part = self.parts[k]
            m = part.mass or 0.0
            ii, li = rng.choice(occ[k])
            slip = rng.choice(["g_for_kg", "x10"] if m >= 1 else ["kg_for_g", "x10"])
            self.mass_slip[(ii, li)] = slip
            self.force_mass.add(k)
            self.inconsistencies.append(
                {
                    "kind": "mass_mismatch",
                    "subject": part.ref,
                    "detail": f"{slip} on {insts[ii].variant}/{insts[ii].sa.ref}, true {m:g} kg",
                }
            )
        lifecycle_pool = [k for k in in_use if k not in excluded and self.parts[k].fam != "FIX"]
        rng.shuffle(lifecycle_pool)
        self.superseded = take(lifecycle_pool, rng.randint(2, 4))
        self.obsolete = take(lifecycle_pool, rng.randint(2, 4))
        self.note_subjects_free = [k for k in lifecycle_pool if k not in taken]
        self.taken = taken
        for k in self.superseded:
            self.inconsistencies.append(
                {
                    "kind": "superseded_in_use",
                    "subject": self.parts[k].ref,
                    "detail": "declared superseded in notes",
                }
            )
        for k in self.obsolete:
            self.inconsistencies.append(
                {
                    "kind": "obsolete_in_use",
                    "subject": self.parts[k].ref,
                    "detail": "declared obsolete in notes",
                }
            )

    # ------------------------------------------------------------ raw reference forms
    def _part_form(self, ref: str, style: str) -> str:
        fam, num = ref.split("-")
        return {
            "lower": ref.lower(),
            "nosep": fam + num,
            "space": f"{fam} {num}",
            "dot": f"{fam}.{num}",
            "us": f"{fam}_{num}",
            "pad": f" {ref} ",
            "cap": f"{fam.capitalize()}-{num}",
            "true": ref,
        }[style]

    def _random_part_form(self, ref: str) -> str:
        if self.rng.random() < 0.8:
            return ref
        return self._part_form(
            ref,
            self.rng.choice(
                ["lower", "nosep", "space", "dot", "us", "pad", "cap", "nosep", "space"]
            ),
        )

    def _sa_form(self, ref: str) -> str:
        if self.rng.random() < 0.75:
            return ref
        _, fam, num = ref.split("-")
        return self.rng.choice(
            [ref.lower(), f"SE{fam}{num}", f"SE {fam} {num}", f"SE-{fam}{num}", f"SE_{fam}_{num}"]
        )

    def plant_typos(self, insts: list[Inst], drifted: set[int]) -> dict[tuple[int, int], str]:
        rng = self.rng
        forms: dict[tuple[int, int], str] = {}
        protected = set(self.mass_slip)
        all_nums = {int(p.ref.split("-")[1]) for p in self.parts.values()}
        multi_sites = [
            (ii, li)
            for k, sites in sorted(self.occ.items())
            if len(sites) >= 3
            for ii, li in sites
            if (ii, li) not in protected
        ]
        rng.shuffle(multi_sites)
        self.typo_log: list[str] = []
        n_o, n_np, n_tr = rng.randint(4, 6), rng.randint(3, 5), rng.randint(2, 3)
        for ii, li in multi_sites:
            k = insts[ii].lines[li][0]
            ref = self.parts[k].ref
            fam, num = ref.split("-")
            if n_o and "0" in num:
                pos = rng.choice([i for i, c in enumerate(num) if c == "0"])
                forms[(ii, li)] = f"{fam}-{num[:pos]}O{num[pos + 1 :]}"
                n_o -= 1
            elif n_np:
                forms[(ii, li)] = num
                n_np -= 1
            elif n_tr and self.parts[k].group is None:
                pos = [i for i in range(1, 5) if num[i] != num[i + 1]]
                if not pos:
                    continue
                i = rng.choice(pos)
                t = num[:i] + num[i + 1] + num[i] + num[i + 2 :]
                if int(t) in all_nums or int(t) in self.used_numbers:
                    continue
                forms[(ii, li)] = f"{fam}-{t}"
                n_tr -= 1
            else:
                continue
            self.typo_log.append(
                f"{insts[ii].variant}/{insts[ii].sa.ref}: {forms[(ii, li)]!r} = {ref}"
            )
            if not (n_o or n_np or n_tr):
                break
        return forms

    # ------------------------------------------------------------ rendering
    def _qty(self, kind: str, q: float) -> tuple[str, str]:
        rng = self.rng
        comma = rng.random() < 0.75
        if kind == "pc":
            unit = rng.choice(PC_UNITS)
            if rng.random() < 0.2:
                return _num(q, 3 if comma else 2, comma, strip=False), unit
            return str(int(q)), unit
        if kind == "len":
            unit = rng.choices(["m", "cm", "mm"], [50, 15, 35])[0]
            v = q * {"m": 1, "cm": 100, "mm": 1000}[unit]
            s = _num(v, {"m": 3, "cm": 1, "mm": 0}[unit], comma)
            if unit == "mm" and v >= 1000 and rng.random() < 0.15:
                s = f"{int(round(v)):,}".replace(",", " ")
            return s, unit
        if kind == "mass":
            unit = "kg" if rng.random() < 0.7 else "g"
            v = q if unit == "kg" else q * 1000
            return _num(v, 3 if unit == "kg" else 0, comma), unit
        unit = "l" if rng.random() < 0.6 else "ml"
        v = q if unit == "l" else q * 1000
        return _num(v, 3 if unit == "l" else 0, comma), unit

    def _mass(self, m: float, slip: str | None = None) -> str:
        rng = self.rng
        comma = rng.random() < 0.75
        if slip == "g_for_kg":
            return f"{_num(m, 4, comma)} g"
        if slip == "kg_for_g":
            return f"{_num(m * 1000, 1, comma)} kg"
        if slip == "x10":
            m = m * 10 if rng.random() < 0.7 else m / 10
        if m < 1:
            unit = "g" if rng.random() < 0.65 else "kg"
        elif m < 20:
            unit = "kg" if rng.random() < 0.85 else "g"
        else:
            unit = "kg"
        v = m * 1000 if unit == "g" else m
        s = _num(v, 1 if unit == "g" else 4, comma)
        if slip is None and rng.random() < 0.08:
            for dec in (1, 0):
                r = round(v, dec)
                if r and 0 < abs(r - v) / v < 0.01:
                    s = _num(r, dec, comma)
                    break
        if slip is None and unit == "kg" and rng.random() < 0.08 and ("," in s or "." in s):
            s += "0"
        sep = " " if rng.random() < 0.85 else ""
        u = "Kg" if unit == "kg" and rng.random() < 0.08 else unit
        return f"{s}{sep}{u}"

    def _desig(self, fr: str, en: str, abbr: str) -> str:
        r = self.rng.random()
        if r < 0.55:
            d = fr
        elif r < 0.85:
            d = abbr
        else:
            d = en
        if self.rng.random() < 0.04:
            d = d + "  "
        return d

    def render(self, insts: list[Inst], typos: dict[tuple[int, int], str]) -> list[list[str]]:
        rng = self.rng
        rows: list[list[str]] = []
        for ii, inst in enumerate(insts):
            sa = inst.sa
            inst.sa_raw = self._sa_form(sa.ref)
            self._map(inst.sa_raw, sa.ref)
            unit = rng.choice(PC_UNITS)
            rows.append(
                [
                    inst.variant,
                    "1",
                    inst.variant,
                    inst.sa_raw,
                    self._desig(sa.fr, sa.en, _abbr(sa.fr)),
                    str(inst.count),
                    unit,
                    rng.choice(INTERNAL),
                    "",
                ]
            )
            for li, (k, q) in enumerate(inst.lines):
                part = self.parts[k]
                raw = typos.get((ii, li)) or self._random_part_form(part.ref)
                self._map(raw, part.ref)
                qte, u = self._qty(part.kind, q)
                alt = self.supplier_conflict.get((inst.variant, k))
                if alt:
                    sup = rng.choice(SUPPLIERS[alt])
                elif k in self.force_mass or any(k == kk for _, kk in self.supplier_conflict):
                    sup = rng.choice(SUPPLIERS[part.sup])
                else:
                    sup = "" if rng.random() < 0.05 else rng.choice(SUPPLIERS[part.sup])
                mass = ""
                if part.mass is not None:
                    slip = self.mass_slip.get((ii, li))
                    if slip or k in self.force_mass or rng.random() > 0.12:
                        mass = self._mass(part.mass, slip)
                rows.append(
                    [
                        inst.variant,
                        "2",
                        inst.sa_raw,
                        raw,
                        self._desig(part.fr, part.en, part.abbr),
                        qte,
                        u,
                        sup,
                        mass,
                    ]
                )
        return rows

    def _map(self, raw: str, true: str) -> None:
        prev = self.raw_map.get(raw)
        if prev is not None and prev != true:
            raise RuntimeError(f"raw ref collision {raw!r}: {prev} vs {true}")
        self.raw_map[raw] = true

    def bad_rows(self, rows: list[list[str]]) -> list[tuple[int, str]]:
        rng = self.rng
        n = rng.randint(8, 14)
        out: list[tuple[int, str]] = []
        for _ in range(n):
            t = rng.choice(
                ["trunc", "ref_err", "header", "empty", "footer", "mojibake", "qty_err", "trunc"]
            )
            src = rng.choice([r for r in rows if r[1] == "2"])
            if t == "trunc":
                line = ";".join(src)
                cut = [i for i, c in enumerate(line) if c == ";"][rng.randint(2, 4)]
                text = line[: cut + rng.randint(1, 6)].rstrip(";")
                if text.count(";") >= 8:
                    text = ";".join(src[:4])
            elif t == "ref_err":
                text = f"{src[0]};2;{src[2]};;#REF!;#REF!;;;"
            elif t == "header":
                text = ";".join(HEADER)
            elif t == "empty":
                text = ";;;;;;;;"
            elif t == "footer":
                text = rng.choice(
                    [
                        f"Extraction PLM du {date(2026, 9, rng.randint(1, 28))} - "
                        f"page {rng.randint(2, 9)}/9",
                        "*** FIN DE L'EXTRACTION ***",
                        "Total lignes exportées",
                    ]
                )
            elif t == "mojibake":
                d = src[4].encode("utf-8").decode("latin-1")
                text = f"{src[0]};2;{src[2]};{d};;;{src[5]};{src[6]};;;"
            else:
                text = f"{src[0]};2;{src[2]};{src[3]};{src[4]};#VALEUR!;;{src[7]};"
                self._map(src[3], self.raw_map[src[3]])
            out.append((rng.randint(1, len(rows) - 1), text))
        return out


# ---------------------------------------------------------------- notes

SUP_TPL = [
    ("{x} remplacée par {y} à partir de la prochaine commande.", True),
    ("Remplacer {x} par {y} (évolution fournisseur, compatibilité totale).", True),
    ("{x} is superseded by {y}. Update BOMs at next revision.", True),
    ("Nouvelle référence {y} en remplacement de {x}, l'ancienne n'est plus fabriquée.", True),
    ("From now on order {y} instead of {x}.", True),
    ("{x} -> {y} : mise à jour suite FAI, ancienne réf. à ne plus approvisionner.", True),
    ("Suite à la DM 2025-{n}, la pièce {x} est remplacée par la {y}.", True),
    ("Remplacée par {y}.", False),
    ("Superseded by {y} (ECN {n}).", False),
]
OBS_TPL = [
    ("{x} obsolète, plus disponible chez le fournisseur.", True),
    ("{x}: end of life announced by supplier, last-time buy closed.", True),
    ("Fin de commercialisation de {x}. Pas de remplaçant identifié à ce jour, BE à saisir.", True),
    ("{x} discontinued, no longer available from manufacturer.", True),
    ("Ne plus commander {x} : article obsolète (fin de série fournisseur).", True),
    ("Pièce {x} déclarée obsolète au dernier comité de configuration.", True),
    ("Article obsolète, plus fabriqué.", False),
    ("EOL - not orderable anymore.", False),
]
EQ_TPL = [
    "{x} et {y} sont interchangeables (mêmes cotes, même matériau).",
    "{y} is a drop-in equivalent of {x}, both approved.",
    "Équivalence validée : {x} = {y} (double source).",
    "{y} peut être monté à la place de {x} sans modification.",
]
NEG_TPL = [
    "{x} n'est PAS obsolète : le fournisseur confirme la production jusqu'en 2032.",
    "Contrary to the previous email, {x} is not discontinued.",
    "Aucun remplacement prévu pour {x}, référence maintenue.",
    "Rumeur de fin de vie sur {x} infirmée par le fournisseur.",
    "{x} remains the reference part, no supersession planned.",
]
Q_TPL = [
    "Faut-il remplacer {x} par {y} ? À discuter en revue de conception.",
    "Is {x} going obsolete? Please check with purchasing.",
    "Étude en cours : remplacement éventuel de {x} par {y}, pas de décision à ce stade.",
]
MAINT_TPL = [
    "{x} remplacé sur la rame 07 après choc ballast, pièce d'origine retournée au fournisseur.",
    "Replaced {x} on unit 12 during scheduled maintenance, no issue found.",
    "Rame 23 : {x} changé en atelier suite à fuite, même référence remontée.",
]
DOC_TPL = [
    "La gamme de montage de {x} est obsolète, utiliser l'indice C en GED.",
    "Drawing of {x} rev. A is obsolete, use rev. B (cosmetic changes only).",
]
CHAT_TPL = [
    "Délai fournisseur pour {x} : {n} semaines.",
    "Couple de serrage pour {x} : {n} N.m, voir gamme.",
    "Photo du montage {x} jointe au dossier.",
    "RAS lors de l'inspection de premier article {x}.",
    "Price increase of 4 % on {x} from January.",
    "{x}: packaging changed to individual bags, no technical impact.",
    "Contrôle réception {x} OK, certificat matière 3.1 reçu.",
    "Point bloquant levé sur {x}.",
    "Revue de conception {x} OK.",
    "Attention à l'orientation de {x} au montage (flèche vers l'extérieur).",
    "Stock magasin {x} : {n} pièces.",
    "Reminder: {x} requires torque marking after assembly.",
    "Lot 2025-{n} de {x} conforme.",
    "{x} : marquage fournisseur modifié (nouveau logo), même référence.",
    "Fournisseur de {x} en retard sur la livraison de mars, relance faite.",
    "{x} OK pour le montage en série.\nÀ confirmer par la qualité.",
    "Calage de {x} vérifié sur la rame prototype, pas d'interférence.",
    "Question client sur {x} : traitée, voir CR réunion.",
]
AUTHORS = [
    "J. Martin",
    "S. Dupont (BE Bogies)",
    "m.leroy",
    "K. Nguyen",
    "A. Benali",
    "P. Lefèvre - Achats",
    "C. Rossi",
    "T. Girard (Qualité)",
    "L. Moreau",
    "E. Schmitt",
    "R. Fontaine",
    "BE CVC",
]


def build_notes(g: Gen, insts: list[Inst]) -> tuple[list[list[str]], list[dict[str, object]]]:
    rng = g.rng
    notes: list[dict[str, object]] = []
    start, end = date(2024, 1, 8), date(2026, 9, 20)

    def rdate(lo: date = start, hi: date = end) -> date:
        return lo + timedelta(days=rng.randint(0, (hi - lo).days))

    def form(ref: str) -> str:
        if rng.random() < 0.65:
            return ref
        if ref.startswith("SE-"):
            return rng.choice([ref.lower(), ref.replace("-", " ")])
        return g._part_form(ref, rng.choice(["lower", "nosep", "space", "dot"]))

    def add(
        x_true: str,
        kind: str,
        tpl: str,
        needs_col: bool | None = None,
        y_true: str | None = None,
        d: date | None = None,
        tag: str = "",
    ) -> dict[str, object]:
        xw = form(x_true)
        yw = form(y_true) if y_true else None
        col = xw
        if needs_col is not True and rng.random() < 0.15 and "{x}" in tpl:
            col = ""
        text = tpl.format(x=xw, y=yw or "", n=rng.randint(10, 99), d=rdate().isoformat())
        note = {
            "ref_col": col,
            "text": text,
            "date": d or rdate(),
            "kind": kind,
            "ref": xw,
            "target": yw if kind in ("superseded_by", "equivalent_to") else None,
            "ref_true": x_true,
            "target_true": y_true if kind in ("superseded_by", "equivalent_to") else None,
            "tag": tag,
        }
        notes.append(note)
        return note

    def newref(proto_key: str) -> str:
        proto = g.parts[proto_key]
        return f"{proto.fam}-{g._alloc(1)}"

    for k in g.superseded:
        y = newref(k)
        for tpl, has_x in rng.sample(SUP_TPL, rng.randint(1, 2)):
            add(g.parts[k].ref, "superseded_by", tpl, needs_col=not has_x, y_true=y)
    for k in g.obsolete:
        for tpl, has_x in rng.sample(OBS_TPL, rng.randint(1, 2)):
            add(g.parts[k].ref, "obsolete", tpl, needs_col=not has_x)
    for a, b in g.equiv_swaps:
        add(g.parts[a].ref, "equivalent_to", rng.choice(EQ_TPL), y_true=g.parts[b].ref)
    free = list(g.note_subjects_free)
    rng.shuffle(free)

    def pop() -> str:
        return g.parts[free.pop()].ref

    for _ in range(2):
        x = pop()
        add(x, "equivalent_to", rng.choice(EQ_TPL), y_true=newref(g.parts_by_ref[x]))
    # lifecycle statements about parts already gone from every BOM
    in_use_keys = sorted(g.occ)
    for _ in range(2):
        proto = rng.choice(in_use_keys)
        old = newref(proto)
        tpl, _h = rng.choice(SUP_TPL[:7])
        add(old, "superseded_by", tpl, y_true=g.parts[proto].ref, tag="not_in_bom")
    for _ in range(2):
        old = newref(rng.choice(in_use_keys))
        tpl, _h = rng.choice(OBS_TPL[:6])
        add(old, "obsolete", tpl, tag="not_in_bom")
    for tpl in rng.sample(NEG_TPL, 4):
        add(pop(), "none", tpl)
    for tpl in rng.sample(Q_TPL, 2):
        x = pop()
        add(x, "none", tpl, y_true=newref(g.parts_by_ref[x]))
    x = pop()
    y = newref(g.parts_by_ref[x])
    d0 = rdate(start, date(2025, 12, 31))
    tpl, _h = rng.choice(SUP_TPL[:7])
    orig = add(x, "superseded_by", tpl, y_true=y, d=d0, tag="cancelled")
    cancel = add(
        x,
        "none",
        "Annule la note @@NID@@ : le remplacement de {x} par {y} est abandonné, "
        "{x} reste la référence.",
        y_true=y,
        d=d0 + timedelta(days=rng.randint(30, 150)),
    )
    cancel["text"] = str(cancel["text"]).replace("{nid}", "@@NID@@")
    cancel["cancels"] = orig
    for tpl in rng.sample(MAINT_TPL, 2):
        add(pop(), "none", tpl)
    for tpl in DOC_TPL:
        add(pop(), "none", tpl)
    sa_refs = sorted({inst.sa.ref for inst in insts})
    target_total = rng.randint(55, 64)
    while len(notes) < target_total:
        subj = rng.choice(sa_refs) if rng.random() < 0.2 else g.parts[rng.choice(in_use_keys)].ref
        add(subj, "none", rng.choice(CHAT_TPL))
    notes.sort(key=lambda n: n["date"])  # type: ignore[arg-type,return-value]
    for i, n in enumerate(notes, start=1):
        n["note_id"] = f"N{i:04d}"
    rows: list[list[str]] = []
    truth: list[dict[str, object]] = []
    for n in notes:
        if "cancels" in n:
            n["text"] = str(n["text"]).replace("@@NID@@", str(n["cancels"]["note_id"]))  # type: ignore[index]
        d: date = n["date"]  # type: ignore[assignment]
        ds = d.isoformat() if rng.random() < 0.6 else d.strftime("%d/%m/%Y")
        rows.append([str(n["note_id"]), str(n["ref_col"]), rng.choice(AUTHORS), ds, str(n["text"])])
        truth.append(
            {
                "note_id": n["note_id"],
                "ref": n["ref"],
                "kind": n["kind"],
                "target": n["target"],
                "ref_true": n["ref_true"],
                "target_true": n["target_true"],
            }
        )
    return rows, truth


# ---------------------------------------------------------------- main


def generate(seed: int, out: Path) -> None:
    g = Gen(seed)
    g.build_parts()
    sas = g.build_sas()
    insts = g.build_instances(sas)
    g.parts_by_ref = {p.ref: p.key for p in g.parts.values()}
    drifted = g.plant_drift(insts)
    g.plant_splits(insts, drifted)
    g.plant_part_defects(insts)
    typos = g.plant_typos(insts, drifted)
    rows = g.render(insts, typos)
    bad = g.bad_rows(rows)
    g.parts_by_ref = {p.ref: p.key for p in g.parts.values()}
    note_rows, note_truth = build_notes(g, insts)

    out.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(HEADER)
    lines = buf.getvalue().splitlines(keepends=True)
    body: list[str] = []
    for r in rows:
        b = io.StringIO()
        csv.writer(b, delimiter=";", lineterminator="\r\n").writerow(r)
        body.append(b.getvalue())
    for pos, text in sorted(bad, key=lambda t: -t[0]):
        body.insert(pos, text + "\r\n")
    with (out / "bom_export.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines + body))
    with (out / "notes.csv").open("w", encoding="utf-8", newline="") as f:
        nw = csv.writer(f, delimiter=";", lineterminator="\r\n")
        nw.writerow(NOTES_HEADER)
        nw.writerows(note_rows)
    truth = {
        "raw_ref_to_true_ref": dict(sorted(g.raw_map.items())),
        "reusable_pairs": g.reusable_pairs,
        "inconsistencies": g.inconsistencies,
        "notes": note_truth,
        "bad_rows": len(bad),
        "_meta": {
            "seed": seed,
            "clones": g.clone_details,
            "distractor_pairs": [sorted([sas[a].ref, sas[b].ref]) for a, b in DISTRACTOR_SLOTS],
            "split_lines_noise": g.splits,
            "typo_sites": g.typo_log,
        },
    }
    (out / "truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _parse_qty(s: str) -> float | None:
    try:
        return float(s.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def check(out: Path) -> bool:
    truth = json.loads((out / "truth.json").read_text(encoding="utf-8"))
    rmap: dict[str, str] = truth["raw_ref_to_true_ref"]
    ok = True
    with (out / "bom_export.csv").open(encoding="utf-8", newline="") as f:
        rd = csv.reader(f, delimiter=";")
        header = next(rd)
        assert header == HEADER, header
        good = bad = 0
        l1: set[str] = set()
        l2: set[str] = set()
        for r in rd:
            if len(r) != 9 or r == HEADER or not r[3] or _parse_qty(r[5]) is None:
                bad += 1
                if len(r) == 9 and r != HEADER and r[3] and r[3] not in rmap:
                    print(f"  MISSING in map (bad row): {r[3]!r}")
                    ok = False
                continue
            good += 1
            if r[3] not in rmap:
                print(f"  MISSING in map: {r[3]!r}")
                ok = False
                continue
            (l1 if r[1] == "1" else l2).add(rmap[r[3]])
    present = l1 | l2
    if bad != truth["bad_rows"]:
        print(f"  bad rows: parsed {bad} vs truth {truth['bad_rows']}")
        ok = False
    for inc in truth["inconsistencies"]:
        if inc["subject"] not in present:
            print(f"  subject absent from data: {inc}")
            ok = False
    for a, b in truth["reusable_pairs"]:
        if a not in l1 or b not in l1:
            print(f"  reusable pair absent: {a} {b}")
            ok = False
    with (out / "notes.csv").open(encoding="utf-8", newline="") as f:
        nrows = list(csv.reader(f, delimiter=";"))[1:]
    if {r[0] for r in nrows} != {n["note_id"] for n in truth["notes"]}:
        print("  note ids differ between notes.csv and truth")
        ok = False
    counts: dict[str, int] = {}
    for inc in truth["inconsistencies"]:
        counts[inc["kind"]] = counts.get(inc["kind"], 0) + 1
    nk: dict[str, int] = {}
    for n in truth["notes"]:
        nk[n["kind"]] = nk.get(n["kind"], 0) + 1
    print(f"{out}: {'OK' if ok else 'FAILED'}")
    print(f"  rows: {good} valid + {bad} bad; raw ref strings: {len(rmap)}")
    print(f"  distinct true parts (level 2): {len(l2)}; SA designs (level 1): {len(l1)}")
    print(f"  notes: {len(nrows)} {dict(sorted(nk.items()))}")
    print(f"  reusable_pairs: {len(truth['reusable_pairs'])}")
    for k in [
        "composition_drift",
        "supplier_conflict",
        "mass_mismatch",
        "superseded_in_use",
        "obsolete_in_use",
    ]:
        print(f"  {k}: {counts.get(k, 0)}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--check", type=Path)
    a = ap.parse_args()
    if a.check:
        raise SystemExit(0 if check(a.check) else 1)
    if a.seed is None or a.out is None:
        ap.error("--seed and --out are required")
    generate(a.seed, a.out)
    raise SystemExit(0 if check(a.out) else 1)


if __name__ == "__main__":
    main()
