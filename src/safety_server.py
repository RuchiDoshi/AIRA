import json
import os
import sys
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process
from mcp.server.fastmcp import FastMCP

# ---------- Load data ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root

DATA_FILES = [
    "wetlab.practices.json",       # lab procedures (pipetting, centrifuge, etc.)
    "uw.lsm.json",   # UW LSM: sharps, waste, spills, PPE, etc.
]

# ALL items from both files — used for search and list tools
ALL_ITEMS: List[Dict[str, Any]] = []

for fname in DATA_FILES:
    path = os.path.join(BASE_DIR, "data", fname)
    print(f"Loading: {path}", file=sys.stderr)
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
        print(f"{fname} first 80 chars: {repr(txt[:80])}", file=sys.stderr)
        data = json.loads(txt)
        ALL_ITEMS.extend(data)

# ---------- Build name lookup ----------
NAME_TO_ITEM: Dict[str, Dict[str, Any]] = {}
NAME_CHOICES: List[str] = []

def _add_choice(label: str, item: Dict[str, Any]) -> None:
    k = (label or "").strip().lower()
    if not k:
        return
    if k not in NAME_TO_ITEM:  # keep first seen
        NAME_TO_ITEM[k] = item
    NAME_CHOICES.append(label)

for item in ALL_ITEMS:
    if item.get("name"):
        _add_choice(item["name"], item)
    for a in item.get("aliases", []):
        _add_choice(a, item)
    for kw in item.get("keywords", []):
        _add_choice(kw, item)

def best_match(query: str, cutoff: int = 72) -> Optional[str]:
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
mcp = FastMCP("wetlab-safety-mcp")


# ── Discovery ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_topics() -> List[Dict[str, str]]:
    """
    Return all available safety and practice topics across both data sources
    (wetlab procedures AND UW Lab Safety Manual content).
    Each entry includes id, name, category, type, and short description.
    Use this to discover what is available before making a specific lookup.
    """
    return [
        {
            "id": item.get("id", ""),
            "name": item["name"],
            "category": item.get("category", ""),
            "type": item.get("type", ""),
            "description": item.get("description", ""),
            "source": item.get("source", {}).get("name", "")
        }
        for item in ALL_ITEMS
    ]


@mcp.tool()
def list_practices() -> List[Dict[str, str]]:
    """
    Return only wetlab practice topics (pipetting, centrifuge, vortexing, etc.).
    Use list_topics() for the full combined list including safety regulations.
    """
    return [
        {"id": item.get("id", ""), "name": item["name"], "description": item.get("description", "")}
        for item in ALL_ITEMS
        if item.get("category") == "practice"
    ]


@mcp.tool()
def list_safety_topics() -> List[Dict[str, str]]:
    """
    Return only safety regulation topics from the UW Laboratory Safety Manual
    (sharps disposal, hazardous waste, spill response, PPE, etc.).
    """
    return [
        {"id": item.get("id", ""), "name": item["name"], "description": item.get("description", "")}
        for item in ALL_ITEMS
        if item.get("category") == "safety"
    ]


# ── Core lookup tools ─────────────────────────────────────────────────────────

@mcp.tool()
def search_topics(query: str, limit: int = 6) -> Dict[str, Any]:
    """
    Fuzzy search across ALL safety and practice topics by name, alias, or keyword.
    Searches both wetlab procedures and UW Lab Safety Manual content.
    Useful when the user is unsure of the exact topic name.
    """
    q = (query or "").strip()
    if not q:
        return {"query": query, "results": []}

    fuzzy = process.extract(q, NAME_CHOICES, scorer=fuzz.WRatio, limit=limit * 2)
    results = []
    seen_ids = set()
    for label, score, _ in fuzzy:
        item = NAME_TO_ITEM.get(label.lower())
        if not item:
            continue
        item_id = item.get("id", item.get("name"))
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        results.append({
            "name": item["name"],
            "score": score,
            "category": item.get("category", ""),
            "type": item.get("type", ""),
            "description": item.get("description", ""),
            "hazards": item.get("hazards", [])
        })
        if len(results) >= limit:
            break

    return {"query": query, "results": results}


