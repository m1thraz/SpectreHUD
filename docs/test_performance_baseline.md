# Test Performance Baseline

This file records wall-clock measurements used to decide whether test-suite
parallelization is worth evaluating. Times are local observations, not CI
performance guarantees.

## 2026-09-01 — Phase 0 Go/No-Go

- Environment: Windows, Git Bash, project virtual environment
- Command: `time ./scripts/test_fast.sh`
  - Exit status: `0`
  - Wall-clock time: `23.335 s`
- Command: `time ./scripts/test_full.sh`
  - Exit status: `0`
  - Wall-clock time: `197.063 s` (`3m17.063s`)

The first attempt from the canonical Git checkout was discarded because that
checkout had no local `.venv`; the script consequently selected an unrelated
system Python 3.13 installation, which crashed in a Qt test. The recorded runs
used the project's existing virtual environment and the same source revision.

Decision rule: stop when the full run is below 30 seconds; otherwise continue
to Phase 1.

**Decision: GO — continue to Phase 1.** The measured full run is above the
30-second threshold.
