import json
from datetime import date

input_file = "data/sources/withref.txt"
output_file = "data/enzymes.restriction.json"

enzymes = []
current = {}

with open(input_file, encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if not line:
            # end of record
            if "name" in current:
                enzymes.append(current)
            current = {}
            continue

        if line.startswith("<1>"):
            current["id"] = f"enzyme:restriction:{line[3:].lower()}"
            current["name"] = line[3:]

        elif line.startswith("<5>"):
            seq = line[3:]
            current["recognition_sequence"] = seq.replace("^", "")
            current["cut_site"] = seq

        elif line.startswith("<3>"):
            current["organism"] = line[3:]

# add required schema fields
for e in enzymes:
    e["type"] = "restriction_enzyme"
    e["category"] = "enzyme"
    e["description"] = f"Restriction enzyme recognizing {e.get('recognition_sequence','unknown')}."
    e["source"] = {
        "name": "REBASE",
        "url": "https://rebase.neb.com",
        "retrieved": str(date.today())
    }

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(enzymes, f, indent=2)

print(f"Saved {len(enzymes)} enzymes → {output_file}")