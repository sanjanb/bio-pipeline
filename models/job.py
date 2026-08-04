"""SQLite job tracking — zero dependencies beyond stdlib + sqlite3."""

import json
import sqlite3
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

DB_PATH = Path(__file__).parent.parent / "output" / "jobs.db"


class JobStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    sequence: str
    job_name: str
    status: JobStatus = JobStatus.PENDING
    alphafold_job_id: str = ""
    pdb_path: str = ""
    pml_path: str = ""
    report_path: str = ""
    error: str = ""
    current_step: int = 0
    confidence_summary: str = ""  # JSON string
    enriched_data: str = ""  # JSON string
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            sequence TEXT NOT NULL,
            job_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            alphafold_job_id TEXT DEFAULT '',
            pdb_path TEXT DEFAULT '',
            pml_path TEXT DEFAULT '',
            report_path TEXT DEFAULT '',
            error TEXT DEFAULT '',
            current_step INTEGER DEFAULT 0,
            confidence_summary TEXT DEFAULT '',
            enriched_data TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    # Migration for existing databases
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN enriched_data TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN current_step INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


def create_job(job: Job) -> Job:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO jobs (id, sequence, job_name, status, current_step, alphafold_job_id, "
        "pdb_path, pml_path, report_path, error, confidence_summary, enriched_data, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (job.id, job.sequence, job.job_name, job.status.value, job.current_step,
         job.alphafold_job_id, job.pdb_path, job.pml_path, job.report_path,
         job.error, job.confidence_summary, job.enriched_data, job.created_at, job.updated_at),
    )
    conn.commit()
    conn.close()
    return job


def update_job(job: Job) -> Job:
    job.updated_at = time.time()
    conn = _get_conn()
    conn.execute(
        "UPDATE jobs SET status=?, current_step=?, alphafold_job_id=?, pdb_path=?, pml_path=?, "
        "report_path=?, error=?, confidence_summary=?, enriched_data=?, updated_at=? WHERE id=?",
        (job.status.value, job.current_step, job.alphafold_job_id, job.pdb_path, job.pml_path,
         job.report_path, job.error, job.confidence_summary, job.enriched_data, job.updated_at, job.id),
    )
    conn.commit()
    conn.close()
    return job


def get_job(job_id: str) -> Job | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return Job(
        id=row["id"], sequence=row["sequence"], job_name=row["job_name"],
        status=JobStatus(row["status"]), current_step=row["current_step"],
        alphafold_job_id=row["alphafold_job_id"],
        pdb_path=row["pdb_path"], pml_path=row["pml_path"],
        report_path=row["report_path"], error=row["error"],
        confidence_summary=row["confidence_summary"],
        enriched_data=row["enriched_data"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def list_jobs(limit: int = 50, offset: int = 0) -> list[Job]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [
        Job(
            id=r["id"], sequence=r["sequence"], job_name=r["job_name"],
            status=JobStatus(r["status"]), current_step=r["current_step"],
            alphafold_job_id=r["alphafold_job_id"],
            pdb_path=r["pdb_path"], pml_path=r["pml_path"],
            report_path=r["report_path"], error=r["error"],
            confidence_summary=r["confidence_summary"],
            enriched_data=r["enriched_data"],
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
        for r in rows
    ]


def job_count() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return count
