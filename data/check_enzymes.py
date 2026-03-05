import json

with open("data/neb_buffer_raw.json") as f:
    neb = json.load(f)

names = [r[0] for r in neb["data"]]
for target in ["AscI", "SexAI", "HindIII", "EcoRI"]:
    match = [n for n in names if target.lower() in n.lower()]
    print(f"{target}: {match}")
