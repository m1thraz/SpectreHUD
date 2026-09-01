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

### Test Output Discipline

- Redirect suite output to a temporary log instead of returning the live,
  unabridged stream.
- For a successful run, report only its final result line and elapsed time.
- For a failed run, return only the `FAILURES` section or the final 30-50 log
  lines that contain the actionable traceback.
- Diagnose a failure by rerunning the single affected test with `-v`; do not
  immediately repeat an entire suite.
- Keep `--tb=line` for the Fast loop and `--tb=short` for the task-completion
  suite and CI.
