"""Self-check tests — no frameworks, just assert-based validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pdb_analyzer import parse_pdb, _confidence_summary
from pymol_generator import generate_pymol_script
from models import Job, JobStatus, create_job, get_job, update_job
from protein_id import is_uniprot_id, validate_sequence


def test_validate_sequence():
    """Sequence validation catches bad input."""
    assert validate_sequence("") is not None
    assert validate_sequence("AC") is not None  # too short
    assert validate_sequence("A" * 2800) is not None  # too long
    assert validate_sequence("ACDEFGHIKLMNPQRSTVWXY") is None  # valid
    assert validate_sequence("acdefghiklmnpqrstvwy") is None  # lowercase OK
    assert validate_sequence("ACDEF123") is not None  # numbers bad
    assert validate_sequence("ACDEFGHIKLMNPQRSTVWZ") is not None  # Z not valid
    print("  [OK] validate_sequence")


def test_confidence_summary():
    """Confidence classification works correctly."""
    residues = [
        {"plddt": 95}, {"plddt": 85}, {"plddt": 60}, {"plddt": 40},
    ]
    s = _confidence_summary(residues)
    assert s["very_high"] == 1
    assert s["high"] == 1
    assert s["low"] == 1
    assert s["very_low"] == 1
    assert s["total"] == 4
    assert s["mean_plddt"] == 70.0
    print("  [OK] confidence_summary")


def test_pymol_generator():
    """PyMOL script generation produces valid file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pml", delete=False) as f:
        pml_path = f.name
    generate_pymol_script("test.pdb", pml_path)
    content = Path(pml_path).read_text()
    assert "load test.pdb" in content
    assert "spectrum" in content
    assert "cartoon" in content
    Path(pml_path).unlink()
    print("  [OK] pymol_generator")


def test_models():
    """Job CRUD works in SQLite."""
    import tempfile
    import os
    os.environ["JOB_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
    # Patch DB_PATH
    import models
    original = models.DB_PATH
    models.DB_PATH = Path(os.environ["JOB_DB"])

    job = Job(id="test123", sequence="ACDEFGHIKLMNPQRSTVWXY", job_name="test")
    create_job(job)
    fetched = get_job("test123")
    assert fetched is not None
    assert fetched.id == "test123"
    assert fetched.status == JobStatus.PENDING

    fetched.status = JobStatus.COMPLETED
    update_job(fetched)
    refetched = get_job("test123")
    assert refetched.status == JobStatus.COMPLETED

    models.DB_PATH = original
    print("  [OK] models CRUD")


def test_uniprot_detection():
    """UniProt ID detection works."""
    assert is_uniprot_id("P04637") == True
    assert is_uniprot_id("Q9Y6K9") == True
    assert is_uniprot_id("ACDEFGHIKLMNPQRSTVWXY") == False
    assert is_uniprot_id("MKWVTFISLLFLFSSAYSARSVLC") == False
    assert is_uniprot_id("P04637") == True
    assert is_uniprot_id("") == False
    print("  [OK] uniprot_detection")


def main():
    print("Running self-check tests...\n")
    test_validate_sequence()
    test_confidence_summary()
    test_pymol_generator()
    test_models()
    test_uniprot_detection()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
