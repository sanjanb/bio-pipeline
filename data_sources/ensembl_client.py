"""Ensembl REST API client for gene lookup, homology, cross-references, and sequences."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://rest.ensembl.org"

# IMPORTANT: Query params separated by `;` not `&`
# e.g. ?type=orthologues;sequence=protein


async def _get_json(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict | list | None:
    """Fetch JSON from Ensembl. Params use ; as separator."""
    try:
        # Ensembl uses ; for query param separation
        query_string = ""
        if params:
            query_string = "?" + ";".join(f"{k}={v}" for k, v in params.items())
        resp = await client.get(f"{BASE_URL}{path}{query_string}", timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Ensembl %s failed: %s %s", path, e.response.status_code, e.response.text[:200])
        return None
    except httpx.HTTPError as e:
        logger.warning("Ensembl %s failed: %s", path, type(e).__name__)
        return None


async def lookup_gene(gene_symbol: str, species: str = "homo_sapiens") -> dict | None:
    """Look up gene by symbol.
    
    GET /lookup/symbol/{species}/{symbol}?content-type=application/json
    Returns dict with ensembl_id, description, biotype, start, end, strand, chromosome,
    and list of transcripts with their translations (protein IDs).
    """
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get_json(client, f"/lookup/symbol/{species}/{gene_symbol}", {
            "content-type": "application/json",
        })
    if data is None:
        return None

    # Extract transcript translations
    transcripts = []
    for transcript in data.get("Transcript", []):
        translation = transcript.get("Translation", {})
        if translation:
            transcripts.append({
                "transcript_id": transcript.get("id"),
                "protein_id": translation.get("id"),
                "start": transcript.get("start"),
                "end": transcript.get("end"),
                "strand": transcript.get("strand"),
            })

    return {
        "ensembl_id": data.get("id"),
        "description": data.get("description"),
        "biotype": data.get("biotype"),
        "start": data.get("start"),
        "end": data.get("end"),
        "strand": data.get("strand"),
        "chromosome": data.get("seq_region_name"),
        "transcripts": transcripts,
    }


async def fetch_homology(ensembl_id: str, target_species: str = "mus_musculus") -> list[dict]:
    """Fetch orthologs.
    
    GET /homology/id/{ensembl_id}?type=orthologues;target_species={target};sequence=protein;content-type=application/json
    Returns list of {species, protein_id, identity, sequence, taxonomy_level}.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get_json(client, f"/homology/id/{ensembl_id}", {
            "type": "orthologues",
            "target_species": target_species,
            "sequence": "protein",
            "content-type": "application/json",
        })
    if data is None:
        return []

    results = []
    for homology in data.get("data", [{}])[0].get("homologies", []):
        target = homology.get("target", {})
        if target.get("species") == target_species:
            results.append({
                "species": target.get("species"),
                "protein_id": target.get("protein_id"),
                "identity": homology.get("target", {}).get("perc_id"),
                "sequence": target.get("align_seq"),
                "taxonomy_level": homology.get("taxonomy_level"),
            })
    return results