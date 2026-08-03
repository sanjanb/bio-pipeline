"""AlphaFold client — fetch from AlphaFold DB or generate mock predictions."""

import random
import time
from pathlib import Path

import httpx

ALPHAFOLD_DB_API = "https://alphafold.ebi.ac.uk/api/prediction"


def is_uniprot_id(text: str) -> bool:
    """Check if text looks like a UniProt accession (e.g., P00533, Q9Y6K9)."""
    text = text.strip().upper()
    if len(text) < 6 or len(text) > 10:
        return False
    if not text[0].isalpha():
        return False
    return text[1:].isalnum()


def fetch_alphafold_structure(uniprot_id: str) -> dict | None:
    """Fetch pre-computed structure from AlphaFold DB. Returns metadata dict or None."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{ALPHAFOLD_DB_API}/{uniprot_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            entry = data[0] if isinstance(data, list) else data
            pdb_url = entry.get("pdbUrl") or entry.get("cifUrl", "")
            return {
                "uniprot_id": uniprot_id,
                "pdb_url": pdb_url,
                "gene": entry.get("gene", uniprot_id),
                "organism": entry.get("organismScientificName", "Unknown"),
                "confidence": entry.get("latestVersion", 1),
            }
    except (httpx.HTTPError, Exception):
        return None


def download_structure(pdb_url: str, output_path: str) -> str:
    """Download PDB/mmCIF from AlphaFold DB."""
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(pdb_url)
        resp.raise_for_status()
        Path(output_path).write_bytes(resp.content)
    return output_path


def generate_mock_pdb(sequence: str, output_path: str) -> tuple[str, list[dict]]:
    """Generate a mock PDB with realistic pLDDT confidence scores.

    Returns (pdb_content, residues_list).
    Each residue dict: {id, name, plddt, confidence_level, x, y, z}
    """
    residues = []
    # Generate a simple helical backbone with some disorder
    random.seed(hash(sequence) % (2**32))

    # Assign confidence distribution: ~40% high, ~30% medium, ~20% low, ~10% very low
    conf_weights = [0.4, 0.3, 0.2, 0.1]
    conf_ranges = [(90, 100), (70, 89), (50, 69), (0, 49)]

    pdb_lines = [
        "HEADER    MOCK STRUCTURE FROM ALPHAFOLD PIPELINE",
        f"TITLE     ALPHA FOLD PREDICTION FOR SEQUENCE ({len(sequence)} RESIDUES)",
    ]

    x, y, z = 0.0, 0.0, 0.0
    for i, aa in enumerate(sequence):
        # Assign confidence
        tier = random.choices(range(4), weights=conf_weights)[0]
        plddt = random.randint(*conf_ranges[tier])

        # Simple helical backbone coordinates
        angle = i * 100 * 3.14159 / 180  # ~3.6 residues per turn
        x = 2.3 * i * 0.5 + 2.3 * 0.5 * (1 if i % 2 == 0 else -1)
        y = 2.3 * 0.5 * angle / (2 * 3.14159)
        z = 1.5 * (i % 3) * 0.3

        # Confidence level string
        if plddt >= 90:
            level = "VERY_HIGH"
        elif plddt >= 70:
            level = "CONFIDENT"
        elif plddt >= 50:
            level = "LOW"
        else:
            level = "VERY_LOW"

        residues.append({
            "id": i + 1,
            "name": aa,
            "plddt": plddt,
            "confidence_level": level,
            "x": round(x, 3),
            "y": round(y, 3),
            "z": round(z, 3),
        })

        # PDB ATOM record
        atom_name = f" CA " if aa != "G" else " CA "
        pdb_lines.append(
            f"ATOM  {i+1:5d} {atom_name} {aa:3s} A{i+1:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}"
            f"  1.00{plddt:6.2f}           C  "
        )

    pdb_lines.append("END")

    pdb_content = "\n".join(pdb_lines) + "\n"
    Path(output_path).write_text(pdb_content, encoding="utf-8")
    return pdb_content, residues


def generate_mock_summary(residues: list[dict]) -> dict:
    """Summarize confidence distribution from mock residues."""
    counts = {"very_high": 0, "confident": 0, "low": 0, "very_low": 0}
    for r in residues:
        level = r["confidence_level"].lower()
        if level in counts:
            counts[level] += 1

    total = len(residues) if residues else 1
    return {
        "total_residues": len(residues),
        "mean_plddt": round(sum(r["plddt"] for r in residues) / total, 1),
        "distribution": {
            k: {"count": v, "percentage": round(v / total * 100, 1)}
            for k, v in counts.items()
        },
    }
