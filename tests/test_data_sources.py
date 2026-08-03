"""Tests for data_sources package - all mocked, no live HTTP."""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx


# -- Cache ----------------------------------------------------------------

def test_cache_roundtrip(tmp_path):
    from data_sources import cache
    cache.CACHE_DIR = tmp_path
    cache.set_cached("test:key", {"hello": "world"})
    result = cache.get_cached("test:key")
    assert result == {"hello": "world"}


def test_cache_expiry(tmp_path):
    from data_sources import cache
    cache.CACHE_DIR = tmp_path
    cache.set_cached("expiring:key", {"data": 1})
    cache_file = list(tmp_path.glob("*.json"))[0]
    data = json.loads(cache_file.read_text())
    data["_cached_at"] = time.time() - 7200
    cache_file.write_text(json.dumps(data))
    result = cache.get_cached("expiring:key", ttl=3600)
    assert result is None


def test_cache_miss(tmp_path):
    from data_sources import cache
    cache.CACHE_DIR = tmp_path
    result = cache.get_cached("nonexistent:key:999")
    assert result is None


# -- Organism -------------------------------------------------------------

def test_normalize_organism():
    from data_sources.organism import normalize_organism
    assert normalize_organism("human") == ("Homo sapiens", "homo_sapiens", 9606)
    assert normalize_organism("Mouse") == ("Mus musculus", "mus_musculus", 10090)
    assert normalize_organism("unknown") is None
    assert normalize_organism("  YEAST  ") == ("Saccharomyces cerevisiae", "saccharomyces_cerevisiae", 4932)


# -- NCBI Client (mocked) ------------------------------------------------

SAMPLE_GB_XML = b"""<?xml version="1.0" ?>
<GBSet>
<GBSeq>
  <GBSeq_accession-version>NP_000537.3</GBSeq_accession-version>
  <GBSeq_gi>379098911</GBSeq_gi>
  <GBSeq_definition>tumor protein p53 [Homo sapiens]</GBSeq_definition>
  <GBSeq_organism>Homo sapiens</GBSeq_organism>
  <GBSeq_sequence>meePqsdpsvepplsqetfsdlwkllpl</GBSeq_sequence>
  <GBSeq_length>393</GBSeq_length>
  <GBSeq_feature-table>
    <GBFeature>
      <GBFeature_key>CDS</GBFeature_key>
      <GBFeature_location>1..393</GBFeature_location>
      <GBFeature_quals>
        <GBQualifier><GBQualifier_name>gene</GBQualifier_name><GBQualifier_value>TP53</GBQualifier_value></GBQualifier>
      </GBFeature_quals>
    </GBFeature>
    <GBFeature>
      <GBFeature_key>Region</GBFeature_key>
      <GBFeature_location>100..200</GBFeature_location>
      <GBFeature_quals>
        <GBQualifier><GBQualifier_name>note</GBQualifier_name><GBQualifier_value>CDD:cd00204, p53 DNA-binding domain</GBQualifier_value></GBQualifier>
      </GBFeature_quals>
    </GBFeature>
  </GBSeq_feature-table>
</GBSeq>
</GBSet>"""


@pytest.mark.asyncio
async def test_fetch_protein_record():
    from data_sources.ncbi_client import fetch_protein_record
    mock_resp = MagicMock()
    mock_resp.content = SAMPLE_GB_XML
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.ncbi_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        result = await fetch_protein_record("NP_000537.3")
    assert result is not None
    assert result["accession"] == "NP_000537.3"
    assert result["gene_name"] == "TP53"
    assert result["organism"] == "Homo sapiens"
    assert len(result["domains"]) == 1


@pytest.mark.asyncio
async def test_fetch_protein_record_error():
    from data_sources.ncbi_client import fetch_protein_record
    with patch("data_sources.ncbi_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=httpx.HTTPError("fail"))
        result = await fetch_protein_record("BAD")
    assert result is None


# -- UniProt Client (mocked) ---------------------------------------------

SAMPLE_UNIPROT = {
    "primaryAccession": "P04637",
    "uniProtkbId": "P53_HUMAN",
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}},
    "genes": [{"geneName": {"value": "TP53"}}],
    "organism": {"scientificName": "Homo sapiens"},
    "sequence": {"value": "MEEPQSDPSVE", "length": 393, "molWeight": 43654},
    "features": [
        {"type": "Helix", "location": {"start": {"value": 10}, "end": {"value": 20}}, "description": ""},
        {"type": "Variant", "location": {"start": {"value": 175}, "end": {"value": 175}}, "description": "R -> H"},
    ],
    "uniProtKBCrossReferences": [
        {"database": "GO", "id": "GO:0006915", "properties": [{"key": "GoTerm", "value": "apoptotic process"}, {"key": "GoCategory", "value": "Biological Process"}]},
        {"database": "PDB", "id": "1TSR"},
    ],
    "comments": [
        {"commentType": "PATHWAY", "pathways": [{"name": "p53 signaling pathway"}]},
        {"commentType": "INTERACTION", "interactions": [{"id": "P04637-9"}]},
    ],
    "keywords": [{"value": "Tumor suppressor"}],
}


