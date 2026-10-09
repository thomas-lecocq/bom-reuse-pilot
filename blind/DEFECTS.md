# Planted defects and noise (read only after scoring)

`generate.py` invents a catalogue of about 200 parts in 20 families (bogie, brake, air, roof HV,
traction, power pack, HVAC, doors, cab, seating, lighting, toilets, coupler, PIS, signalling,
fasteners, seals, cables, connectors, consumables). It has 24 base sub-assembly (SA) designs and 8
variants `RGX-<n>C-<TH|AC|DC|BM|BT>`. Each variant uses 19 to 23 SAs. Part numbers, SA numbers,
clones, defect sites and noise sites all come from the seed. `truth.json["_meta"]` lists the clone
modifications, the distractor pairs, the split-line sites and the reference typo sites for each
seed.

## Scored: reusable pairs (`reusable_pairs`)
For 3 to 5 SA slots, the generator copies the base design under a new `SE-<FAM>-nnn` reference
with a suffixed designation ("version B", "ind. 2", "(programme Grand Est)" ...). Each copy then
gets one of these modifications:
- `identical`: same lines and quantities.
- `qty`: one fastener quantity changes by 2 or 4.
- `equiv`: one component is swapped for a second-source part. That part has a new reference, the
  same designation plus "(2e source)", the alternate supplier, and a mass within ±3%. An
  `equivalent_to` note links the two parts. They are two different true references, not
  duplicates.
- `extra`: one identification plate or label set is added.

The clone replaces the base on a random subset of the variants, and the base stays on at least 2
variants.

**Distractors (not reusable):** motor vs trailer bogie, 25 kV vs 1.5 kV roof equipment, saloon vs
cab HVAC, left vs right access door (mirror parts), 1st vs 2nd class seating, and PRM vs standard
toilet. Each pair has consecutive SA numbers, so the references look alike, and they share 45 to
60% of their lines.

## Scored: `composition_drift`
For 3 to 5 base SAs that are used on at least 3 variants and are not cloned, one variant's copy is
changed in one of these ways:
- a quantity changes (pieces halved, +2 or doubled; lengths ×0.6 or ×1.5);
- one line is missing;
- one extra line is added from the same family;
- one part is replaced by a sibling from its consecutive-number group (M12x50 → M12x40, right
  guide rail → left guide rail, organic → sintered pad ...).

The subject is the true SA reference.

## Scored: `supplier_conflict`
For 3 to 5 piece parts used on at least 2 variants, every row of the part on one variant names a
genuinely different company: the known second source (Visserie Industrielle du Nord, Étanche Pro,
Kabelwerk Rhein, Freins et Garnitures du Centre ...), or else the distributor Distrifer Négoce.
Rows of these parts are never left with an empty supplier.

## Scored: `mass_mismatch`
For 3 to 5 piece parts with a mass of at least 0.05 kg, one row has a unit slip. The slip is one
of:
- the kg value written with `g`;
- the gram value written with `kg`;
- the decimal shifted (×10, or ÷10 in 30% of cases).

All other rows of these parts show a mass.

## Scored: `superseded_in_use` / `obsolete_in_use`
For 2 to 4 in-use non-fastener parts, one or two notes say the part is superseded. They are written
in FR or EN and with varied wording ("remplacée par", "is superseded by", "order Y instead of X",
"X -> Y", "Nouvelle référence Y en remplacement de X"). The target is a new reference that is not
in the BOM. Some superseded/obsolete notes leave `ref_article` empty and give the reference only in
the text. Others ("Remplacée par Y.", "EOL - not orderable anymore.") give it only in the
`ref_article` column. The same holds for 2 to 4 parts declared obsolete ("fin de commercialisation",
"EOL", "discontinued", "ne plus commander").

## Scored: notes (`notes[].kind`)
Each note is labelled `superseded_by`, `obsolete`, `equivalent_to` or `none`. The `none` notes are
the traps:
- **Negations:** "n'est PAS obsolète", "is not discontinued", "aucun remplacement prévu",
  "rumeur ... infirmée".
