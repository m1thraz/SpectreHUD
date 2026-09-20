"""Render repeatable Professional Print stress cases and run PDF preflight checks."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile
from core.reporting.report_finding import ReportFindingItem
from scripts.generate_sample_report import _find_browser, _render_pdf
from scripts.report_pdf_preflight import analyze_pdf_pages, load_pdf_pages


DEFAULT_SOURCE = REPO_ROOT / "docs" / "examples" / "sample-report-source.md"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "pdfs" / "report-export-stress"
EXPECTED_PAGE_SIZE = (595.28, 841.89)


@dataclass(frozen=True)
class StressScenario:
    slug: str
    description: str
    required_phrase: str
    build_markdown: Callable[[str], str]


@dataclass(frozen=True)
class StressResult:
    scenario: str
    description: str
    pdf: str
    page_count: int
    word_count: int
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _insert_before_section_end(markdown: str, section: str, addition: str) -> str:
    marker = f"<!-- spectre:section:end:{section} -->"
    if marker not in markdown:
        raise ValueError(f"source report is missing {marker}")
    return markdown.replace(marker, f"{addition.rstrip()}\n\n{marker}", 1)


def _replace_section(markdown: str, section: str, replacement: str) -> str:
    pattern = re.compile(
        rf"<!-- spectre:section:start:{re.escape(section)} -->.*?"
        rf"<!-- spectre:section:end:{re.escape(section)} -->",
        re.DOTALL,
    )
    wrapped = (
        f"<!-- spectre:section:start:{section} -->\n\n"
        f"{replacement.strip()}\n\n"
        f"<!-- spectre:section:end:{section} -->"
    )
    rendered, count = pattern.subn(wrapped, markdown, count=1)
    if count != 1:
        raise ValueError(f"source report does not contain one complete {section} section")
    return rendered


def _dense_findings(markdown: str) -> str:
    severities = ("critical", "high", "medium", "low", "info")
    phases = ("recon", "access", "privesc", "postex", "scripts", "misc")
    statuses = ("open", "in_progress", "resolved", "accepted_risk")
    findings: list[ReportFindingItem] = []
    for index in range(5, 19):
        finding = ReportFindingItem(
            id=f"stress-{index:03d}",
            title=(
                f"Synthetic Multi-System Validation Finding {index:02d} with Extended Title"
            ),
            severity=severities[index % len(severities)],
            cvss_score=float((index * 7) % 101) / 10.0,
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N",
            status=statuses[index % len(statuses)],
            phase=phases[index % len(phases)],
            targets=[f"service-{index}.example.test", f"192.0.2.{index}"],
            timestamp=f"2026-09-{(index % 18) + 1:02d} 14:{index:02d}:00",
            description=(
                "A synthetic control gap was reproduced across two representative systems. "
                "The observation deliberately contains enough prose to exercise multi-line "
                "finding metadata, paragraph flow, and automatic page-boundary selection.\n\n"
                "The validation remained non-destructive and used only documentation-reserved "
                "addresses. No production service or real customer data was involved.\n\n"
                f"```text\nstress-case={index:02d}\nresult=synthetic-only\n```"
            ),
            recommendation=(
                "Apply the synthetic remediation in staged environments, add a negative test, "
                "and record the validation outcome before deployment."
            ),
            references=["CWE-200", "OWASP Testing Guide (synthetic reference)"],
        )
        findings.append(finding)

    original_rows = (
        ("Administrative Export Authorization Bypass", "critical", "access"),
        ("Stored Operator Note Injection", "high", "access"),
        ("Shared Deployment Credential", "medium", "privesc"),
        ("Verbose Build Metadata", "low", "recon"),
    )
    matrix_rows = [
        f"| {index} | {title} | {severity.upper()} | {phase} | Open |"
        for index, (title, severity, phase) in enumerate(original_rows, start=1)
    ]
    matrix_rows.extend(
        f"| {index} | {finding.title} | {finding.severity.upper()} | "
        f"{finding.phase} | Open |"
        for index, finding in enumerate(findings, start=5)
    )
    severity_counts = {
        severity: sum(1 for _, item_severity, _ in original_rows if item_severity == severity)
        + sum(1 for finding in findings if finding.severity == severity)
        for severity in severities
    }
    total = " · ".join(
        f'<span class="severity-pill severity-{severity}">{severity.upper()}</span> '
        f"{severity_counts[severity]}"
        for severity in severities
    )
    executive = "\n".join(
        [
            "## 1. Executive Summary",
            "",
            "This synthetic summary intentionally contains a dense findings matrix to stress "
            "multi-page table pagination and repeated headers.",
            "",
            "### Findings Matrix",
            "",
            "| ID | Finding | Severity | Phase | Status |",
            "|---|---|---|---|---|",
            *matrix_rows,
            "",
            f"**Total:** {total}",
            "",
            "### Key Highlights",
            "",
            "- **Coverage:** Eighteen synthetic findings span every supported phase and severity.",
            "- **Purpose:** Validate matrix headers, wrapping, severity badges, and page flow.",
        ]
    )
    markdown = _replace_section(markdown, "executive_summary", executive)
    return _insert_before_section_end(
        markdown,
        "finding_section",
        "\n\n".join(
            finding.to_markdown(language="en", include_phase=True) for finding in findings
        ),
    )


def _large_remediation_table(markdown: str) -> str:
    rows = []
    severities = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    statuses = ("Open", "In Progress", "Accepted Risk", "Resolved")
    for index in range(1, 61):
        rows.append(
            "| {severity} | ST-{index:03d} · Synthetic remediation item with a deliberately "
            "long name | Validate ownership, deploy the scoped control, collect evidence, and "
            "repeat the negative test in the next release window. | {status} |".format(
                severity=severities[index % len(severities)],
                index=index,
                status=statuses[index % len(statuses)],
            )
        )
    replacement = "\n".join(
        [
            "## 5. Remediation & Action Plan",
            "",
            "This synthetic backlog stresses repeated table headers and multi-line rows.",
            "",
            "| Severity | Vulnerability | Recommended Action | Status |",
            "|---|---|---|---|",
            *rows,
            "",
            "The remediation backlog ends with this required sentinel: REMEDIATION-END-060.",
        ]
    )
    return _replace_section(markdown, "remediation_table", replacement)


def _oversized_evidence(markdown: str) -> str:
    lines = [
        f"{index:03d} 2026-09-19T10:{index % 60:02d}:00Z synthetic-event "
        f"target=192.0.2.{(index % 200) + 1} outcome=validated"
        for index in range(1, 181)
    ]
    unbroken = "synthetic-token-" + ("abcdef0123456789" * 100)
    finding = ReportFindingItem(
        id="stress-long-evidence",
        title="Oversized Terminal Evidence and Unbroken Token Handling",
        severity="high",
        cvss_score=7.5,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
        phase="access",
        targets=["logs.example.test"],
        timestamp="2026-09-19 16:42:00",
        description=(
            "The following synthetic terminal capture intentionally exceeds one printed page.\n\n"
            "```text\n"
            + "\n".join(lines)
            + "\n```\n\n"
            "The next value is intentionally unbroken to verify wrapping:\n\n"
            f"`{unbroken}`\n\n"
            "EVIDENCE-END-180 confirms that the complete block survived pagination."
        ),
        recommendation="Store large raw captures as appendices while retaining a concise summary.",
    )
    return _insert_before_section_end(
        markdown, "finding_section", finding.to_markdown(language="en", include_phase=True)
    )


def _extended_attack_path(markdown: str) -> str:
    steps = []
    phases = (
        "Reconnaissance & Enumeration",
        "Initial Access & Exploitation",
        "Privilege Escalation",
        "Post-Exploitation & Lateral Movement",
    )
    for index in range(1, 25):
        steps.extend(
            [
                f"{index}. **{phases[(index - 1) % len(phases)]}**: Synthetic chain step {index:02d}",
                "   - *Description:* A controlled observation links the preceding condition "
                "to the next synthetic step while exercising timeline pagination.",
                f"   - *Finding:* Synthetic Attack Path Finding {index:02d} "
                f"<!-- finding:stress-path-{index:03d} -->",
            ]
        )
    replacement = "\n".join(
        [
            "## 3. Attack Path",
            "",
            "This long synthetic chain validates timeline continuation across page boundaries.",
            "",
            "### Attack Chain",
            "",
            *steps,
            "",
            "ATTACK-PATH-END-024",
        ]
    )
    return _replace_section(markdown, "attack_path", replacement)


def _long_metadata_and_media(markdown: str) -> str:
    replacements = {
        "Northstar Research Portal": (
            "Northstar Intercontinental Research, Archival, Collaboration, and "
            "Synthetic Validation Portal"
        ),
        "Northstar Research Labs (Fictional)": (
            "Northstar Research Laboratories and International Demonstration Consortium "
            "(Entirely Fictional)"
        ),
        "portal.example.test / 192.0.2.0/24": (
            "portal.example.test, api.portal.example.test, worker.portal.example.test, "
            "192.0.2.0/24, and 2001:db8:abcd:0012::/64"
        ),
    }
    for original, replacement in replacements.items():
        markdown = markdown.replace(original, replacement)
    media = "\n\n".join(
        f"### Synthetic Screenshot {index}\n\n"
        "![Synthetic Professional Print preview](SpectreHUD-Sample-Report-preview.png)\n\n"
        "A deliberately repeated local image validates scaling, captions, and page flow."
        for index in range(1, 5)
    )
    return _insert_before_section_end(
        markdown,
        "appendix",
        f"{media}\n\nMEDIA-END-004 confirms that every image block was exported.",
    )


SCENARIOS = (
    StressScenario(
        "dense-findings",
        "18 mixed-severity findings with long metadata and synchronized summary rows",
        "Synthetic Multi-System Validation Finding 18",
        _dense_findings,
    ),
    StressScenario(
        "large-remediation-table",
        "60 multi-line remediation rows with repeated table headers",
        "REMEDIATION-END-060",
        _large_remediation_table,
    ),
    StressScenario(
        "oversized-evidence",
        "180-line code evidence plus an intentionally unbroken token",
        "EVIDENCE-END-180",
        _oversized_evidence,
    ),
    StressScenario(
        "extended-attack-path",
        "24 semantic attack-path steps spanning multiple pages",
        "ATTACK-PATH-END-024",
        _extended_attack_path,
    ),
    StressScenario(
        "long-metadata-and-media",
        "long cover metadata, IPv6 scope, and four embedded screenshots",
        "MEDIA-END-004",
        _long_metadata_and_media,
    ),
)


def build_stress_markdown(source: str, scenario_slug: str) -> str:
    scenario = next((item for item in SCENARIOS if item.slug == scenario_slug), None)
    if scenario is None:
        raise ValueError(f"unknown stress scenario: {scenario_slug}")
    return scenario.build_markdown(source)


def run_stress_suite(
    source_path: Path,
    output_dir: Path,
    *,
    browser: Path,
    temp_dir: Path | None = None,
) -> tuple[StressResult, ...]:
    source = source_path.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[StressResult] = []
    with tempfile.TemporaryDirectory(prefix="spectrehud-report-stress-", dir=temp_dir) as work:
        work_dir = Path(work)
        for scenario in SCENARIOS:
            markdown = scenario.build_markdown(source)
            html = HtmlReportExporter.build_full_html(
                markdown,
                project_dir=source_path.parent,
                project_name="SpectreHUD Professional Print Stress Test",
                language="en",
                profile=ReportExportProfile.PROFESSIONAL_PRINT,
                category="pentest",
                include_toc=True,
            )
            html_path = work_dir / f"{scenario.slug}.html"
            pdf_path = output_dir / f"{scenario.slug}.pdf"
            html_path.write_text(html, encoding="utf-8")
            _render_pdf(browser, html_path, pdf_path, temp_dir=temp_dir)
            report = analyze_pdf_pages(
                load_pdf_pages(pdf_path),
                expected_page_size=EXPECTED_PAGE_SIZE,
                required_phrases=(scenario.required_phrase,),
            )
            results.append(
                StressResult(
                    scenario=scenario.slug,
                    description=scenario.description,
                    pdf=str(pdf_path),
                    page_count=report.page_count,
                    word_count=report.word_count,
                    issues=report.issues,
                )
            )
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "ok": all(result.ok for result in results),
                "results": [asdict(result) | {"ok": result.ok} for result in results],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return tuple(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--browser", help="Path to Chrome, Chromium, or Edge")
    parser.add_argument("--temp-dir", type=Path, help="Optional temporary workspace directory")
    args = parser.parse_args()

    results = run_stress_suite(
        args.source.resolve(),
        args.output_dir.resolve(),
        browser=_find_browser(args.browser),
        temp_dir=args.temp_dir.resolve() if args.temp_dir else None,
    )
    for result in results:
        state = "PASS" if result.ok else "FAIL"
        print(
            f"{state} {result.scenario}: {result.page_count} pages, "
            f"{result.word_count} words"
        )
        for issue in result.issues:
            print(f"  - {issue}")
    print(f"Summary: {args.output_dir.resolve() / 'summary.json'}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
