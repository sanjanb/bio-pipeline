"""NCBI BLAST client for sequence similarity searches."""

import asyncio
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"

EMAIL = "platform@biotech.dev"
TOOL = "protein-intelligence"

# Rate limits: 10s between submits, poll 15s apart
_SUBMIT_DELAY = 10.0
_POLL_INTERVAL = 15.0
_last_submit = 0.0


async def _rate_limit_submit() -> None:
    global _last_submit
    elapsed = asyncio.get_event_loop().time() - _last_submit
    if elapsed < _SUBMIT_DELAY:
        await asyncio.sleep(_SUBMIT_DELAY - elapsed)
    _last_submit = asyncio.get_event_loop().time()


async def submit_blast(sequence: str, database: str = "swissprot", program: str = "blastp") -> str | None:
    """Submit BLAST search.
    
    POST with CMD=Put, PROGRAM, DATABASE, QUERY, FORMAT_TYPE=JSON2, EMAIL, TOOL.
    Parse RID and RTOE from response.
    Returns RID string or None on failure.
    Required params: EMAIL=platform@biotech.dev, TOOL=protein-intelligence
    """
    await _rate_limit_submit()
    params = {
        "CMD": "Put",
        "PROGRAM": program,
        "DATABASE": database,
        "QUERY": sequence,
        "FORMAT_TYPE": "JSON2",
        "EMAIL": EMAIL,
        "TOOL": TOOL,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(BASE_URL, data=params)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("BLAST submit failed: %s", e)
        return None

    # Parse RID and RTOE from response
    rid_match = re.search(r"RID = (\w+)", resp.text)
    rtoe_match = re.search(r"RTOE = (\d+)", resp.text)

    if not rid_match:
        logger.warning("BLAST submit: no RID in response")
        return None

    rid = rid_match.group(1)
    rtoe = int(rtoe_match.group(1)) if rtoe_match else 60
    logger.info("BLAST submitted: RID=%s, estimated wait=%ds", rid, rtoe)
    return rid


async def poll_blast(rid: str, timeout: int = 120) -> dict | None:
    """Poll for BLAST results.
    
    GET ?CMD=Get&FORMAT_OBJECT=SearchInfo&RID={rid}
    Wait until status=READY or timeout.
    Returns dict with status and hit_count.
    """
    start_time = asyncio.get_event_loop().time()
    params = {
        "CMD": "Get",
        "FORMAT_OBJECT": "SearchInfo",
        "RID": rid,
    }

    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(BASE_URL, params=params)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("BLAST poll failed: %s", e)
            await asyncio.sleep(_POLL_INTERVAL)
            continue

        # Parse status
        status_match = re.search(r"Status=(\w+)", resp.text)
        if not status_match:
            logger.warning("BLAST poll: no status in response")
            await asyncio.sleep(_POLL_INTERVAL)
            continue

        status = status_match.group(1)
        if status == "READY":
            hit_count_match = re.search(r"Hits found: (\d+)", resp.text)
            hit_count = int(hit_count_match.group(1)) if hit_count_match else 0
            return {"status": status, "hit_count": hit_count}
        elif status == "FAILED":
            logger.warning("BLAST search failed for RID=%s", rid)
            return {"status": status, "hit_count": 0}
        elif status in ("WAITING", "UNKNOWN"):
            await asyncio.sleep(_POLL_INTERVAL)
            continue
        else:
            logger.warning("BLAST unknown status: %s", status)
            await asyncio.sleep(_POLL_INTERVAL)

    logger.warning("BLAST poll timeout for RID=%s", rid)
    return {"status": "TIMEOUT", "hit_count": 0}


async def fetch_blast_results(rid: str, max_hits: int = 20) -> list[dict]:
    """Fetch BLAST results.
    
    GET ?CMD=Get&RID={rid}&FORMAT_TYPE=JSON2&HITLIST_SIZE={max_hits}
    Parse JSON2 response.
    Returns list of {accession, title, score, e_value, percent_identity, alignment_length, gaps, query_coverage}
    """
    params = {
        "CMD": "Get",
        "RID": rid,
        "FORMAT_TYPE": "JSON2",
        "HITLIST_SIZE": str(max_hits),
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("BLAST fetch results failed: %s", e)
        return []

    results = []
    # JSON2 format: BlastOutput2 -> report -> results -> search -> hits
    try:
        for report in data.get("BlastOutput2", []):
            search = report.get("report", {}).get("results", {}).get("search", {})
            for hit in search.get("hits", []):
                desc = hit.get("description", [{}])[0]
                hsp = hit.get("hsps", [{}])[0] if hit.get("hsps") else {}

                align_len = hsp.get("align_len") or 1
                identity = hsp.get("identity") or 0
                results.append({
                    "accession": desc.get("accession", ""),
                    "title": desc.get("title", ""),
                    "score": hsp.get("bit_score"),
                    "e_value": hsp.get("evalue"),
                    "percent_identity": round(identity / align_len * 100, 1),
                    "alignment_length": align_len,
                    "gaps": hsp.get("gaps"),
                    "query_coverage": hsp.get("query_cov"),
                })
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("BLAST parse results failed: %s", e)
        return []

    return results


async def run_blast(sequence: str, database: str = "swissprot", max_hits: int = 20) -> list[dict]:
    """Convenience: submit + poll + fetch.
    
    Returns list of hits or empty list.
    """
    rid = await submit_blast(sequence, database)
    if not rid:
        return []

    poll_result = await poll_blast(rid)
    if not poll_result or poll_result.get("status") != "READY":
        return []

    if poll_result.get("hit_count", 0) == 0:
        return []

    return await fetch_blast_results(rid, max_hits)