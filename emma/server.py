from fastmcp import FastMCP
from rapidfuzz import process
import json
import os

# Create MCP app
mcp = FastMCP("enzyme_server")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(BASE_DIR, "neb_enzymes.json")

with open(json_path, "r", encoding="utf-8") as f:
    enzymes = json.load(f)
    
enzyme_names = [e["name"] for e in enzymes]


@mcp.tool()
def get_reagent_details(name: str) -> dict:
    """
    Get enzyme details by name (fuzzy match supported).
    """

    match, score, _ = process.extractOne(name, enzyme_names)

    if score < 60:
        return {"error": "No close match found"}

    for enzyme in enzymes:
        if enzyme["name"] == match:
            return enzyme

    return {"error": "Not found"}


if __name__ == "__main__":
    mcp.run()

@mcp.tool()
def search_by_sequence(sequence: str) -> list:
    """
    Search enzymes by recognition sequence fragment.
    """
    results = []
    for enzyme in enzymes:
        if sequence.upper() in enzyme["recognition_sequence"].upper():
            results.append(enzyme)
    return results[:10]