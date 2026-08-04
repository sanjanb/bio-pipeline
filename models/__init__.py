"""Data models package — canonical ProteinProfile + Job tracking."""

from .protein import (
    ProteinProfile,
    Domain,
    Variant,
    Homolog,
    Publication,
    StructureInfo,
)
from .job import (
    DB_PATH,
    Job,
    JobStatus,
    _get_conn,
    create_job,
    update_job,
    get_job,
    list_jobs,
    job_count,
)

__all__ = [
    "ProteinProfile",
    "Domain",
    "Variant",
    "Homolog",
    "Publication",
    "StructureInfo",
    "DB_PATH",
    "Job",
    "JobStatus",
    "_get_conn",
    "create_job",
    "update_job",
    "get_job",
    "list_jobs",
    "job_count",
]
