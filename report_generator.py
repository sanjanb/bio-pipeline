"""Generate HTML confidence reports from pLDDT analysis."""

import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report(
    job_name: str,
    sequence: str,
    analysis: dict,
    pdb_filename: str,
    pml_filename: str,
    output_path: str,
    pdb_content: str = "",
    enriched_data: dict | None = None,
) -> str:
    """Build an HTML report with confidence summary + per-residue chart data."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    summary = analysis["summary"]
    residues = analysis["residues"]

    # Build chart data (first 200 residues for readability)
    chart_residues = residues[:200]
    chart_labels = [f"{r['residue']}" for r in chart_residues]
    chart_values = [r["plddt"] for r in chart_residues]

    html = template.render(
        job_name=job_name,
        sequence_length=len(sequence.replace(" ", "").replace("\n", "")),
        sequence_preview=sequence[:100] + "..." if len(sequence) > 100 else sequence,
        summary=summary,
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values),
        pdb_filename=pdb_filename,
        pml_filename=pml_filename,
        total_residues=analysis["total_residues"],
        pdb_content=pdb_content,
        enriched_data=enriched_data or {},
    )

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
