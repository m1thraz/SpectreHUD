#!/usr/bin/env python3
"""Exercise a platform plugin bundle through a packaged SpectreHUD executable."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any


SMOKE_FLAG = "--smoke-test-export-plugin"


def _extract_bundle(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination_root):
                raise RuntimeError(f"Unsafe path in plugin bundle: {member.filename}")
        bundle.extractall(destination)


def _plugin_directory(root: Path, plugin_id: str) -> Path:
    matches = []
    for manifest in root.rglob("plugin.json"):
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("plugin_id") == plugin_id:
            matches.append(manifest.parent)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {plugin_id!r} manifest in {root}, found {len(matches)}."
        )
    return matches[0]


def _run_case(
    executable: Path,
    *,
    plugin_root: Path,
    plugin_id: str,
    case_dir: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    output_dir = case_dir / "output"
    result_file = case_dir / "result.json"
    result = subprocess.run(
        [
            str(executable),
            SMOKE_FLAG,
            str(plugin_root),
            plugin_id,
            str(output_dir),
            str(result_file),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if not result_file.is_file():
        raise RuntimeError(
            f"Packaged runtime did not write {result_file}; exit={result.returncode}, "
            f"stderr={result.stderr.strip()!r}."
        )
    return result, json.loads(result_file.read_text(encoding="utf-8"))


def _copy_without_vendor(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("vendor"))


def _corrupt_native_dependency(plugin_dir: Path) -> Path:
    native_candidates = sorted(
        (
            path
            for path in (plugin_dir / "vendor").rglob("*")
            if path.is_file() and path.suffix.casefold() in {".pyd", ".so"}
        ),
        key=lambda path: (not path.name.casefold().startswith("etree"), str(path)),
    )
    if not native_candidates:
        raise RuntimeError("Plugin bundle does not contain a native dependency to corrupt.")
    native_candidates[0].write_bytes(b"not-a-compatible-native-library\n")
    return native_candidates[0]


def smoke_test_bundle(
    *,
    executable: Path,
    bundle: Path,
    work_dir: Path,
    plugin_id: str = "spectrehud.docx",
) -> None:
    if work_dir.exists():
        raise RuntimeError(f"Smoke-test work directory already exists: {work_dir}")
    work_dir.mkdir(parents=True)

    valid_root = work_dir / "valid" / "plugins"
    _extract_bundle(bundle, valid_root)
    valid_plugin = _plugin_directory(valid_root, plugin_id)
    valid_process, valid_payload = _run_case(
        executable,
        plugin_root=valid_root,
        plugin_id=plugin_id,
        case_dir=work_dir / "valid",
    )
    if valid_process.returncode != 0 or valid_payload.get("export_status") != "success":
        raise RuntimeError(f"Valid plugin bundle failed: {valid_payload}")
    artifacts = [Path(value) for value in valid_payload.get("artifacts", [])]
    if not artifacts or not all(path.is_file() for path in artifacts):
        raise RuntimeError(f"Valid plugin smoke test produced no artifacts: {valid_payload}")

    missing_root = work_dir / "missing-dependency" / "plugins"
    missing_plugin = missing_root / valid_plugin.name
    _copy_without_vendor(valid_plugin, missing_plugin)
    missing_process, missing_payload = _run_case(
        executable,
        plugin_root=missing_root,
        plugin_id=plugin_id,
        case_dir=work_dir / "missing-dependency",
    )
    if (
        missing_process.returncode == 0
        or missing_payload.get("availability") != "missing_dependency"
    ):
        raise RuntimeError(f"Missing dependency was not contained: {missing_payload}")

    incompatible_root = work_dir / "incompatible-dependency" / "plugins"
    incompatible_plugin = incompatible_root / valid_plugin.name
    shutil.copytree(valid_plugin, incompatible_plugin)
    corrupted = _corrupt_native_dependency(incompatible_plugin)
    incompatible_process, incompatible_payload = _run_case(
        executable,
        plugin_root=incompatible_root,
        plugin_id=plugin_id,
        case_dir=work_dir / "incompatible-dependency",
    )
    if (
        incompatible_process.returncode == 0
        or incompatible_payload.get("availability") != "load_failed"
    ):
        raise RuntimeError(
            f"Incompatible native dependency was not contained: {incompatible_payload}"
        )

    print(f"valid export: {artifacts[0]}")
    print(f"missing dependency: {missing_payload['availability']}")
    print(f"incompatible dependency: {incompatible_payload['availability']} ({corrupted.name})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--plugin-id", default="spectrehud.docx")
    args = parser.parse_args()
    smoke_test_bundle(
        executable=args.executable.resolve(),
        bundle=args.bundle.resolve(),
        work_dir=args.work_dir.resolve(),
        plugin_id=args.plugin_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
