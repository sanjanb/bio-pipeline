# Protein Intelligence Platform — Development Roadmap

> **Goal:** Transform the current working prototype into a full Protein Research Workspace.
> **Status:** Phase 1 complete (canonical model, no mock PDB, improved identification).

---

## Current State Assessment

| Area                       | Completion | Status |
| -------------------------- | ---------- | ------ |
| Basic web application      | ~80%       | Done   |
| Protein input (UniProt)    | ~70%       | Done   |
| UniProt client             | ~80%       | Done   |
| NCBI client                | ~70%       | Done   |
| Ensembl client             | ~60%       | Partial |
| BLAST client               | ~55%       | Partial |
| AlphaFold DB retrieval     | ~80%       | Done   |
| pLDDT analysis             | ~70%       | Done   |
| PyMOL generation           | ~60%       | Partial |
| 3D browser viewer          | ~10%       | Not started |
| Domain analysis            | ~40%       | Partial |
| Variant analysis           | ~60%       | Partial |
| VEP integration            | 0%         | Not started |
| Interaction network        | ~10%       | Not started |
| Cytoscape.js               | 0%         | Not started |
| PubMed integration         | ~60%       | Partial |
| AI interpretation          | 0%         | Not started |
| Research report            | ~40%       | Partial |
| Job system                 | ~60%       | Partial |
| Production architecture    | ~25%       | Not started |
| Authentication             | 0%         | Not started |

**Assessment:** Functional Protein Intelligence prototype with data-ingestion foundation already started.

---

## Architecture Overview

### Current

```
UniProt → NCBI → Ensembl → BLAST → AlphaFold DB → PDB → pLDDT → PyMOL → HTML Report
```

### Target

```
                       PROTEIN INPUT
                          ↓
                 ┌─────────────────┐
                 │ Protein Profile │  ← Canonical data model
                 └────────┬────────┘
                          ↓
       ┌──────────────────┼──────────────────┐
       ↓                  ↓                  ↓
   SEQUENCE           STRUCTURE           VARIANTS
       ↓                  ↓                  ↓
    BLAST              3D Viewer            VEP
       ↓                  ↓                  ↓
   DOMAINS            pLDDT/PAE         MUTATIONS
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ↓
                 ┌─────────────────┐
                 │ INTERACTIONS    │  ← Cytoscape.js
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ LITERATURE      │  ← PubMed + relevance
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ EVIDENCE LAYER  │  ← Structured provenance
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ AI INTERPRETATION│  ← LLM on evidence JSON
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ RESEARCH REPORT │  ← Full protein report
                 └─────────────────┘
```

---

## Development Phases

### Phase 0 — Stabilize (Complete)

- [x] FastAPI web app with background tasks
- [x] UniProt/NCBI/Ensembl/BLAST clients
- [x] AlphaFold DB structure retrieval
- [x] PDB parsing and pLDDT analysis
- [x] PyMOL script generation
- [x] HTML report generation
- [x] SQLite job tracking
- [x] File-based caching
- [x] Docker + Render deployment
- [x] Real-time pipeline progress tracking
- [x] Simplified UniProt-only input

---

### Phase 1 — Scientific Data Correctness ✅

> Fix the data model and remove mock outputs.

#### PIP-001: Canonical ProteinProfile Model ✅

**Priority:** Critical
**Effort:** 1-2 days
**Status:** Done — `models/protein.py` created with ProteinProfile, Domain, Variant, Homolog, Publication, StructureInfo dataclasses.

```python
@dataclass
class ProteinProfile:
    # Identity
    uniprot_id: str
    gene_symbol: str
    protein_name: str
    organism: str
    ncbi_id: str | None
    ensembl_id: str | None

    # Sequence
    sequence: str
    length: int
    molecular_weight: float | None

    # Structure
    structure_available: bool
    pdb_url: str | None
    mean_plddt: float | None
    confidence_distribution: dict | None

    # Annotations
    domains: list[Domain]
    variants: list[Variant]
    homologs: list[Homolog]
    publications: list[Publication]
    interactions: list[Interaction]

    # Metadata
    data_sources: list[str]
    last_updated: float
```

