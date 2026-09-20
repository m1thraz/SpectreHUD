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
- Result: all 5 scenarios passed after the content-preservation and pagination
  polishing changes

The five reports contained 70 pages and 11,019 positioned words in total.
Preflight checked A4 geometry, safe page edges, unexpectedly sparse pages,
main-content height including embedded images, required end markers, and leaked
internal Spectre markers. Every page was also rendered to PNG and visually
reviewed.

| Scenario | Load | Pages | Words | Automated result |
|---|---:|---:|---:|---|
| Dense findings | 18 findings and an 18-row summary matrix | 20 | 2,915 | Pass |
| Large remediation table | 60 multi-line rows | 13 | 2,917 | Pass |
| Oversized evidence | 180 code lines and a 1,600-character token | 13 | 2,156 | Pass |
| Extended attack path | 24 semantic timeline steps and a trailing note | 12 | 1,794 | Pass |
| Long metadata and media | long cover fields, IPv6 scope, and 4 screenshots | 12 | 1,237 | Pass |

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
  images scale within the page and are not cropped. Each screenshot, caption,
  and explanatory note stays together as one figure.
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

### Kept screenshots with their captions and notes

Professional Print now projects block images as semantic `<figure>` elements
with a `<figcaption>`. A directly following explanatory paragraph becomes part
of that caption only in Professional Print; Classic Web retains its independent
paragraph behavior.

The print stylesheet reserves caption space by limiting evidence images to
195 mm. The media stress case consequently fell from 16 to 12 pages without
cropping or isolated caption pages.

### Refined medium-finding density

The finding opener now reserves 56 mm rather than a blanket 75 mm. This keeps
the lead and useful opening context together while allowing the browser to use
safe remaining page space. Recommendation and reference blocks stay intact, and
split findings clone their visual border treatment across page fragments.

The 18-finding scenario fell from 23 to 20 pages. The official sample report
remains eight pages, with all finding headers and closing sections visible.

### Extended preflight beyond word count

Preflight now records embedded image bounds and measures the height occupied by
main content after excluding the running header/footer bands. A low-word page
with less than four percent main-content height is rejected, while a page with a
large evidence image is correctly treated as meaningful content.

Focused tests cover both the formerly missed low-coverage case and an image-heavy
page that must pass.

## Verdict

Professional Print is robust for the normal report workflow and for heavy
findings, tables, code evidence, long metadata, and multi-page attack paths. It
does not clip content in those workloads, and manually added content around
structured attack-path steps is retained. Screenshot grouping, finding density,
and sparse-page diagnostics now also pass their real-browser stress cases. No
remaining correctness or presentation blocker was found in this test matrix.

## Reproduce

Install the development extras so `pdfplumber` is available, then run:

```powershell
python scripts/stress_test_report_export.py `
  --browser "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

The command writes one PDF per scenario plus `summary.json` to
`tmp/pdfs/report-export-stress/`. A non-zero exit status means at least one
geometry, content, or marker check failed.
