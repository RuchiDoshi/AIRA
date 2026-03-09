import json
import re

with open("data/overhang_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

with open("data/enzymes.restriction.buffer.json", encoding="utf-8") as f:
    enzymes = json.load(f)

# ── Parse the NEB cleavage site notation e.g. "G/GTACC" ──────────────────────
def parse_overhang(cleavage_site: str):
    """
    Parse NEB slash notation into structured overhang data.
    Returns dict with type, sequence, and length or None if unparseable.
    
    Examples:
      G/AATTC  -> 5' overhang, AATT, len 4
      CTGCA/G  -> 3' overhang, ACGT (complement), len 4  
      GG/CC    -> blunt
    """
    cs = (cleavage_site or "").strip()
    if not cs or "/" not in cs:
        return None

    parts = cs.split("/")
    if len(parts) != 2:
        return None

    left, right = parts
    left_len  = len(left)
    right_len = len(right)
    total_len = left_len + right_len

    # Blunt: slash is exactly in the middle
    if left_len == right_len:
        return {
            "type": "blunt",
            "sequence": None,
            "length": 0
        }

    # 5' overhang: right side is longer (cut leaves 5' extension)
    if right_len > left_len:
        overhang_seq = right[:right_len - left_len] if left_len > 0 else right
        # More precise: the overhang is the "extra" bases on the right
        overhang_seq = cs.replace("/", "")[left_len : left_len + (right_len - left_len)]
        return {
            "type": "5_prime",
            "sequence": overhang_seq.upper(),
            "length": right_len - left_len
        }

    # 3' overhang: left side is longer
    if left_len > right_len:
        overhang_seq = left[right_len:]
        return {
            "type": "3_prime",
            "sequence": overhang_seq.upper(),
            "length": left_len - right_len
        }

    return None


def clean_recleavable(raw_str: str):
    """Strip footnote numbers and split into list."""
    if not raw_str:
        return []
    # Remove superscript-style footnote numbers (e.g. "SnaBI6" -> "SnaBI")
    cleaned = re.sub(r'\d+$', '', raw_str.strip())
    entries = re.split(r',\s*', cleaned)
    result = []
    for e in entries:
        e = re.sub(r'\d+', '', e).strip().strip('()')
        if e:
            result.append(e)
    return result


# ── Build overhang lookup keyed by enzyme name ────────────────────────────────
overhang_lookup = {}
skipped = 0

for row in raw:
    name = (row.get("enzyme") or "").strip()

    # Filter out header/example rows - real enzyme names start with uppercase
    # and don't contain "'" or "..." or "->"
    if not name or any(c in name for c in ["'", ".", ">"]):
        skipped += 1
        continue
    # Skip if cleavage site looks like example text
    cs = (row.get("cleavage_site") or "").strip()
    if not cs or any(c in cs for c in ["'", "."]):
        skipped += 1
        continue

    overhang = parse_overhang(cs)
    recleavable = clean_recleavable(row.get("recleavable_by", ""))
    after_fill = (row.get("after_fill_ligation") or "").strip()

    overhang_lookup[name] = {
        "overhang": overhang,
        "after_fill_ligation": after_fill if after_fill else None,
        "recleavable_by": recleavable if recleavable else None,
    }

print(f"Overhang entries parsed: {len(overhang_lookup)}")
print(f"Rows skipped (headers/examples): {skipped}")
print("Sample entries:")
for k, v in list(overhang_lookup.items())[:5]:
    print(f"  {k}: {v}")

# ── Merge into enzymes ────────────────────────────────────────────────────────
matched = 0
for enzyme in enzymes:
    name = enzyme.get("name", "").strip()
    match = overhang_lookup.get(name)
    if match:
        matched += 1
        enzyme["overhang"]             = match["overhang"]
        enzyme["after_fill_ligation"]  = match["after_fill_ligation"]
        enzyme["recleavable_by"]       = match["recleavable_by"]
    else:
        # Try to derive overhang from existing cut_site (^ notation) as fallback
        cut_site = enzyme.get("cut_site", "")
        if cut_site and "^" in cut_site:
            seq = cut_site.replace("^", "")
            pos = cut_site.index("^")
            half = len(seq) // 2
            if pos == half:
                enzyme["overhang"] = {"type": "blunt", "sequence": None, "length": 0}
            elif pos < half:
                oh_seq = seq[pos:half]
                enzyme["overhang"] = {"type": "5_prime", "sequence": oh_seq, "length": len(oh_seq)}
            else:
                oh_seq = seq[half:pos]
                enzyme["overhang"] = {"type": "3_prime", "sequence": oh_seq, "length": len(oh_seq)}
        else:
            enzyme["overhang"] = None
        enzyme["after_fill_ligation"] = None
        enzyme["recleavable_by"]      = None

print(f"\nTotal enzymes: {len(enzymes)}")
print(f"Matched with NEB overhang data: {matched}")
print(f"Fallback (^ parsing or null): {len(enzymes) - matched}")

with open("data/enzymes.restriction.buffer.json", "w", encoding="utf-8") as f:
    json.dump(enzymes, f, indent=2, ensure_ascii=False)

print("\nSaved to data/enzymes.restriction.buffer.json")