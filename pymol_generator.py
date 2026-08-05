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
