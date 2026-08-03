"""Data sources package for Protein Intelligence Platform.

Exports API clients for major bioinformatics databases and a file-based cache.
"""

from .cache import DEFAULT_TTL, get_cached, set_cached
from .ncbi_client import (
    fetch_gene_from_protein,
    fetch_protein_record,
    fetch_pubmed_details,
    search_protein,
    search_pubmed,
)
from .uniprot_client import fetch_protein_entry, fetch_variants, search_protein as search_uniprot
from .ensembl_client import (
    fetch_crossrefs,
    fetch_homology,
    fetch_sequence,
    lookup_gene,
)
from .blast_client import fetch_blast_results, poll_blast, run_blast, submit_blast
from .organism import COMMON_ORGANISMS, normalize_organism

__all__ = [
    # Cache
    "get_cached",
    "set_cached",
    "DEFAULT_TTL",
    # NCBI
    "fetch_protein_record",
    "search_protein",
    "fetch_gene_from_protein",
    "search_pubmed",
    "fetch_pubmed_details",
    # UniProt
    "fetch_protein_entry",
    "fetch_variants",
    "search_uniprot",
    # Ensembl
    "lookup_gene",
    "fetch_homology",
    "fetch_crossrefs",
    "fetch_sequence",
    # BLAST
    "submit_blast",
    "poll_blast",
    "fetch_blast_results",
    "run_blast",
    # Organism
    "normalize_organism",
    "COMMON_ORGANISMS",
]