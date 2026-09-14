from core.reporting import (
    ReportEvidenceItem,
    ReportFindingItem,
    duplicate_report_finding,
    finding_from_loot_entry,
)


def test_persisted_manual_evidence_keeps_missing_source_empty():
    finding = ReportFindingItem(
        id="manual-finding",
        title="Manual",
        description="Description",
    )
    finding.attach_evidence(
        ReportEvidenceItem(
            id="manual-evidence",
            type="text",
            content="Manual proof",
        )
    )

    restored = ReportFindingItem.from_markdown(
        finding.to_markdown(),
        entry_id=finding.id,
    )

    assert restored.evidence_items[0].source_loot_id is None


def test_finding_from_loot_preserves_supported_finding_data():
    entry = {
        "id": "loot-credential-1",
        "type": "credentials",
        "category": "privesc",
        "severity": "critical",
        "title": "Reusable administrator credential",
        "content": "administrator:S3cret!",
        "recommendation": "Rotate the credential and disable password reuse.",
        "target_ip": "10.10.10.23",
        "timestamp": "2026-09-14 13:37:00",
        "finding_status": "in_progress",
        "cvss_score": "9.1",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:H",
        "references": ["CWE-521", "https://example.test/advisory"],
    }

    finding = finding_from_loot_entry(entry)

    assert finding.id == entry["id"]
    assert finding.title == entry["title"]
    assert finding.severity == "critical"
    assert finding.phase == "privesc"
    assert finding.status == "in_progress"
    assert finding.targets == ["10.10.10.23"]
    assert finding.timestamp == "2026-09-14 13:37:00"
    assert finding.cvss_score == 9.1
    assert finding.cvss_vector == entry["cvss_vector"]
    assert finding.recommendation == entry["recommendation"]
    assert finding.references == entry["references"]
    assert finding.loot_marker is not None

    evidence = finding.evidence_items[0]
    assert evidence.id == "loot-credential-1-evidence"
    assert evidence.type == "credential"
    assert evidence.language == "credentials"
    assert evidence.source_loot_id == "loot-credential-1"
    assert "spectre:evidence:start:v1" in finding.description


def test_finding_markdown_roundtrip_preserves_cvss_and_evidence_provenance():
    original = finding_from_loot_entry(
        {
            "id": "loot-shot-1",
            "type": "screenshot",
            "category": "access",
            "severity": "high",
            "title": "Admin panel reached",
            "content": "![Authenticated admin panel](evidence/admin.png)",
            "target_ip": "10.10.10.9",
            "timestamp": "2026-09-14 14:10:00",
            "cvss_score": 8.8,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        }
    )

    restored = ReportFindingItem.from_markdown(
        original.to_markdown(language="en", include_phase=True),
        entry_id=original.id,
        language="en",
    )

    assert restored.cvss_score == 8.8
    assert restored.cvss_vector == original.cvss_vector
    assert restored.timestamp == original.timestamp
    assert restored.phase == "access"
    assert len(restored.evidence_items) == 1
    evidence = restored.evidence_items[0]
    assert evidence.id == "loot-shot-1-evidence"
    assert evidence.type == "screenshot"
    assert evidence.caption == "Admin panel reached"
    assert evidence.content == "evidence/admin.png"
    assert evidence.source_loot_id == "loot-shot-1"


def test_duplicate_finding_rekeys_embedded_evidence_without_copying_loot_identity():
    original = finding_from_loot_entry(
        {
            "id": "loot-flag-1",
            "type": "flag",
            "title": "Root flag",
            "content": "root{proof}",
            "category": "post_exploitation",
        }
    )

    duplicate = duplicate_report_finding(
        original,
        new_id="finding-copy",
        title="Root flag (Kopie)",
    )
    restored = ReportFindingItem.from_markdown(
        duplicate.to_markdown(include_phase=True),
        entry_id=duplicate.id,
    )

    assert duplicate.loot_marker is None
    assert duplicate.evidence_items[0].id == "finding-copy-ev-1"
    assert "loot-flag-1-evidence" not in duplicate.description
    assert restored.evidence_items[0].id == "finding-copy-ev-1"
    assert restored.evidence_items[0].source_loot_id == "loot-flag-1"


def test_credential_evidence_roundtrip_uses_adaptive_fence():
    content = "admin\n```\n# heading-like evidence\n```"
    original = finding_from_loot_entry(
        {
            "id": "loot-adversarial-1",
            "type": "credentials",
            "title": "Captured multiline secret",
            "content": content,
        }
    )

    restored = ReportFindingItem.from_markdown(
        original.to_markdown(),
        entry_id=original.id,
    )

    assert "````\n" in original.description
    assert restored.evidence_items[0].content == content
    assert restored.evidence_items[0].language == "credentials"
