# Professional Print Export Stress Test

This document records the reproducible stress test for the Professional Print
exporter. It complements focused unit tests with real Chromium PDF rendering,
geometry/content preflight, and visual page inspection.

## Test run

- Date: 2026-09-20
- Revision: `b3c3f0e` plus the uncommitted pagination/sample-report changes under review
- Renderer: installed Google Chrome in headless print-to-PDF mode
- Output: A4 Professional Print PDFs
- Inputs: synthetic data and documentation-reserved addresses only
- Result: all 5 scenarios passed the automated checks after preserving
  unstructured attack-path content

The five reports contained 77 pages and 11,122 positioned words in total.
Preflight checked A4 geometry, safe page edges, unexpectedly sparse pages,
required end markers, and leaked internal Spectre markers. Every page was also
rendered to PNG and visually reviewed.

| Scenario | Load | Pages | Words | Automated result |
|---|---:|---:|---:|---|
| Dense findings | 18 findings and an 18-row summary matrix | 23 | 2,962 | Pass |
| Large remediation table | 60 multi-line rows | 13 | 2,917 | Pass |
| Oversized evidence | 180 code lines and a 1,600-character token | 13 | 2,151 | Pass |
| Extended attack path | 24 semantic timeline steps and a trailing note | 12 | 1,794 | Pass |
| Long metadata and media | long cover fields, IPv6 scope, and 4 screenshots | 16 | 1,298 | Pass |

The generated PDFs and page renders are temporary diagnostics under
`tmp/pdfs/report-export-stress/`; they are intentionally not versioned.

## What works well

- The 18-row findings matrix flows onto a second page with a repeated header.
  Long finding names, full phase labels, statuses, and unified severity badges
  remain legible and inside their columns.
- All 18 finding bodies remain complete. Finding headers, metadata, code,
  recommendations, and references are neither clipped nor overlaid.
- The 60-row remediation table repeats its header on continuation pages. Rows
  wrap cleanly, the final row and sentinel are present, and the appendix begins
  at a clean boundary.
- A 180-line code block can continue across several pages. The final line is
  present, and the deliberately unbroken token wraps within the printable area.
- All 24 attack-path steps are present, ordered, and visually connected across
  continuation pages. Free text after the final step remains visible before the
  next report section.
- Long client/scope metadata fits on the cover, including an IPv6 range. Large
  images scale within the page and are not cropped.
- No raw section/finding/page-break markers leaked into any PDF. No out-of-bounds
  or unsafe-edge text was detected.

## Resolved during follow-up

### Preserved free text around structured attack-path steps

The initial run exposed a loss of free text after the final numbered attack-path
step. Step recognition now stops at unstructured Markdown boundaries, and the
renderer emits preserved blocks between timeline groups or after the final
group in their original order.

Regression coverage verifies both a manual paragraph between generated steps
and a conclusion after the final step. The repeated real-browser run retained
`ATTACK-PATH-END-024` on page 7, directly before Technical Findings, and all five
stress scenarios passed.

## Remaining improvements

### P2 — Keep a screenshot with its explanatory caption or note

Large screenshots are scaled correctly, but the following explanatory paragraph
can be pushed onto a nearly empty page. This is valid output, yet it looks less
deliberate than the rest of the report.

Recommended change: emit evidence images as semantic `<figure>` elements with a
`<figcaption>`, then let the pagination estimator reserve space for both. If an
image plus caption cannot fit, scale the image to the remaining printable height
or move the complete figure to the next page.

### P3 — Refine density decisions for medium findings

The dense-findings report is stable and readable, but the planner places most
medium-sized findings on individual pages, leaving substantial whitespace. That
is a safe professional default and not a correctness defect.

Recommended change: only if a more compact report is desired, calibrate the
finding height estimate with measured browser geometry or allow a second finding
when both complete blocks fit with a minimum bottom margin. Keep the current
behavior as the fallback; avoiding clipped findings is more important than page
count.

### P3 — Extend preflight beyond word count

The current sparse-page guard correctly rejects pages with fewer than eight
words, but an isolated 10-word image note can still consume a page. The visual
review caught this; the automated preflight did not.

Recommended change: add occupied-height and semantic adjacency checks. Useful
signals are a low text bounding-box ratio, a paragraph separated from the image
that precedes it, and required end sentinels per semantic section.

## Verdict

Professional Print is robust for the normal report workflow and for heavy
findings, tables, code evidence, long metadata, and multi-page attack paths. It
does not clip content in those workloads, and manually added content around
structured attack-path steps is retained. The remaining screenshot/caption,
finding-density, and preflight refinements are presentation and diagnostic
polish rather than release blockers.

## Reproduce

Install the development extras so `pdfplumber` is available, then run:

```powershell
python scripts/stress_test_report_export.py `
  --browser "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

The command writes one PDF per scenario plus `summary.json` to
`tmp/pdfs/report-export-stress/`. A non-zero exit status means at least one
geometry, content, or marker check failed.
