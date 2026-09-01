# Agent Instructions

## Testing Workflow

- During development and iteration, run `./scripts/test_fast.sh`.
- Before completing a task or creating a commit, run `./scripts/test_full.sh`.
- Run release tests (`python -m pytest -m release -q`) only for packaging,
  dependency, entry-point, installer, wheel, or release-metadata changes.
- For a change confined to one module, first run its directly affected tests,
  for example `python -m pytest tests/test_<module>.py -q`.
- After a failure, rerun only the last failures with `python -m pytest --lf -q`
  instead of immediately repeating the whole suite.
- `python run_tests.py` and an unfiltered `python -m pytest` remain the complete
  release/final safety gate; do not redefine their meaning.
