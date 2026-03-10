"""
calc_server.py — Lab Calculations MCP Server
Provides unit conversions and calculations for common molecular biology workflows.
No data files required — all formulas are hardcoded.
"""

import math
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lab-calculations-mcp")

# ── Molecular weights (g/mol) ─────────────────────────────────────────────────
MW_NUCLEOTIDES = {
    # dNTPs (average for mixed sequences)
    "dsDNA_per_bp": 660,      # average MW per base pair
    "ssDNA_per_nt": 330,      # average MW per nucleotide
    "RNA_per_nt":   340,      # average MW per RNA nucleotide
}

MW_AMINO_ACIDS = {
    "A": 89.09,  "R": 174.20, "N": 132.12, "D": 133.10,
    "C": 121.16, "E": 147.13, "Q": 146.15, "G": 75.03,
    "H": 155.16, "I": 131.17, "L": 131.17, "K": 146.19,
    "M": 149.21, "F": 165.19, "P": 115.13, "S": 105.09,
    "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
}


# ── Molarity & dilutions ──────────────────────────────────────────────────────

@mcp.tool()
def calculate_molarity(
    mass_g: float,
    molecular_weight_g_mol: float,
    volume_l: float
) -> Dict[str, Any]:
    """
    Calculate molarity (mol/L) from mass, molecular weight, and volume.
    mass_g: mass in grams
    molecular_weight_g_mol: molecular weight in g/mol
    volume_l: volume in liters
    Returns molarity in mol/L, mmol/L, and µmol/L.
    """
    if molecular_weight_g_mol <= 0 or volume_l <= 0:
        return {"error": "Molecular weight and volume must be greater than 0."}
    moles = mass_g / molecular_weight_g_mol
    molarity = moles / volume_l
    return {
        "mass_g": mass_g,
        "molecular_weight_g_mol": molecular_weight_g_mol,
        "volume_l": volume_l,
        "moles": moles,
        "molarity_M": molarity,
        "molarity_mM": molarity * 1e3,
        "molarity_uM": molarity * 1e6,
        "formula": "M = (mass_g / MW) / volume_L"
    }


@mcp.tool()
def calculate_dilution(
    c1: float,
    v1: Optional[float],
    c2: float,
    v2: Optional[float],
    unit: str = "same"
) -> Dict[str, Any]:
    """
    Solve C1V1 = C2V2 for the missing variable.
    Provide exactly three of the four values; set the unknown to null.
    c1: initial concentration
    v1: initial volume (null to solve for this)
    c2: final concentration
    v2: final volume (null to solve for this)
    unit: label for concentration units (e.g. 'mM', 'ng/uL') — cosmetic only
    """
    knowns = sum(x is not None for x in [c1, v1, c2, v2])
    if knowns != 3:
        return {"error": "Provide exactly 3 values; set the unknown to null."}
    if c1 is None:
        result = (c2 * v2) / v1
        return {"solved_for": "c1", "c1": result, "v1": v1, "c2": c2, "v2": v2, "unit": unit}
    if v1 is None:
        result = (c2 * v2) / c1
        return {"solved_for": "v1", "c1": c1, "v1": result, "c2": c2, "v2": v2, "unit": unit}
    if c2 is None:
        result = (c1 * v1) / v2
        return {"solved_for": "c2", "c1": c1, "v1": v1, "c2": result, "v2": v2, "unit": unit}
    if v2 is None:
        result = (c1 * v1) / c2
        return {"solved_for": "v2", "c1": c1, "v1": v1, "c2": c2, "v2": result, "unit": unit}


@mcp.tool()
def calculate_serial_dilution(
    start_concentration: float,
    dilution_factor: int,
    steps: int,
    volume_per_step_ul: float = 100.0
) -> Dict[str, Any]:
    """
    Calculate concentrations and volumes for a serial dilution series.
    start_concentration: starting concentration (any unit)
    dilution_factor: fold dilution at each step (e.g. 10 for 1:10)
    steps: number of dilution steps
    volume_per_step_ul: volume of each dilution in µL (default 100)
    """
    if dilution_factor <= 1:
        return {"error": "Dilution factor must be greater than 1."}
    series = []
    for i in range(steps + 1):
        conc = start_concentration / (dilution_factor ** i)
        transfer_ul = volume_per_step_ul / dilution_factor if i > 0 else None
        diluent_ul  = volume_per_step_ul - transfer_ul if transfer_ul else None
        series.append({
            "step": i,
            "concentration": conc,
            "transfer_ul": round(transfer_ul, 2) if transfer_ul else "N/A (stock)",
            "diluent_ul": round(diluent_ul, 2) if diluent_ul else "N/A (stock)",
            "label": f"1:{dilution_factor**i}" if i > 0 else "stock"
        })
    return {
        "start_concentration": start_concentration,
        "dilution_factor": dilution_factor,
        "steps": steps,
        "volume_per_step_ul": volume_per_step_ul,
        "series": series
    }


