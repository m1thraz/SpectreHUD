# Release-Readiness-Plan: SpectreHUD v2.0.0

## Ziel

SpectreHUD soll als stabiler, reproduzierbar baubarer und dokumentierter Release
veröffentlicht werden. Dieser Plan enthält bewusst keine neuen Produktfeatures,
sondern nur Release-Härtung, Qualitätssicherung und Veröffentlichungsvorbereitung.

## Entscheidung vor dem Start

### Release-Version festgelegt: v2.0.0

Der erste öffentliche Stable-Release wird als `v2.0.0` veröffentlicht.
`pyproject.toml` und `main.py --version` verwenden bereits diese Version; die
weiteren Release-Artefakte und der finale Git-Tag müssen sie ebenfalls tragen.

**Abnahme:** Ein Versions-Check über `spectrehud --version` und Paketmetadaten liefert
exakt die veröffentlichte Release-Version.

---

## Phase 1: Test-Isolation und Zuverlässigkeit

**Status: lokal erledigt (28.08.2026).** Die gemeinsame pytest-Fixture isoliert die impliziten
Konfigurations- und Projektpfade pro Test. `run_tests.py` delegiert an dieselbe
pytest-Sammlung wie CI. Lokale Abnahme: 291 Tests erfolgreich im Einzelprozess;
`compileall` für `core`, `ui`, `data`, `main.py` und `scripts` erfolgreich.

### 1.1 Globale Testzustände entfernen

Einige Tests verlassen sich implizit auf den globalen Konfigurationsordner
(`~/.ctf_cheatsheet_widget`). Das kann zu testübergreifenden Seiteneffekten führen.

- Jede Test-Fixture bekommt ein eigenes temporäres `config_dir` und `projects_dir`.
- Tests dürfen keine Benutzerkonfiguration, reale Projekte oder globale Registry-Dateien
  lesen bzw. schreiben.
- `SPECTRE_CONFIG_DIR` und `SPECTRE_PROJECTS_DIR` müssen in Setups zuverlässig gesichert
  und in Teardowns auf ihren vorherigen Wert zurückgesetzt werden.

**Abnahme:** `pytest` läuft in einem einzelnen Prozess vollständig und reproduzierbar
grün, ohne Zugriffe auf Benutzerpfade.

### 1.2 Test-Runner angleichen

- `run_tests.py`, `pytest` und CI müssen dieselbe Anzahl an Suites und Tests ausführen.
- Die in README und Architektur-Dokumentation genannten Testzahlen werden automatisch
  oder im Release-Schritt gegen den tatsächlichen Bestand geprüft.

**Abnahme:** Lokaler Test-Runner und `pytest` melden denselben erfolgreichen Testbestand.

---

## Phase 2: CI als Release-Gate

### 2.1 CI-Matrix verifizieren

- Testmatrix auf Windows und Linux mit allen offiziell unterstützten Python-Versionen ausführen.
- Headless-Qt-Setup, Linting, Tests, Wheel-Build und Wheel-Installation müssen erfolgreich sein.
- Fehlende oder instabile Plattformabhängigkeiten klar beheben oder als nicht unterstützt dokumentieren.

**Abnahme:** Der relevante CI-Workflow ist auf dem Release-Commit vollständig grün.

**Implementierungsstand (28.08.2026):** Die zuvor überlappenden Workflows wurden
in `ci.yml` zusammengeführt: Windows und Linux werden jeweils mit Python 3.10 bis
3.13 getestet; der Linux-3.11-Lauf erzeugt zusätzlich den Coverage-Bericht. Nach
der Matrix validiert ein gezielter Windows-3.11-Job Syntax, Wheel-Installation und
Windows-EXE. Der Release-Workflow nutzt denselben isolierten Wheel-Build und lehnt
Tags ab, deren Version nicht mit `pyproject.toml` übereinstimmt. Die erste grüne
Ausführung auf GitHub bleibt die noch ausstehende Abnahme.

### 2.2 Release-Artefakte validieren

- Wheel ohne Netzwerkabhängigkeit bauen.
- Wheel in eine frische Testumgebung installieren.
- `spectrehud --help` und `spectrehud --version` ausführen.
- Windows-EXE mit PyInstaller bauen und auf Startbarkeit prüfen.

