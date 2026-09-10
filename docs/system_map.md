# SpectreHUD System Map

Diese Karte enthält nur Verträge und Fallen, die erst an den Grenzen mehrerer Komponenten sichtbar werden.

## Projektwechsel
- Nicht offensichtlich: Report-Dirty-Entscheidung und Speichern der alten Session passieren vor der Aktivierung; der Zielreport wird danach vor dem atomaren Laden von Loot, History, Notes und Phase geladen, das erst im Erfolgs-Callback erfolgt.
- Bekannte Falle: `activate_project()` verwirft bereits den alten In-Memory-Schlüssel und publiziert `PROJECT_CHANGED` mit `name`, bevor Unlock, Report-Laden und Session-Laden erfolgreich sind; nach Abschluss publiziert der Coordinator denselben EventType nochmals mit `project_name`.
- Bekannte Falle: Wird der Unlock des Zielprojekts abgebrochen, liefert der Coordinator derzeit `False`, ohne das zuvor aktivierte Projekt zurückzustellen; UI und Runtime können deshalb unterschiedliche Projekte annehmen.
- Warum so gebaut: Die vier Session-Komponenten werden erst nach vollständiger Validierung gemeinsam ersetzt, während `report.md` wegen eigenem Dirty-/Save-Vertrag separat geschützt wird.

## Pentest-Mode Ein-/Ausschalten
- Nicht offensichtlich: Pentest-Mode wird nur beim Erstellen aktiviert: unverschlüsselte Security-Metadaten werden angelegt und dieselbe `project_state.json` anschließend verschlüsselt überschrieben; der abgeleitete Schlüssel lebt nur im Speicher und höchstens für ein Projekt.
- Bekannte Falle: Die Dateiendung zeigt nicht, ob `project_state.json` verschlüsselt ist, und `pentest_mode: true` bedeutet nicht „entsperrt“; Projektwechsel und Shutdown verwerfen den In-Memory-Schlüssel.
- Bekannte Falle: Für bestehende Projekte gibt es derzeit keinen Disable-Flow; das Ausschalten der Checkbox im Erstellungsdialog blendet nur die Passwortfelder aus und löscht deren Eingabe.
- Warum so gebaut: `security_meta.json` bleibt lesbar, damit Modus, KDF-Parameter und Passwort-Verifier vor dem Entschlüsseln geprüft werden können, ohne eine zweite State-Quelle einzuführen.

## Report-Export
- Nicht offensichtlich: Alle Exporte konsumieren den aktuellen Markdown-Text des Source-Editors; Professional Print segmentiert ihn semantisch und bereinigt nur die Darstellung, während Classic Web generisch rendert — keiner der Pfade regeneriert oder speichert `report.md`.
- Bekannte Falle: Änderungen in der editierbaren Live-Preview werden nur bei einem expliziten Preview-Commit zurückgeschrieben; die Exportaktionen führen diesen Commit derzeit nicht selbst aus und können deshalb den letzten Source-Stand exportieren.
- Bekannte Falle: Markdown, Obsidian, CherryTree und sichtbares HTML entfernen interne Section-/Finding-/Loot-Marker; ein Export ist daher kein verlustfreier Ersatz für die synchronisierbare `report.md`.
- Warum so gebaut: Interne Marker tragen Struktur- und Sync-Identität, sollen aber weder in Kundenartefakten sichtbar sein noch vom Exportpfad verändert werden.

## Event-Payloads mit verstecktem Vertrag
- `PROJECT_CHANGED` — `{name: str}` oder `{project_name: str}`: Manager und Workspace-Commit publizieren unterschiedliche Formen und Zeitpunkte; der EventType allein garantiert daher keinen vollständig abgeschlossenen Projektwechsel.
- `ACTIVE_PHASE_CHANGED` — `{phase_id: str | None, source: str}`: `None` ist ein gültiges Löschen der Phase, und nur `source == "hotkey"` löst das sichtbare Phase-HUD aus; Session-Laden verwendet `project_load`.
- `HOTKEY_SETTINGS_CHANGED` — `{hotkey, snip_hotkey, quit_hotkey, quick_*?}`: Die drei Quick-Hotkeys fehlen, wenn sie nicht Teil der Änderung waren; der Consumer muss dafür die bereits gespeicherte Konfiguration verwenden.
