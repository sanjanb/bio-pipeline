"""Organism name normalization helper for bioinformatics APIs."""

COMMON_ORGANISMS = {
    "human": ("Homo sapiens", "homo_sapiens", 9606),
    "mouse": ("Mus musculus", "mus_musculus", 10090),
    "rat": ("Rattus norvegicus", "rattus_norvegicus", 10116),
    "zebrafish": ("Danio rerio", "danio_rerio", 7955),
    "fly": ("Drosophila melanogaster", "drosophila_melanogaster", 7227),
    "worm": ("Caenorhabditis elegans", "caenorhabditis_elegans", 6239),
    "yeast": ("Saccharomyces cerevisiae", "saccharomyces_cerevisiae", 4932),
    "ecoli": ("Escherichia coli", "escherichia_coli", 511145),
    "arabidopsis": ("Arabidopsis thaliana", "arabidopsis_thaliana", 3702),
}


def normalize_organism(name: str) -> tuple[str, str, int] | None:
    """Returns (scientific_name, ensembl_name, taxon_id) or None."""
    key = name.strip().lower()
    return COMMON_ORGANISMS.get(key)