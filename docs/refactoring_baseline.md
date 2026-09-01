# Refactoring Baseline

Last verified: 2026-09-01, before the targeted architecture refactoring.

## Phase 0: AppController test coupling

The baseline distinguishes explicit references to `AppController` from
integration tests that construct it indirectly through `MainWindow`.

```text
AppController test coupling:
- direct AppController construction: 0 sites
- unbound method calls: 9 sites in 9 tests
- SimpleNamespace controller doubles: 5 construction sites
- MethodType harness bindings: 2 sites used by 6 tests
- explicit integration-level AppController references: 0
- indirect integration through MainWindow: 26 construction sites
  (23 test bodies, 1 fixture, 2 setUp methods)
```

### Explicit responsibility coupling

| Responsibility | Test file | Coupled tests / sites |
| --- | --- | ---: |
| Runtime settings application | `tests/test_fonts.py` | 4 |
| Runtime settings application | `tests/test_appearance_transparency.py` | 2 |
| Screenshot commit/rollback | `tests/test_screenshot_manager.py` | 1 |
| Screenshot commit/rollback | `tests/test_adversarial_screenshot_registry.py` | 2 |

`tests/test_fonts.py` and `tests/test_appearance_transparency.py` each build a
`SimpleNamespace` controller harness and bind
`AppController.apply_application_style` with `MethodType`. Together those two
harnesses support six tests that invoke `AppController._on_settings_applied`
as an unbound method.

The screenshot tests create three additional `SimpleNamespace` controller
doubles and invoke `AppController._on_screenshot_saved` directly. These tests
currently own the detailed persistence, rollback, cleanup, and event assertions
that should move to the planned screenshot transaction service.

### Indirect integration boundary

The suite contains 26 `MainWindow(...)` construction sites in integration
coverage. All of them instantiate `AppController` indirectly. They should remain
the behavioral safety net while unit-level responsibility tests migrate to the
new services and coordinators. The count consists of:

- 23 direct constructions inside integration test bodies;
- one construction in the `cheatsheet_window` integration fixture;
- two constructions in integration-test `setUp` methods.

### Refactoring implications

- Keep `_on_settings_applied(settings)` as a thin compatibility boundary while
  moving its workflow into `SettingsCoordinator`.
- Keep `_on_screenshot_saved(entry)` as a thin UI boundary while moving commit,
  rollback, and cleanup assertions to the screenshot transaction service.
- Introduce dependency-construction changes incrementally: no test currently
  requires direct `AppController(...)` construction, but 26 `MainWindow`
  integration paths depend on the existing composition behavior.

### Coupling after phases 5 and 6

The six font/transparency tests now exercise `SettingsCoordinator` directly,
and a single focused test verifies that `AppController._on_settings_applied`
only delegates. Screenshot commit/rollback assertions now exercise
`ScreenshotTransactionService`; controller coverage is limited to the success
and failure UI/event boundary. The nine unbound responsibility-level calls
recorded above have therefore been removed while the indirect `MainWindow`
integration coverage remains intact.

## Phase 4 decision: preview state remains local

Re-evaluated after the report export boundary and UI-builder cleanup. The view
mode methods remain deliberately inside `ReportEditorTab` because they directly
coordinate its editor and preview widgets, formatting-toolbar visibility,
splitter geometry, dirty state, status label, save/autosave behavior, and the
conversion-loss confirmation dialog. Extracting them would move these widget
dependencies into another object without creating an independent state
machine. No `view_mode_controller` is introduced in this refactoring cycle.

## Phase 7: Single Composition Root in MainWindow

`MainWindow` is the sole composition root responsible for resolving and
instantiating application services (from `ServiceContainer` or standalone test
arguments). `AppController` has been strictly decoupled from container
construction: it takes fully resolved services through its constructor and
does not evaluate a container or instantiate domain services itself. This
boundary is guarded by `test_app_controller_receives_resolved_application_services`
in `tests/test_architecture_boundaries.py`.

## Phases 8–10: Conditional Refactoring Reviews

- **Phase 8 (`SettingsDialog`):** Evaluated and confirmed. The dialog is already
  cohesively modularized into class-level pages (`HotkeySettingsPage`,
  `LanguageSettingsPage`, `AppearanceSettingsPage`, `GeneralSettingsPage`).
  `_on_save_settings()` preserves transactional workspace-commit semantics.
  No further extraction is warranted.
- **Phase 9 (`LootController`):** Evaluated and confirmed. Presentation and
  filter pill generation remain cohesive with the view workflows. No artificial
  rendering framework layer was introduced.
- **Phase 10 (Layering Reviews):**
  - *`ThemeLoader`*: Remains in `core/` as a lightweight discovery and
    validation engine for JSON theme palettes, referencing `CYBER_DARK_PALETTE`
    tokens for validation.
  - *`ScreenshotManager`*: Remains a cohesive Qt capture coordinator with
    multi-monitor compositing, while the critical persistence/rollback/cleanup
    transaction was cleanly isolated into `ScreenshotTransactionService` (Phase 5).

