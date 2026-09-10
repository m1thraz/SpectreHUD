# SpectreHUD v2.0.3 – Release Notes

SpectreHUD v2.0.3 is a maintenance release focused on appearance consistency
and faster, more predictable development verification. It preserves the v2.0.x
project, registry, template, and Pentest Mode formats.

## Highlights

### HUD and Report Editor appearance

- Restored the transparent `MainScrollArea` rendering used by the established
  HUD glass design without reintroducing per-widget stylesheets.
- Added independent live transparency controls for the HUD and Report Editor
  under Appearance settings.
- The HUD defaults to 5% transparency to retain the existing glass appearance;
  the Report Editor remains opaque by default.
- Application styling now applies the two opacity settings through the shared
  theme path at startup and after settings changes.
- Theme-derived tooltip colors keep popup labels readable inside locally styled
  scroll areas.

### Test workflow and maintenance

- Split the largest test modules by responsibility while preserving the full
  386-test collection.
- Classified Fast, Integration, and Release tests so normal development loops
  avoid packaging work without weakening the final gate.
- Added `scripts/test_fast.sh` and `scripts/test_full.sh` with concise output,
  active-venv guards, and `pytest-xdist --dist=loadscope` execution.
- Kept release tests in the packaging/release path and out of the ordinary
  operating-system/Python CI matrix.
- Documented test isolation, output discipline, and serial `-n0` diagnosis for
  suspected flaky or order-dependent tests.
- On the recorded Windows baseline, the non-release suite decreased from
  290.236 seconds serially to 39.139 seconds in parallel with identical test
  outcomes. Local timings are diagnostic observations, not CI guarantees.

## Compatibility and upgrade

- Python 3.10 through 3.13
- Windows and Linux
- No project-state, registry, report-template, custom-theme, or Pentest Mode
  migration is required from v2.0.0 through v2.0.2.

Close a running SpectreHUD instance before replacing the executable. Existing
projects, report templates, and custom themes can be reused without conversion.

For the complete change history, see the repository [changelog](../CHANGELOG.md).
The test timing and isolation record is available in
[`performance_baseline.md`](testing/performance_baseline.md).
