# Lab MCP Resource Schema Reference

**Schema ID:** `reagent-or-practice.schema.json`  
**Draft:** JSON Schema 2020-12  
**Last updated:** 2026-03-05

This schema covers two broad resource types loaded by the MCP server: **reagents** (restriction enzymes, buffers, chemicals, kits, etc.) and **wetlab practices** (procedures, safety protocols, equipment guides).

---

## Required Fields (all records)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier. Format: `enzyme:restriction:ecori` or `practice:micropipetting` |
| `name` | string | Human-readable name |
| `type` | string (enum) | Resource type — see [Type Values](#type-values) |
| `category` | string (enum) | Broad category — see [Category Values](#category-values) |
| `description` | string | Plain-language description |
| `source` | object | Provenance — see [Source Object](#source-object) |

---

## Type Values

| Value | Category enforced | Notes |
|---|---|---|
| `restriction_enzyme` | `enzyme` | Also requires `recognition_sequence` |
| `pcr_polymerase` | `enzyme` | |
| `ligase` | `enzyme` | |
| `nuclease` | `enzyme` | |
| `buffer` | `buffer` | |
| `chemical` | `chemical` | |
| `kit` | `kit` | |
| `other` | `other` | |
| `lab_equipment` | `practice` | Requires `procedure` + `media` |
| `lab_procedure` | `practice` | Requires `procedure` + `media` |
| `lab_safety` | `practice` | Requires `procedure` + `media` |
| `lab_sterility` | `practice` | Requires `procedure` + `media` |
| `lab_documentation` | `practice` | Requires `procedure` + `media` |
| `lab_calculation` | `practice` | Requires `procedure` + `media` |

---

## Category Values

`enzyme` · `chemical` · `buffer` · `kit` · `other` · `practice`

---

## Optional Fields (all records)

| Field | Type | Description |
|---|---|---|
| `organism` | string | Source organism for enzymes (e.g., `"Escherichia coli RY13"`) |
| `aliases` | string[] | Alternative names used in fuzzy search |
| `keywords` | string[] | Extra search/query helpers (e.g., `"two-stop"`, `"blow out"`) |
| `storage` | string | Storage conditions (e.g., `"-20°C"`) |
| `hazards` | string[] | Hazard statements |
| `safety` | object | PPE list + safety notes — see [Safety Object](#safety-object) |
| `applications` | string[] | Common use cases |
| `notes` | string | Free-text notes |
| `vendor` | object | Commercial source info — see [Vendor Object](#vendor-object) |
| `media` | object[] | Linked images/PDFs — see [Media Object](#media-object) |

---

## Source Object

Required on every record. Tracks data provenance.

```json
"source": {
  "name": "REBASE",
  "url": "https://rebase.neb.com",
  "retrieved": "2026-02-28"
}
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | Source name (e.g., `"REBASE"`, `"NEB Buffer Performance Chart"`) |
| `url` | string (uri-reference) | Web URL or local file path (`file:///...` or `./docs/file.pdf`) |
| `retrieved` | string | ISO date `YYYY-MM-DD` |

---

## Buffer Activity Object

Added in v2. Stores NEB (or Thermo FastDigest) buffer compatibility for restriction enzymes. Set to `null` when no commercial buffer data exists for an enzyme.

```json
"buffer_activity": {
  "system": "NEB",
  "recommended_buffer": "rCutSmart Buffer",
  "buffers": {
    "r1.1": "<10",
    "r2.1": 50,
    "r3.1": 50,
    "rCutSmart": 100
  },
  "assay_conditions": {
    "incubation_temp": "37°C",
    "heat_inactivation": "80°C",
    "unit_substrate": "λ DNA"
  },
  "source": {
    "name": "NEB Buffer Performance Chart",
    "url": "https://www.neb.com/en-us/tools-and-resources/usage-guidelines/nebuffer-performance-chart-with-restriction-enzymes",
    "retrieved": "2026-03-05"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `system` | string (enum) | ✅ | `"NEB"` or `"Thermo FastDigest"` |
| `recommended_buffer` | string | | Vendor's recommended buffer for this enzyme |
| `buffers` | object | ✅ | Map of buffer name → % activity |
| `assay_conditions` | object | | Temperature, heat inactivation, substrate used |
| `source` | object | ✅ | Same shape as top-level source object |

### Buffer Names (NEB system)

| Key | Full name |
|---|---|
| `r1.1` | NEBuffer r1.1 |
| `r2.1` | NEBuffer r2.1 |
| `r3.1` | NEBuffer r3.1 |
| `rCutSmart` | rCutSmart Buffer |

### Activity Values

Each buffer value is either:
- An **integer** `0–100` representing percent activity
- A **string** `"<10"` for below-threshold (impaired) activity — used when NEB reports activity is present but too low to quantify precisely

> **Why `null` on many enzymes?** The restriction enzyme dataset sourced from REBASE contains ~6,000 entries including thousands of isoschizomers (same recognition sequence, different organism). NEB only sells ~266 enzymes commercially, so most entries correctly have `buffer_activity: null`.

---

## Assay Conditions Object

Sub-object of `buffer_activity`.

| Field | Type | Example values |
|---|---|---|
| `incubation_temp` | string or null | `"37°C"`, `"65°C"` |
| `heat_inactivation` | string or null | `"65°C"`, `"80°C"`, `"No"` |
| `unit_substrate` | string or null | `"λ DNA"`, `"pBC4 DNA"`, `"pBR322 DNA"` |

---

## Enzyme-Specific Fields

Only applicable to `type: restriction_enzyme` (and other enzyme types).

| Field | Type | Required for restriction_enzyme | Description |
|---|---|---|---|
| `recognition_sequence` | string | ✅ | IUPAC DNA sequence (e.g., `"GAATTC"`, `"CCGC(-3/-1)"`) |
| `cut_site` | string | | Cut position with `^` marker (e.g., `"G^AATTC"`) |
| `overhang` | object | | See [Overhang Object](#overhang-object) |
| `optimal_temperature_c` | number | | Optimal reaction temperature |
| `methylation_sensitivity` | string | | Dam/Dcm/CpG sensitivity notes |
| `star_activity_notes` | string | | Conditions that cause non-specific cutting |
| `buffers` | string[] | | Legacy buffer name list (prefer `buffer_activity`) |

### Overhang Object

```json
"overhang": {
  "type": "5_prime",
  "sequence": "AATT"
}
```

| Field | Type | Values |
|---|---|---|
| `type` | string (enum) | `"5_prime"`, `"3_prime"`, `"blunt"` |
| `sequence` | string or null | Overhang sequence, or `null` for blunt |

---

## Chemical-Specific Fields

| Field | Type | Description |
|---|---|---|
| `formula` | string | Molecular formula (e.g., `"NaCl"`) |
| `cas_number` | string | CAS registry number |
| `state` | string (enum) | `"solid"`, `"liquid"`, `"gas"` |
| `incompatibilities` | string[] | Incompatible substances |
| `concentration` | object | `{ "value": 1.0, "unit": "M" }` |
| `ph` | number | pH of solution |
| `working_concentration` | string | Typical working concentration |

---

## Kit-Specific Fields

| Field | Type | Description |
|---|---|---|
| `components` | object[] | `[{ "name": "...", "concentration": "..." }]` |

---

## Procedure Object

Required for all `practice` category records.

```json
"procedure": {
  "goal": "Load a precise liquid volume into a tube.",
  "prep": ["Check pipette calibration", "Select correct tip size"],
  "steps": [
    {
      "order": 1,
      "text": "Press plunger to first stop.",
      "why": "Creates precise dead volume.",
      "warning": "Do not press to second stop during aspiration."
    }
  ],
  "common_mistakes": ["Pressing to second stop while aspirating"],
  "parameters": ["Volume range: 1–10 µL"]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `goal` | string | | One-sentence purpose |
| `prep` | string[] | | Pre-procedure checklist |
| `steps` | object[] | ✅ (for practice) | Ordered steps |
| `common_mistakes` | string[] | | Frequent errors to avoid |
| `parameters` | string[] | | Key configurable values |

### Step Object

| Field | Type | Required | Description |
|---|---|---|---|
| `order` | integer ≥ 1 | ✅ | Step number |
| `text` | string | ✅ | Instruction text |
| `why` | string | | Rationale for the step |
| `warning` | string | | Safety or quality warning |

---

## Safety Object

```json
"safety": {
  "ppe": ["gloves", "lab coat", "eye protection"],
  "notes": "Dispose of ethidium bromide waste in designated containers."
}
```

---

## Vendor Object

```json
"vendor": {
  "name": "NEB",
  "catalog_number": "R0101S",
  "product_url": "https://www.neb.com/en-us/products/r0101-ecori"
}
```

---

## Media Object

Used to attach images, PDF pages, or other files to a record.

```json
"media": [
  {
    "kind": "image",
    "path": "./images/micropipette-diagram.png",
    "caption": "Two-stop pipette mechanism",
    "alt_text": "Diagram showing first and second stop positions"
  },
  {
    "kind": "pdf_page",
    "path": "./docs/protocol.pdf",
    "page": 3,
    "caption": "Restriction digest protocol page"
  }
]
```

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | string (enum) | ✅ | `"image"`, `"pdf_page"`, `"file"` |
| `path` | string (uri-reference) | ✅ | Relative or absolute path/URL |
| `caption` | string | | Display caption |
| `alt_text` | string | | Accessibility text for images |
| `page` | integer ≥ 1 | | Page number (for `pdf_page` only) |

---

## Full Minimal Examples

### Restriction Enzyme (with buffer data)
```json
{
  "id": "enzyme:restriction:ecori",
  "name": "EcoRI",
  "organism": "Escherichia coli RY13",
  "type": "restriction_enzyme",
  "category": "enzyme",
  "description": "Restriction enzyme recognizing GAATTC, produces 5' AATT overhangs.",
  "recognition_sequence": "GAATTC",
  "cut_site": "G^AATTC",
  "overhang": { "type": "5_prime", "sequence": "AATT" },
  "buffer_activity": {
    "system": "NEB",
    "recommended_buffer": "rCutSmart Buffer",
    "buffers": { "r1.1": 75, "r2.1": 100, "r3.1": 50, "rCutSmart": 100 },
    "assay_conditions": {
      "incubation_temp": "37°C",
      "heat_inactivation": "65°C",
      "unit_substrate": "λ DNA"
    },
    "source": {
      "name": "NEB Buffer Performance Chart",
      "url": "https://www.neb.com/en-us/tools-and-resources/usage-guidelines/nebuffer-performance-chart-with-restriction-enzymes",
      "retrieved": "2026-03-05"
    }
  },
  "source": {
    "name": "REBASE",
    "url": "https://rebase.neb.com",
    "retrieved": "2026-02-28"
  }
}
```

### Restriction Enzyme (no NEB data)
```json
{
  "id": "enzyme:restriction:aaai",
  "name": "AaaI",
  "organism": "Acetobacter aceti ss aceti",
  "type": "restriction_enzyme",
  "category": "enzyme",
  "description": "Restriction enzyme recognizing CGGCCG.",
  "recognition_sequence": "CGGCCG",
  "cut_site": "C^GGCCG",
  "buffer_activity": null,
  "source": {
    "name": "REBASE",
    "url": "https://rebase.neb.com",
    "retrieved": "2026-02-28"
  }
}
```

### Wetlab Practice
```json
{
  "id": "practice:micropipetting",
  "name": "Micropipetting",
  "type": "lab_procedure",
  "category": "practice",
  "description": "Accurate liquid transfer using a micropipette.",
  "keywords": ["pipette", "two-stop", "first stop", "blow out"],
  "safety": { "ppe": ["gloves", "lab coat"], "notes": "Avoid aerosols." },
  "procedure": {
    "goal": "Transfer a precise volume of liquid.",
    "steps": [
      { "order": 1, "text": "Set volume on dial.", "why": "Ensures correct volume." },
      { "order": 2, "text": "Press to first stop, submerge tip, release slowly.", "warning": "Do not press to second stop while aspirating." }
    ]
  },
  "media": [
    { "kind": "image", "path": "./images/pipette.png", "caption": "Pipette mechanism" }
  ],
  "source": {
    "name": "Lab Handbook",
    "url": "./docs/lab-handbook.pdf",
    "retrieved": "2026-01-10"
  }
}
```