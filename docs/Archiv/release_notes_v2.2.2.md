# SpectreHUD v2.2.2 – Release Notes

SpectreHUD v2.2.2 turns Professional Print into a more predictable, polished
report-delivery workflow. The release adds semantic pagination, a clearer attack-path
presentation, consistent risk labeling, and a reproducible example and stress-test process.

---

## Highlights

### Semantic Professional Print Pagination

- **Content-Aware Page Planning:** Professional Print now places page breaks at safe semantic
  boundaries instead of relying only on browser pagination.
- **Stable Report Sections:** Section headings, finding leads, attack-path steps, tables, code
  blocks, blockquotes, and screenshots carry dedicated print behavior.
- **Better Page Use:** Medium-sized findings can use remaining page space without stranding their
  opening context, while recommendation and reference blocks remain intact.
- **Evidence Grouping:** Screenshots stay with their captions and directly associated explanatory
  notes whenever they fit on one page.

### Visual Attack-Path Timeline

- **Print-Safe Timeline:** Structured attack paths render as a compact vertical sequence with
  phase, description, and linked finding context.
- **Complete Narrative Preservation:** Manually written text between or after structured steps is
  retained in the exported report.

### Consistent Findings Presentation

- **Unified Severity Badges:** Findings matrices, individual finding headers, executive summaries,
  and remediation tables use the same severity colors and typography.
- **Readable Summary Totals:** Compact severity totals now match their badges without oversized,
  visually noisy counts.
- **Full Phase Names:** Internal phase identifiers such as `privesc` and `postex` are expanded to
  their localized display names in exported executive-summary tables.

### Reproducible Example Report

- **Synthetic Demonstration:** The repository includes an obviously fictional Professional Print
  report, source Markdown, and README preview.
- **Repeatable Generation:** A dedicated script regenerates the example through the production
  export path so future layout changes can be reviewed against a stable reference.

---

## Export Reliability & Verification

- Added a deterministic five-scenario stress harness covering dense findings, large remediation
  tables, oversized evidence, extended attack paths, and long metadata with media.
- Extended PDF preflight beyond word counts to inspect positioned content coverage and image bounds,
  catching nearly empty pages without rejecting legitimate image-heavy pages.
- The final stress matrix passes all five scenarios across 70 rendered pages and 11,019 positioned
  words; the maintained example report remains stable at eight pages.
- Interactive and classic HTML exports retain their existing editing and layout behavior; the new
  evidence grouping and pagination rules are scoped to Professional Print.

## Compatibility

- Existing report Markdown and project data require no migration.
- Existing manual page breaks remain supported and are anchored at clean section boundaries.
- The export pipeline remains headless in `core/` and does not add Qt dependencies.
