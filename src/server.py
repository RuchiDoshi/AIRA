import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process
from mcp.server.fastmcp import FastMCP

# ---------- Load data ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
DATA_PATH = os.path.join(BASE_DIR, "data", "enzymes.restriction.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    REAGENTS: List[Dict[str, Any]] = json.load(f)

# build name lookup
NAME_TO_ITEM: Dict[str, Dict[str, Any]] = {}
NAME_CHOICES: List[str] = []

for item in REAGENTS:
    nm = (item.get("name") or "").strip()
    if nm:
        NAME_TO_ITEM[nm.lower()] = item
        NAME_CHOICES.append(nm)

def best_name_match(query: str, cutoff: int = 80) -> Optional[str]:
    q = (query or "").strip()
    if not q:
        return None
    if q.lower() in NAME_TO_ITEM:
        return q

    match = process.extractOne(q, NAME_CHOICES, scorer=fuzz.WRatio)
    if match and match[1] >= cutoff:
        return match[0]
    return None

# ---------- MCP server ----------
mcp = FastMCP("restriction-enzymes-mcp")

@mcp.tool()
def get_reagent_details(name: str) -> Dict[str, Any]:
    """Flexible lookup by enzyme/reagent name."""
    matched = best_name_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "message": "No close match found.",
            "suggestions": process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
        }
    return {"found": True, "match": matched, "data": NAME_TO_ITEM[matched.lower()]}

@mcp.tool()
def search_reagents(query: str, limit: int = 10) -> Dict[str, Any]:
    """Fuzzy search by name; also supports DNA-ish queries."""
    q = (query or "").strip()
    if not q:
        return {"query": query, "results": []}

    results = []
    fuzzy = process.extract(q, NAME_CHOICES, scorer=fuzz.WRatio, limit=limit)
    for name, score, _ in fuzzy:
        results.append({"name": name, "score": score, "data": NAME_TO_ITEM[name.lower()]})

    # If query looks like DNA, also match recognition_sequence
    dnaish = all(ch in "ACGTN^/" for ch in q.upper()) and any(ch in "ACGT" for ch in q.upper())
    if dnaish:
        qseq = q.upper().replace("^", "")
        for item in REAGENTS:
            seq = (item.get("recognition_sequence") or "").upper()
            if seq and qseq in seq:
                results.append({"name": item.get("name"), "score": 100, "data": item})
                if len(results) >= limit:
                    break

    return {"query": query, "results": results[:limit]}

@mcp.tool()
def find_enzymes_by_sequence(sequence: str, limit: int = 25) -> Dict[str, Any]:
    """Return enzymes whose recognition_sequence appears in the provided DNA sequence."""
    seq = (sequence or "").upper().replace(" ", "")
    matches = []
    for item in REAGENTS:
        rs = (item.get("recognition_sequence") or "").upper()
        if rs and rs in seq:
            matches.append(item)
            if len(matches) >= limit:
                break
    return {"query_sequence": sequence, "matches": matches}

if __name__ == "__main__":
    import sys
    print("Starting MCP server...", file=sys.stderr)
    mcp.run()
    print("MCP server stopped.", file=sys.stderr)