**Files to create/modify:**
- `models/protein.py` — New canonical model
- `data_sources/pipeline.py` — Populate ProteinProfile
- `app.py` — Use ProteinProfile in responses

---

#### PIP-002: Remove Mock PDB Generation ✅

**Priority:** Critical
**Effort:** 0.5 days
**Status:** Done — `generate_mock_pdb()` removed from `app.py`. Structure unavailable is now explicit with clear messaging.

Replace `generate_mock_pdb()` with explicit "structure unavailable" state.

```python
# Current (BAD)
generate_mock_pdb(input_value, pdb_path)

# Target
if not structure_available:
    job.structure_status = "unavailable"
    job.structure_note = "No AlphaFold DB structure exists for this sequence."
```

**Files to modify:**
- `alphafold_client.py` — Remove mock function
- `app.py` — Handle structure-unavailable gracefully
- `templates/result.html` — Show "Structure not available" state

---

#### PIP-003: Improve FASTA → Protein Identification ✅

**Priority:** High
**Effort:** 1-2 days
**Status:** Done — Re-enabled sequence input with `search_candidates()` in pipeline. UI has input type toggle (UniProt/Sequence).

Current flow takes first UniProt match silently. Target:

```
FASTA input
    ↓
Validate & normalize
    ↓
Sequence search (UniProt)
    ↓
Candidate matches (ranked)
    ↓
If ambiguous → show candidates to user
    ↓
If unique → auto-select
```

**UI:**
```
We found 3 possible proteins:

1. TP53 — Homo sapiens — 393 aa
2. TP53 — Pan troglodytes — 393 aa
3. TP53 — Mus musculus — 390 aa

[Select]
```

**Files to modify:**
- `data_sources/pipeline.py` — Return ranked candidates
- `templates/index.html` — Candidate selection UI
- `app.py` — Handle candidate confirmation

---

### Phase 2 — Sequence & Domain Analysis ✅

> Complete BLAST and domain visualization.

#### PIP-004: Normalize Domain Annotations ✅

**Priority:** High
**Effort:** 1-2 days

UniProt features and NCBI CDD regions → unified domain model:

```python
@dataclass
class Domain:
    name: str
    source: str        # "uniprot" | "ncbi_cdd" | "interpro"
    start: int
    end: int
    length: int
    description: str
    confidence: float | None
```

**UI:** Linear domain diagram:
```
1 ─────────────────────── 393

    ├─────────────┤
    DNA-binding
       102–292

                   ├───────┤
                   Tetramerization
                   325–356
```

**Files to create/modify:**
- `models/protein.py` — Add Domain dataclass
- `data_sources/uniprot_client.py` — Extract features
- `data_sources/ncbi_client.py` — Extract CDD regions
- `templates/result.html` — Domain visualization

---

#### PIP-005: Complete BLAST Normalization + UI ✅

**Priority:** Medium
**Effort:** 1-2 days

```python
@dataclass
class BlastAnalysis:
    query: str
    database: str
    program: str
    hits: list[BlastHit]

@dataclass
class BlastHit:
    accession: str
    organism: str
    identity: float
    coverage: float
    e_value: float
    bit_score: float
    alignment: str
```

**UI:**
```
Top Homologs

Protein     Organism       Identity   Coverage   E-value
---------------------------------------------------------
ABC1        Human          100%       100%       0
ABC2        Mouse           92%        99%       0
ABC3        Rat             91%        98%       0
```

**Files to modify:**
- `data_sources/blast_client.py` — Parse into BlastAnalysis
- `templates/result.html` — BLAST results table

---

### Phase 3 — Structure & Visualization

> Add PAE and browser-based 3D viewer.

#### PIP-006: AlphaFold Structure Metadata + PAE ✅ ✅

**Priority:** High
**Effort:** 1-2 days

