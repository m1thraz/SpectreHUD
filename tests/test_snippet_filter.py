"""
Unit tests for the pure Python snippet filter and search engine.

These tests run entirely in memory without requiring a Qt event loop or QApplication instance.
"""

import pytest
from core.snippet_filter import (
    filter_by_category,
    tokenize_query,
    filter_and_rank_snippets,
)


@pytest.fixture
def sample_snippets():
    return [
        {
            "id": "snip_nmap_syn",
            "title": "Nmap SYN Stealth Scan",
            "category": "Network Scanning",
            "category_id": "network_scanning",
            "template": "nmap -sS -T4 {TARGET_IP}",
            "description": "Fast stealth port scan",
            "tags": ["nmap", "scan", "stealth", "recon"],
        },
        {
            "id": "snip_nmap_vuln",
            "title": "Nmap Vulnerability Script Scan",
            "category": "Network Scanning",
            "category_id": "network_scanning",
            "template": "nmap --script vuln {TARGET_IP}",
            "description": "Run vulnerability detection scripts",
            "tags": ["nmap", "vuln", "scripts"],
        },
        {
            "id": "snip_linpeas",
            "title": "LinPEAS Privilege Escalation",
            "category": "Linux Privilege Escalation",
            "category_id": "linux_privesc",
            "template": "curl -L https://github.com/linpeas.sh | sh",
            "description": "Automated Linux local enumeration",
            "tags": ["linux", "privesc", "enumeration"],
        },
        {
            "id": "snip_winpeas",
            "title": "WinPEAS Privilege Escalation",
            "category": "Windows Privilege Escalation",
            "category_id": "windows_privesc",
            "template": "winpeas.exe quiet cmd fast",
            "description": "Automated Windows local enumeration",
            "tags": ["windows", "privesc", "enumeration"],
        },
        {
            "id": "snip_sqlmap",
            "title": "SQLMap Automated SQL Injection",
            "category": "Web Exploitation",
            "category_id": "web_http",
            "template": "sqlmap -u {TARGET_URL} --batch --dbs",
            "description": "Database enumeration via SQLi",
            "tags": ["sql", "sqli", "web", "database"],
        },
    ]


def test_filter_by_category_all(sample_snippets):
    """'all' or None should return the complete list."""
    assert len(filter_by_category(sample_snippets, "all")) == 5
    assert len(filter_by_category(sample_snippets, None)) == 5


def test_filter_by_specific_category(sample_snippets):
    """Filtering by specific category_id returns only matching items."""
    results = filter_by_category(sample_snippets, "network_scanning")
    assert len(results) == 2
    assert all(s["category_id"] == "network_scanning" for s in results)


def test_filter_by_favorites(sample_snippets):
    """'favorites' returns only pinned snippet IDs."""
    favorites = {"snip_nmap_syn", "snip_sqlmap"}
    results = filter_by_category(sample_snippets, "favorites", favorite_ids=favorites)
    assert len(results) == 2
    assert {s["id"] for s in results} == favorites


def test_tokenize_query_plain_text():
    """Plain queries extract clean search text without tags."""
    parsed = tokenize_query("nmap stealth scan")
    assert parsed["text"] == "nmap stealth scan"
    assert parsed["tags"] == set()


def test_tokenize_query_with_tags():
    """Queries with tag:qualifier extract both text and lowercase tag set."""
    parsed = tokenize_query("nmap tag:stealth tag:Recon -sS")
    assert parsed["text"] == "nmap -sS"
    assert parsed["tags"] == {"stealth", "recon"}


def test_filter_and_rank_by_tag(sample_snippets):
    """Filtering by tag:linux matches only snippets containing that tag."""
    results = filter_and_rank_snippets(sample_snippets, query="tag:linux")
    assert len(results) == 1
    assert results[0]["id"] == "snip_linpeas"


def test_filter_and_rank_fuzzy_search(sample_snippets):
    """Fuzzy queries rank best matches at top."""
    results = filter_and_rank_snippets(sample_snippets, query="nmap")
    assert len(results) == 2
    assert results[0]["id"].startswith("snip_nmap")


def test_filter_and_rank_with_favorite_boost(sample_snippets):
    """Pinned favorites receive score boost and rank higher."""
    # Without favorite, vuln scan or syn scan rank normally
    favs = {"snip_nmap_vuln"}
    results = filter_and_rank_snippets(sample_snippets, query="nmap", favorite_ids=favs)
    assert results[0]["id"] == "snip_nmap_vuln"


def test_filter_and_rank_with_limit(sample_snippets):
    """Limit restricts the number of returned results."""
    results = filter_and_rank_snippets(sample_snippets, query="nmap", limit=1)
    assert len(results) == 1


def test_empty_inputs():
    """Empty or None snippets return empty list safely."""
    assert filter_by_category([]) == []
    assert filter_and_rank_snippets([], query="test") == []
