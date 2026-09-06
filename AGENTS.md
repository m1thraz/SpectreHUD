# Agent Instructions

## Testing

Use the smallest test scope that can validate the change.

### Tier 0 — Pure Core (~2.5–3.0s total, <0.5s test logic)

For isolated pure-Python `core/` logic, run only directly relevant headless tests.

```bash
python -m pytest tests/test_<module>.py -q
```

### Tier 1 — Architecture (~2.0–2.5s)

Run after import, layering, dependency, or platform-abstraction changes:

```bash
python -m pytest tests/test_architecture_boundaries.py -q
```

Guards: `core/**` must not import `ui/**` or eagerly load PyQt6.

### Tier 2 — Affected Tests (~3–15s)

For local changes, run only the directly affected test or module.

```bash
python -m pytest tests/test_<module>.py -k "<test_name>" -q
python -m pytest tests/test_<module>.py -q
```

Do not escalate while the change remains isolated.

After failures:

```bash
python -m pytest --lf -q
```

Typical rerun: ~2–5s.

### Tier 3 — Fast Gate

~20–30s parallel / ~80–90s serial.

For broad changes or cross-component development:

```bash
./scripts/test_fast.sh
```

Fallback:

```bash
python -m pytest -m "not integration and not release" -x --tb=line -q
```

### Tier 4 — Full Gate (~5.0–5.5 min)

For broad architectural changes or major release validation:

```bash
./scripts/test_full.sh
```

or:

```bash
python scripts/run_tests.py
```

Release tests (~40–45s) only for packaging, dependencies, entry points, installers, wheels, or release metadata:

```bash
python -m pytest -m release -q
```

Tier 4 is optional for normal local handover when targeted tests and lint pass; CI runs the full matrix.

### Fast-Track

* Pure docs/assets (`.md`, `.svg`, `.png`, changelog): **no tests or linters**.
* UI text, i18n, docstrings, CSS, typos: skip Tier 3/4; run only relevant targeted checks plus:

  ```bash
  ruff check .
  ```

  Typical total: ~8–10s.
* `ruff check .` alone: <1s.
* Always lint before handover unless only docs/assets changed.

---

## Rules

### Comments

* Prefer WHY over WHAT.
* Comment only non-obvious invariants, constraints, failure semantics, ownership/security boundaries, ordering, lifecycle, platform quirks, or intentional oddities.
* Do not restate code, names, types, or obvious control flow.
* Do not optimize docstring coverage; trivial WHAT-docstrings are token tax.

### Core Isolation

`core/` must remain pure Python and headless. Never introduce PyQt6, `QApplication`, or UI-widget imports.

### Parallel Tests

Fast/full suites use `pytest-xdist --dist=loadscope`.

If a test appears flaky or order-dependent, reproduce it serially with `-n0` before blaming application code.

### Commits

**Never create Git commits.** The user commits only after review.

---

## Test Output

* Redirect suite output to a temporary log.
* Success: report only final result and elapsed time.
* Failure: report only the actionable traceback / final 30–50 lines.
* Diagnose by rerunning the single failing test with `-v`, not the full suite.
* Use `--tb=line` for fast iteration and `--tb=short` for completion/CI.
