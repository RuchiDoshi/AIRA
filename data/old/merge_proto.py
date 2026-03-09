import json
import re

# ── Parse proto.txt ───────────────────────────────────────────────────────────
proto_lookup = {}  # enzyme_name -> enzyme_type string

with open("data/proto.txt", encoding="utf-8") as f:
    lines = f.readlines()

current_type = None

for line in lines:
    stripped = line.strip()

    # Detect section headers e.g. "TYPE II ENZYMES", "TYPE IIS ENZYMES" etc.
    header_match = re.match(r'^TYPE\s+(I{1,3}V?|I?V?I*S?|IIS|IIP|IIM|IIG|IIF|IIE|IIC|IIB|IIA|IIT|IIH|IV)\s+ENZYMES', stripped)
    if header_match:
        current_type = "Type " + header_match.group(1)
        continue

    # Skip blank lines, dashes, headers
    if not stripped or stripped.startswith("=") or stripped.startswith("-") or stripped.startswith("REBASE") or stripped.startswith("Copyright") or stripped.startswith("Rich"):
        continue

    # Parse enzyme lines: "EcoRI    GAATTC" or "AarI    CACCTGC (4/8)"
    parts = stripped.split()
    if len(parts) >= 2 and current_type:
        name = parts[0]
        proto_lookup[name] = current_type

print(f"Proto entries parsed: {len(proto_lookup)}")

# Show type breakdown
from collections import Counter
type_counts = Counter(proto_lookup.values())
for t, count in sorted(type_counts.items()):
    print(f"  {t}: {count}")

# ── Also derive type from recognition sequence as fallback ────────────────────
def infer_type_from_sequence(rec_seq: str) -> str | None:
    """
    Infer enzyme type from recognition sequence notation.
    Type IIS: offset cut notation like CACCTGC(4/8) or GGTCTC(1/5)
    Type III: large offset like CAGCAG(25/27)
    """
    if not rec_seq:
        return None
    # Type IIS/III: parenthetical offset notation
    m = re.search(r'\((\d+)/(\d+)\)', rec_seq)
    if m:
        offset = int(m.group(1))
        if offset >= 20:
            return "Type III"
        else:
            return "Type IIS"
    # Negative offset notation like CCGC(-3/-1)
    if re.search(r'\(-\d+/-\d+\)', rec_seq):
        return "Type IIS"
    return None

# ── Merge into enzymes ────────────────────────────────────────────────────────
with open("data/enzymes.restriction.buffer.json", encoding="utf-8") as f:
    enzymes = json.load(f)

matched_proto  = 0
inferred       = 0
default_type   = 0

for enzyme in enzymes:
    name = enzyme.get("name", "").strip()

    if name in proto_lookup:
        enzyme["enzyme_type"] = proto_lookup[name]
        matched_proto += 1
    else:
        # Fallback: infer from recognition sequence notation
        inferred_type = infer_type_from_sequence(
            enzyme.get("recognition_sequence", "")
        )
        if inferred_type:
            enzyme["enzyme_type"] = inferred_type
            inferred += 1
        else:
            # Safe default — vast majority of REBASE enzymes are Type II
            enzyme["enzyme_type"] = "Type II"
            default_type += 1

print(f"\nTotal enzymes: {len(enzymes)}")
print(f"Matched from proto.txt: {matched_proto}")
print(f"Inferred from sequence notation: {inferred}")
print(f"Defaulted to Type II: {default_type}")

# Sanity check - show any Type I and III that got assigned
type_iis = [e['name'] for e in enzymes if e.get('enzyme_type') == 'Type IIS'][:10]
print(f"\nSample Type IIS enzymes: {type_iis}")

with open("data/enzymes.restriction.buffer.json", "w", encoding="utf-8") as f:
    json.dump(enzymes, f, indent=2, ensure_ascii=False)

print("\nSaved to data/enzymes.restriction.buffer.json")