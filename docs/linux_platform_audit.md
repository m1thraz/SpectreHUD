# Linux Platform Audit

**Status:** Phases 0-8 implemented; Linux CI confirmation pending; Phase 9 next

**Verified:** 2026-09-01 against v2.0.3 development state

This document records existing operating-system boundaries before Linux support
is refactored. It is an inventory, not a claim that every listed feature is
already supported.

## Classification summary

| Area | Classification | Current boundary and evidence |
| --- | --- | --- |
| Clipboard | Platform-neutral through Qt; Wayland smoke test pending | `core/clipboard_watcher.py` uses `QApplication.clipboard()` and contains no OS branch. |
| Atomic writes | Platform-dependent, already locally encapsulated | `core/atomic_write.py` limits its POSIX-specific `chmod` behavior to `_secure_chmod`; `fsync` and `os.replace` are shared. |
| Display geometry | Platform-neutral pure logic | `core/display_geometry.py` computes virtual desktop bounds independently of the OS. |
| Single-instance lock | Platform-neutral Qt boundary | `core/single_instance.py` uses `QLockFile`, but inherits the legacy config-directory choice. |
| External URL opening | Platform-neutral where Qt is already used | Settings theme folder, HTML output, and Obsidian URIs use `QDesktopServices`. Failure handling is inconsistent. |
| Local file/folder opening | Platform-dependent and duplicated | The same Windows/macOS/`xdg-open` branch occurs in `core/project/repository.py`, `ui/controllers/project_controller.py`, and `ui/loot_card.py`. |
| Config/data/cache paths | Platform-dependent and duplicated | Config, projects, logging, themes, and Settings defaults derive paths independently. No cache API exists. |
| Network detection | Platform-dependent and incorrectly grouped | `core/net_detector.py` separates Windows but treats Linux and macOS as one `ip`-command platform and checks only `tun0`, `wg0`, and `tap0`. |
| Screenshots | Qt implementation; Linux/X11 plausible; Wayland-problematic | `core/screenshot_manager.py` directly uses `QScreen.grabWindow(0)` and recognizes null pixmaps, but exposes no session capability or user-facing unavailable state. |
| Global hotkeys | Backend isolated, capability missing; Wayland-problematic | `core/hotkey_listener.py` imports `pynput` lazily and catches startup errors, so the app can continue, but it provides no `is_available()` state to UI. |
| Local shortcuts | Platform-neutral Qt | `MainWindow` and report editor shortcuts use `QShortcut` and do not depend on `pynput`. |
| Desktop shortcut | Windows-only and mostly isolated | `create_desktop_shortcut.py` invokes PowerShell and assumes Desktop/OneDrive Desktop. It is nevertheless included in the cross-platform wheel. |
| Standalone packaging | Windows-only | `scripts/build_exe.py` and `SpectreHUD.spec` include Win32 `pynput` backends. |
| Test CI | Windows and Linux source tests | `.github/workflows/ci.yml` runs Python 3.10-3.13 on both OS families and Xvfb coverage on Linux 3.11. |
| Package CI | Windows-only | The wheel is built, installed into a fresh environment, and CLI-smoked only in the Windows package job. |

## Detailed inventory

### Paths and persisted data

- `core/config.py::get_default_config_dir()` uses `SPECTRE_CONFIG_DIR`, otherwise
  `~/.ctf_cheatsheet_widget`.
- `core/project/repository.py` duplicates the config fallback and separately
  chooses `SPECTRE_PROJECTS_DIR` or `~/spectre_projects`.
- `core/logger.py` duplicates the legacy config-directory fallback for logs.
- `core/theme_loader.py` uses `~/.config/spectrehud/themes`, ignoring
  `SPECTRE_CONFIG_DIR` and Windows standard application-data locations.
- `ui/settings_dialog.py` independently falls back to `~/spectre_projects` for
  the workspace field.
- `DEFAULT_CONFIG["workspace_dir"]` is evaluated from `Path.home()` at import
  time. Tests normally avoid real-home writes through `SPECTRE_CONFIG_DIR`,
  `SPECTRE_PROJECTS_DIR`, temporary directories, or in-memory storage.
