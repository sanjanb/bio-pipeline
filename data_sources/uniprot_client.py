"""UniProt REST API client for protein entries, variants, and search."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://rest.uniprot.org"

# Be polite: 0.2s between requests
_RATE_LIMIT_DELAY = 0.2
_last_call = 0.0


async def _rate_limit() -> None:
    global _last_call
    import asyncio
    elapsed = asyncio.get_event_loop().time() - _last_call
    if elapsed < _RATE_LIMIT_DELAY:
        await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_call = asyncio.get_event_loop().time()


async def _get_json(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict | None:
    """Fetch JSON from UniProt."""
    await _rate_limit()
    try:
        resp = await client.get(f"{BASE_URL}{path}", params=params, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.warning("UniProt %s failed: %s", path, e)
        return None


async def fetch_protein_entry(accession: str) -> dict | None:
    """Fetch full UniProt entry as JSON.
    
    GET /uniprotkb/{accession}.json
    Returns dict with:
    - accession, id, protein_name, gene_names, organism_name
    - sequence (string + length + mol_weight)
    - features: list of {type, location_start, location_end, description}
      (types: Variant, Beta_strand, Helix, Active_site, Binding_site, Mutagenesis, etc.)
    - xrefs: dict mapping database → list of IDs (pdb, ensembl, refseq, pfam, reactome, intact)
    - go_terms: list of {id, name, category}
    - pathways: from cc_pathway comments
    - interactions: from cc_interaction comments
    - keywords: list of keyword strings
    """
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get_json(client, f"/uniprotkb/{accession}.json")
    if data is None:
        return None

    # Extract protein name
    protein_name = ""
    if "proteinDescription" in data:
        rec_name = data["proteinDescription"].get("recommendedName", {})
        full_name = rec_name.get("fullName", {})
        protein_name = full_name.get("value", "")

    # Extract gene names
    gene_names = []
    for gene in data.get("genes", []):
        gene_name = gene.get("geneName", {}).get("value")
        if gene_name:
            gene_names.append(gene_name)

    # Organism
    organism_name = data.get("organism", {}).get("scientificName", "")

    # Sequence
    seq_info = data.get("sequence", {})
    sequence = seq_info.get("value", "")
    length = seq_info.get("length")
    mol_weight = seq_info.get("molWeight")

    # Features
    features = []
    for feat in data.get("features", []):
        feat_type = feat.get("type", "")
        location = feat.get("location", {})
        start = location.get("start", {}).get("value")
        end = location.get("end", {}).get("value")
        desc = feat.get("description", "")
        features.append({
            "type": feat_type,
            "location_start": start,
            "location_end": end,
            "description": desc,
        })

    # Cross-references
    xrefs: dict[str, list[str]] = {}
    for xref in data.get("uniProtKBCrossReferences", []):
        db = xref.get("database", "")
        db_id = xref.get("id", "")
        if db and db_id:
            xrefs.setdefault(db.lower(), []).append(db_id)

    # GO terms
    go_terms = []
    for go in data.get("uniProtKBCrossReferences", []):
        if go.get("database") == "GO":
            go_id = go.get("id", "")
            props = go.get("properties", [])
            go_name = ""
            category = ""
            for prop in props:
                if prop.get("key") == "GoTerm":
                    go_name = prop.get("value", "")
                elif prop.get("key") == "GoCategory":
                    category = prop.get("value", "")
            if go_id:
                go_terms.append({"id": go_id, "name": go_name, "category": category})

    # Pathways (from comments)
    pathways = []
    for comment in data.get("comments", []):
        if comment.get("commentType") == "PATHWAY":
            for pathway in comment.get("pathways", []):
                pathways.append(pathway.get("name", ""))

    # Interactions
    interactions = []
    for comment in data.get("comments", []):
        if comment.get("commentType") == "INTERACTION":
            for interact in comment.get("interactions", []):
                interact_id = interact.get("id", "")
                if interact_id:
                    interactions.append(interact_id)

    # Keywords
    keywords = [kw.get("value", "") for kw in data.get("keywords", [])]

    return {
        "accession": data.get("primaryAccession", accession),
        "id": data.get("uniProtkbId", ""),
        "protein_name": protein_name,
        "gene_names": gene_names,
        "organism_name": organism_name,
        "sequence": {
            "value": sequence,
            "length": length,
            "mol_weight": mol_weight,
        },
        "features": features,
        "xrefs": xrefs,
        "go_terms": go_terms,
        "pathways": pathways,
        "interactions": interactions,
        "keywords": keywords,
    }


async def fetch_variants(accession: str) -> list[dict]:
    """Fetch known variants from UniProt Variation API.
    
    GET /variation/human/{accession} (returns JSON with features array)
    Returns list of {position, wild_type, alternative_sequence, descriptions, frequency, disease_associations}
    Note: this endpoint only works for human proteins; return empty list for non-human.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get_json(client, f"/variation/human/{accession}")
    if data is None:
        return []

    variants = []
    for feat in data.get("features", []):
        location = feat.get("location", {})
        start = location.get("start", {}).get("value")
        end = location.get("end", {}).get("value")
        position = start if start == end else f"{start}-{end}"

        descriptions = []
        for desc in feat.get("descriptions", []):
            descriptions.append(desc.get("value", ""))

        # Alternative sequences
        alt_seqs = []
        for alt in feat.get("alternativeSequences", []):
            alt_seqs.append(alt.get("sequence", ""))

        # Frequency
        frequency = None
        for prop in feat.get("properties", []):
            if prop.get("key") == "Frequency":
                frequency = prop.get("value")
                break

        # Disease associations
        diseases = []
        for xref in feat.get("crossReferences", []):
            if xref.get("database") in ("ClinVar", "OMIM", "Orphanet"):
                diseases.append({"database": xref.get("database"), "id": xref.get("id")})

        variants.append({
            "position": position,
            "wild_type": feat.get("wildType", ""),
            "alternative_sequence": alt_seqs[0] if alt_seqs else "",
            "descriptions": descriptions,
            "frequency": frequency,
            "disease_associations": diseases,
        })
    return variants


async def search_protein(query: str, limit: int = 5) -> list[dict]:
    """Search UniProt.
    
    GET /uniprotkb/search?query={query}&format=json&size={limit}
    Returns list of {accession, id, protein_name, gene_names, organism_name}.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get_json(client, "/uniprotkb/search", {
            "query": query,
            "format": "json",
            "size": str(limit),
        })
    if data is None:
        return []

    results = []
    for entry in data.get("results", []):
        protein_name = ""
        if "proteinDescription" in entry:
            rec_name = entry["proteinDescription"].get("recommendedName", {})
            full_name = rec_name.get("fullName", {})
            protein_name = full_name.get("value", "")

        gene_names = []
        for gene in entry.get("genes", []):
            gene_name = gene.get("geneName", {}).get("value")
            if gene_name:
                gene_names.append(gene_name)

        organism_name = entry.get("organism", {}).get("scientificName", "")

        results.append({
            "accession": entry.get("primaryAccession", ""),
            "id": entry.get("uniProtkbId", ""),
            "protein_name": protein_name,
            "gene_names": gene_names,
            "organism_name": organism_name,
        })
    return results