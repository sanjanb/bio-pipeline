"""Protein identifier validation and resolution.

Small interface, pure functions — testable through that interface.
Two callers: app.py (HTTP validation) and prediction.py (pipeline routing).
"""

VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYX")


def is_uniprot_id(text: str) -> bool:
    """Check if text looks like a UniProt accession (e.g., P00533, Q9Y6K9)."""
    text = text.strip().upper()
    if len(text) < 6 or len(text) > 10:
        return False
    if not text[0].isalpha():
        return False
    return text[1:].isalnum()


def validate_sequence(seq: str) -> str | None:
    """Validate an amino acid sequence. Returns error message or None."""
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