- No central `data_dir()` or `cache_dir()` exists, and no XDG environment
  variable is currently read.

Persistent user data can therefore exist under the legacy
`~/.ctf_cheatsheet_widget` and `~/spectre_projects` locations. Phase 2 must not
delete or silently move either tree. The migration/read-fallback decision must
be explicit and tested before defaults change.

### Opening files, directories, and URLs

Duplicated OS branches:

- `core/project/repository.py::open_project_folder()`
- `ui/controllers/project_controller.py` after project creation/import
- `ui/loot_card.py` for screenshot images

Each uses `os.startfile()` on Windows, `open` on macOS, and `xdg-open` elsewhere.
The last branch silently assumes every non-Windows/non-macOS system provides
`xdg-open`.

Existing Qt paths:

- `ui/settings_dialog.py` opens the theme directory with `QDesktopServices`.
- `ui/report_editor_tab.py` opens generated HTML with `QDesktopServices`.
- `ui/coordinators/export_coordinator.py` opens Obsidian URIs with
  `QDesktopServices` and checks its boolean result.

The future platform opener should own only the operation and result. UI callers
remain responsible for localized error messages.

### Network detection

`core/net_detector.py` is the only network-interface detector. Current behavior:

1. Windows parses localized English/German `ipconfig` output.
2. Linux and macOS both invoke Linux `ip -4 addr show`.
3. Only `tun0`, `wg0`, and `tap0` are queried.
4. Socket hostname and outbound-route probes act as generic fallbacks.

This is Linux-specific behavior presented as generic Unix support. There are no
focused tests for command output, candidate prioritization, missing `ip`, broken
JSON/text, multiple VPN interfaces, or loopback-only output.

### Desktop capabilities

#### Global hotkeys

`HotkeyListener.start()` catches `ImportError`, `ValueError`, `OSError`, and
`RuntimeError`, logs the failure, and leaves `_running` false. This already
prevents most missing-X11 backend failures from aborting startup. However:

- no public availability/capability result exists;
- Settings cannot distinguish configured from operational;
- Wayland is not detected;
- tests replace `pynput` modules and therefore do not demonstrate a real Linux
  global hook.

#### Screen capture

`ScreenshotManager` handles missing screens, exceptions, and null pixmaps and
restores the HUD on failed capture. It has no platform/session preflight, and a
Wayland-restricted null capture currently produces only a log entry rather than
a specific feature-unavailable result for the UI.

#### Clipboard

Clipboard monitoring is fully routed through Qt and is opt-in/paused by default.
No direct X11 API exists. CI exercises mocked/offscreen behavior; real X11 and
Wayland clipboard smoke results are not yet recorded.

### Packaging and CI

- The normal matrix runs non-release tests on Ubuntu and Windows for Python
  3.10-3.13. Ubuntu installs X11/Qt libraries; Python 3.11 runs under Xvfb with
  coverage.
- The package job is Windows-only. It builds and inspects the wheel, installs it
  into a fresh venv, checks `spectrehud --version` and `--help`, builds the EXE,
  and smoke-tests it.
- The release workflow is Windows-only and publishes the Windows executable plus
  wheel.
- The wheel manifest intentionally includes the Windows-only desktop-shortcut
  helper. No Linux `.desktop` file or freedesktop icon installation exists.
- README labels Windows and Linux as supported and already notes Wayland limits,
  but the feature-level support matrix is not backed by recorded X11/Wayland
  manual smoke evidence.

### Tests with platform assumptions or missing coverage

- `tests/test_hotkeys.py` deliberately fakes `pynput` to avoid an X connection;
  it validates listener behavior, not backend availability.
- Screenshot tests use Qt offscreen images and mocked screens/windows; they do
  not validate X11 or Wayland capture capability.
- `tests/test_atomic_write.py` conditionally asserts POSIX `0600` permissions;
  focused Linux failure tests for read-only directories and failed replace are
  still missing.
