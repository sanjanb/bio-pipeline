"""NCBI E-utilities client for protein and PubMed data."""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "protein-intelligence"
EMAIL = "platform@biotech.dev"

# Rate limit: 3 req/s → 0.35s between calls
_RATE_LIMIT_DELAY = 0.35
_last_call = 0.0


async def _rate_limit() -> None:
    global _last_call
    elapsed = asyncio.get_event_loop().time() - _last_call
    if elapsed < _RATE_LIMIT_DELAY:
        await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_call = asyncio.get_event_loop().time()


async def _get_xml(client: httpx.AsyncClient, endpoint: str, params: dict) -> ET.Element | None:
    """Fetch and parse XML from NCBI."""
    await _rate_limit()
    try:
        resp = await client.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except (httpx.HTTPError, ET.ParseError) as e:
        logger.warning("NCBI %s failed: %s", endpoint, e)
        return None


async def fetch_protein_record(accession: str) -> dict | None:
    """Fetch protein record from NCBI.
    
    Returns dict with:
    - accession, gi, definition, organism, sequence, length
    - gene_name (from /gene qualifier in CDS feature)
    - domains (from CDD region features if present)
    Uses efetch.fcgi?db=protein&rettype=gb&retmode=xml
    Parse GBSeq_feature-table for CDS and region features.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "efetch.fcgi", {
            "db": "protein",
            "id": accession,
            "rettype": "gb",
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return None

    # Parse GBSeq
    gbseq = root.find("GBSeq")
    if gbseq is None:
        return None

    def get_text(elem: ET.Element | None, tag: str) -> str | None:
        child = elem.find(tag) if elem is not None else None
        return child.text if child is not None else None

    accession_val = get_text(gbseq, "GBSeq_accession-version") or get_text(gbseq, "GBSeq_primary-accession")
    gi = get_text(gbseq, "GBSeq_gi")
    definition = get_text(gbseq, "GBSeq_definition")
    organism = get_text(gbseq, "GBSeq_organism")
    sequence = get_text(gbseq, "GBSeq_sequence")
    length = get_text(gbseq, "GBSeq_length")

    gene_name = None
    domains = []

    # Parse features
    feature_table = gbseq.find("GBSeq_feature-table")
    if feature_table is not None:
        for feature in feature_table.findall("GBFeature"):
            feature_key = get_text(feature, "GBFeature_key")
            if feature_key == "CDS":
                for qual in feature.findall("GBFeature_quals/GBQualifier"):
                    if get_text(qual, "GBQualifier_name") == "gene":
                        gene_name = get_text(qual, "GBQualifier_value")
                        break
            elif feature_key == "Region":
                for qual in feature.findall("GBFeature_quals/GBQualifier"):
                    if get_text(qual, "GBQualifier_name") == "note":
                        note = get_text(qual, "GBQualifier_value")
                        if note and "CDD" in note:
                            location = get_text(feature, "GBFeature_location")
                            domains.append({"location": location, "description": note})

    return {
        "accession": accession_val,
        "gi": gi,
        "definition": definition,
        "organism": organism,
        "sequence": sequence,
        "length": int(length) if length and length.isdigit() else None,
        "gene_name": gene_name,
        "domains": domains,
    }


async def search_protein(gene: str, organism: str = "Homo sapiens") -> list[dict]:
    """Search NCBI protein DB by gene name + organism.
    
    Uses esearch.fcgi?db=protein&term={gene}[Gene Name] AND {organism}[Organism]
    Returns list of {accession, title} dicts.
    """
    term = f"{gene}[Gene Name] AND {organism}[Organism]"
    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "esearch.fcgi", {
            "db": "protein",
            "term": term,
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return []

    id_list = root.find("IdList")
    if id_list is None:
        return []

    ids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]
    if not ids:
        return []

    # Fetch summaries for titles
    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "esummary.fcgi", {
            "db": "protein",
            "id": ",".join(ids),
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return []

    results = []
    for docsum in root.findall(".//DocSum"):
        accession = None
        title = None
        for item in docsum.findall("Item"):
            if item.get("Name") == "Caption":
                accession = item.text
            elif item.get("Name") == "Title":
                title = item.text
        if accession:
            results.append({"accession": accession, "title": title or ""})
    return results


async def fetch_gene_from_protein(protein_accession: str) -> dict | None:
    """Map protein accession to gene info.
    
    Uses elink.fcgi?dbfrom=protein&db=gene&linkname=protein_gene
    Then esummary.fcgi?db=gene for gene details.
    Returns dict with gene_id, symbol, description, chromosomal_location.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: elink to get gene IDs
        root = await _get_xml(client, "elink.fcgi", {
            "dbfrom": "protein",
            "db": "gene",
            "linkname": "protein_gene",
            "id": protein_accession,
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return None

    link_set = root.find("LinkSet")
    if link_set is None:
        return None

    gene_ids = []
    for link in link_set.findall(".//Link/Id"):
        if link.text:
            gene_ids.append(link.text)

    if not gene_ids:
        return None

    # Step 2: esummary for gene details
    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "esummary.fcgi", {
            "db": "gene",
            "id": ",".join(gene_ids),
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return None

    # Take first gene
    docsum = root.find(".//DocSum")
    if docsum is None:
        return None

    result = {"gene_id": gene_ids[0]}
    for item in docsum.findall("Item"):
        name = item.get("Name")
        if name == "Name":
            result["symbol"] = item.text
        elif name == "Description":
            result["description"] = item.text
        elif name == "Chromosome":
            result["chromosomal_location"] = item.text
        elif name == "MapLocation":
            result["map_location"] = item.text
    return result


async def search_pubmed(query: str, max_results: int = 10) -> list[dict]:
    """Search PubMed.
    
    Returns list of {pmid, title, authors, journal, year, doi}.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "esearch.fcgi", {
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return []

    id_list = root.find("IdList")
    if id_list is None:
        return []

    pmids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]
    if not pmids:
        return []

    return await fetch_pubmed_details(pmids)


async def fetch_pubmed_details(pmids: list[str]) -> list[dict]:
    """Fetch full details for a list of PMIDs."""
    if not pmids:
        return []

    async with httpx.AsyncClient(timeout=30) as client:
        root = await _get_xml(client, "efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        })
    if root is None:
        return []

    results = []
    for article in root.findall(".//PubmedArticle"):
        pmid_elem = article.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else None

        title_elem = article.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else ""

        # Authors
        authors = []
        for author in article.findall(".//Author"):
            last = author.find("LastName")
            fore = author.find("ForeName")
            if last is not None and fore is not None:
                authors.append(f"{fore.text} {last.text}")
            elif last is not None:
                authors.append(last.text)

        # Journal
        journal_elem = article.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else ""

        # Year
        year = None
        pub_date = article.find(".//PubDate")
        if pub_date is not None:
            year_elem = pub_date.find("Year")
            if year_elem is not None:
                year = year_elem.text
            else:
                medline_date = pub_date.find("MedlineDate")
                if medline_date is not None:
                    year = medline_date.text.split()[0] if medline_date.text else None

        # DOI
        doi = None
        for article_id in article.findall(".//ArticleId"):
            if article_id.get("IdType") == "doi":
                doi = article_id.text
                break

        if pmid:
            results.append({
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
            })
    return results