@mcp.tool()
def get_topic_details(name: str) -> Dict[str, Any]:
    """
    Return the full record for any topic — wetlab practice OR safety regulation —
    by name, alias, or keyword. Returns the complete procedure, steps, safety info,
    and media. Use this as the primary lookup for any user question about a specific
    topic (e.g., 'sharps disposal', 'micropipetting', 'chemical spill', 'PPE').
    """
    matched = best_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "suggestions": [
                {"name": m, "score": s}
                for m, s, _ in process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
            ]
        }
    item = NAME_TO_ITEM[matched.lower()]
    return {"found": True, "match": matched, "data": item}


@mcp.tool()
def get_practice_steps(name: str) -> Dict[str, Any]:
    """
    Return procedure steps, safety info, common mistakes, and media for a wetlab
    practice (e.g. 'micropipetting', 'centrifuge', 'vortexing', 'thermocycler').
    For regulatory safety topics use get_topic_details() instead.
    """
    matched = best_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "suggestions": [
                {"name": m, "score": s}
                for m, s, _ in process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
            ]
        }
    item = NAME_TO_ITEM[matched.lower()]
    procedure = item.get("procedure") or {}
    safety = item.get("safety") or {}
    return {
        "found": True,
        "match": matched,
        "category": item.get("category"),
        "description": item.get("description"),
        "goal": procedure.get("goal"),
        "prep": procedure.get("prep", []),
        "steps": procedure.get("steps", []),
        "common_mistakes": procedure.get("common_mistakes", []),
        "parameters": procedure.get("parameters", []),
        "ppe": safety.get("ppe", []),
        "safety_notes": safety.get("notes"),
        "hazards": item.get("hazards", []),
        "media": item.get("media", []),
        "source": item.get("source", {})
    }


# ── Safety-focused tools ───────────────────────────────────────────────────────

@mcp.tool()
def get_safety_info(name: str) -> Dict[str, Any]:
    """
    Return safety-focused data for any topic: PPE requirements, safety notes,
    hazards, and warnings embedded in procedure steps.
    Works for both wetlab practices and UW Lab Safety Manual topics.
    Use this when the user asks specifically about risks or safety precautions.
    """
    matched = best_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "suggestions": [
                {"name": m, "score": s}
                for m, s, _ in process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
            ]
        }
    item = NAME_TO_ITEM[matched.lower()]
    procedure = item.get("procedure") or {}
    safety = item.get("safety") or {}

    # Extract steps that carry a warning field
    step_warnings = [
        {"step": s.get("order"), "text": s.get("text"), "warning": s.get("warning")}
        for s in procedure.get("steps", [])
        if s.get("warning")
    ]

    return {
        "found": True,
        "match": matched,
        "category": item.get("category"),
        "type": item.get("type"),
        "ppe": safety.get("ppe", []),
        "safety_notes": safety.get("notes"),
        "hazards": item.get("hazards", []),
        "step_warnings": step_warnings,
        "source": item.get("source", {})
    }


