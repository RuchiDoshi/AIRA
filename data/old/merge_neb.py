import json
import re
from datetime import date

with open("data/neb_buffer_raw.json", encoding="utf-8") as f:
    neb = json.load(f)

with open("data/enzymes.restriction.json", encoding="utf-8") as f:
    enzymes = json.load(f)

def parse_pct(val):
    if val == '' or val is None:
        return None
    val = val.strip().rstrip('*')
    if val.startswith('<'):
        return val
    try:
        return int(val)
    except:
        return val if val else None

def clean_name(name: str) -> str:
    """Normalize NEB enzyme names to match REBASE entries."""
    name = (name or "").strip()
    # Fix mojibake (double-encoded UTF-8, e.g. Â® -> ®)
    try:
        name = name.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    name = name.replace('\xa0', ' ')                          # non-breaking space
    name = re.sub(r'[®™]', '', name)                          # trademark symbols
    name = re.sub(r'\s*\*+$', '', name)                       # trailing asterisks
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def base_name(name: str) -> str:
    """Strip -HF, v2, -HF®v2 etc. to get the REBASE base name e.g. BsaI-HF®v2 -> BsaI."""
    return re.sub(r'[-\s]*(HF|v\d+).*$', '', name, flags=re.IGNORECASE).strip()

# ── Build NEB lookup ──────────────────────────────────────────────────────────
neb_lookup = {}  # clean_name -> data
neb_lookup_base = {}  # base_name -> data (fallback for HF variants)

for row in neb['data']:
    if len(row) < 8:
        continue
    raw_name = row[0].strip()
    cln  = clean_name(raw_name)
    base = base_name(cln)

    r1  = parse_pct(row[4])
    r2  = parse_pct(row[5])
    r3  = parse_pct(row[6])
    rcs = parse_pct(row[7])

    buffers = {}
    if r1  is not None: buffers['r1.1']      = r1
    if r2  is not None: buffers['r2.1']      = r2
    if r3  is not None: buffers['r3.1']      = r3
    if rcs is not None: buffers['rCutSmart'] = rcs

    entry = {
        'recommended_buffer': clean_name(row[3]),
        'buffers': buffers,
        'heat_inactivation': row[8] or None,
        'incubation_temp_c': row[9] or None,
        'unit_substrate': row[14] or None,
    }

    neb_lookup[cln] = entry
    # Store under base name as fallback (don't overwrite if base already has an entry)
    if base and base not in neb_lookup_base:
        neb_lookup_base[base] = entry

print(f"NEB lookup entries: {len(neb_lookup)}")
print(f"Base name fallback entries: {len(neb_lookup_base)}")
print("Sample keys:", list(neb_lookup.keys())[:10])

for test in ["BsaI", "AscI", "HindIII", "EcoRI", "BsmBI"]:
    found_exact = test in neb_lookup
    found_base  = test in neb_lookup_base
    print(f"  {test}: {'EXACT' if found_exact else 'BASE' if found_base else 'MISSING'}")

# ── Merge into enzymes ────────────────────────────────────────────────────────
today = date.today().isoformat()
matched = 0

for enzyme in enzymes:
    raw  = enzyme['name'].strip()
    cln  = clean_name(raw)
    base = base_name(cln)

    match = neb_lookup.get(cln) or neb_lookup.get(raw) or neb_lookup_base.get(cln) or neb_lookup_base.get(base)
       
    if match:
        matched += 1
        enzyme['buffer_activity'] = {
            'system': 'NEB',
            'recommended_buffer': match['recommended_buffer'],
            'buffers': match['buffers'],
            'assay_conditions': {
                'incubation_temp': match['incubation_temp_c'],
                'heat_inactivation': match['heat_inactivation'],
                'unit_substrate': match['unit_substrate'],
            },
            'source': {
                'name': 'NEB Buffer Performance Chart',
                'url': 'https://www.neb.com/en-us/tools-and-resources/usage-guidelines/nebuffer-performance-chart-with-restriction-enzymes',
                'retrieved': today
            }
        }
    else:
        enzyme['buffer_activity'] = None

print(f"\nTotal enzymes: {len(enzymes)}")
print(f"Matched with NEB data: {matched}")
print(f"No NEB data (null): {len(enzymes) - matched}")

with open("data/enzymes.restriction.buffer.json", "w", encoding="utf-8") as f:
    json.dump(enzymes, f, indent=2, ensure_ascii=False)

print("\nSaved to data/enzymes.restriction.buffer.json")