# ── DNA & RNA concentration ───────────────────────────────────────────────────

@mcp.tool()
def calculate_dna_concentration_from_absorbance(
    a260: float,
    dilution_factor: float = 1.0,
    sample_type: str = "dsDNA",
    a280: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate DNA/RNA concentration from A260 absorbance (Beer-Lambert law).
    a260: absorbance at 260nm
    dilution_factor: dilution applied before measurement (e.g. 50 for 1:50)
    sample_type: one of 'dsDNA', 'ssDNA', 'RNA', 'oligonucleotide'
    a280: optional absorbance at 280nm for purity ratio
    Returns concentration in ng/µL and µg/mL.
    """
    conversion = {"dsDNA": 50, "ssDNA": 33, "RNA": 40, "oligonucleotide": 33}
    factor = conversion.get(sample_type)
    if not factor:
        return {"error": f"Unknown sample_type '{sample_type}'. Use: dsDNA, ssDNA, RNA, oligonucleotide"}

    concentration_ng_ul = a260 * factor * dilution_factor
    result = {
        "a260": a260,
        "dilution_factor": dilution_factor,
        "sample_type": sample_type,
        "concentration_ng_ul": concentration_ng_ul,
        "concentration_ug_ml": concentration_ng_ul,  # same numeric value
        "conversion_factor_used": f"{factor} ng/µL per A260 unit",
    }

    if a280 is not None and a280 > 0:
        ratio = a260 / a280
        result["a260_a280_ratio"] = round(ratio, 2)
        if sample_type in ("dsDNA", "ssDNA"):
            if ratio >= 1.8:
                result["purity_assessment"] = "Good (ratio 1.8-2.0 expected for pure DNA)"
            elif ratio < 1.8:
                result["purity_assessment"] = "Possible protein or phenol contamination (ratio < 1.8)"
            else:
                result["purity_assessment"] = "Possible RNA contamination (ratio > 2.0)"
        elif sample_type == "RNA":
            if ratio >= 2.0:
                result["purity_assessment"] = "Good (ratio ~2.0 expected for pure RNA)"
            else:
                result["purity_assessment"] = "Possible protein or phenol contamination (ratio < 2.0)"

    return result


@mcp.tool()
def convert_dna_concentration(
    concentration_ng_ul: float,
    sequence_length_bp: int,
    molecule_type: str = "dsDNA"
) -> Dict[str, Any]:
    """
    Convert DNA concentration between ng/µL and nM/µM (molar concentration).
    Useful for setting up ligation reactions that require equimolar insert:vector ratios.
    concentration_ng_ul: concentration in ng/µL
    sequence_length_bp: length of the DNA fragment in base pairs (or nt for ssDNA)
    molecule_type: 'dsDNA' or 'ssDNA'
    """
    mw_per_unit = MW_NUCLEOTIDES["dsDNA_per_bp"] if molecule_type == "dsDNA" else MW_NUCLEOTIDES["ssDNA_per_nt"]
    mw_fragment  = mw_per_unit * sequence_length_bp  # g/mol

    # ng/µL = µg/mL = mg/L
    # concentration in mol/L = (mg/L * 1e-3) / (g/mol) ... careful with units
    # ng/µL -> g/L: multiply by 1e-6 * 1e3 = 1e-3... actually:
    # 1 ng/µL = 1 µg/mL = 1 mg/L = 1e-3 g/L
    concentration_g_l  = concentration_ng_ul * 1e-3   # ng/µL -> g/L (= mg/L)
    # Wait: 1 ng/µL = 1e-9 g / 1e-6 L = 1e-3 g/L  ✓
    concentration_mol_l = concentration_g_l / mw_fragment
    concentration_nM    = concentration_mol_l * 1e9
    concentration_uM    = concentration_mol_l * 1e6
    concentration_fmol_ul = concentration_mol_l * 1e15 * 1e-6  # fmol/µL

    return {
        "concentration_ng_ul": concentration_ng_ul,
        "sequence_length_bp": sequence_length_bp,
        "molecule_type": molecule_type,
        "molecular_weight_g_mol": round(mw_fragment, 0),
        "concentration_nM": round(concentration_nM, 4),
        "concentration_uM": round(concentration_uM, 6),
        "concentration_fmol_ul": round(concentration_fmol_ul, 4),
        "note": "Useful for ligation: typical insert:vector molar ratio is 3:1 to 5:1"
    }


# ── PCR & primer tools ────────────────────────────────────────────────────────

@mcp.tool()
def calculate_primer_tm(
    sequence: str,
    method: str = "wallace",
    Na_mM: float = 50.0
) -> Dict[str, Any]:
    """
    Calculate melting temperature (Tm) of a primer sequence.
    sequence: DNA sequence (5' to 3', ACGT only)
    method: 'wallace' (quick, for primers 14-20nt) or 'nearest_neighbor' (more accurate)
    Na_mM: sodium concentration in mM for salt correction (default 50mM)
    Returns Tm in °C and basic primer stats.
    """
    seq = sequence.upper().strip().replace(" ", "")
    invalid = set(seq) - set("ACGT")
    if invalid:
        return {"error": f"Invalid bases in sequence: {invalid}. Use A, C, G, T only."}

    n  = len(seq)
    gc = seq.count("G") + seq.count("C")
    at = seq.count("A") + seq.count("T")
    gc_pct = (gc / n) * 100 if n > 0 else 0

    result = {
        "sequence": seq,
        "length": n,
        "gc_count": gc,
        "at_count": at,
        "gc_percent": round(gc_pct, 1),
    }

    # Wallace rule: Tm = 2(A+T) + 4(G+C)  — valid for short oligos <20nt
    tm_wallace = 2 * at + 4 * gc
    result["tm_wallace_c"] = tm_wallace
    result["tm_wallace_note"] = "Wallace rule: Tm = 2(A+T) + 4(G+C). Best for primers 14-20 nt."

    # Basic nearest-neighbor (SantaLucia 1998 unified parameters)
    # ΔH and ΔS values in cal/mol and cal/mol/K
    NN_DH = {
        "AA": -7900, "AT": -7200, "TA": -7200, "CA": -8500,
        "GT": -8400, "CT": -7800, "GA": -8200, "CG": -10600,
        "GC": -9800, "GG": -8000, "AC": -7800, "TC": -8200,
        "TG": -8500, "AG": -7800, "TT": -7900, "CC": -8000,
    }
    NN_DS = {
        "AA": -22.2, "AT": -20.4, "TA": -21.3, "CA": -22.7,
        "GT": -22.4, "CT": -21.0, "GA": -22.2, "CG": -27.2,
        "GC": -24.4, "GG": -19.9, "AC": -21.0, "TC": -22.2,
        "TG": -22.7, "AG": -20.4, "TT": -22.2, "CC": -19.9,
    }
    R = 1.987  # cal/mol/K
    # Primer concentration assumption: 250nM
    CT = 250e-9

    dH = sum(NN_DH.get(seq[i:i+2], 0) for i in range(n - 1))
    dS = sum(NN_DS.get(seq[i:i+2], 0) for i in range(n - 1))
    # Initiation parameters
    if seq[0] in "GC":
        dH += 100; dS += -2.8
    else:
        dH += 2300; dS += 4.1
    if seq[-1] in "GC":
        dH += 100; dS += -2.8
    else:
        dH += 2300; dS += 4.1

    if dS != 0:
        tm_nn = (dH / (dS + R * math.log(CT / 4))) - 273.15
        # Salt correction (Owczarzy 2004)
        tm_salt = tm_nn + 16.6 * math.log10(Na_mM / 1000)
        result["tm_nearest_neighbor_c"] = round(tm_nn, 1)
        result["tm_salt_corrected_c"] = round(tm_salt, 1)
        result["tm_nn_note"] = f"Nearest-neighbor (SantaLucia 1998), salt-corrected for {Na_mM}mM Na+, [primer]=250nM"

    # Annealing temp recommendation
    base_tm = result.get("tm_salt_corrected_c", tm_wallace)
    result["recommended_annealing_temp_c"] = round(base_tm - 5, 1)
    result["recommended_annealing_note"] = "Typical starting point: Tm - 5°C. Optimize by gradient PCR."

    return result


@mcp.tool()
def calculate_pcr_mastermix(
    num_reactions: int,
    reaction_volume_ul: float = 25.0,
    overage_factor: float = 1.1,
    components: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Calculate master mix volumes for PCR.
    num_reactions: number of reactions
    reaction_volume_ul: volume per reaction in µL (default 25)
    overage_factor: extra volume multiplier to account for pipetting loss (default 1.1 = 10% extra)
    components: optional list of custom components [{"name": "...", "final_conc": "...", "stock_conc": ..., "stock_unit": "..."}]
    If components not provided, uses standard Taq/Q5 2x mastermix setup.
    """
    total_rxns = num_reactions * overage_factor
    total_vol  = total_rxns * reaction_volume_ul

    # Default standard PCR components (assumes 2x polymerase mastermix)
    default_components = [
        {"name": "2x Polymerase Mastermix", "volume_per_rxn_ul": reaction_volume_ul / 2},
        {"name": "Forward Primer (10µM)", "volume_per_rxn_ul": reaction_volume_ul * 0.04},   # 400nM final
        {"name": "Reverse Primer (10µM)", "volume_per_rxn_ul": reaction_volume_ul * 0.04},
        {"name": "Template DNA", "volume_per_rxn_ul": 1.0},
        {"name": "Nuclease-free Water", "volume_per_rxn_ul": reaction_volume_ul - (reaction_volume_ul / 2) - (reaction_volume_ul * 0.04 * 2) - 1.0},
    ]

    comp_list = default_components if not components else components

    result_components = []
    for comp in comp_list:
        vol_per_rxn = comp.get("volume_per_rxn_ul", 0)
        result_components.append({
            "component": comp["name"],
            "volume_per_reaction_ul": round(vol_per_rxn, 2),
            "total_volume_ul": round(vol_per_rxn * total_rxns, 2),
        })

    return {
        "num_reactions": num_reactions,
        "reaction_volume_ul": reaction_volume_ul,
        "overage_factor": overage_factor,
        "total_reactions_with_overage": round(total_rxns, 1),
        "total_mastermix_volume_ul": round(total_vol, 1),
        "components": result_components,
        "note": "Add template separately to each tube after dispensing mastermix."
    }


# ── Transformation & plating ──────────────────────────────────────────────────

@mcp.tool()
def calculate_transformation_efficiency(
    colonies_counted: int,
    dna_mass_ng: float,
    total_recovery_volume_ul: float,
    plated_volume_ul: float,
    dilution_factor: float = 1.0
) -> Dict[str, Any]:
    """
    Calculate transformation efficiency in CFU/µg DNA.
    colonies_counted: number of colonies on the plate
    dna_mass_ng: mass of DNA used in transformation in ng
    total_recovery_volume_ul: total volume after recovery (e.g. 1000µL)
    plated_volume_ul: volume plated (e.g. 100µL)
    dilution_factor: any dilution applied before plating (default 1.0 = undiluted)
    """
    if dna_mass_ng <= 0 or plated_volume_ul <= 0:
        return {"error": "DNA mass and plated volume must be > 0."}

    # Scale colonies to total recovery volume
    colonies_total = colonies_counted * (total_recovery_volume_ul / plated_volume_ul) * dilution_factor
    dna_mass_ug    = dna_mass_ng / 1000
    efficiency     = colonies_total / dna_mass_ug

    assessment = ""
    if efficiency >= 1e9:
        assessment = "Excellent (≥10⁹ CFU/µg)"
    elif efficiency >= 1e8:
        assessment = "Good (10⁸–10⁹ CFU/µg)"
    elif efficiency >= 1e7:
        assessment = "Acceptable (10⁷–10⁸ CFU/µg) — sufficient for most cloning"
    elif efficiency >= 1e6:
        assessment = "Low (10⁶–10⁷ CFU/µg) — may struggle with large constructs"
    else:
        assessment = "Very low (<10⁶ CFU/µg) — check competent cell preparation"

    return {
        "colonies_on_plate": colonies_counted,
        "dna_mass_ng": dna_mass_ng,
        "total_recovery_volume_ul": total_recovery_volume_ul,
        "plated_volume_ul": plated_volume_ul,
        "dilution_factor": dilution_factor,
        "estimated_total_colonies": round(colonies_total),
        "efficiency_cfu_per_ug": f"{efficiency:.2e}",
        "efficiency_numeric": efficiency,
        "assessment": assessment,
        "formula": "Efficiency = (colonies × total_vol/plated_vol × dilution) / DNA_µg"
    }


# ── Unit conversions ──────────────────────────────────────────────────────────

@mcp.tool()
def convert_units(
    value: float,
    from_unit: str,
    to_unit: str
) -> Dict[str, Any]:
    """
    Convert between common lab units.
    Supported conversions:
      Volume: L, mL, uL, nL
      Mass: g, mg, ug, ng, pg
      Concentration: M, mM, uM, nM, pM
      Temperature: C, F, K
    from_unit / to_unit: case-insensitive unit string (e.g. 'uL', 'mL', 'ng', 'ug')
    """
    VOLUME = {"l": 1, "ml": 1e-3, "ul": 1e-6, "nl": 1e-9}
    MASS   = {"g": 1, "mg": 1e-3, "ug": 1e-6, "ng": 1e-9, "pg": 1e-12}
    CONC   = {"m": 1, "mm": 1e-3, "um": 1e-6, "nm": 1e-9, "pm": 1e-12}

    fu = from_unit.lower()
    tu = to_unit.lower()

    for table, name in [(VOLUME, "volume"), (MASS, "mass"), (CONC, "concentration")]:
        if fu in table and tu in table:
            result = value * table[fu] / table[tu]
            return {
                "value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "result": result,
                "type": name
            }

    # Temperature
    if fu in ("c", "f", "k") and tu in ("c", "f", "k"):
        if fu == "c" and tu == "f":   result = value * 9/5 + 32
        elif fu == "f" and tu == "c": result = (value - 32) * 5/9
        elif fu == "c" and tu == "k": result = value + 273.15
        elif fu == "k" and tu == "c": result = value - 273.15
        elif fu == "f" and tu == "k": result = (value - 32) * 5/9 + 273.15
        elif fu == "k" and tu == "f": result = (value - 273.15) * 9/5 + 32
        else: result = value
        return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": round(result, 4), "type": "temperature"}

    return {
        "error": f"Cannot convert {from_unit} to {to_unit}. Supported: volume (L/mL/uL/nL), mass (g/mg/ug/ng/pg), concentration (M/mM/uM/nM/pM), temperature (C/F/K)."
    }


@mcp.tool()
def calculate_ligation_volumes(
    vector_ng: float,
    vector_size_bp: int,
    insert_size_bp: int,
    insert_vector_molar_ratio: float = 3.0,
    total_reaction_volume_ul: float = 20.0
) -> Dict[str, Any]:
    """
    Calculate insert mass needed for a ligation reaction given a vector amount.
    Uses the formula: insert_ng = (insert_size / vector_size) × vector_ng × molar_ratio
    vector_ng: mass of vector DNA in ng
    vector_size_bp: size of linearized vector in bp
    insert_size_bp: size of insert in bp
    insert_vector_molar_ratio: desired molar ratio of insert:vector (default 3:1)
    total_reaction_volume_ul: total ligation volume in µL (default 20)
    """
    insert_ng = (insert_size_bp / vector_size_bp) * vector_ng * insert_vector_molar_ratio

    return {
        "vector_ng": vector_ng,
        "vector_size_bp": vector_size_bp,
        "insert_size_bp": insert_size_bp,
        "molar_ratio": insert_vector_molar_ratio,
        "insert_ng_needed": round(insert_ng, 2),
        "total_reaction_volume_ul": total_reaction_volume_ul,
        "recommended_setup": {
            "vector_ul": "variable (depends on stock concentration)",
            "insert_ul": "variable (depends on stock concentration)",
            "10x_ligase_buffer_ul": round(total_reaction_volume_ul * 0.1, 1),
            "T4_DNA_ligase_ul": 1.0,
            "water_ul": "to total volume"
        },
        "formula": "insert_ng = (insert_bp / vector_bp) × vector_ng × molar_ratio",
        "note": "Standard ratio is 3:1 for routine cloning. Use 5:1 for difficult ligations or small inserts."
    }


if __name__ == "__main__":
    import sys
    print("Starting lab calculations MCP server...", file=sys.stderr)
    mcp.run()
    print("Server stopped.", file=sys.stderr)