- `tests/test_single_instance.py` exercises real subprocess locking and contains
  a Windows timing accommodation, but uses temporary paths and Qt's portable
  lock implementation.
- `tests/test_packaging_integration.py` checks wheel content, while fresh wheel
  installation/entry-point execution remains a Windows CI responsibility.
- Path tests do not currently model Windows standard paths, XDG variables, or
  Linux fallbacks independently of the developer's home directory.

## Boundary decision for Phase 1

Introduce only responsibilities that the inventory justifies:

```text
core/platform/
├── __init__.py
├── capabilities.py   # OS/session facts; no Qt/UI dependency
├── paths.py          # config/data/cache/project defaults and legacy locations
├── network.py        # platform-specific interface acquisition + pure ranking
└── opener.py         # one Qt local-path open operation with explicit result
```

The exact module set may be introduced incrementally. `core/platform/*` must not
import `ui.*`; an AST boundary test should enforce this. Clipboard and atomic
writes remain in their existing modules because they are already cohesive.

## Phase-0 conclusion

The first implementation checkpoint should proceed in this order:

1. capability/session facts and architecture boundary;
2. one path source with legacy-data compatibility;
3. one Qt-based local-path opener;
4. Linux JSON network discovery and pure interface ranking;
5. Fast Gate on Windows and Linux CI before packaging changes.

No production behavior was changed during this audit.

## Implementation status

### Phase 1 - platform boundary

- `core/platform/capabilities.py` now provides UI-free OS/session capability
  detection for Windows, Linux/X11, Linux/Wayland, and headless sessions.
- `tests/test_architecture_boundaries.py` prevents `core/platform/*` from
  importing `ui.*`.
- Capability detection is covered through injected environment and platform
  values; it does not depend on the CI runner's real display session.

### Phase 2 - paths and legacy data

- `core/platform/paths.py` is the single source for config, data, cache,
  workspace, and user-theme paths.
- Linux honors `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_CACHE_HOME`, with
  the standard home-directory fallbacks when those variables are unset.
- Windows uses roaming AppData for configuration and local AppData for mutable
  data/cache. Existing `SPECTRE_*_DIR` overrides remain authoritative.
- A populated legacy `~/.ctf_cheatsheet_widget` configuration remains in use
  when the new standard config directory is empty. No files are copied,
  deleted, or silently migrated.
- The established user-visible `~/spectre_projects` workspace default is
  intentionally preserved. Existing custom-theme storage is also detected so
  the platform-path change does not make installed themes disappear.

### Phase 3 - opening local files and directories

- `core/platform/opener.py::open_path()` now routes existing local files and
  directories through `QDesktopServices` and returns an explicit boolean.
- Project folders, archived-project destinations, loot screenshots, exported
  HTML reports, and the custom-theme directory use this shared operation.
- Missing paths and desktop-service failures return `False`; UI callers provide
  localized feedback where they own the interaction.
- The duplicated `os.startfile` / `open` / `xdg-open` branches have been
  removed. URI-based Obsidian opening remains separate because it is not a
  local-path operation.

### Phase 4 - Linux network discovery

- Linux and macOS now follow separate branches. macOS intentionally uses the
  generic socket fallbacks instead of invoking Linux's `ip` command.
- Linux invokes `ip -j -4 addr` once and parses its JSON output without shell
  pipelines or assumptions about exactly three interface names.
- A pure selector ignores loopback/link-local addresses, prefers `tun*`,
  `tap*`, `wg*`, and `tailscale*`, and still accepts suitable addresses from
  ordinary interfaces when no VPN-style interface exists.
- Missing commands, command failures, empty output, malformed JSON, and
  loopback-only results degrade to the existing generic detection fallbacks.

### Checkpoint 1

- Focused platform, architecture, network, and UI integration tests pass on the
  Windows development host.
- The Fast Gate and complete non-release gate both finish successfully.
- Linux behavior is covered with injected platform values and synthetic
  `ip -j` output. Confirmation on a real Linux runner remains the next CI step.

### Phase 5 - Linux wheel validation

- CI now has a dedicated Ubuntu/Python 3.11 package job in addition to the
  existing Windows package and executable gate.
