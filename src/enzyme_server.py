import json
import os
import sys
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process
from mcp.server.fastmcp import FastMCP

# ---------- Load data ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
DATA_FILES = [
    "enzymes.restriction.buffer.json",
]

REAGENTS = []

for fname in DATA_FILES:
    path = os.path.join(BASE_DIR, "data", fname)
    print(f"Loading: {path}", file=sys.stderr)
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
        print(f"{fname} first 80 chars: {repr(txt[:80])}", file=sys.stderr)
        data = json.loads(txt)
        REAGENTS.extend(data)

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

for item in REAGENTS:
    if item.get("name"):
        _add_choice(item["name"], item)
    for a in item.get("aliases", []):
        _add_choice(a, item)
    for kw in item.get("keywords", []):
        _add_choice(kw, item)

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

def _get_item(name: str) -> Optional[Dict[str, Any]]:
    """Resolve name to item dict, or None if not found."""
    matched = best_name_match(name)
    if not matched:
        return None
    return NAME_TO_ITEM.get(matched.lower())

# ---------- MCP server ----------
mcp = FastMCP("restriction-enzymes-mcp")


@mcp.tool()
def get_reagent_details(name: str) -> Dict[str, Any]:
    """Flexible lookup by enzyme/reagent name. Returns full data record."""
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
    """Fuzzy search by name; also supports DNA sequence queries."""
    q = (query or "").strip()
    if not q:
        return {"query": query, "results": []}

    results = []
    fuzzy = process.extract(q, NAME_CHOICES, scorer=fuzz.WRatio, limit=limit)
    for name, score, _ in fuzzy:
        results.append({"name": name, "score": score, "data": NAME_TO_ITEM[name.lower()]})

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


@mcp.tool()
def get_buffer_activity(name: str) -> Dict[str, Any]:
    """Return buffer % activity, recommended buffer, and assay conditions for an enzyme."""
    matched = best_name_match(name)
    if not matched:
        return {"found": False, "query": name}
    item = NAME_TO_ITEM[matched.lower()]
    ba = item.get("buffer_activity")
    if not ba:
        return {
            "found": True,
            "match": matched,
            "has_buffer_data": False,
            "message": "No NEB buffer data available (enzyme may not be commercially sold by NEB)."
        }
    return {"found": True, "match": matched, "has_buffer_data": True, "buffer_activity": ba}