```python
@dataclass
class StructureAnalysis:
    source: str            # "alphafold_db" | "unavailable"
    accession: str
    model_version: str
    chains: list[str]
    residue_count: int
    mean_plddt: float
    confidence_distribution: dict  # {<50: N, 50-70: N, 70-90: N, >90: N}
    pae_available: bool
    pae_url: str | None
```

**Files to modify:**
- `pdb_analyzer.py` — Add PAE parsing if available
- `alphafold_client.py` — Fetch PAE JSON URL
- `models/protein.py` — Add StructureAnalysis

---

#### PIP-007: Browser-Based Interactive 3D Viewer

**Priority:** High
**Effort:** 2-3 days

Replace "install PyMOL" with in-browser molecular viewer.

Options:
- **3Dmol.js** — lightweight, CDN-loaded, no build step
- **NGL Viewer** — more feature-rich, heavier
- **Mol* (molstar)** — RCSB standard, very heavy

Recommendation: **3Dmol.js** — simplest integration, no build tooling needed.

```html
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<div id="viewer" style="height: 400px; width: 100%;"></div>
<script>
  let viewer = $3Dmol.createViewer(document.getElementById('viewer'));
  viewer.addModel(pdbData, "pdb");
  viewer.setStyle({}, {cartoon: {colorprops: "pLDDT"}});
  viewer.zoomTo();
  viewer.render();
</script>
```

**Features:**
- Load PDB from backend
- Color by pLDDT confidence
- Click residue → show info panel
- Highlight domains
- Highlight variant positions

**Files to create/modify:**
- `templates/result.html` — Add 3D viewer div
- `static/viewer.js` — Viewer initialization
- `app.py` — PDB data endpoint for viewer

---

### Phase 4 — Variant Analysis

> Make variants a first-class feature with structure mapping.

#### PIP-008: Variant → Residue → 3D Mapping

**Priority:** High
**Effort:** 2-3 days

```python
@dataclass
class Variant:
    protein_position: int
    wild_type: str
    mutant: str
    consequence: str
    frequency: float | None
    disease_associations: list[str]
    clinical_annotations: list[str]
    structure_position: int | None
    pLDDT_at_position: float | None
    domain_at_position: str | None
```

**Killer feature:** "Show mutation on structure"

```
R175H
    ↓
Find residue 175 in PDB
    ↓
Highlight in 3D viewer
    ↓
Show side panel:
  - Domain: DNA-binding
  - pLDDT: 94.2
  - Nearby residues
  - Conservation
  - Variant annotations
```

**Files to modify:**
- `data_sources/uniprot_client.py` — Richer variant parsing
- `models/protein.py` — Add Variant dataclass
- `templates/result.html` — Variant table + 3D highlighting
- `static/viewer.js` — Variant highlight interaction

---

#### PIP-009: Ensembl VEP Integration

**Priority:** Medium
**Effort:** 1-2 days

Create dedicated VEP client:

```python
# data_sources/vep_client.py

async def query_vep(
    variant: str,        # e.g. "chr17:7675088G>A"
    species: str = "homo_sapiens",
) -> list[VEPResult]:
    """Query Ensembl VEP for variant consequences."""
    ...
```

**Data flow:**
```
Variant (genomic)
    ↓
VEP API
    ↓
Transcript consequences
    ↓
Protein consequence
    ↓
Annotation
```

**Files to create:**
- `data_sources/vep_client.py`
- Wire into variant pipeline

---

### Phase 5 — Interaction Network

> Build protein interaction network with Cytoscape.js.

#### PIP-010: Interaction Network + Cytoscape.js

**Priority:** Medium
**Effort:** 2-3 days

```python
@dataclass
class Interaction:
    source: str          # UniProt ID
    target: str          # UniProt ID
    evidence: str        # "experimental" | "database" | "text_mining"
    source_db: str       // "string" | "intact" | "biogrid"
    score: float | None
```

**Frontend:** Cytoscape.js network visualization

```
              Protein B
                  │
                  │
Protein C ─── TP53 ─── Protein D
                  │
                  │
              Protein E
```

