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

Run the smallest relevant tests while iterating, then the full suite:

```bash
python -m pytest tests/test_changed_area.py
python run_tests.py
```

For packaging changes:

```bash
python -m build --wheel
python scripts/verify_wheel.py dist/
```

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
