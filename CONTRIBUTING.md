# Contributing to SpectreHUD

SpectreHUD is a portfolio project and local desktop tool for authorized security
labs. Focused bug fixes, tests, documentation corrections, and workflow
improvements are welcome. Please keep changes aligned with the product's
single-user desktop scope.

## Before opening a change

1. Search existing issues and pull requests.
2. Use an issue for changes that alter behaviour or require a design decision.
3. Do not publish suspected vulnerabilities in a public issue; follow
   [SECURITY.md](SECURITY.md).
4. Read the [development guide](docs/development.md),
   [architecture guide](docs/architecture.md), and
   [threat model](docs/threat_model.md).

## Development workflow

Create a branch from `main`, keep commits scoped, and avoid unrelated formatting
or generated-file changes. Install the development dependencies and run the
test suite:

```bash
python -m pip install -e ".[dev]"
pytest -q -m "not integration and not release"
```

During development, run affected modules first. Add `pytest -q -m "not release"`
for UI, `MainWindow`, process, locking, or cross-component changes. Before a
larger change is submitted, run the complete `pytest -q` gate. The equivalent
`python run_tests.py` command intentionally runs that same complete suite. See
the [development guide](docs/development.md) for marker ownership and packaging
checks.

Before submitting a pull request:

- Add or update tests for behavioural changes.
- Update English and German locale files together for user-facing text.
- Keep persistence changes atomic and preserve rollback behaviour.
- Verify affected Qt workflows manually on a supported desktop platform.
- Update documentation when architecture, configuration, or exports change.
- Confirm `git diff --check` is clean.

## Pull requests

Describe the user-visible outcome, implementation boundary, verification, and
any manual checks that remain. A pull request should be small enough to review
as one coherent change. Compatibility shims and new abstractions require a
concrete current use case.

By contributing, you agree that your contribution is licensed under the
project's [MIT License](LICENSE).
