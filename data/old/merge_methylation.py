import json
import re

# ── Symbol map for methylation ────────────────────────────────────────────────
SYMBOL_MAP = {
    "●":       "not_sensitive",
    "■":       "blocked",
    "□ ol":    "blocked_overlapping",
    "□ scol":  "blocked_some_overlapping",
    "◆":       "impaired",
    "◇ ol":    "impaired_overlapping",
    "◇ scol":  "impaired_some_overlapping",
    "":        None,
}

def parse_symbol(val: str):
    v = (val or "").strip()
    v = v.replace("◼", "■").replace("◻", "□")
    return SYMBOL_MAP.get(v, None)

def clean_name(name: str) -> str:
    name = (name or "").strip()
    # Fix mojibake from double-encoded UTF-8
    try:
        name = name.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    name = re.sub(r'\s*\*+$', '', name)
    name = re.sub(r'[®™]', '', name)
    name = re.sub(r'\xa0', ' ', name)       # non-breaking space
    name = re.sub(r'[-\s]*(HF|v\d+).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def base_name(name: str) -> str:
    return re.sub(r'[-\s]*(HF|v\d+).*$', '', name, flags=re.IGNORECASE).strip()

# ── Parse methylation_raw.json ────────────────────────────────────────────────
with open("data/methylation_raw.json", encoding="utf-8") as f:
    meth_raw = json.load(f)

meth_lookup = {}
for row in meth_raw:
    name = (row.get("enzyme") or "").strip()
    if not name or any(c in name for c in "●■□◆◇◼◻"):
        continue
    clean = clean_name(name)
    meth_lookup[clean] = {
        "dam": parse_symbol(row.get("dam", "")),
        "dcm": parse_symbol(row.get("dcm", "")),
        "cpg": parse_symbol(row.get("cpg", "")),
    }

print(f"Methylation entries: {len(meth_lookup)}")

# ── Parse typeiis_raw.json (columns shifted by 1 due to hidden column) ────────
with open("data/typeiis_raw.json", encoding="utf-8") as f:
    iis_raw = json.load(f)

iis_lookup = {}
for row in iis_raw:
    name = clean_name(row.get("enzyme", ""))
    if not name:
        continue

    # Corrected column mapping:
    heat_inact    = row.get("recommended_buffer", "").strip()    # Y/N
    rec_buffer    = row.get("incubation_temp", "").strip()       # e.g. rCutSmart
    inc_temp      = row.get("activity_at_37c", "").strip()       # e.g. 37°C
    storage_temp  = row.get("recognition_sequence", "").strip()  # e.g. -20°C
    rec_seq       = row.get("recognition_seq_length", "").strip()
    overhang_len  = row.get("isoschizomers", "").strip()
    isoschizomers = row.get("methylation_sensitivity", "").strip()

    temp_match   = re.search(r'(-?\d+)', inc_temp)
    inc_temp_int = int(temp_match.group(1)) if temp_match else None

    try:
        oh_len_int = int(overhang_len)
    except:
        oh_len_int = None

    iis_lookup[name] = {
        "heat_inactivation_possible": heat_inact.upper() == "Y",
        "recommended_buffer":   rec_buffer or None,
        "incubation_temp_c":    inc_temp_int,
        "storage_temp":         storage_temp or None,
        "recognition_sequence": rec_seq or None,
        "overhang_length":      oh_len_int,
        "isoschizomers_neb":    [i.strip() for i in isoschizomers.split(",") if i.strip()],
    }

print(f"Type IIS entries: {len(iis_lookup)}")

# ── Load and merge ────────────────────────────────────────────────────────────
with open("data/enzymes.restriction.buffer.json", encoding="utf-8") as f:
    enzymes = json.load(f)

meth_matched = 0
iis_matched  = 0

for enzyme in enzymes:
    raw  = enzyme.get("name", "").strip()
    cln  = clean_name(raw)
    base = base_name(cln)

    # Methylation
    meth = meth_lookup.get(cln) or meth_lookup.get(raw) or meth_lookup.get(base)
    if meth:
        enzyme["methylation_sensitivity"] = {
            "dam": meth["dam"],
            "dcm": meth["dcm"],
            "cpg": meth["cpg"],
            "source": "NEB Dam-Dcm and CpG Methylation chart"
        }
        meth_matched += 1
    else:
        enzyme.setdefault("methylation_sensitivity", None)

    # Type IIS enrichment
    iis = iis_lookup.get(cln) or iis_lookup.get(raw) or iis_lookup.get(base)
    if iis:
        iis_matched += 1
        enzyme["enzyme_type"] = "Type IIS"
        enzyme["iis_data"] = {
            "heat_inactivation_possible": iis["heat_inactivation_possible"],
            "incubation_temp_c":          iis["incubation_temp_c"],
            "storage_temp":               iis["storage_temp"],
            "overhang_length":            iis["overhang_length"],
            "isoschizomers_neb":          iis["isoschizomers_neb"],
        }
        # Backfill buffer_activity assay_conditions if missing
        ba = enzyme.get("buffer_activity")
        if ba and isinstance(ba, dict):
            ac = ba.setdefault("assay_conditions", {})
            if not ac.get("incubation_temp"):
                ac["incubation_temp"] = iis["incubation_temp_c"]
            if not ac.get("heat_inactivation"):
                ac["heat_inactivation_possible"] = iis["heat_inactivation_possible"]

print(f"\nTotal enzymes: {len(enzymes)}")
print(f"Methylation matched: {meth_matched}")
print(f"Type IIS enriched: {iis_matched}")

from collections import Counter
types = Counter(e.get("enzyme_type") for e in enzymes)
print("\nEnzyme type breakdown:")
for t, c in sorted(types.items(), key=lambda x: (x[0] is None, x[0])):
    print(f"  {t}: {c}")

with open("data/enzymes.restriction.buffer.json", "w", encoding="utf-8") as f:
    json.dump(enzymes, f, indent=2, ensure_ascii=False)

print("\nSaved to data/enzymes.restriction.buffer.json")