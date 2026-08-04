"""Canonical protein data model — single source of truth for all data sources."""

from dataclasses import dataclass, field


@dataclass
class Domain:
    name: str
    source: str          # "uniprot" | "ncbi_cdd" | "interpro"
    start: int
    end: int
    length: int = 0
    description: str = ""

    def __post_init__(self):
        if self.length == 0:
            self.length = self.end - self.start + 1


@dataclass
class Variant:
    protein_position: int
    wild_type: str
    mutant: str
    consequence: str = ""
    frequency: float | None = None
    disease_associations: list[dict] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)


@dataclass
class Homolog:
    species: str
    protein_id: str
    identity: float | None = None
    sequence: str = ""
    taxonomy_level: str = ""


@dataclass
class Publication:
    pmid: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    abstract: str = ""


@dataclass
class BlastHit:
    accession: str = ""
    title: str = ""
    organism: str = ""
    identity: float | None = None
    coverage: float | None = None
    e_value: float | None = None
    bit_score: float | None = None
    alignment_length: int | None = None
    gaps: int | None = None


@dataclass
class BlastAnalysis:
    query_length: int = 0
    database: str = ""
    program: str = ""
    hit_count: int = 0
    hits: list[BlastHit] = field(default_factory=list)


@dataclass
class StructureInfo:
    available: bool = False
    source: str = ""            # "alphafold_db" | "unavailable"
    pdb_url: str = ""
    mean_plddt: float | None = None
    confidence_distribution: dict = field(default_factory=dict)
    residue_count: int = 0
    model_version: int | None = None
    chains: list[str] = field(default_factory=list)
    pae_url: str = ""
    pae_available: bool = False


@dataclass
class ProteinProfile:
    """Canonical internal model — every data source populates this."""

    # Identity
    uniprot_id: str = ""
    gene_symbol: str = ""
    protein_name: str = ""
    organism: str = ""
    ncbi_id: str | None = None
    ensembl_id: str | None = None

    # Sequence
    sequence: str = ""
    length: int = 0
    molecular_weight: float | None = None

    # Structure
    structure: StructureInfo = field(default_factory=StructureInfo)

    # Annotations
    domains: list[Domain] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)
    homologs: list[Homolog] = field(default_factory=list)
    publications: list[Publication] = field(default_factory=list)
    blast: BlastAnalysis | None = None

    # Metadata
    data_sources: list[str] = field(default_factory=list)
    errors: dict = field(default_factory=dict)

    def has_error(self) -> bool:
        return bool(self.errors)

    def source_summary(self) -> str:
        return ", ".join(self.data_sources) if self.data_sources else "none"
