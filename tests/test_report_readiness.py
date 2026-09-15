from core.reporting import (
    ReportEvidenceItem,
    ReportFindingItem,
    ReportMetadata,
    ReportNarrativeSection,
    ReportReadinessLevel,
    ReportWorkspaceDocument,
    assess_report_readiness,
)


def test_readiness_distinguishes_blockers_from_review_items():
    document = ReportWorkspaceDocument(
        metadata=ReportMetadata(client="Example", target_scope="10.0.0.1"),
        findings=[
            ReportFindingItem(
                id="finding-1",
                title="Exposed service",
                description="Service is reachable.",
            )
        ],
    )

    result = assess_report_readiness(document)

    assert result.status == "incomplete"
    assert {issue.code for issue in result.blockers} == {
        "metadata.tester",
        "metadata.timeframe",
        "finding.recommendation",
    }
    assert {issue.code for issue in result.review_items} == {
        "finding.evidence",
        "summary.incomplete",
    }
    assert all(issue.level is ReportReadinessLevel.BLOCKER for issue in result.blockers)
    assert result.total_findings == 1
    assert result.open_findings == 1
    assert result.evidence_items == 0


def test_complete_report_is_ready_without_treating_open_findings_as_blockers():
    document = ReportWorkspaceDocument(
        metadata=ReportMetadata(
            client="Example",
            tester="Analyst",
            target_scope="10.0.0.1",
            timeframe="2026-09-01 – 2026-09-05",
        ),
        findings=[
            ReportFindingItem(
                id="finding-1",
                title="Exposed service",
                description="Service is reachable.",
                recommendation="Restrict access.",
                evidence_items=[
                    ReportEvidenceItem(
                        id="evidence-1",
                        type="terminal",
                        content="nmap -sV 10.0.0.1",
                    )
                ],
            )
        ],
        narratives=[
            ReportNarrativeSection(
                identity="executive_summary",
                section_type="executive_summary",
                content="""## Executive Summary

Assessment summary.

### Key Highlights

- **Initial Access Vector:** Exposed service
- **Privilege Escalation:** None observed
- **Business Impact & Risk:** Unauthorized access
- **Recommended Remediation:** Restrict access
""",
            )
        ],
        language="en",
    )

    result = assess_report_readiness(document)

    assert result.status == "ready"
    assert result.issues == ()
    assert result.open_findings == 1
    assert result.evidence_items == 1