- **Questions and studies:** "Faut-il remplacer X par Y ?", "Is X going obsolete?", "Étude en
  cours ... pas de décision".
- **A cancelled supersession:** note A says X is replaced by Y (kind `superseded_by`). A later note
  B says "Annule la note A ... X reste la référence" (kind `none`). X is therefore **not** in
  `superseded_in_use`.
- **Maintenance "replaced":** a physical swap on a trainset ("remplacé sur la rame 07", "changé en
  atelier, même référence").
- **"Obsolete" about documents:** an obsolete assembly procedure or drawing revision.
- **Chatter:** lead time, torque, stock, FAI, packaging, logo change, price, a multi-line quoted
  note, and notes about SA references.
- **Lifecycle notes on parts no longer in the BOM:** 2 superseded (the target *is* in use) and 2
  obsolete. The note kind is set, but no inconsistency is raised.

Note references are written as-is or reformatted (lowercase, space, dot, no separator). `truth`
gives both `ref`/`target` as written and `ref_true`/`target_true`.

## Scored: `bad_rows`
8 to 14 extra unreadable lines are inserted at random positions. None of them replaces a real row.
They are:
- truncated lines (fewer fields);
- `#REF!` lines with an empty reference;
- a repeated header;
- an empty `;;;;;;;;` line;
- a PLM footer or page break;
- a mojibake line with too many fields;
- a copy of a real row whose quantity is `#VALEUR!`. Its reference is valid and is in the map.

## Scored: `raw_ref_to_true_ref` (duplicates)
Part references are `FAM-nnnnnn`, with numbers unique across the whole catalogue. On about 20% of
rows they are written in another format: lowercase, `FAM nnnnnn`, `FAMnnnnnn`, `FAM.nnnnnn`,
`FAM_nnnnnn`, ` FAM-nnnnnn ` (padded), or `Fam-nnnnnn`. There are also a few typo sites:
- a letter O instead of a zero;
- the family prefix dropped (number only);
- two adjacent digits transposed. This is only done on parts outside a near-duplicate group, and
  only when the transposed number does not exist.

SA references are written as lowercase, `SEFAMnnn`, `SE FAM nnn`, `SE-FAMnnn` or `SE_FAM_nnn`.

Near-duplicate *different* parts have consecutive numbers: screw sizes, A4 stainless vs zinc-plated
steel, nut vs self-locking nut, O-ring sizes and NBR vs FKM, cable sections, air spring gen. 1 vs
gen. 2, organic vs sintered pads, wheel vs axle discs, left vs right leaves, rails and covers,
1200 vs 1500 mm LED strips, 50 vs 100 l reservoirs, 1st vs 2nd class seats and fabrics. They map to
different true references.

## Unscored noise (must NOT be flagged)
- **Designations:** full French, an automatic French abbreviation (GCHE/DRT, AMORT., CALC. ...) or
  English. Some have a trailing double space, and one contains a quoted `;`.
- **Quantities:**
  - piece units are PC, pc, pce, pcs, u, un or EA;
  - integers are sometimes written `8,000` or `8.00`;
  - lengths are in m, cm or mm, sometimes with a French thousands space (`12 500`);
  - masses are in kg or g, volumes in l or ml;
  - decimals use a comma or a point.
- **Unit masses:**
  - kg or g, with or without a space;
  - `Kg` casing;
  - a trailing zero;
  - rounding under 1%;
  - 12% of rows empty.

  Only piece parts carry a mass.
- **Suppliers:** name variants of the same company (case, accents, legal suffix, abbreviation, the
  acronym AMH). 5% of rows are empty.
- **Level 1:** the SA count per train varies by variant. The level-1 supplier is "Interne" or a
  variant of it, or empty.
- **Split lines:** 1 or 2 sites where a piece line is split into two lines of half the quantity in
  the same SA. The sum equals the other variants, so this is not drift.
- **Row order:** SA order within a variant is shuffled.
