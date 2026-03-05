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

# Build NEB lookup - strip footnote symbols including encoding artifacts (Â§, §, $, etc.)
neb_lookup = {}
for row in neb['data']:
    if len(row) < 8:
        continue
    raw_name = row[0].strip()
    clean_name = re.sub(r'[\s§$†‡Â®™\u00c2\u00a7\u00ae]+.*$', '', raw_name).strip()

    r1  = parse_pct(row[4])
    r2  = parse_pct(row[5])
    r3  = parse_pct(row[6])
    rcs = parse_pct(row[7])

    buffers = {}
    if r1  is not None: buffers['r1.1']      = r1
    if r2  is not None: buffers['r2.1']      = r2
    if r3  is not None: buffers['r3.1']      = r3
    if rcs is not None: buffers['rCutSmart'] = rcs

    neb_lookup[clean_name] = {
        'recommended_buffer': row[3].replace('™', '').replace('®', '').strip(),
        'buffers': buffers,
        'heat_inactivation': row[8] or None,
        'incubation_temp_c': row[9] or None,
        'unit_substrate': row[14] or None,
    }

print(f"NEB lookup entries: {len(neb_lookup)}")
print("Sample keys:", list(neb_lookup.keys())[:10])

# Verify the problem enzymes are now found
for test in ["AscI", "SexAI", "HindIII", "EcoRI"]:
    print(f"  {test}: {'FOUND' if test in neb_lookup else 'MISSING'}")

today = date.today().isoformat()
matched = 0

for enzyme in enzymes:
    name = enzyme['name'].strip()
    match = neb_lookup.get(name)

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
