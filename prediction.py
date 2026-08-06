"""Prediction pipeline — deep module.

Small interface:
    run_prediction(job_id, input_value, job_name) -> PredictionResult

Large implementation hidden behind that single call:
    - Sequence-to-UniProt resolution
    - Multi-source data enrichment (UniProt, NCBI, Ensembl, PubMed)
    - AlphaFold structure fetch + download
    - PDB parsing + pLDDT confidence analysis
    - BLAST homology search
    - PyMOL visualization script generation
    - HTML report generation
    - Job state management throughout

Seam: callers create a Job, then call run_prediction. Everything else is internal.
Testable: mock get_job/update_job for DB, mock fetch_* for HTTP, mock parse/generate for files.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from models import Job, JobStatus, get_job, update_job
from protein_id import is_uniprot_id
from alphafold_client import fetch_alphafold_structure, download_structure
from pdb_analyzer import parse_pdb
from pymol_generator import generate_pymol_script
from report_generator import generate_report
from data_sources.pipeline import gather_protein_data_sync, search_candidates_sync
from data_sources.blast_client import run_blast

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class PredictionResult:
    """Result of a prediction pipeline run."""
    success: bool
    job_id: str
    error: str = ""
    structure_available: bool = False


def run_prediction(job_id: str, input_value: str, job_name: str) -> PredictionResult:
    """Execute the full prediction pipeline for a job.

    Single entry point for all prediction work.
    Callers create a job, then call this. Everything else is internal.
    """
    job = get_job(job_id)
    if not job:
        return PredictionResult(success=False, job_id=job_id, error="Job not found")

    try:
        pdb_path = str(OUTPUT_DIR / f"{job_id}.pdb")

        # Step 0-1: Gather data from all sources
        job.current_step = 0
        job.status = JobStatus.SUBMITTED
        update_job(job)

        job.current_step = 1
        update_job(job)

        # For sequence input, try to identify the protein first
        uniprot_id = None
        if not is_uniprot_id(input_value):
            candidates = search_candidates_sync(input_value, limit=3)
            if not candidates:
                job.status = JobStatus.FAILED
                job.error = "Could not identify this protein. Try a UniProt accession (e.g., P04637) instead."
                update_job(job)
                return PredictionResult(success=False, job_id=job_id, error=job.error)
            uniprot_id = candidates[0].get("accession")
            logger.info("Identified protein as %s from sequence input", uniprot_id)

        enriched = gather_protein_data_sync(uniprot_id=uniprot_id or input_value)

        # Step 2: Fetch AlphaFold structure
        job.current_step = 2
        update_job(job)

        structure_available = False
        target_id = uniprot_id or input_value
        if is_uniprot_id(target_id):
            data = fetch_alphafold_structure(target_id)
            if data and data.get("pdb_url"):
                download_structure(data["pdb_url"], pdb_path)
                job.alphafold_job_id = data.get("entryId", target_id)
                structure_available = True
                if data.get("pae_url"):
                    enriched["pae_url"] = data["pae_url"]

        if not structure_available:
            # No mock — record explicit unavailable state
            job.status = JobStatus.COMPLETED
            job.current_step = 6
            job.error = ""
            enriched["structure_status"] = "unavailable"
            enriched["structure_note"] = "No AlphaFold DB structure available for this protein."
            job.enriched_data = json.dumps(enriched, default=str)

            report_path = str(OUTPUT_DIR / f"{job_id}_report.html")
            generate_report(
                job_name=job_name,
                sequence=input_value,
                analysis={"residues": [], "total_residues": 0, "summary": {"total_residues": 0, "mean_plddt": 0}},
                pdb_filename="",
                pml_filename="",
                output_path=report_path,
                pdb_content="",
                enriched_data=enriched,
            )
            job.report_path = report_path
            update_job(job)
            return PredictionResult(success=True, job_id=job_id, structure_available=False)

        job.status = JobStatus.RUNNING
        update_job(job)

        # Step 3: Parse structure
        job.current_step = 3
        update_job(job)
        analysis = parse_pdb(pdb_path)
        job.pdb_path = pdb_path

        # Step 3.5: Run BLAST analysis (non-blocking, with timeout)
        blast_results = []
        try:
            sequence = enriched.get("protein_info", {}).get("sequence", {}).get("value", "")
            if sequence and len(sequence) >= 10:
                logger.info("Running BLAST for %s", target_id)
                blast_results = asyncio.run(run_blast(sequence, database="swissprot", max_hits=10))
                enriched["blast_results"] = blast_results
                if "provenance" not in enriched:
                    enriched["provenance"] = {}
                enriched["provenance"]["blast_results"] = {
                    "source": "blast_swissprot",
                    "source_id": "swissprot",
                    "retrieved_at": time.time(),
                }
        except Exception as e:
            logger.warning("BLAST failed (non-critical): %s", e)
            enriched["blast_error"] = str(e)

        # Step 4: Generate PyMOL script
        job.current_step = 4
        update_job(job)
        pml_path = str(OUTPUT_DIR / f"{job_id}.pml")
        generate_pymol_script(pdb_path, pml_path, analysis["residues"])
        job.pml_path = pml_path

        # Step 5: Generate report
        job.current_step = 5
        update_job(job)
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
            enriched_data=enriched,
        )
        job.report_path = report_path

        chart_data = {
            "labels": [r["residue"] for r in analysis["residues"]],
            "values": [r["plddt"] for r in analysis["residues"]],
        }
        summary_with_chart = {**analysis["summary"], **chart_data}
        job.confidence_summary = json.dumps(summary_with_chart)
        job.enriched_data = json.dumps(enriched, default=str)

        job.status = JobStatus.COMPLETED
        job.current_step = 6
        update_job(job)

        return PredictionResult(success=True, job_id=job_id, structure_available=True)

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        update_job(job)
        return PredictionResult(success=False, job_id=job_id, error=str(e))
