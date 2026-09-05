# Agent Instructions

## Tiered Testing Workflow

To maximize development velocity and minimize token / execution costs, follow this tiered testing hierarchy (mit realen Richtwerten für die Laufzeit):

### Tier 0: Pure Core Logic (~2.5–3.0s total, <0.5s Testlogik, Zero-Qt / Headless)
- When developing pure services in `core/` (e.g. `snippet_filter`, `loot_filter`, `navigation_state`, `template_engine`, `fuzzy_matcher`, `validators`), run targeted headless tests first without starting any Qt event loop:
  ```bash
  python -m pytest tests/test_snippet_filter.py tests/test_loot_filter.py tests/test_navigation_state.py -q
  ```
  *(Laufzeit: ca. 2.5–3.0s inklusive pytest Discovery)*

### Tier 1: Architecture Boundaries Guard (~2.0–2.5s)
- Whenever modifying module imports, layers, or platform abstractions, verify architectural decoupling:
  ```bash
  python -m pytest tests/test_architecture_boundaries.py -q
  ```
  *(Ensures `core/**` never imports `ui/**` and `core.platform` does not eagerly load PyQt6. Laufzeit: ca. 2.0–2.5s).*

### Tier 2: Directly Affected Module Tests (Aggressive Scoping: ~3–15s)
- **STRICT RULE**: Never escalate to entire test suites if changes are confined to a single component, method, or UI element. Run only the directly mapped test file or scope strictly with `-k`:
  ```bash
  # Scoped execution on specific tests (ca. 3–5s):
  python -m pytest tests/test_report_editor_tab.py -k "<test_name>" -q

  # Single UI/Qt component module (ca. 10–15s):
  python -m pytest tests/test_<module>.py -q
  ```
- After any failure, re-run only failed tests immediately:
  ```bash
  # Re-run only the failed tests (ca. 2–5s):
  python -m pytest --lf -q
  # Or run failed tests first, followed by the rest:
  python -m pytest --ff -q
  ```

### Fast-Track: When to Skip Tier 3 / Tier 4 (~8–10s)
- **Reine Dokumentation, Markdown (`.md`), Grafiken (`.svg`, `.png`) oder Changelog-Updates (Zero-Code Changes)**:
  - **STRIKTES VERBOT von Tests und Lintern!** Überspringe Tier 0 bis Tier 4 sowie `ruff check .` vollständig!
  - Da keinerlei Python-Code oder Importe berührt wurden, haben Testläufe und Linter absolut keinen Mehrwert und verschwenden nur Zeit und Token.
  - Direkt nach den Datei-Edits synchronisieren und an den User zurückmelden.
- **Reine UI-Texte, Lokalisierung (i18n), Docstrings, CSS-Tweaks oder Typo-Fixes**:
  Überspringe Tier 3 und Tier 4 vollständig! Führe nur gezielt aus:
  ```bash
  python -m pytest tests/test_architecture_boundaries.py tests/test_i18n_lint.py -q
  ruff check .
  ```
  *(Laufzeit: ca. 8–10s total; `ruff check .` allein: <1.0s).*
- **Lokale Tier 4 Optionalität**:
  Tier 4 (`./scripts/test_full.sh` / voller Lauf) ist lokal vor Übergabe optional, sofern Tier 0–2, Tier 1 und der Linter grün sind. Die vollständige Test-Matrix wird ohnehin auf GitHub Actions CI ausgeführt.

### Tier 3: Fast Gate Suite (Local Iteration: ~20–30s parallel / ~80–90s seriell)
- During major feature development and broad iteration, run the Fast Gate suite:
  ```bash
  ./scripts/test_fast.sh
  # or with pytest-xdist: python -m pytest -m "not integration and not release" -n auto --dist=loadscope -x --tb=line -q
  # (falls pytest-xdist fehlt / seriell: python -m pytest -m "not integration and not release" -x --tb=line -q -> ca. 80–90s)
  ```

### Tier 4: Full Safety & Release Gate (Task Completion: ~5–5.5 min)
- For broad architectural changes or prior to major releases, run:
  ```bash
  ./scripts/test_full.sh
  # or: python scripts/run_tests.py
  ```
  *(Laufzeit: ca. 5.0–5.5 min für alle Tests inkl. voller Wheel-Packaging- und Qt-Integrationstests).*
- Run release tests (`python -m pytest -m release -q` -> ca. 40–45s) only for packaging, dependency, entry-point, installer, wheel, or release-metadata changes.
- Always run the linter before handing tasks back (ca. 0.8s) – **außer bei reinen Doku-/Asset-Änderungen**:
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
