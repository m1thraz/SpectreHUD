# SpectreHUD Architecture & Technical Guide

This document provides a comprehensive technical overview of SpectreHUD's software architecture, component relationships, design patterns, security guarantees, and technical debt tracking.

---

## 1. High-Level Architecture Overview

SpectreHUD follows a **layered, decoupled architecture** built upon Qt 6 (PyQt6), Python 3.10+, dependency injection, reactive event dispatching, and storage abstractions.

```mermaid
graph TD
    UI[UI Shell / Panels: MainWindow, Panels, Dialogs] --> AppCtrl[AppController]
    AppCtrl --> DomainCtrls[Domain Controllers: Cheatsheet, Loot, History, Project, Report]
    DomainCtrls --> EventBus[EventBus (core/event_bus.py)]
    DomainCtrls --> Services[Domain Services: LootManager, SnippetManager, ProjectManager, etc.]
    AppCtrl --> Container[ServiceContainer (core/container.py)]
    Container --> Services
    Services --> Storage[StorageBackend: FileStorageBackend / InMemoryStorageBackend]
    Storage --> Filesystem[(Atomic Filesystem / OS)]
```

---

## 2. Architectural Layers & Components

### 2.1 UI Presentation Layer (`ui/`)
- **`MainWindow` (`ui/main_window.py`)**: Frameless, transparent, Spotlight-style overlay shell. Handles native window movement, geometry positioning, and global keyboard shortcuts.
- **Panels (`ui/panels/`)**:
  - `HeaderPanel`: Title, project switcher dropdown, language toggle, and action buttons.
  - `SearchPanel`: Real-time fuzzy query input with filter tags.
  - `VariableBar`: Dynamic template parameter substitutions (`{target_ip}`, `{lhost}`, `{lport}`, `{wordlist}`, etc.).
  - `ContentPanel`: Multi-mode view container (Cheatsheet, Loot, History, Report Editor).
  - `FooterPanel`: Status bar, shortcut hints, and active recording indicators.
- **Dialogs (`ui/`)**: Modal forms for adding snippets, loot entries, custom variables, and application settings.

### 2.2 Domain & Workflow Controllers (`ui/controllers/`)
- **`AppController` (`ui/app_controller.py`)**: The central coordinator connecting UI signals, mode switching, and domain controllers.
- **Sub-Controllers**:
  - `CheatsheetController`: Filtering, variable substitution, and snippet copying.
  - `LootController`: Loot CRUD operations, tabular search, and export generation.
  - `HistoryController`: Clipboard command log ingestion, filtering, and loot promotions.
  - `ProjectController`: Project creation, switching, validation, and metadata persistence.
  - `ReportController`: Pentest / CTF markdown report assembly and live editing.
- **UI Decoupling with DTOs (`core/menu_actions.py` & `ui/menu_builder.py`)**:
  - Controllers build context menus using pure Python `MenuAction` data transfer objects (`label`, `callback`, `icon`, `is_separator`, `is_enabled`).
  - `MenuBuilder.build_qmenu()` converts these DTOs into Qt `QMenu` instances at the view boundary, making controller logic 100% unit-testable in headless environments.

### 2.3 Reactive Event Bus (`core/event_bus.py`)
- Provides loose coupling between services and controllers via publish/subscribe.
- **`EventType` Events**: `PROJECT_CHANGED`, `LOOT_UPDATED`, `HISTORY_UPDATED`, `SNIPPETS_UPDATED`, `CONFIG_UPDATED`, `VARIABLE_CHANGED`.
- **Thread-Safe & Fault-Tolerant**: Protected by `threading.RLock`, with exception isolation so a failing subscriber cannot crash the publisher or other listeners.

### 2.4 Dependency Injection & Service Container (`core/container.py`)
- **`ServiceContainer`**: Coordinates all core managers, storage backends, and event buses in one place.
- **Factory Methods**:
  - `ServiceContainer.create_production(...)`: Instantiates filesystem-backed storage, default config directories, and locale settings.
  - `ServiceContainer.create_isolated_test_container(...)`: Uses in-memory storage for configuration and session data, plus isolated temporary filesystem directories for filesystem-dependent services such as `ProjectManager` and `ReportFileManager`. It is designed for test isolation and does not guarantee zero disk I/O.
  - `ServiceContainer.create_in_memory(...)`: Backward-compatible legacy alias for `create_isolated_test_container(...)`; new tests should use the explicit name.

### 2.5 Storage Abstraction Layer (`core/storage.py`)
- **`StorageBackend` Interface**:
  - `load_json(file_or_key, default)`
  - `save_json(file_or_key, data)`
  - `delete(file_or_key)`
  - `exists(file_or_key)`
- **`FileStorageBackend`**: Uses atomic writes (`core/atomic_write.py`) with temporary file swapping (`.tmp_*` -> rename) and maximum file size guards (`core/validators.py`).
- **`InMemoryStorageBackend`**: Pure memory store with deep-copy isolation.
- **Process Concurrency**: Project-state files use atomic replacement, so interrupted
  writes never expose partial JSON. Registry mutations additionally use a cross-process
  lock and read-merge-write step so concurrent project imports are retained. Concurrent
  edits to the *same* project state remain last-writer-wins; they are valid but not a
  collaborative merge protocol.

### 2.6 Virtual Qt Item Models (`ui/models/`)
- Replaces manual widget row creation with virtualized Qt item models:
  - `LootTableModel` (`QAbstractTableModel`): 6 columns, custom alignments, and `UserRole` payload access.
  - `SnippetListModel` (`QAbstractListModel`): Virtualized snippet list with HTML tooltips.
  - `HistoryTableModel` (`QAbstractTableModel`): 4 columns for command and clipboard history logs.

