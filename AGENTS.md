# Agent Instructions

## Testing Workflow

- During development and iteration, run `./scripts/test_fast.sh`.
- Before handing a completed task back for user acceptance, run
  `./scripts/test_full.sh`.
- Never create Git commits. Only the user commits changes after reviewing and
  accepting the completed work.
- Run release tests (`python -m pytest -m release -q`) only for packaging,
  dependency, entry-point, installer, wheel, or release-metadata changes.
- For a change confined to one module, first run its directly affected tests,
  for example `python -m pytest tests/test_<module>.py -q`.
- After a failure, rerun only the last failures with `python -m pytest --lf -q`
  instead of immediately repeating the whole suite.
- `python run_tests.py` and an unfiltered `python -m pytest` remain the complete
  release/final safety gate; do not redefine their meaning.

### Parallelization

- `scripts/test_fast.sh` and `scripts/test_full.sh` run in parallel by default
  with `pytest-xdist` and `--dist=loadscope`.
- If a test appears flaky or order-dependent, reproduce the individual test
  serially with `-n0` before attributing the failure to application code.

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