@mcp.tool()
def find_compatible_enzymes(
    buffer: str,
    min_activity: int = 75,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Find enzymes with >= min_activity% in a given NEB buffer.
    buffer: one of 'r1.1', 'r2.1', 'r3.1', 'rCutSmart'
    min_activity: minimum % activity threshold (default 75)
    """
    buffer = buffer.strip()
    results = []
    for item in REAGENTS:
        ba = item.get("buffer_activity")
        if not ba or not ba.get("buffers"):
            continue
        activity = ba["buffers"].get(buffer)
        if activity is None or isinstance(activity, str):
            continue
        if activity >= min_activity:
            results.append({
                "name": item["name"],
                "activity": activity,
                "recognition_sequence": item.get("recognition_sequence"),
                "recommended_buffer": ba.get("recommended_buffer")
            })
    results.sort(key=lambda x: x["activity"], reverse=True)
    return {
        "buffer": buffer,
        "min_activity": min_activity,
        "count": len(results),
        "results": results[:limit]
    }


@mcp.tool()
def check_double_digest(enzyme1: str, enzyme2: str, min_activity: int = 75) -> Dict[str, Any]:
    """
    Check which NEB buffers support simultaneous digestion with two enzymes.
    Returns compatible buffers where both enzymes meet the min_activity threshold.
    Also warns if either enzyme has methylation sensitivity that could affect the digest.
    """
    BUFFERS = ["r1.1", "r2.1", "r3.1", "rCutSmart"]

    def get_enzyme_data(name: str):
        matched = best_name_match(name)
        if not matched:
            return None, None, None
        item = NAME_TO_ITEM[matched.lower()]
        ba = item.get("buffer_activity")
        return matched, (ba["buffers"] if ba else None), item

    matched1, buffers1, item1 = get_enzyme_data(enzyme1)
    matched2, buffers2, item2 = get_enzyme_data(enzyme2)

    if not matched1 or not matched2:
        return {"found": False, "message": f"Could not find: {enzyme1 if not matched1 else enzyme2}"}
    if not buffers1 or not buffers2:
        no_data = enzyme1 if not buffers1 else enzyme2
        return {"found": True, "compatible_buffers": [], "message": f"No NEB buffer data for {no_data}."}

    compatible = []
    for buf in BUFFERS:
        a1 = buffers1.get(buf)
        a2 = buffers2.get(buf)
        if isinstance(a1, str) or isinstance(a2, str):
            continue
        if a1 is not None and a2 is not None and a1 >= min_activity and a2 >= min_activity:
            compatible.append({
                "buffer": buf,
                f"{matched1}_activity": a1,
                f"{matched2}_activity": a2
            })

    # Methylation warnings
    methylation_warnings = []
    for matched, item in [(matched1, item1), (matched2, item2)]:
        ms = item.get("methylation_sensitivity")
        if ms and isinstance(ms, dict):
            warnings = []
            if ms.get("dam") and ms["dam"] != "not_sensitive":
                warnings.append(f"Dam ({ms['dam']})")
            if ms.get("dcm") and ms["dcm"] != "not_sensitive":
                warnings.append(f"Dcm ({ms['dcm']})")
            if ms.get("cpg") and ms["cpg"] != "not_sensitive":
                warnings.append(f"CpG ({ms['cpg']})")
            if warnings:
                methylation_warnings.append(
                    f"{matched} is sensitive to: {', '.join(warnings)}"
                )

    return {
        "enzyme1": matched1,
        "enzyme2": matched2,
        "min_activity_threshold": min_activity,
        "compatible_buffers": compatible,
        "recommended": compatible[0]["buffer"] if compatible else None,
        "methylation_warnings": methylation_warnings if methylation_warnings else None,
        "message": "No shared compatible buffer found." if not compatible else None
    }


@mcp.tool()
def get_enzyme_summary(name: str) -> Dict[str, Any]:
    """
    Return a concise, lab-ready summary of an enzyme covering all key properties:
    type, recognition sequence, overhang, incubation temp, heat inactivation,
    recommended buffer, and methylation sensitivity.
    Use this as the first call when a user asks a general question about an enzyme.
    """
    matched = best_name_match(name)
    if not matched:
        return {
            "found": False,
            "query": name,
            "suggestions": process.extract(name, NAME_CHOICES, scorer=fuzz.WRatio, limit=5)
        }

    item = NAME_TO_ITEM[matched.lower()]
    ba   = item.get("buffer_activity") or {}
    ac   = ba.get("assay_conditions") or {}
    ms   = item.get("methylation_sensitivity")
    oh   = item.get("overhang")
    iis  = item.get("iis_data")

    # Resolve incubation temp — prefer buffer_activity, fall back to iis_data
    incubation_temp = ac.get("incubation_temp") or (iis or {}).get("incubation_temp_c")

    # Resolve heat inactivation
    heat_inact = ac.get("heat_inactivation") or ac.get("heat_inactivation_possible")
    if heat_inact is None and iis:
        heat_inact = iis.get("heat_inactivation_possible")

    # Methylation summary — only flag non-sensitive values
    meth_flags = {}
    if ms and isinstance(ms, dict):
        for methylase in ("dam", "dcm", "cpg"):
            val = ms.get(methylase)
            if val and val != "not_sensitive":
                meth_flags[methylase] = val

    return {
        "found": True,
        "match": matched,
        "enzyme_type": item.get("enzyme_type"),
        "organism": item.get("organism"),
        "recognition_sequence": item.get("recognition_sequence"),
        "cut_site": item.get("cut_site"),
        "overhang": oh,
        "incubation_temp": incubation_temp,
        "heat_inactivation": heat_inact,
        "recommended_buffer": ba.get("recommended_buffer") or (iis or {}).get("recommended_buffer"),
        "buffer_activity": ba.get("buffers"),
        "methylation_warnings": meth_flags if meth_flags else None,
        "iis_data": iis,
        "after_fill_ligation": item.get("after_fill_ligation"),
        "recleavable_by": item.get("recleavable_by"),
    }


@mcp.tool()
def check_methylation_sensitivity(name: str, methylase: Optional[str] = None) -> Dict[str, Any]:
    """
    Check Dam, Dcm, and/or CpG methylation sensitivity for an enzyme.
    methylase: optional filter — one of 'dam', 'dcm', 'cpg'. If omitted, returns all three.
    Use this to diagnose failed digests when template DNA comes from Dam+/Dcm+ E. coli strains.
    """
    matched = best_name_match(name)
    if not matched:
        return {"found": False, "query": name}

    item = NAME_TO_ITEM[matched.lower()]
    ms = item.get("methylation_sensitivity")

    if not ms:
        return {
            "found": True,
            "match": matched,
            "has_methylation_data": False,
            "message": "No methylation sensitivity data available for this enzyme."
        }

    methylase = (methylase or "").strip().lower()
    if methylase in ("dam", "dcm", "cpg"):
        status = ms.get(methylase)
        return {
            "found": True,
            "match": matched,
            "has_methylation_data": True,
            "methylase": methylase,
            "status": status,
            "is_sensitive": status not in (None, "not_sensitive"),
            "advice": _methylation_advice(methylase, status)
        }

    # Return all three
    result = {"found": True, "match": matched, "has_methylation_data": True, "sensitivities": {}}
    for m in ("dam", "dcm", "cpg"):
        val = ms.get(m)
        result["sensitivities"][m] = {
            "status": val,
            "is_sensitive": val not in (None, "not_sensitive"),
            "advice": _methylation_advice(m, val)
        }
    return result


def _methylation_advice(methylase: str, status: Optional[str]) -> Optional[str]:
    """Generate plain-language advice based on methylation status."""
    if not status or status == "not_sensitive":
        return None
    sources = {
        "dam": "Dam methylase (methylates GATC). Use dam⁻ E. coli strain (e.g., SCS110, GM2163) to prepare template.",
        "dcm": "Dcm methylase (methylates CCWGG). Use dcm⁻ E. coli strain to prepare template.",
        "cpg": "CpG methylation. Use CpG methylation-free template or treat with CpG demethylase."
    }
    severity = {
        "blocked":                     "Digestion will be completely blocked.",
        "blocked_overlapping":         "Digestion blocked when recognition site overlaps a methylated sequence.",
        "blocked_some_overlapping":    "Digestion blocked in some sequence contexts with overlapping methylation.",
        "impaired":                    "Digestion efficiency is reduced but not fully blocked.",
        "impaired_overlapping":        "Digestion impaired when recognition site overlaps a methylated sequence.",
        "impaired_some_overlapping":   "Digestion impaired in some contexts with overlapping methylation.",
    }
    base = sources.get(methylase, "")
    sev  = severity.get(status, "")
    return f"{sev} {base}".strip() if sev else base


@mcp.tool()
def find_ligation_compatible_enzymes(enzyme: str, limit: int = 20) -> Dict[str, Any]:
    """
    Find enzymes that produce overhangs compatible for ligation with the given enzyme.
    Two enzymes are ligation-compatible if they produce identical overhang sequences
    (e.g., BamHI GATC overhang is compatible with BclI GATC overhang).
    Use this for planning cloning strategies where insert and vector are cut with different enzymes.
    """
    matched = best_name_match(enzyme)
    if not matched:
        return {"found": False, "query": enzyme}

    item = NAME_TO_ITEM[matched.lower()]
    oh   = item.get("overhang")

    if not oh or oh.get("type") == "blunt":
        if oh and oh.get("type") == "blunt":
            blunt_enzymes = [
                {"name": e["name"], "recognition_sequence": e.get("recognition_sequence")}
                for e in REAGENTS
                if e.get("name") != matched
                and isinstance(e.get("overhang"), dict)
                and e["overhang"].get("type") == "blunt"
            ]
            return {
                "found": True,
                "match": matched,
                "overhang": oh,
                "compatible_enzymes": blunt_enzymes[:limit],
                "note": "Blunt ends are compatible with all other blunt-end enzymes."
            }
        return {
            "found": True,
            "match": matched,
            "has_overhang_data": False,
            "message": "No overhang data available for this enzyme."
        }

    target_seq  = (oh.get("sequence") or "").upper()
    target_type = oh.get("type")

    if not target_seq:
        return {
            "found": True,
            "match": matched,
            "has_overhang_data": False,
            "message": "Overhang type known but sequence not available."
        }

    compatible = []
    for e in REAGENTS:
        if e.get("name") == matched:
            continue
        eoh = e.get("overhang")
        if not eoh or not isinstance(eoh, dict):
            continue
        e_seq  = (eoh.get("sequence") or "").upper()
        e_type = eoh.get("type")
        if e_seq == target_seq and e_type == target_type:
            compatible.append({
                "name": e["name"],
                "recognition_sequence": e.get("recognition_sequence"),
                "organism": e.get("organism"),
                "has_buffer_data": e.get("buffer_activity") is not None
            })
        if len(compatible) >= limit:
            break

    return {
        "found": True,
        "match": matched,
        "overhang": oh,
        "compatible_count": len(compatible),
        "compatible_enzymes": compatible,
        "note": f"All enzymes above produce a {target_type} '{target_seq}' overhang compatible with {matched}."
    }


@mcp.tool()
def find_golden_gate_enzymes(
    min_overhang_length: Optional[int] = None,
    cutsmart_only: bool = False
) -> Dict[str, Any]:
    """
    Return all Type IIS enzymes suitable for Golden Gate assembly.
    min_overhang_length: optional filter for minimum overhang length (e.g., 4 for standard Golden Gate).
    cutsmart_only: if True, only return enzymes with >= 75% activity in rCutSmart buffer.
    Type IIS enzymes cut outside their recognition sequence, enabling seamless assembly.
    Common choices: BsaI, BbsI, BsmBI, SapI, PaqCI.
    """
    results = []

    for item in REAGENTS:
        if item.get("enzyme_type") != "Type IIS":
            continue

        iis  = item.get("iis_data") or {}
        ba   = item.get("buffer_activity") or {}
        oh   = item.get("overhang") or {}
        buffers = ba.get("buffers") or {}

        oh_len = iis.get("overhang_length") or oh.get("length")
        if min_overhang_length is not None:
            if oh_len is None or oh_len < min_overhang_length:
                continue

        if cutsmart_only:
            cs_activity = buffers.get("rCutSmart")
            if not isinstance(cs_activity, int) or cs_activity < 75:
                continue

        results.append({
            "name": item["name"],
            "recognition_sequence": item.get("recognition_sequence"),
            "overhang_length": oh_len,
            "incubation_temp_c": iis.get("incubation_temp_c"),
            "heat_inactivation_possible": iis.get("heat_inactivation_possible"),
            "recommended_buffer": ba.get("recommended_buffer") or iis.get("recommended_buffer"),
            "cutsmart_activity": buffers.get("rCutSmart"),
            "isoschizomers": iis.get("isoschizomers_neb", []),
            "has_commercial_data": ba.get("recommended_buffer") is not None or iis.get("recommended_buffer") is not None
        })

    results.sort(key=lambda x: (not x["has_commercial_data"], x["name"]))

    return {
        "count": len(results),
        "filters_applied": {
            "min_overhang_length": min_overhang_length,
            "cutsmart_only": cutsmart_only
        },
        "results": results
    }


@mcp.tool()
def find_enzymes_by_type(
    enzyme_type: str,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Return all enzymes of a given classification type.
    enzyme_type: one of 'Type I', 'Type II', 'Type IIS', 'Type III', 'Type IV', etc.
    Useful for filtering to commercially relevant subsets.
    """
    et = enzyme_type.strip()
    matches = [
        {
            "name": item["name"],
            "recognition_sequence": item.get("recognition_sequence"),
            "organism": item.get("organism"),
            "has_buffer_data": item.get("buffer_activity") is not None
        }
        for item in REAGENTS
        if item.get("enzyme_type") == et
    ]
    return {
        "enzyme_type": et,
        "count": len(matches),
        "results": matches[:limit]
    }


if __name__ == "__main__":
    print("Starting MCP server...", file=sys.stderr)
    mcp.run()
    print("MCP server stopped.", file=sys.stderr)