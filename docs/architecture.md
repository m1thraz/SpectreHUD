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
  - `ServiceContainer.create_in_memory(...)`: Instantiates 100% in-memory fakes (0 disk I/O, sub-millisecond execution) for unit and regression testing.

### 2.5 Storage Abstraction Layer (`core/storage.py`)
- **`StorageBackend` Interface**:
  - `load_json(file_or_key, default)`
  - `save_json(file_or_key, data)`
  - `delete(file_or_key)`
  - `exists(file_or_key)`
- **`FileStorageBackend`**: Uses atomic writes (`core/atomic_write.py`) with temporary file swapping (`.tmp_*` -> rename) and maximum file size guards (`core/validators.py`).
- **`InMemoryStorageBackend`**: Pure memory store with deep-copy isolation.

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

---

## 3. Security & Resilience Architecture

1. **Path Traversal Protection**:
   - `core/validators.py` sanitizes project names, output paths, and snippet titles, preventing directory traversal outside project sandboxes.
2. **File Size Guards & Memory Bomb Prevention**:
   - Maximum file size thresholds on all JSON imports, registries, notes, and screenshots (`MAX_SNIPPETS_FILE_SIZE`, `MAX_REGISTRY_FILE_SIZE`, `MAX_IMAGE_FILE_SIZE`).
3. **Atomic File Persistence**:
   - `core/atomic_write.py` ensures power-loss and crash resilience by writing to unique temp files before atomically replacing target JSON/markdown files.
4. **Structured & Rotating Logging (`core/logger.py`)**:
   - Hierarchical namespacing (`spectrehud.<module>`), `SPECTRE_LOG_LEVEL` environment configuration, 5 MB file threshold, and 3-backup log rotation.

---

## 4. Testing & CI/CD Strategy

- **Master Test Runner (`run_tests.py`)**:
  - Automatically discovers all 33 test suites across `tests/`.
  - Runs in headless mode (`QT_QPA_PLATFORM=offscreen`).
- **GitHub Actions CI (`.github/workflows/tests.yml`)**:
  - Multi-OS matrix: `ubuntu-latest`, `windows-latest`.
  - Python matrix: `3.10`, `3.11`, `3.12`.
  - Linux headless display setup using `xvfb-run`.
  - Automated `flake8` syntax validation and `coverage` reporting.

---

## 5. Technical Debt & Future Roadmap

| Priority | Area | Description | Recommended Solution |
|---|---|---|---|
| **Prio D** | **i18n Localization** | English/German translations missing in some secondary dialogs and empty state banners. | Audit all UI text strings against `core/i18n.py` language dictionaries. |
| **Prio E** | **Async Workers** | Heavy regex filtering or bulk project exports run on the main Qt GUI thread. | Offload long-running operations to `QThreadPool` / `QRunnable`. |
| **Prio E** | **Plugin Architecture** | Cheatsheet snippets and tools are currently bundled in JSON files. | Introduce a lightweight plugin interface for custom tool integrators. |
