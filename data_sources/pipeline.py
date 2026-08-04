"""Async orchestrator for multi-source protein data gathering.

Populates a canonical ProteinProfile from UniProt, NCBI, Ensembl, and PubMed.
"""

import asyncio
import logging
from typing import Any

from . import (
    fetch_protein_entry,
    fetch_variants,
    search_uniprot,
    fetch_protein_record,
    fetch_gene_from_protein,
    search_pubmed,
    lookup_gene,
    fetch_homology,
)

logger = logging.getLogger(__name__)


def _build_profile(uniprot_data: dict | None) -> "ProteinProfile":
    """Convert raw UniProt dict into a ProteinProfile."""
    from models.protein import ProteinProfile, Domain, Variant, Homolog, Publication

    if not uniprot_data:
        return ProteinProfile()

    profile = ProteinProfile(
        uniprot_id=uniprot_data.get("accession", ""),
        protein_name=uniprot_data.get("protein_name", ""),
        gene_symbol=uniprot_data.get("gene_names", [""])[0] if uniprot_data.get("gene_names") else "",
        organism=uniprot_data.get("organism_name", ""),
        sequence=uniprot_data.get("sequence", {}).get("value", ""),
        length=uniprot_data.get("sequence", {}).get("length", 0),
        molecular_weight=uniprot_data.get("sequence", {}).get("mol_weight"),
        data_sources=["uniprot"],
    )

    # Extract domains from UniProt features
    for feat in uniprot_data.get("features", []):
        if feat["type"] in ("Domain", "Region", "Family", "Repeat"):
            profile.domains.append(Domain(
                name=feat.get("description") or feat["type"],
                source="uniprot",
                start=feat.get("location_start", 0) or 0,
                end=feat.get("location_end", 0) or 0,
            ))

    return profile


async def search_candidates(sequence: str, limit: int = 5) -> list[dict]:
    """Search UniProt for candidate proteins matching a sequence.

    Returns ranked list of {accession, protein_name, gene_names, organism_name, score}.
    """
    # Search by sequence fragment
    query = f"sequence:{sequence[:30]}"
    try:
        matches = await search_uniprot(query, limit=limit)
        return matches
    except Exception as e:
        logger.warning("Sequence search failed: %s", e)
        return []


async def gather_protein_data(
    uniprot_id: str | None = None,
    sequence: str | None = None,
) -> dict[str, Any]:
    """Gather protein data from all available sources.

    Args:
        uniprot_id: UniProt accession (e.g., P04637)
        sequence: Raw amino acid sequence

    Returns:
        Merged dict with protein_info, ncbi_record, gene_info, ensembl_gene,
        homologs, variants, publications, and errors.
    """
    result: dict[str, Any] = {
        "protein_info": None,
        "ncbi_record": None,
        "gene_info": None,
        "ensembl_gene": None,
        "homologs": None,
        "variants": None,
        "publications": None,
        "errors": {},
    }

    # If only sequence provided, try to find UniProt accession
    if uniprot_id is None and sequence is not None:
        search_query = f"sequence:{sequence[:20]}..."
        try:
            matches = await search_uniprot(search_query, limit=1)
            if matches:
                uniprot_id = matches[0].get("accession")
                logger.info("Found UniProt accession %s for sequence", uniprot_id)
            else:
                logger.info("No UniProt match for sequence, returning minimal data")
                result["protein_info"] = {"sequence": {"value": sequence}}
                return result
        except Exception as e:
            logger.warning("UniProt search failed: %s", e)
            result["errors"]["uniprot_search"] = str(e)
            result["protein_info"] = {"sequence": {"value": sequence}}
            return result

    if uniprot_id is None:
        result["errors"]["input"] = "No UniProt ID or sequence provided"
        return result

    # 1. UniProt protein entry
    try:
        result["protein_info"] = await fetch_protein_entry(uniprot_id)
    except Exception as e:
        logger.warning("fetch_protein_entry failed: %s", e)
        result["errors"]["fetch_protein_entry"] = str(e)

    # 2. UniProt variants (human only)
    try:
        result["variants"] = await fetch_variants(uniprot_id)
    except Exception as e:
        logger.warning("fetch_variants failed: %s", e)
        result["errors"]["fetch_variants"] = str(e)

    # 3. NCBI protein record
    try:
        result["ncbi_record"] = await fetch_protein_record(uniprot_id)
    except Exception as e:
        logger.warning("fetch_protein_record failed: %s", e)
        result["errors"]["fetch_protein_record"] = str(e)

    # 4. NCBI gene info from protein
    try:
        result["gene_info"] = await fetch_gene_from_protein(uniprot_id)
    except Exception as e:
        logger.warning("fetch_gene_from_protein failed: %s", e)
        result["errors"]["fetch_gene_from_protein"] = str(e)

    # 5. Ensembl gene lookup + homology
    gene_symbol = None
    if result["gene_info"] and result["gene_info"].get("symbol"):
        gene_symbol = result["gene_info"]["symbol"]
    elif result["protein_info"] and result["protein_info"].get("gene_names"):
        gene_symbol = result["protein_info"]["gene_names"][0]

    if gene_symbol:
        try:
            ensembl_gene = await lookup_gene(gene_symbol)
            result["ensembl_gene"] = ensembl_gene

            if ensembl_gene and ensembl_gene.get("ensembl_id"):
                homologs = await fetch_homology(ensembl_gene["ensembl_id"], "mus_musculus")
                result["homologs"] = homologs
        except Exception as e:
            logger.warning("Ensembl lookup/homology failed: %s", e)
            result["errors"]["ensembl"] = str(e)

    # 6. PubMed search
    search_terms = []
    if result["protein_info"]:
        if result["protein_info"].get("protein_name"):
            search_terms.append(result["protein_info"]["protein_name"])
        if result["protein_info"].get("gene_names"):
            search_terms.append(result["protein_info"]["gene_names"][0])
        if result["protein_info"].get("organism_name"):
            search_terms.append(result["protein_info"]["organism_name"])

    if search_terms:
        query = " ".join(search_terms)
        try:
            result["publications"] = await search_pubmed(query, max_results=10)
        except Exception as e:
            logger.warning("search_pubmed failed: %s", e)
            result["errors"]["search_pubmed"] = str(e)

    return result


def gather_protein_data_sync(
    uniprot_id: str | None = None,
    sequence: str | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper for gather_protein_data."""
    return asyncio.run(gather_protein_data(uniprot_id=uniprot_id, sequence=sequence))


def search_candidates_sync(sequence: str, limit: int = 5) -> list[dict]:
    """Synchronous wrapper for search_candidates."""
    return asyncio.run(search_candidates(sequence, limit))