Click node → show protein info, evidence, pathway, publications.

**Files to create/modify:**
- `data_sources/interaction_client.py` — Fetch from STRING/IntAct
- `templates/result.html` — Cytoscape.js integration
- `static/network.js` — Network visualization

---

### Phase 6 — Literature Intelligence

> Upgrade PubMed from search to relevance-ranked literature.

#### PIP-011: PubMed Relevance Ranking

**Priority:** Low-Medium
**Effort:** 1 day

```python
@dataclass
class Literature:
    query: str
    publications: list[Publication]

@dataclass
class Publication:
    pmid: str
    title: str
    authors: list[str]
    journal: str
    year: int
    abstract: str
    relevance_score: float  # 0-1, based on protein specificity
```

**Query expansion:**
```
Protein name → general literature
    +
Mutation-specific literature
    +
Structure-specific literature
    +
Disease-specific literature
```

---

#### PIP-012: Evidence & Provenance System

**Priority:** Medium
**Effort:** 1-2 days

Every data point traces back to its source:

```python
@dataclass
class Evidence:
    claim: str
    source: str          # "uniprot" | "alphafold" | "pubmed" | ...
    source_id: str       # accession, PMID, etc.
    confidence: float
    retrieved_at: float
```

This prevents the AI layer from hallucinating — it only interprets attributed evidence.

---

### Phase 7 — AI Interpretation

> LLM interprets structured evidence, not raw protein data.

#### PIP-013: AI Evidence Interpretation Engine

**Priority:** Low (build after structured evidence is complete)
**Effort:** 2-3 days

**Architecture:**
```
ProteinProfile
    +
StructureAnalysis
    +
VariantAnalysis
    +
NetworkAnalysis
    +
Literature
    ↓
Evidence JSON (structured, attributed)
    ↓
LLM Prompt (interpret THIS evidence)
    ↓
Structured Interpretation
```

**Output sections:**
1. Summary
2. Structural observations
3. Variant observations
4. Functional observations
5. Network observations
6. Literature observations
7. Research questions
8. Limitations
9. Confidence assessment

**Key principle:** Never ask LLM "tell me about TP53." Always provide evidence JSON and ask "interpret this evidence."

---

### Phase 8 — Report & UI Evolution

> Transform from pipeline demo to research workspace.

#### PIP-014: Research Report V2

**Priority:** Medium
**Effort:** 1-2 days

```
Protein Research Report

1.  Protein Identity
2.  Sequence
3.  Domains
4.  Homologs
5.  Structure
6.  pLDDT Confidence
7.  PAE (if available)
8.  Variants
9.  Mutation-Structure Mapping
10. Interaction Network
11. Pathways
12. Literature
13. AI Interpretation
14. Key Observations
15. Limitations
16. Data Sources
17. Reproducibility Metadata
```

---

#### PIP-015: Research Workspace UI

**Priority:** Medium
**Effort:** 2-3 days

Transform from pipeline UI to tabbed research workspace:

```
┌──────────────────────────────────────────────┐
│ TP53                                  P04637 │
├──────────────────────────────────────────────┤
│ Overview │ Sequence │ Structure │ Variants   │
│ Network  │ Literature │ AI │ Report          │
├──────────────────────────────────────────────┤
│                                              │
│              ACTIVE PANEL                    │
│                                              │
└──────────────────────────────────────────────┘
```

---

### Phase 9 — Production Architecture

> Prepare for real users.

#### PIP-016: Separate Job from Protein Model

**Priority:** Low (do after scientific workflow is solid)
**Effort:** 1 day

```python
# Current: Job contains everything
Job(id, sequence, status, paths, enriched_data, ...)

# Target: Separate concerns
Job(id, protein_id, status, created_at, ...)
Protein(id, uniprot_id, gene_symbol, ...)
Analysis(id, protein_id, type, result_json, ...)
Report(id, analysis_id, html_path, ...)
```

---

#### PIP-017: Task Queue (Replace BackgroundTasks)

