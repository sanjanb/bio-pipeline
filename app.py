"""Structure Prediction Pipeline — FastAPI application."""

import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import Job, JobStatus, create_job, update_job, get_job, list_jobs, job_count
from alphafold_client import is_uniprot_id, fetch_alphafold_structure, download_structure, generate_mock_pdb, generate_mock_summary
from pdb_analyzer import parse_pdb
from pymol_generator import generate_pymol_script
from report_generator import generate_report
from data_sources.pipeline import gather_protein_data_sync

# ── Setup ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Structure Prediction Pipeline", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYX")


def validate_sequence(seq: str) -> str | None:
    """Return error message if invalid, None if OK."""
    clean = seq.replace(" ", "").replace("\n", "").replace("\r", "").upper()
    if not clean:
        return "Sequence is empty"
    if len(clean) < 10:
        return "Sequence must be at least 10 residues"
    if len(clean) > 2700:
        return "Sequence must be under 2700 residues (AlphaFold limit)"
    invalid = set(clean) - VALID_AMINO_ACIDS
    if invalid:
        return f"Invalid characters: {', '.join(sorted(invalid))}. Use standard amino acid codes."
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    recent = list_jobs(limit=5)
    return templates.TemplateResponse(request, "index.html", {"error": None, "recent_jobs": recent})


@app.get("/jobs", response_class=HTMLResponse)
async def jobs(request: Request):
    all_jobs = list_jobs(limit=50)
    total = job_count()
    return templates.TemplateResponse(request, "jobs.html", {"jobs": all_jobs, "total": total})


@app.post("/predict", response_class=HTMLResponse)
async def predict(
    request: Request,
    background_tasks: BackgroundTasks,
    input_type: str = Form("sequence"),
    sequence: str = Form(""),
    uniprot_id: str = Form(""),
    job_name: str = Form(""),
):
    # Route by input type
    if input_type == "uniprot":
        uniprot_id = uniprot_id.strip().upper()
        if not uniprot_id:
            return templates.TemplateResponse(request, "index.html", {"error": "UniProt ID is required"})
        if not is_uniprot_id(uniprot_id):
            return templates.TemplateResponse(request, "index.html", {"error": f"Invalid UniProt accession: {uniprot_id}. Use format like P04637 or Q9Y6K9."})
        input_value = uniprot_id
        job_sequence = f"UniProt:{uniprot_id}"
    else:
        clean_seq = sequence.replace(" ", "").replace("\n", "").replace("\r", "").upper()
        error = validate_sequence(clean_seq)
        if error:
            return templates.TemplateResponse(request, "index.html", {"error": error})
        input_value = clean_seq
        job_sequence = clean_seq

    # Create job
    job_id = uuid.uuid4().hex[:12]
    job = Job(
        id=job_id,
        sequence=job_sequence,
        job_name=job_name or f"pred-{job_id}",
    )
    create_job(job)

    # Kick off prediction in background
    background_tasks.add_task(_run_prediction, job_id, input_value, job.job_name)

    return RedirectResponse(url=f"/status/{job_id}", status_code=303)


@app.get("/status/{job_id}", response_class=HTMLResponse)
async def status(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return templates.TemplateResponse(request, "index.html", {"error": "Job not found"})

    return templates.TemplateResponse(request, "status.html", {"job": job})


@app.get("/api/status/{job_id}")
async def api_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {"error": "not found"}
    return {"status": job.status.value, "job_id": job.id}


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def result(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return templates.TemplateResponse(request, "index.html", {"error": "Job not found"})
    if job.status != JobStatus.COMPLETED:
        return RedirectResponse(url=f"/status/{job_id}", status_code=303)

    summary = json.loads(job.confidence_summary) if job.confidence_summary else {}
    chart_labels = summary.pop("labels", [])
    chart_values = summary.pop("values", [])
    return templates.TemplateResponse(request, "result.html", {
        "job": job, "summary": summary,
        "chart_labels": chart_labels, "chart_values": chart_values,
    })


@app.get("/view/{job_id}")
async def view_report(request: Request, job_id: str):
    job = get_job(job_id)
    if not job or not job.report_path or not Path(job.report_path).exists():
        return HTMLResponse("Report not found", status_code=404)
    html = Path(job.report_path).read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    job = get_job(job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)

    file_map = {
        "structure.pdb": job.pdb_path,
        "visualization.pml": job.pml_path,
        "report.html": job.report_path,
    }
    file_path = file_map.get(filename)
    if not file_path or not Path(file_path).exists():
        return HTMLResponse("File not found", status_code=404)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


# ── Background worker ────────────────────────────────────────────────────────

def _run_prediction(job_id: str, input_value: str, job_name: str):
    """Fetch or generate structure, analyze, generate outputs."""
    job = get_job(job_id)
    if not job:
        return

    try:
        pdb_path = str(OUTPUT_DIR / f"{job_id}.pdb")

        # Step 1: Gather data from all sources
        job.status = JobStatus.SUBMITTED
        update_job(job)

        if is_uniprot_id(input_value):
            enriched = gather_protein_data_sync(uniprot_id=input_value)
            # Fetch AlphaFold structure
            data = fetch_alphafold_structure(input_value)
            if data and data.get("pdb_url"):
                download_structure(data["pdb_url"], pdb_path)
                job.alphafold_job_id = data.get("entryId", input_value)
        else:
            enriched = gather_protein_data_sync(sequence=input_value)
            # Generate mock structure
            generate_mock_pdb(input_value, pdb_path)

        job.status = JobStatus.RUNNING
        update_job(job)

        # Step 2: Parse structure
        analysis = parse_pdb(pdb_path)
        job.pdb_path = pdb_path

        # Step 3: Generate PyMOL script
        pml_path = str(OUTPUT_DIR / f"{job_id}.pml")
        generate_pymol_script(pdb_path, pml_path, analysis["residues"])
        job.pml_path = pml_path

        # Step 4: Generate report with enriched data
        report_path = str(OUTPUT_DIR / f"{job_id}_report.html")
        pdb_content = Path(pdb_path).read_text(encoding="utf-8")
        generate_report(
            job_name=job_name,
            sequence=input_value,
            analysis=analysis,
            pdb_filename=f"{job_id}.pdb",
            pml_filename=f"{job_id}.pml",
            output_path=report_path,
            pdb_content=pdb_content,
            enriched_data=enriched,  # NEW parameter
        )
        job.report_path = report_path

        # Chart data
        chart_data = {
            "labels": [r["residue"] for r in analysis["residues"]],
            "values": [r["plddt"] for r in analysis["residues"]],
        }
        summary_with_chart = {**analysis["summary"], **chart_data}
        job.confidence_summary = json.dumps(summary_with_chart)

        # Store enriched data
        job.enriched_data = json.dumps(enriched, default=str)

        job.status = JobStatus.COMPLETED
        update_job(job)

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        update_job(job)
