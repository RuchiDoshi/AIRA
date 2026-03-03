# Lab MCP Data Schema (schema.md)

This project stores lab knowledge (reagents) in JSON so an MCP server can provide:
- get_reagent_details(name)
- search_reagents(query)
- list_categories()

## Core idea

**Reagent** is the umbrella term for anything used in lab work:
- enzymes (restriction enzymes, polymerases, ligases)
- chemicals (ethanol, NaCl, HCl)
- buffers (PBS, TAE)
- kits (DNA extraction kit)

Each reagent is a JSON object. Some fields are shared across all reagents; other fields depend on `type`.

---

## File format & conventions

- Store records as a JSON array: `[ { ... }, { ... } ]`
- Each record must have a stable `id` (string).
  - Use a slug-like format, e.g.:
    - `enzyme:restriction:ecori`
    - `chemical:ethanol`
    - `buffer:tae`
- `type` is required and determines which optional fields apply.
- Keep everything “computer-friendly”:
  - temperatures in Celsius numbers
  - hazards as an array of strings
  - references as URLs

---

## Required fields (all reagents)

- `id` (string): unique identifier
- `name` (string): human-readable name (e.g., "EcoRI", "Ethanol")
- `type` (string): one of:
  - `restriction_enzyme`
  - `pcr_polymerase`
  - `ligase`
  - `nuclease`
  - `buffer`
  - `chemical`
  - `kit`
  - `other`
- `category` (string): broad grouping, usually:
  - `enzyme`, `chemical`, `buffer`, `kit`, `other`
- `description` (string): 1–3 sentence summary
- `source` (object):
  - `name` (string): e.g. "NEB", "REBASE", "PubChem"
  - `url` (string): page used to extract/verify info
  - `retrieved` (string date): YYYY-MM-DD

---

## Common optional fields (all reagents)

- `aliases` (string[]): other names / spellings
- `storage` (string): e.g. "-20C", "4C", "RT"
- `hazards` (string[]): e.g. ["flammable", "corrosive"] or []
- `safety` (object):
  - `ppe` (string[]): e.g. ["gloves", "goggles"]
  - `notes` (string)
- `applications` (string[]): e.g. ["cloning", "PCR", "DNA cleanup"]
- `notes` (string): free-form
- `vendor` (object):
  - `name` (string): e.g. "NEB"
  - `catalog_number` (string)
  - `product_url` (string)

---

## Restriction enzyme-specific fields (type = restriction_enzyme)

- `recognition_sequence` (string): e.g. "GAATTC"
- `cut_site` (string): text representation, e.g. "G^AATTC"
- `overhang` (object):
  - `type` (string): `5_prime` | `3_prime` | `blunt`
  - `sequence` (string|null): e.g. "AATT" or null for blunt
- `optimal_temperature_c` (number): e.g. 37
- `methylation_sensitivity` (string, optional)
- `star_activity_notes` (string, optional)
- `buffers` (string[]): e.g. ["CutSmart"]

---

## Chemical-specific fields (type = chemical)

- `formula` (string): e.g. "C2H6O"
- `cas_number` (string): e.g. "64-17-5"
- `concentration` (object, optional):
  - `value` (number)
  - `unit` (string): "M", "%", "mg/mL"
- `state` (string, optional): "solid" | "liquid" | "gas"
- `incompatibilities` (string[], optional): e.g. ["strong oxidizers"]

---

## Buffer-specific fields (type = buffer)

- `components` (array of objects):
  - `name` (string): e.g. "Tris"
  - `concentration` (string): e.g. "40 mM"
- `ph` (number, optional)
- `working_concentration` (string, optional): e.g. "1X"

---

## Example records

### Restriction enzyme example
```json
{
  "id": "enzyme:restriction:ecori",
  "name": "EcoRI",
  "type": "restriction_enzyme",
  "category": "enzyme",
  "description": "Restriction endonuclease that recognizes GAATTC and generates a 5' AATT overhang.",
  "recognition_sequence": "GAATTC",
  "cut_site": "G^AATTC",
  "overhang": { "type": "5_prime", "sequence": "AATT" },
  "optimal_temperature_c": 37,
  "buffers": ["CutSmart"],
  "hazards": [],
  "storage": "-20C",
  "source": {
    "name": "NEB",
    "url": "https://example.com/ecori",
    "retrieved": "2026-02-27"
  }
}