@mcp.tool()
def get_disposal_guidance(waste_type: str) -> Dict[str, Any]:
    """
    Look up disposal guidance for a specific waste type.
    Recognizes: 'sharps', 'needles', 'pipette tips', 'biohazardous glass',
    'chemical waste', 'hazardous waste', 'lab glass', 'trace chemo', and more.
    Returns full disposal procedure from the UW Lab Safety Manual.
    """
    matched = best_match(waste_type)
    if not matched:
        return {
            "found": False,
            "query": waste_type,
            "suggestions": [
                {"name": m, "score": s}
                for m, s, _ in process.extract(waste_type, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
            ]
        }
    item = NAME_TO_ITEM[matched.lower()]
    procedure = item.get("procedure") or {}
    return {
        "found": True,
        "match": matched,
        "type": item.get("type"),
        "description": item.get("description"),
        "goal": procedure.get("goal"),
        "steps": procedure.get("steps", []),
        "common_mistakes": procedure.get("common_mistakes", []),
        "prohibited_in_trash": procedure.get("prohibited_in_trash"),
        "always_sharps": procedure.get("always_sharps"),
        "sharps_if_contaminated": procedure.get("sharps_if_contaminated"),
        "contaminated_items": procedure.get("contaminated_items"),
        "hazards": item.get("hazards", []),
        "ppe": (item.get("safety") or {}).get("ppe", []),
        "source": item.get("source", {})
    }


@mcp.tool()
def get_spill_response(spill_type: str = "chemical") -> Dict[str, Any]:
    """
    Return step-by-step spill response guidance.
    spill_type: 'chemical', 'biohazardous', or 'bio' — defaults to 'chemical'.
    Includes S.W.I.M. framework, small vs. large spill decision guide,
    spill kit contents, and emergency contacts.
    """
    query = "biohazardous spill" if spill_type.lower() in ("bio", "biohazardous", "biological") else "chemical spill"
    matched = best_match(query)
    if not matched:
        return {"found": False, "query": query}
    item = NAME_TO_ITEM[matched.lower()]
    procedure = item.get("procedure") or {}
    return {
        "found": True,
        "match": matched,
        "description": item.get("description"),
        "hazards": item.get("hazards", []),
        "ppe": (item.get("safety") or {}).get("ppe", []),
        "safety_notes": (item.get("safety") or {}).get("notes"),
        "decision_guide": procedure.get("decision_guide"),
        "swim_framework": procedure.get("swim_framework"),
        "steps": procedure.get("steps", []),
        "spill_kit_contents": procedure.get("spill_kit_contents") or procedure.get("biohazard_spill_kit_contents"),
        "emergency_contacts": procedure.get("emergency_contacts"),
        "common_mistakes": procedure.get("common_mistakes", []),
        "source": item.get("source", {})
    }


@mcp.tool()
def get_ppe_requirements(name: str) -> Dict[str, Any]:
    """
    Return PPE requirements for a given practice or hazard type.
    Checks the topic's own safety field and, for general PPE questions,
    returns detailed glove, eye, apparel, and lab coat rules from the UW LSM.
    """
    matched = best_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "suggestions": [
                {"name": m, "score": s}
                for m, s, _ in process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
            ]
        }
    item = NAME_TO_ITEM[matched.lower()]
    safety = item.get("safety") or {}
    procedure = item.get("procedure") or {}
    return {
        "found": True,
        "match": matched,
        "ppe": safety.get("ppe", []),
        "notes": safety.get("notes"),
        "hazards": item.get("hazards", []),
        # Detailed PPE sub-sections present on the LSM PPE entry
        "eye_protection": procedure.get("eye_protection"),
        "apparel_rules": procedure.get("apparel_rules"),
        "lab_coat_rules": procedure.get("lab_coat_rules"),
        "glove_rules": procedure.get("glove_rules"),
        "ppe_outside_lab": procedure.get("ppe_outside_lab"),
        "source": item.get("source", {})
    }


@mcp.tool()
def list_all_hazards() -> List[Dict[str, Any]]:
    """
    Return a summary of all hazards across every topic in both data sources.
    Useful for a quick lab safety overview or onboarding checklist.
    """
    return [
        {
            "id": item.get("id", ""),
            "topic": item["name"],
            "category": item.get("category", ""),
            "hazards": item.get("hazards", []),
            "ppe": (item.get("safety") or {}).get("ppe", [])
        }
        for item in ALL_ITEMS
        if item.get("hazards")
    ]


if __name__ == "__main__":
    print("Starting wetlab safety MCP server...", file=sys.stderr)
    mcp.run()
    print("MCP server stopped.", file=sys.stderr)