- The Linux job builds and inspects the wheel, installs that artifact into a
  fresh venv, changes out of the repository checkout, and executes
  `spectrehud --version` plus `spectrehud --help` from the installed entry point.
- Release-marked tests remain owned by the Windows package job, so adding the
  Linux installation gate does not duplicate or remove release-test coverage.
- No AppImage, Flatpak, or other standalone Linux artifact is introduced in
  this phase.

### Phase 6 - screenshot capture capabilities

- `core/platform/capabilities.py` now includes `ScreenCaptureStatus` (`AVAILABLE`,
  `LIMITED`, `UNAVAILABLE`) and exposes `screen_capture_status` as well as
  `is_screen_capture_available()`.
- `core/screenshot_manager.py` accepts optional `PlatformCapabilities` (defaulting
  to `detect_platform_capabilities()`).
- `start_capture()` checks capability availability upfront. When capture is
  restricted or unavailable (such as in a Wayland session), it logs a warning
  and returns `False` immediately without hiding the parent window or scheduling
  overlays.
- `ui/app_controller.py::trigger_screenshot()` provides informative, localized user
  feedback and warning logs on restricted sessions instead of causing unhandled
  exceptions or null-pixmap failures.
- Translations for unavailable screen capture states are available in English and
  German.

### Phase 7 - global hotkeys and session resilience

- `core/hotkey_listener.py` accepts optional `PlatformCapabilities` and exposes
  `is_available()` and `is_running()` states.
- When global system hotkeys are unavailable (such as under Wayland), `start()`
  degrades gracefully: it logs a warning, remains inactive, and returns `False`
  without invoking `pynput` or interrupting application startup.
- Runtime initialization failures in the underlying `pynput` backend (such as
  missing or disconnected X11 display hooks) are caught, setting `_available = False`
  and allowing the application to proceed with in-app shortcuts.
- In-app `QShortcut` instances in `MainWindow` (Esc, Ctrl+F, Ctrl+N, Ctrl+P,
  Ctrl+S, Ctrl+1..4, Tab, etc.) remain completely independent from `pynput` and
  functional across all desktop environments.
- `ui/settings_dialog.py::HotkeySettingsPage` dynamically renders a prominent,
  localized information notice when global shortcuts are unavailable in the
  current desktop session.

### Checkpoint 2

- Focused unit and integration test suites (`test_platform_capabilities.py`,
  `test_screenshot_manager.py`, `test_hotkeys.py`, `test_settings_dialog.py`) pass
  deterministically on both supported and simulated Wayland environments.
- Full Fast Gate suite passes with zero errors and no regression in Windows or
  existing feature workflows.
- Application starts cleanly and degrades features predictably when global system
  hooks or desktop grabs are restricted by the OS session.

### Phase 8 - POSIX filesystem semantics and adversarial validation

- Added dedicated adversarial filesystem test suite `tests/test_linux_filesystem_adversarial.py`
  validating POSIX-specific behaviors across Tickets 25-28.
- **Case Sensitivity (Ticket 25)**: Explicit casing verification for files (`report.md`,
  `Report.md`, `REPORT.md`) and project names to guarantee that POSIX distinct filenames are
  not conflated.
- **Permission Failures (Ticket 26)**: Validated fail-closed handling on read-only files,
  read-only workspace directories, and unwritable backup targets. `ReportFileManager.save()`
  and `backup()` fail gracefully without leaving orphaned temporary files, and
  `validate_workspace_directory()` rejects non-writable locations upfront via write probing.
- **Symlink Handling (Ticket 27)**: Validated proper path resolution through valid symlinks and
  predictable handling of broken/dangling symlinks without hangs or crashes.
- **Atomic Write Durability under POSIX (Ticket 28)**: Validated `atomic_write_text`,
  `atomic_write_bytes`, and `atomic_write_json` on POSIX (`0o600` permission enforcement via
  `_secure_chmod`, `fsync` flushing, and transactional cleanup of temporary `.tmp_*` files
  when writes or replacements encounter I/O or permission errors).
