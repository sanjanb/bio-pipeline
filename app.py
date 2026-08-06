"""Protein Intelligence Platform — FastAPI application.

Thin HTTP layer. All business logic lives in prediction.py (deep module).
Routes validate input, create jobs, dispatch to the pipeline, and render templates.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import Job, create_job, get_job, list_jobs, job_count
from protein_id import is_uniprot_id, validate_sequence
from prediction import run_prediction

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Protein Intelligence Platform", version="0.2.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger("uvicorn.error")


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
    input_type: str = Form("uniprot"),
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
            return templates.TemplateResponse(request, "index.html", {
                "error": f"Invalid UniProt accession: {uniprot_id}. Use format like P04637 or Q9Y6K9."
            })
        input_value = uniprot_id
        job_sequence = f"UniProt:{uniprot_id}"
    else:
        clean_seq = sequence.replace(" ", "").replace("\n", "").replace("\r", "").upper()
        error = validate_sequence(clean_seq)
        if error:
            return templates.TemplateResponse(request, "index.html", {"error": error})
        input_value = clean_seq
        job_sequence = clean_seq

    # Create job and dispatch
    import uuid
    job_id = uuid.uuid4().hex[:12]
    job = Job(
        id=job_id,
        sequence=job_sequence,
        job_name=job_name or f"pred-{job_id}",
    )
    create_job(job)

    background_tasks.add_task(run_prediction, job_id, input_value, job.job_name)
    return RedirectResponse(url=f"/status/{job_id}", status_code=303)


@app.api_route("/status/{job_id}", methods=["GET", "POST"], response_class=HTMLResponse)
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
    return {"status": job.status.value, "current_step": job.current_step, "job_id": job.id}


@app.get("/api/pdb/{job_id}")
async def api_pdb(job_id: str):
    job = get_job(job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    pdb_path = OUTPUT_DIR / f"{job_id}.pdb"
    if not pdb_path.exists():
        return HTMLResponse("PDB file not found", status_code=404)
    return FileResponse(path=str(pdb_path), media_type="text/plain")


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def result(request: Request, job_id: str):
    import json
    from models import JobStatus

    job = get_job(job_id)
    if not job:
        return templates.TemplateResponse(request, "index.html", {"error": "Job not found"})
    if job.status != JobStatus.COMPLETED:
        return RedirectResponse(url=f"/status/{job_id}", status_code=303)

    summary = json.loads(job.confidence_summary) if job.confidence_summary else {}
    chart_labels = summary.pop("labels", [])
    chart_values = summary.pop("values", [])

    # Parse enriched data for protein info, domains, BLAST
    try:
        enriched = json.loads(job.enriched_data) if job.enriched_data else {}
    except (json.JSONDecodeError, ValueError):
        enriched = {}
    protein_info = enriched.get("protein_info")
    domains = enriched.get("domains", [])
    blast_hits = enriched.get("blast_results", [])
    sequence_length = protein_info.get("sequence", {}).get("length", 0) if protein_info and protein_info.get("sequence") else 0

    return templates.TemplateResponse(request, "result.html", {
        "job": job, "summary": summary,
        "chart_labels": chart_labels, "chart_values": chart_values,
        "protein_info": protein_info,
        "domains": domains,
        "blast_hits": blast_hits,
        "variants": enriched.get("variants", []),
        "publications": enriched.get("publications", []),
        "sequence_length": sequence_length,
        "structure_status": enriched.get("structure_status", "available"),
        "provenance": enriched.get("provenance", {}),
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
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")