@pytest.mark.asyncio
async def test_fetch_protein_entry():
    from data_sources.uniprot_client import fetch_protein_entry
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_UNIPROT
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.uniprot_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        result = await fetch_protein_entry("P04637")
    assert result is not None
    assert result["accession"] == "P04637"
    assert result["gene_names"] == ["TP53"]
    assert result["sequence"]["length"] == 393
    assert len(result["features"]) == 2
    assert len(result["go_terms"]) == 1
    assert result["pathways"] == ["p53 signaling pathway"]


@pytest.mark.asyncio
async def test_fetch_protein_entry_404():
    from data_sources.uniprot_client import fetch_protein_entry
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.uniprot_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        result = await fetch_protein_entry("FAKE")
    assert result is None


# -- Ensembl Client (mocked) ---------------------------------------------

@pytest.mark.asyncio
async def test_lookup_gene():
    from data_sources.ensembl_client import lookup_gene
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "ENSG00000141510", "description": "tumor protein p53",
        "biotype": "protein_coding", "start": 7668402, "end": 7687550,
        "strand": -1, "seq_region_name": "17",
        "Transcript": [{"id": "ENST00000269305", "Translation": {"id": "ENSP00000269305"}, "start": 7668402, "end": 7687550, "strand": -1}],
    }
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.ensembl_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        result = await lookup_gene("TP53")
    assert result is not None
    assert result["ensembl_id"] == "ENSG00000141510"
    assert result["chromosome"] == "17"
    assert len(result["transcripts"]) == 1


@pytest.mark.asyncio
async def test_fetch_homology():
    from data_sources.ensembl_client import fetch_homology
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"homologies": [
        {"target": {"species": "mus_musculus", "protein_id": "ENSMUSP00000059420", "perc_id": 78.5}, "taxonomy_level": "ortholog_one2one"}
    ]}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.ensembl_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        result = await fetch_homology("ENSG00000141510", "mus_musculus")
    assert len(result) == 1
    assert result[0]["identity"] == 78.5


# -- BLAST Client (mocked) -----------------------------------------------

@pytest.mark.asyncio
async def test_submit_blast():
    from data_sources.blast_client import submit_blast
    mock_resp = MagicMock()
    mock_resp.text = "RID = ABC123\nRTOE = 60"
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.blast_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        result = await submit_blast("MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHQYREQIKRVKDSDDVPMVLVGNKCDLAARTVESRQAQDLARSYGIPYIETSAKTRQGVEDAFYTLVREIRQH")
    assert result == "ABC123"


@pytest.mark.asyncio
async def test_submit_blast_no_rid():
    from data_sources.blast_client import submit_blast
    mock_resp = MagicMock()
    mock_resp.text = "No RID found"
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.blast_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        result = await submit_blast("SEQ")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_blast_results():
    from data_sources.blast_client import fetch_blast_results
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"BlastOutput2": [{"report": {"results": {"search": {"hits": [
        {"description": [{"accession": "P01234", "title": "GTPase KRas"}],
         "hsps": [{"bit_score": 200.0, "evalue": 1e-50, "identity": 100, "align_len": 180, "gaps": 0, "query_cov": 95.0}]}
    ]}}}}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("data_sources.blast_client.httpx.AsyncClient") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_resp)
        results = await fetch_blast_results("RID123")
    assert len(results) == 1
    assert results[0]["accession"] == "P01234"
    assert results[0]["percent_identity"] == 100


# -- AlphaFold Client (existing) -----------------------------------------

def test_uniprot_detection():
    from alphafold_client import is_uniprot_id
    assert is_uniprot_id("P04637") is True
    assert is_uniprot_id("Q9Y6K9") is True
    assert is_uniprot_id("ACDEF") is False
    assert is_uniprot_id("MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHQYREQIKRVKDSDDVPMVLVGNKCDLAARTVESRQAQDLARSYGIPYIETSAKTRQGVEDAFYTLVREIRQH") is False


def test_mock_pdb_generation(tmp_path):
    from alphafold_client import generate_mock_pdb
    out = tmp_path / "test.pdb"
    content, residues = generate_mock_pdb("ACDEFGHIKLMNPQRSTVWY", str(out))
    assert "ATOM" in content
    assert "CA" in content
    assert len(residues) == 20
    assert all(0 <= r["plddt"] <= 100 for r in residues)
