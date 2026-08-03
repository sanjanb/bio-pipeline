"""Generate PyMOL visualization scripts from PDB + pLDDT data."""

from pathlib import Path


def generate_pymol_script(
    pdb_path: str,
    output_pml: str,
    residue_data: list[dict] | None = None,
) -> str:
    """Create a .pml script that colors by pLDDT confidence."""
    pdb = Path(pdb_path).name

    script = f"""# Auto-generated PyMOL script - Structure Prediction Pipeline
# Colors by AlphaFold pLDDT confidence scores

load {pdb}, structure

# Color scheme (AlphaFold convention)
# Dark blue  = very high confidence (>90)
# Blue       = confident (70-90)
# Yellow     = low confidence (50-70)
# Orange     = very low confidence (<50)

# Cartoon representation
color grey80, structure
util.cbc structure

# pLDDT coloring by B-factor
# AlphaFold stores pLDDT in the B-factor column
# PyMOL can color by b-factor directly
cmd.spectrum("b", "blue_white_red", "structure", 0, 100)

# Style
show cartoon, structure
hide lines, structure
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set cartoon_gap_color, grey50

# Surface (optional - uncomment to show)
# show surface, structure
# set transparency, 0.6

# Labels (optional - uncomment for specific residues)
# label structure and resi <resnum>, "%3s%s" % (resn, resi)
# set label_size, 12

# View settings
set ray_opaque_background, 0
bg_color white
set depth_cue, 0
set spec_power, 200
set spec_reflect, 0.5

# Ray-traced high-quality render
# ray 1200, 900
# png structure_prediction.png, dpi=300

# Save session
save structure_prediction.pse
"""
    Path(output_pml).write_text(script, encoding="utf-8")
    return output_pml


def generate_batch_script(
    pdb_path: str,
    output_pml: str,
    high_conf_residues: list[int],
    active_site_residues: list[int] | None = None,
) -> str:
    """Generate a more detailed script with specific residue highlighting."""
    pdb = Path(pdb_path).name

    highlight_lines = ""
    if high_conf_residues:
        resis = "+".join(str(r) for r in high_conf_residues[:50])
        highlight_lines = f"""
# Highlight high-confidence residues
show sticks, structure and resi {resis}
color yellow, structure and resi {resis}
"""

    active_site_lines = ""
    if active_site_residues:
        resis = "+".join(str(r) for r in active_site_residues)
        active_site_lines = f"""
# Active site residues
show sticks, structure and resi {resis}
color red, structure and resi {resis}
label structure and resi {resis}, "%3s" % resi
set label_color, red
"""

    script = f"""# Auto-generated PyMOL script - Structure Prediction Pipeline
# Detailed visualization with residue-level highlights

load {pdb}, structure

# Base representation
color grey80, structure
show cartoon, structure
hide lines, structure
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1

# pLDDT coloring
cmd.spectrum("b", "blue_white_red", "structure", 0, 100)
{highlight_lines}{active_site_lines}
# Settings
set ray_opaque_background, 0
bg_color white
set depth_cue, 0
set spec_power, 200
set antialias, 2

# High-quality render
# ray 1200, 900
# png structure_detail.png, dpi=300

save structure_detail.pse
"""
    Path(output_pml).write_text(script, encoding="utf-8")
    return output_pml
