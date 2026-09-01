#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "${BASH_SOURCE[0]%/*}" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

if [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
    python_cmd="$repo_root/.venv/Scripts/python.exe"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
    python_cmd="$repo_root/.venv/bin/python"
else
    python_cmd="python"
fi

"$python_cmd" -m pytest -m "not release" --tb=short -q
