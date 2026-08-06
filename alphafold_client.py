"""AlphaFold client — fetch from AlphaFold DB.

Adapter at the structure source seam. Only AlphaFold-specific HTTP logic lives here.
Identifier validation moved to protein_id.py (the real seam for that concern).
"""

from pathlib import Path

import httpx

ALPHAFOLD_DB_API = "https://alphafold.ebi.ac.uk/api/prediction"


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
            pae_url = entry.get("paeImageUrl") or entry.get("paeDocUrl", "")
            return {
                "uniprot_id": uniprot_id,
                "pdb_url": pdb_url,
                "gene": entry.get("gene", uniprot_id),
                "organism": entry.get("organismScientificName", "Unknown"),
                "confidence": entry.get("latestVersion", 1),
                "pae_url": pae_url,
                "pdb_version": entry.get("latestVersion", 1),
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