### 2.7 Modular Style System (`ui/styles/`)
- Deconstructed QSS stylesheets into cohesive modules:
  - `palette.py`: Color constants and semantic palette definitions.
  - `typography.py`: Font families, font weights, and size hierarchies.
  - `buttons.py`: Standard, primary, and ghost button styling.
  - `tables.py`: Table views, header styling, and row selection states.
  - `cards.py`: Snippet card containers and code blocks.
  - `dialogs.py`: Modal dialogues, form layouts, and inputs.
  - `theme.py`: Aggregator generating the complete `CYBER_DARK_QSS` theme.

### 2.8 Structured Template Engine & Repository Subsystem (`core/reporting/`)
- **`ReportTemplate` & `TemplateSection` (`template_engine.py`)**: Strict data models defining pentest report structures with section requirements, auto-append directives, and dynamic parameters.
- **`TemplateRepository` (`template_repository.py`)**: Dual-tier template storage loading built-in factory templates and sandboxed custom user templates with ID regex validation (`^[a-zA-Z0-9_-]{1,64}$`).
- **`ReportTemplateEngine` (`template_engine.py`)**: Renders structured Markdown write-ups from templates, replacing placeholders (`{{TARGET_IP}}`, `{{DATE}}`, `{{METRICS_SUMMARY}}`), formatting tabular findings with pipe escaping, and organizing loot by phase and severity.
- **`FindingMetrics` & `render_severity_badge` (`charts.py`)**: Calculates finding distribution and renders visual HTML severity badges (*Critical, High, Medium, Low, Info*).

### 2.9 Archival & Standalone Export Subsystems (`core/`)
- **`BoxArchiver` (`core/box_archiver.py`)**: Compresses complete project workspaces into portable `.zip` archives with path traversal and Zip-Slip prevention.
- **`HtmlReportExporter` (`core/html_report_exporter.py`)**: Converts Markdown reports into self-contained HTML documents with embedded base64 screenshots, responsive layouts, and Cyber-Dark styling for offline client delivery.

### 2.10 Dynamic Internationalization Subsystem (`core/i18n.py`)
- **`I18nManager`**: Thread-safe internationalization runtime supporting live locale switching (`de` / `en`) without application restart.
- **Parametric Interpolation**: Supports variable substitution (e.g. `{count}`, `{target}`) and fallback defaults across all 4 main views, panels, and 6 modal dialogs.

---

## 3. Security & Resilience Architecture

1. **Path Traversal & Symlink Escape Protection**:
   - `core/validators.py` sanitizes project names, output paths, and snippet titles, preventing directory traversal outside project sandboxes.
   - `core/project/repository.py` validates workspace boundaries for both created and imported projects, actively rejecting pre-existing symlinked subdirectories (`recon/`, `exploit/`, `loot/`).
   - `core/reporting/template_repository.py` validates template IDs and verifies safe sandbox paths with `Path.is_relative_to()`.
2. **File Size Guards & Memory Bomb Prevention**:
   - Maximum file size thresholds on all JSON imports, registries, templates, notes, and screenshots (`MAX_SNIPPETS_FILE_SIZE`, `MAX_REGISTRY_FILE_SIZE`, `MAX_TEMPLATE_FILE_SIZE`, `MAX_IMAGE_FILE_SIZE`).
3. **Atomic File Persistence**:
   - `core/atomic_write.py` ensures power-loss and crash resilience by writing to unique temp files before atomically replacing target JSON/markdown files.
4. **Single Source of Truth for Session Data**:
   - `project_state.json` inside each project folder is the sole source of truth for loot, variables, and clipboard history.
   - `LootManager` and `ClipboardWatcher` operate as session buffers in RAM, avoiding redundant and conflicting global storage files.
5. **Code Fence & Table Injection Immunity**:
   - Markdown exporter strictly sanitizes code-fence language specifiers and escapes table pipes to prevent format breakage or injection.
6. **Structured & Rotating Logging (`core/logger.py`)**:
   - Hierarchical namespacing (`spectrehud.<module>`), `SPECTRE_LOG_LEVEL` environment configuration, 5 MB file threshold, and 3-backup log rotation. File logging is configured lazily at bootstrap, keeping module imports 100% side-effect free.

---

## 4. Multi-Location Workspace & Registry Semantics

- **Default Workspace (`workspace_dir`)**: Configures the base directory where newly created CTF box projects are stored by default.
- **Multi-Location Registry (`projects_registry.json`)**: Allows projects to reside across multiple locations (e.g. secondary drives, mounted network shares, imported folders) without moving them into the default workspace. Changing `workspace_dir` in Settings updates the default path for future boxes while preserving existing registered project locations.

---

## 5. Testing & CI/CD Strategy

- **Master Test Runner (`run_tests.py`)**:
  - Automatically discovers and executes all **40 test suites** (253 tests) across `tests/`.
  - Runs in headless mode (`QT_QPA_PLATFORM=offscreen`).
- **GitHub Actions CI (`.github/workflows/ci.yml`)**:
  - Multi-OS matrix: `ubuntu-latest`, `windows-latest`.
  - Python matrix: `3.10`, `3.11`, `3.12`, `3.13`.
  - Linux headless display setup using `xvfb-run`.
  - Automated `flake8` syntax validation and `coverage` reporting.
