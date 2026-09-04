# Agent Instructions

## Tiered Testing Workflow

To maximize development velocity and minimize token / execution costs, follow this tiered testing hierarchy:

### Tier 0: Pure Core Logic (<0.5s, Zero-Qt / Headless)
- When developing pure services in `core/` (e.g. `snippet_filter`, `loot_filter`, `navigation_state`, `template_engine`, `fuzzy_matcher`, `validators`), run targeted headless tests first without starting any Qt event loop:
  ```bash
  python -m pytest tests/test_snippet_filter.py tests/test_loot_filter.py tests/test_navigation_state.py -q
  ```

### Tier 1: Architecture Boundaries Guard
- Whenever modifying module imports, layers, or platform abstractions, verify architectural decoupling:
  ```bash
  python -m pytest tests/test_architecture_boundaries.py -q
  ```
  *(Ensures `core/**` never imports `ui/**` and `core.platform` does not eagerly load PyQt6).*

### Tier 2: Directly Affected Module Tests (Aggressive Scoping)
- **STRICT RULE**: Never escalate to entire test suites if changes are confined to a single component, method, or UI element. Run only the directly mapped test file or scope strictly with `-k`:
  ```bash
  python -m pytest tests/test_<module>.py -q
  # Scoped execution on specific tests:
  python -m pytest tests/test_report_editor_tab.py -k "<test_name>" -q
  ```
- After any failure, re-run only failed tests immediately:
  ```bash
  # Re-run only the failed tests:
  python -m pytest --lf -q
  # Or run failed tests first, followed by the rest:
  python -m pytest --ff -q
  ```

### Fast-Track: When to Skip Tier 3 / Tier 4
- **Reine UI-Texte, Lokalisierung (i18n), Docstrings, CSS-Tweaks oder Typo-Fixes**:
  Überspringe Tier 3 und Tier 4 vollständig! Führe nur gezielt aus:
  ```bash
  python -m pytest tests/test_architecture_boundaries.py tests/test_i18n_lint.py -q
  ruff check .
  ```
- **Lokale Tier 4 Optionalität**:
  Tier 4 (`./scripts/test_full.sh` / voller Lauf) ist lokal vor Übergabe optional, sofern Tier 0–2, Tier 1 und der Linter grün sind. Die vollständige Test-Matrix wird ohnehin auf GitHub Actions CI ausgeführt.

### Tier 3: Fast Gate Suite (Local Iteration)
- During major feature development and broad iteration, run the Fast Gate suite:
  ```bash
  ./scripts/test_fast.sh
  # or: python -m pytest -m "not integration and not release" -n auto --dist=loadscope -x --tb=line -q
  # (falls pytest-xdist fehlt: python -m pytest -m "not integration and not release" -x --tb=line -q)
  ```

### Tier 4: Full Safety & Release Gate (Task Completion)
- For broad architectural changes or prior to major releases, run:
  ```bash
  ./scripts/test_full.sh
  # or: python scripts/run_tests.py
  ```
- Run release tests (`python -m pytest -m release -q`) only for packaging, dependency, entry-point, installer, wheel, or release-metadata changes.
- Always run the linter before handing tasks back:
  ```bash
  ruff check .
  ```

---

## Testing Principles & Constraints

### Parallelization & Worker Isolation
- `scripts/test_fast.sh` and `scripts/test_full.sh` run in parallel by default with `pytest-xdist` and `--dist=loadscope`.
- If a test appears flaky or order-dependent, reproduce the individual test serially with `-n0` before attributing the failure to application code.

### Pure Core Isolation (Zero-Qt)
- All services in `core/` must remain pure Python and headless. Never introduce `PyQt6`, `QApplication`, or UI widget imports into `core/`.

### Commit Policy
- **Never create Git commits.** Only the user commits changes after reviewing and accepting completed work.

---

## Test Output Discipline

- Redirect suite output to a temporary log instead of returning the live, unabridged stream.
- For a successful run, report only its final result line and elapsed time.
- For a failed run, return only the `FAILURES` section or the final 30–50 log lines containing the actionable traceback.
- Diagnose a failure by rerunning the single affected test with `-v`; do not immediately repeat an entire suite.
- Keep `--tb=line` for the Fast loop and `--tb=short` for the task-completion suite and CI.
