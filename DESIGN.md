# Protein Intelligence Platform — Design System

## Brand
- **Name:** Protein Intelligence Platform
- **Tagline:** Predict structures, analyze confidence, and visualize results — all in one pipeline.
- **Domain:** Bioinformatics / Computational Biology
- **Audience:** Researchers, bioinformaticians, structural biologists

## Design Tokens

### Colors
| Token | Value | Usage |
|-------|-------|-------|
| primary | #1a56db | CTAs, links, active states, brand |
| primary-dark | #1e40af | Hover states |
| primary-light | #dbeafe | Light backgrounds, badges |
| accent | #0891b2 | Secondary highlights, section borders |
| accent-light | #cffafe | Accent backgrounds |
| bg | #f8fafc | Page background |
| surface | #ffffff | Cards, forms |
| border | #e2e8f0 | Dividers, card borders |
| text | #1e293b | Primary text |
| text-secondary | #64748b | Descriptions, metadata |
| text-muted | #94a3b8 | Placeholders, disabled |

### Confidence Colors
| Level | Color | Background |
|-------|-------|------------|
| Very High (>90) | #2563eb | #EFF6FF → #DBEAFE |
| High (70-90) | #0ea5e9 | #F0F9FF → #E0F2FE |
| Low (50-70) | #eab308 | #FEFCE8 → #FEF9C3 |
| Very Low (<50) | #ef4444 | #FEF2F2 → #FEE2E2 |

### Typography
- **Headings:** Space Grotesk (400-700)
- **Body:** Outfit (300-600)
- **Mono:** SF Mono / Fira Code / Cascadia Code

### Spacing & Radius
- Radius SM: 6px
- Radius MD: 10px
- Radius LG: 16px
- Container max-width: 960px

### Shadows
- SM: 0 1px 3px rgba(0,0,0,0.08)
- MD: 0 4px 8px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.06)
- LG: 0 12px 20px -3px rgba(0,0,0,0.12), 0 4px 8px -4px rgba(0,0,0,0.07)

## Design Principles
1. **Scientific clarity** — Information density without clutter. Data tables, stats grids, and domain tracks should feel precise.
2. **Progressive disclosure** — Hero form → status animation → rich results. Don't overwhelm on first load.
3. **Confidence visualization** — The blue-to-red pLDDT color scale is the visual signature. Use it consistently.
4. **Professional bioinformatics** — This is a research tool, not a toy. Clean, clinical, trustworthy.
5. **Responsive** — Must work on lab tablets and desktop monitors.

## Page Inventory
1. **Homepage (`/`)** — Prediction form + feature cards + recent jobs
2. **Status (`/status/{job_id}`)** — 6-step pipeline animation with polling
3. **Results (`/result/{job_id}`)** — Full results: 3D viewer, confidence, domains, BLAST, variants, interactions, publications
4. **Jobs (`/jobs`)** — Job history listing with status badges
5. **Report (`/view/{job_id}`)** — Standalone printable HTML report with inline 3D viewer

## Interaction Patterns
- Form toggle: UniProt ID vs sequence input
- Pipeline steps: CSS animation with pulse/glow on active, checkmark on done
- 3D viewer: 3Dmol.js with pLDDT coloring, hover/click residue inspection
- Variant rows: Click to highlight residue in 3D viewer
- Interaction network: Cytoscape.js with concentric layout
- Chart: Chart.js line chart for per-residue pLDDT scores
