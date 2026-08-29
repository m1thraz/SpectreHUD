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

**Status: Implementiert; vor dem RC erneut ausführen.** Die gemeinsame pytest-Fixture isoliert die impliziten
Konfigurations- und Projektpfade pro Test. `run_tests.py` delegiert an dieselbe
pytest-Sammlung wie CI. Die finale Abnahme dokumentiert den konkreten CI-Lauf statt
eine dauerhaft veraltende Testanzahl.

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
- Jeder Testschritt benötigt ein begrenztes Timeout mit aussagekräftigem Log, damit ein
  hängender GUI- oder Plattformtest nicht unbegrenzt CI-Kapazität blockiert.
- Fehlende oder instabile Plattformabhängigkeiten klar beheben oder als nicht unterstützt dokumentieren.

**Abnahme:** Der relevante CI-Workflow ist auf dem Release-Commit vollständig grün.

**Implementierungsstand:** Die zuvor überlappenden Workflows wurden
in `ci.yml` zusammengeführt: Windows und Linux werden jeweils mit Python 3.10 bis
3.13 getestet; der Linux-3.11-Lauf erzeugt zusätzlich den Coverage-Bericht. Nach
der Matrix validiert ein gezielter Windows-3.11-Job Syntax, Wheel-Installation und
Windows-EXE. Der Release-Workflow nutzt denselben isolierten Wheel-Build und lehnt
Tags ab, deren Version nicht mit `pyproject.toml` übereinstimmt. Die erste grüne
Ausführung auf GitHub bleibt die noch ausstehende Abnahme.

**Lokaler CI-Abgleich (2026-08-29):** Die vollständige pytest-Sammlung umfasst
345 Tests (ein erwarteter Skip). Der CI-Lint-Gate mit `flake8` für kritische
Syntax- und Namensfehler sowie `compileall` für `core`, `ui`, `data`, `main.py`
und `scripts` liefen ohne Befund. Die plattformübergreifende GitHub-Ausführung
bleibt dennoch erforderlich.

**RC-Commit-Abgleich (2026-08-29):** Auf dem lokalen GitHub-Commit wurde der
vollständige Lauf erneut ausgeführt: 344 bestanden, 1 erwartet übersprungen,
ohne hängenden pytest-Prozess. Eine Windows-spezifische Lock-Testbereinigung
wurde dabei korrigiert; die betroffene Single-Instance-Suite besteht vollständig
(8/8). Der finale CI-Lauf muss diesen Korrektur-Commit abdecken.

### 2.2 Release-Artefakte validieren

- Wheel ohne Netzwerkabhängigkeit bauen.
- Wheel in eine frische Testumgebung installieren.
- `spectrehud --help` und `spectrehud --version` ausführen.
- Windows-EXE mit PyInstaller bauen und auf Startbarkeit prüfen.

**Abnahme:** Wheel und EXE entstehen reproduzierbar und bestehen Installation sowie CLI-Smoke-Test.

**Nachweis vor dem RC:** Ein frisches `spectrehud-2.0.0`-Wheel und das Quellarchiv
werden gebaut; `scripts/verify_wheel.py` muss den aktuellen Paketinhalt bestätigen.
Eine frische virtuelle Umgebung muss das Wheel samt Abhängigkeiten installieren sowie
`spectrehud --version` und `spectrehud --help` erfolgreich ausführen. Der
Windows-EXE-Build und die vollständige CI-Matrix bleiben harte Release-Gates.

**Lokaler Nachweis (2026-08-29):** Das Wheel wurde gebaut und mit
`scripts/verify_wheel.py` geprüft (122 Archivdateien). Die Installation in einer
frischen virtuellen Umgebung sowie `spectrehud --version` und
`spectrehud --help` waren erfolgreich. Die Windows-x64-EXE wurde mit PyInstaller
6.22.2 gebaut; `SpectreHUD.exe --version` und `SpectreHUD.exe --help` beendeten
beide mit Exit-Code 0. Die EXE enthält explizit Übersetzungen, beide
Standard-Snippet-Dateien und die Report-Vorlagen.

---

## Phase 3: Manuelle Produktabnahme unter Windows

Die folgende Checkliste wird auf einer normalen Windows-Desktop-Sitzung ausgeführt:

1. App-Start, Fensteranzeige, Always-on-top und Tray-Menü.
2. Globale Hotkeys: HUD umschalten, Screenshot starten und Anwendung beenden.
3. Clipboard-Recorder: Startzustand pausiert, Aktivierung, Aufzeichnung und Projektpersistenz.
4. Screenshot-Snip: Aufnahme, Loot-Eintrag, Berichtseinbindung und Fehlerfall beim Speichern.
5. Projektverwaltung: Erstellen, Wechseln, externer Workspace, leerer Workspace und Rollback bei Fehlern.
6. Report-Workflow: Template wählen, Markdown mit Toolbar sowie Find/Replace bearbeiten,
   Change View (Editor/Split/Live Preview) prüfen, Dark- und Light-HTML exportieren,
   im Browser editieren/speichern und ZIP-Archiv erstellen.
7. Mehrmonitorbetrieb mit unterschiedlichen Skalierungen; negative Bildschirmkoordinaten einschließen.
8. Pentest-Modus: verschlüsseltes Projekt anlegen, sperren/entsperren, Passwortfehler
   kontrolliert behandeln und prüfen, dass `project_state.json` nicht im Klartext liegt.
9. Quit-Workflow: normal speichern, erneuter Speicherversuch, Abbrechen und „ohne Speichern beenden“.

**Abnahme:** Keine Blocker, Datenverluste, UI-Thread-Warnungen oder nicht erklärten Fehlerdialoge.

---

## Phase 4: Sicherheits- und Dokumentationsabschluss

### 4.1 Sicherheits-Regression

- Pfadtraversal, Symlink-Escape, ZIP-Slip, zu große Importe und Bildgrößenlimits erneut testen.
- Clipboard bleibt standardmäßig deaktiviert.
- Dokumentation weist sichtbar auf die Klartext-Standardablage sowie Umfang und Grenzen des optionalen Pentest-Modus hin.

**Abnahme:** Adversariale Regressionstests sind grün; keine neue High-/Critical-Schwachstelle offen.

### 4.2 Release-Dokumentation

- Changelog bzw. Release Notes mit wichtigsten Funktionen, Fixes und Breaking Changes erstellen.
- Installation, unterstützte Plattformen und bekannte Einschränkungen prüfen.
- Wayland-Screenshot-Einschränkung und Datenschutzhinweis beibehalten bzw. aktualisieren.

**Abnahme:** Ein neuer Nutzer kann Installation, erste Schritte und Einschränkungen ohne Quellcodelektüre verstehen.

**Stand:** Die Release Notes liegen in
[`release_notes_v2.0.0.md`](release_notes_v2.0.0.md). README und Architektur-
Dokumentation enthalten Installation, unterstützte Plattformen, Wayland-Hinweis
und Datenschutzgrenzen.

---

## Phase 5: Release-Ablauf

1. Release-Candidate-Branch oder -Tag erstellen.
2. CI und manuelle Abnahme vollständig abschließen.
3. Git-Arbeitsbaum prüfen; nur beabsichtigte Änderungen committen.
4. Finalen Versions-Tag erstellen (`v2.0.0`, gemäß Versionsentscheidung).
5. Wheel und Windows-EXE als Release-Artefakte veröffentlichen.
6. Release Notes und Prüfsummen/Artefaktlinks veröffentlichen.

## Go/No-Go-Kriterien

Der offizielle Release darf nur erfolgen, wenn alle Punkte erfüllt sind:

- [ ] Versionsnummer überall einheitlich *(finaler Tag steht noch aus)*
- [x] Vollständiger, isolierter Testlauf lokal grün *(345 Tests, 1 erwarteter Skip; RC-Commit erneut prüfen)*
- [ ] CI auf unterstützten Plattformen grün
- [x] Wheel und EXE lokal erfolgreich gebaut und getestet
- [ ] Manuelle Windows-Abnahme ohne Blocker
- [x] Sicherheitsregression lokal grün *(Teil des vollständigen Testlaufs; auf RC-Commit erneut prüfen)*
- [x] Release Notes und bekannte Einschränkungen dokumentiert *(Veröffentlichung mit Release steht noch aus)*
- [ ] Git-Arbeitsbaum geprüft und Release-Tag vorbereitet