**Priority:** Low (before serious production traffic)
**Effort:** 2-3 days

```
FastAPI
    ↓
Redis
    ↓
Celery / RQ
    ↓
Worker processes
    ↓
Data sources
    ↓
Results → SQLite/PostgreSQL
```

---

#### PIP-018: Expand Caching

**Priority:** Medium
**Effort:** 1 day

Cache all external API responses:

```
UniProt     → cached by accession
NCBI        → cached by protein ID
Ensembl     → cached by gene ID
BLAST       → cached by query hash
PubMed      → cached by query hash
AlphaFold   → cached by UniProt ID
VEP         → cached by variant string
Interactions → cached by protein set
```

---

#### PIP-019: PostgreSQL Migration

**Priority:** Low (when introducing users/projects)
**Effort:** 2-3 days

```
User
 └── Project
      ├── Protein
      │    ├── Sequence
      │    ├── Structure
      │    ├── Variants
      │    ├── Interactions
      │    └── Literature
      │
      └── Analyses
           ├── BLAST
           ├── Domain
           ├── Variant
           └── AI Interpretation
```

---

## Recommended Sprint Order

```
SPRINT 1 (Week 1-2) ✅
├── PIP-001: Canonical ProteinProfile model
├── PIP-002: Remove mock PDB
└── PIP-003: Improve FASTA identification

SPRINT 2 (Week 3-4) ✅
├── PIP-004: Normalize domain annotations
├── PIP-005: Complete BLAST normalization
└── PIP-006: Structure metadata + PAE

SPRINT 3 (Week 5-6)
├── PIP-007: Browser 3D viewer (3Dmol.js)
├── PIP-008: Variant → structure mapping
└── PIP-009: VEP integration

SPRINT 4 (Week 7-8)
├── PIP-010: Interaction network + Cytoscape.js
├── PIP-011: PubMed relevance ranking
└── PIP-012: Evidence provenance system

SPRINT 5 (Week 9-10)
├── PIP-013: AI interpretation engine
├── PIP-014: Research report V2
└── PIP-015: Research workspace UI

SPRINT 6 (Week 11-12)
├── PIP-016: Separate Job/Protein models
├── PIP-017: Task queue
├── PIP-018: Expand caching
└── PIP-019: PostgreSQL migration
```

---

## What NOT to Build Yet

- Authentication / users
- Payments / subscriptions
- Kubernetes / microservices
- AWS architecture
- Mobile app
- AlphaFold model hosting
- Landing page / marketing

**Reason:** Scientific workflow must be excellent first.

---

## Next Milestone

### Protein Research Workspace (Target: End of Sprint 3)

Input: `P04637`

Output:
```
┌──────────────────────────────────────────┐
│ TP53                                     │
│ Homo sapiens                             │
│ P04637                                   │
├──────────────────────────────────────────┤
│ Overview                                 │
│                                          │
│ Sequence       393 aa                    │
│ Domains        4                         │
│ Homologs       20                        │
│ Structure      Available                 │
│ Mean pLDDT     87.3                      │
│ Variants       12                        │
│ Publications   45                        │
├──────────────────────────────────────────┤
│                                          │
│          INTERACTIVE 3D STRUCTURE        │
│                                          │
├──────────────────────────────────────────┤
│ Variants | Network | Literature          │
├──────────────────────────────────────────┤
│                                          │
│ AI Research Interpretation               │
│                                          │
├──────────────────────────────────────────┤
│              GENERATE REPORT             │
└──────────────────────────────────────────┘
```

---

## Notes

- Don't rebuild the foundation — extend it
- SQLite is fine until users/projects are introduced
- Caching is already in place — expand aggressively
- Keep every data source modular (no mixing)
- The differentiator is research intelligence, not another protein pipeline


// TODO: All dataclasses in models/protein.py (ProteinProfile, Domain, Variant, Homolog, Publication, BlastHit, BlastAnalysis, StructureInfo) are never instantiated in production -- pipeline uses raw dicts - why they are not used