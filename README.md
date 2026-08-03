# Structure Prediction Pipeline

MVP web service that predicts protein 3D structures using AlphaFold Server, generates PyMOL visualization scripts, and produces confidence reports.

## Quick Start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Run the server
uvicorn app:app --reload

# Open browser
open http://localhost:8000
```

## What It Does

1. **Input**: Paste a protein amino acid sequence
2. **Predict**: Submits to AlphaFold Server API (free, no API key needed)
3. **Analyze**: Parses PDB output, extracts per-residue pLDDT confidence scores
4. **Visualize**: Generates PyMOL script that colors structure by confidence
5. **Report**: Produces HTML report with confidence summary + chart

## Output Files

| File | Description |
|------|-------------|
| `structure.pdb` | Predicted 3D structure |
| `visualization.pml` | PyMOL script (cartoon + pLDDT coloring) |
| `report.html` | Confidence report with charts |

## Using PyMOL Script

```bash
pymol visualization.pml

# Inside PyMOL, render high-quality image:
ray 1200, 900
png output.png, dpi=300
```

## Tech Stack

- **FastAPI** — async web framework
- **AlphaFold Server API** — free structure prediction
- **Biopython** — PDB parsing and analysis
- **PyMOL scripting** — visualization generation
- **SQLite** — job tracking (zero config)
- **Chart.js** — confidence visualization
- **uv** — fast Python package manager

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Input form |
| `POST` | `/predict` | Submit sequence |
| `GET` | `/status/{job_id}` | Poll status (auto-refresh) |
| `GET` | `/result/{job_id}` | View results |
| `GET` | `/download/{job_id}/{file}` | Download PDB/script/report |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ALPHAFOLD_API` | `https://alphafoldserver.com/openapi` | AlphaFold endpoint |
| `POLL_INTERVAL` | `30` | Seconds between status checks |
| `OUTPUT_DIR` | `./output` | Where results are stored |

## Docker

```bash
docker build -t structure-predictor .
docker run -p 8000:8000 structure-predictor
```

## Tests

```bash
python tests/test_pipeline.py
```

## Limitations (MVP)

- No authentication
- Synchronous prediction (background task, no queue)
- Local filesystem only
- Max sequence length: 2700 residues (AlphaFold limit)
- Prediction takes 1–30 minutes (not instant)

## License

MIT