**Abnahme:** Wheel und EXE entstehen reproduzierbar und bestehen Installation sowie CLI-Smoke-Test.

**Lokaler Stand (28.08.2026):** Ein frisches `spectrehud-2.0.0`-Wheel und das
Quellarchiv wurden gebaut. `scripts/verify_wheel.py` bestätigt 111 Dateien im Wheel.
Eine frische virtuelle Umgebung installierte das Wheel samt Abhängigkeiten erfolgreich;
`spectrehud --version` liefert `SpectreHUD 2.0.0` und `spectrehud --help` funktioniert.
Der Windows-EXE-Build und die vollständige CI-Matrix bleiben vor dem Release offen.

---

## Phase 3: Manuelle Produktabnahme unter Windows

Die folgende Checkliste wird auf einer normalen Windows-Desktop-Sitzung ausgeführt:

1. App-Start, Fensteranzeige, Always-on-top und Tray-Menü.
2. Globale Hotkeys: HUD umschalten, Screenshot starten und Anwendung beenden.
3. Clipboard-Recorder: Startzustand pausiert, Aktivierung, Aufzeichnung und Projektpersistenz.
4. Screenshot-Snip: Aufnahme, Loot-Eintrag, Berichtseinbindung und Fehlerfall beim Speichern.
5. Projektverwaltung: Erstellen, Wechseln, externer Workspace, leerer Workspace und Rollback bei Fehlern.
6. Report-Workflow: Template wählen, Markdown bearbeiten, Vorschau, HTML-Export und ZIP-Archiv.
7. Mehrmonitorbetrieb mit unterschiedlichen Skalierungen; negative Bildschirmkoordinaten einschließen.
8. Quit-Workflow: normal speichern, erneuter Speicherversuch, Abbrechen und „ohne Speichern beenden“.

**Abnahme:** Keine Blocker, Datenverluste, UI-Thread-Warnungen oder nicht erklärten Fehlerdialoge.

---

## Phase 4: Sicherheits- und Dokumentationsabschluss

### 4.1 Sicherheits-Regression

- Pfadtraversal, Symlink-Escape, ZIP-Slip, zu große Importe und Bildgrößenlimits erneut testen.
- Clipboard bleibt standardmäßig deaktiviert.
- Dokumentation weist sichtbar auf lokale Klartextspeicherung von Loot- und Clipboard-Daten hin.

**Abnahme:** Adversariale Regressionstests sind grün; keine neue High-/Critical-Schwachstelle offen.

### 4.2 Release-Dokumentation

- Changelog bzw. Release Notes mit wichtigsten Funktionen, Fixes und Breaking Changes erstellen.
- Installation, unterstützte Plattformen und bekannte Einschränkungen prüfen.
- Wayland-Screenshot-Einschränkung und Datenschutzhinweis beibehalten bzw. aktualisieren.

**Abnahme:** Ein neuer Nutzer kann Installation, erste Schritte und Einschränkungen ohne Quellcodelektüre verstehen.

---

## Phase 5: Release-Ablauf

1. Release-Candidate-Branch oder -Tag erstellen.
2. CI und manuelle Abnahme vollständig abschließen.
3. Git-Arbeitsbaum prüfen; nur beabsichtigte Änderungen committen.
4. Finalen Versions-Tag erstellen (`v1.0.0` oder `v2.0.0`, gemäß Versionsentscheidung).
5. Wheel und Windows-EXE als Release-Artefakte veröffentlichen.
6. Release Notes und Prüfsummen/Artefaktlinks veröffentlichen.

## Go/No-Go-Kriterien

Der offizielle Release darf nur erfolgen, wenn alle Punkte erfüllt sind:

- [ ] Versionsnummer überall einheitlich
- [x] Vollständiger, isolierter Testlauf grün *(291 Tests, lokal am 28.08.2026)*
- [ ] CI auf unterstützten Plattformen grün
- [ ] Wheel und EXE erfolgreich gebaut und getestet *(Wheel: gebaut, verifiziert und frisch installiert; EXE-Test steht noch aus.)*
- [ ] Manuelle Windows-Abnahme ohne Blocker
- [ ] Sicherheitsregression grün
- [ ] Release Notes und bekannte Einschränkungen veröffentlicht
- [ ] Git-Arbeitsbaum geprüft und Release-Tag vorbereitet
