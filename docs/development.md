# Contributor Development Guide

This guide is the shortest route from a fresh checkout to a reviewable
SpectreHUD change. Read [architecture.md](architecture.md) for the full component
map and [threat_model.md](threat_model.md) before changing validation or
adversarial tests.

## Local setup

SpectreHUD supports Python 3.10 through 3.13 on Windows and Linux.

```bash
python -m venv .venv
```

Activate the virtual environment using the command appropriate for your shell,
then install and test the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python run_tests.py
```

Alternatively, invoke the virtual environment's Python executable directly. Qt
tests use the offscreen platform in automation. Features involving global
hotkeys, the tray, window geometry, screenshots, and native file dialogs still
require a manual desktop smoke test.

## Where changes belong

- `core/`: domain services, persistence, validation, reporting, and exporters.
- `core/project/`: project registry, state storage, repository, and manager.
- `ui/controllers/`: domain-facing UI actions and rendering adapters.
- `ui/coordinators/`: application workflows spanning multiple controllers or
  services.
- `ui/panels/` and `ui/report/`: reusable Qt composition components.
- `data/i18n/`: English and German translation dictionaries.
- `tests/`: unit, workflow-invariant, UI smoke, and packaging tests.
- `docs/`: technical reference, explicit product boundaries, and export guides.

Use existing modules before creating a new abstraction. Keep Qt widgets out of
`core/`, and keep persistence ownership in domain services rather than view
components.

## Verification sequence

The suite has three intentional execution levels. During implementation, start
with only the directly affected test modules. After the change stabilizes, run
the Fast Suite. For UI, `MainWindow`, process, locking, or cross-component
changes, also run the suite including integration tests. Before completing a
larger task, run the complete suite once:

```bash
# Targeted development loop
pytest -q tests/test_changed_area.py

# Fast development check
pytest -q -m "not integration and not release"

# Fast and integration tests; excludes distribution builds
pytest -q -m "not release"

# Complete final gate, including release tests
pytest -q
```

Tests marked `integration` cross a component, Qt-window, subprocess, or operating
system boundary. Tests marked `release` build or inspect distribution artifacts.
Markers classify execution cost; an unfiltered pytest run still executes every
test. The default pytest output is compact, while failures retain short
tracebacks and their exact test IDs. `python run_tests.py` intentionally remains
an alias for the complete, unfiltered final gate.

The workflow-invariant modules, `test_smoke.py`, and Cheatsheet geometry are
integration suites because their assertions depend on a composed `MainWindow`.
The focused UI, container, i18n, adversarial, report, and single-instance
modules mark only individual window, popup, workflow, or subprocess tests;
their isolated service/widget tests remain in the Fast Suite.

For packaging, dependency, entry-point, or release-metadata changes, also run:

```bash
python -m pytest -m release
python -m pip wheel . --no-deps --no-build-isolation -w dist/
python scripts/verify_wheel.py dist/
```

Do not introduce parallel execution until Qt state, environment variables,
filesystem fixtures, application locks, and subprocess tests have demonstrated
worker-level isolation.

CI validates Python 3.10–3.13 on Windows and Linux, performs coverage on Linux,
and builds and smoke-tests the Windows wheel and executable.

## Project-specific review points

- Persistence must complete before in-memory state is committed.
- Rollback paths must restore runtime and persisted configuration consistently.
- One state mutation should publish one domain event with a stable payload.
- New user-facing strings require matching `en.json` and `de.json` keys.
- Exported HTML is a recipient-facing trust boundary; ordinary local Qt text is
  not treated as a hostile multi-tenant surface.
- Preserve the single-instance product invariant.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for submission expectations and
[SECURITY.md](../SECURITY.md) for private disclosure.
