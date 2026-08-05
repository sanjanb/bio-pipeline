"""Parse PDB files with Biopython -- extract pLDDT, secondary structure, statistics."""

from pathlib import Path
from Bio.PDB import PDBParser
from Bio.PDB.DSSP import DSSP


def parse_pdb(pdb_path: str) -> dict:
    """Parse PDB and extract per-residue pLDDT scores and summary stats."""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("model", pdb_path)

    # Extract pLDDT from b-factors (AlphaFold stores pLDDT in b-factor column)
    residues = []
    for model in structure:
        for chain in model:
            for residue in chain.get_residues():
                if residue.get_id()[0] != " ":  # skip hetero-atoms
                    continue
                # Average b-factor over atoms = pLDDT for this residue
                b_factors = [atom.get_bfactor() for atom in residue]
                plddt = sum(b_factors) / len(b_factors) if b_factors else 0
                residues.append({
                    "chain": chain.get_id(),
                    "residue": residue.get_id()[1],
                    "name": residue.get_resname(),
                    "plddt": round(plddt, 2),
                })

    # Classify confidence regions
    summary = _confidence_summary(residues)

    return {
        "residues": residues,
        "total_residues": len(residues),
        "summary": summary,
    }


def _confidence_summary(residues: list) -> dict:
    """Classify residues into confidence tiers."""
    counts = {"very_high": 0, "high": 0, "low": 0, "very_low": 0}
    for r in residues:
        score = r["plddt"]
        if score > 90:
            counts["very_high"] += 1
        elif score > 70:
            counts["high"] += 1
        elif score > 50:
            counts["low"] += 1
        else:
            counts["very_low"] += 1

    total = len(residues) or 1
    return {
        "very_high": counts["very_high"],
        "high": counts["high"],
        "low": counts["low"],
        "very_low": counts["very_low"],
        "total": len(residues),
        "pct_very_high": round(counts["very_high"] / total * 100, 1),
        "pct_high": round(counts["high"] / total * 100, 1),
        "pct_low": round(counts["low"] / total * 100, 1),
        "pct_very_low": round(counts["very_low"] / total * 100, 1),
        "mean_plddt": round(sum(r["plddt"] for r in residues) / total, 2),
    }
