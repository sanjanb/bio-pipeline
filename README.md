<div align="center">

# Protein Intelligence Platform

**AlphaFold-powered protein structure prediction with real-time pipeline visualization**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![AlphaFold](https://img.shields.io/badge/AlphaFold-DB-blue?style=for-the-badge)](https://alphafold.ebi.ac.uk)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=for-the-badge)](https://render.com)

</div>

---

## Overview

Protein Intelligence Platform is a web service that predicts protein 3D structures using the AlphaFold database, analyzes per-residue confidence scores, generates PyMOL visualization scripts, and produces interactive HTML reports — all in one automated pipeline.

```mermaid
graph LR
    A["User Input<br/>UniProt Accession"] --> B["AlphaFold DB<br/>Structure Lookup"]
    B --> C["PDB Analysis<br/>pLDDT Confidence"]
    C --> D["PyMOL Script<br/>3D Visualization"]
    D --> E["HTML Report<br/>Charts &amp; Summary"]

    style A fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    style B fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    style C fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style D fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    style E fill:#E0F7FA,stroke:#00695C,color:#004D40
```

---

## Pipeline Flow

The prediction pipeline progresses through **6 stages** with real-time status tracking:

```mermaid
graph TD
    S0["Step 0<br/>Initializing"] --> S1
    S1["Step 1<br/>Connecting to<br/>sequence database"] --> S2
    S2["Step 2<br/>Sequence found<br/>in database"] --> S3
    S3["Step 3<br/>Fetching predicted<br/>structure"] --> S4
    S4["Step 4<br/>Computing per-residue<br/>confidence"] --> S5
    S5["Step 5<br/>Generating 3D<br/>visualization"] --> S6
    S6["Step 6<br/>Report ready"]

    style S0 fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    style S1 fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    style S2 fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    style S3 fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style S4 fill:#FFF8E1,stroke:#F57F17,color:#E65100
    style S5 fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    style S6 fill:#E0F7FA,stroke:#00695C,color:#004D40
```

Each step is persisted to SQLite and polled by the frontend every 2 seconds, providing live progress updates.

---

## Architecture

```mermaid
graph TB
    subgraph "Frontend"
        UI["Web UI<br/>Jinja2 Templates"]
        JS["JavaScript<br/>Polling &amp; Charts"]
    end

    subgraph "Backend"
        API["FastAPI<br/>Async Endpoints"]
        BG["Background Tasks<br/>Prediction Worker"]
    end

    subgraph "Data Sources"
        AF["AlphaFold DB<br/>Structure Prediction"]
        UN["UniProt<br/>Protein Metadata"]
        EN["Ensembl<br/>Gene &amp; Homology"]
        NC["NCBI<br/>Protein Records"]
        PM["PubMed<br/>Publications"]
    end

    subgraph "Output"
        PDB["PDB File<br/>3D Structure"]
        PML["PyMOL Script<br/>Visualization"]
        RPT["HTML Report<br/>Confidence Charts"]
        DB["SQLite<br/>Job Tracking"]
    end

    UI --> API
    JS -->|polls every 2s| API
    API --> BG
    BG --> AF
    BG --> UN
    BG --> EN
    BG --> NC
    BG --> PM
    BG --> PDB
    BG --> PML
    BG --> RPT
    BG --> DB

    style UI fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    style JS fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    style API fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    style BG fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    style AF fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style UN fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style EN fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style NC fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style PM fill:#FFF3E0,stroke:#E65100,color:#BF360C
    style PDB fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    style PML fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    style RPT fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    style DB fill:#E0F7FA,stroke:#00695C,color:#004D40
```

---

## Tech Stack

| Layer          | Technology                                                                 |
| -------------- | -------------------------------------------------------------------------- |
| **Framework**      | FastAPI (async Python)                                                     |
| **Template**       | Jinja2                                                                     |
| **Database**       | SQLite (zero-config job tracking)                                          |
| **Structure Data** | AlphaFold DB API (free, no key required)                                   |
| **Bioinformatics** | Biopython (PDB parsing), Ensembl REST, UniProt API, NCBI E-utilities      |
| **Visualization**  | PyMOL scripting, Chart.js (confidence charts)                              |
| **Package Manager**| [uv](https://github.com/astral-sh/uv) (fast Python installs)                |
| **Deployment**     | Docker on Render                                                           |

---

## Quick Start

### Prerequisites

- [Python 3.11+](https://python.org)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Local Development

```bash
# Clone the repository
git clone https://github.com/sanjanb/bio-pipeline.git
cd bio-pipeline

# Install dependencies
uv sync

# Run the development server
uv run uvicorn app:app --reload

# Open http://localhost:8000
```

### Docker

```bash
# Build the image
docker build -t protein-intelligence .

# Run the container
docker run -p 8000:8000 protein-intelligence

# Open http://localhost:8000
```

---

## API Endpoints

| Method   | Path                          | Description                              |
| -------- | ----------------------------- | ---------------------------------------- |
| `GET`    | `/`                             | Prediction input form                    |
| `POST`   | `/predict`                      | Submit UniProt accession for prediction  |
| `GET`    | `/status/{job_id}`              | Real-time pipeline status (auto-refresh) |
| `GET`    | `/api/status/{job_id}`          | JSON status for polling (`status`, `current_step`) |
| `GET`    | `/result/{job_id}`              | Results page with confidence charts      |
| `GET`    | `/download/{job_id}/{filename}` | Download PDB, PyMOL script, or report    |
| `GET`    | `/jobs`                         | Job history listing                      |

---

## Configuration

| Variable         | Default                                      | Description                     |
| ---------------- | -------------------------------------------- | ------------------------------- |
| `ALPHAFOLD_API`  | `https://alphafold.ebi.ac.uk/api/prediction` | AlphaFold DB endpoint           |
| `OUTPUT_DIR`     | `./output`                                     | Where prediction outputs stored |
| `DB_PATH`        | `./output/jobs.db`                             | SQLite database path            |

---

## Project Structure

```
biotech-pipeline/
├── app.py                  # FastAPI application & routes
├── models.py               # Job model & SQLite operations
├── alphafold_client.py     # AlphaFold DB API client
├── pdb_analyzer.py         # PDB parsing & pLDDT analysis
├── pymol_generator.py      # PyMOL visualization scripts
├── report_generator.py     # HTML report generation
├── data_sources/           # Multi-source protein data
│   ├── pipeline.py         # Async orchestrator
│   ├── uniprot_client.py   # UniProt API
│   ├── ensembl_client.py   # Ensembl REST API
│   ├── ncbi_client.py      # NCBI E-utilities
│   ├── blast_client.py     # NCBI BLAST
│   ├── cache.py            # File-based caching
│   └── organism.py         # Organism normalization
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Input form
│   ├── status.html         # Pipeline progress
│   ├── result.html         # Results & charts
│   └── jobs.html           # Job history
├── static/
│   └── style.css           # Application styles
├── tests/                  # Test suite
├── Dockerfile              # Container build
├── render.yaml             # Render deployment
├── pyproject.toml          # Project metadata
└── uv.lock                 # Dependency lockfile
```

---

## Output Files

| File              | Description                                      |
| ----------------- | ------------------------------------------------ |
| `{job_id}.pdb`    | Predicted 3D protein structure (PDB format)      |
| `{job_id}.pml`    | PyMOL script — cartoon + pLDDT confidence coloring |
| `{job_id}_report.html` | Interactive HTML report with confidence charts   |

### Viewing PyMOL Scripts

```bash
# Open in PyMOL
pymol {job_id}.pml

# Render high-quality image inside PyMOL
ray 1200, 900
png output.png, dpi=300
```

---

## Limitations

- **No authentication** — open access (suitable for internal/demo use)
- **Background processing** — predictions run as FastAPI background tasks (no job queue)
- **Local filesystem** — outputs stored on disk (not S3/cloud)
- **Sequence length** — max 2700 residues (AlphaFold DB limit)
- **Prediction time** — 1–30 minutes depending on protein complexity

---

## License

MIT

---

<div align="center">

**Built with [AlphaFold DB](https://alphafold.ebi.ac.uk) | [Biopython](https://biopython.org) | [FastAPI](https://fastapi.tiangolo.com) | [PyMOL](https://pymol.org)**

</div>
