# SpectreHUD v2.0.0 – Release Notes

## Highlights

- **Projektorientierter Workflow:** getrennte Arbeitsbereiche, sicherer
  Projektwechsel, Import bestehender Projekte und ZIP-Archivierung.
- **Cheatsheet & Session-Daten:** durchsuchbare Befehle mit Variablen,
  Session-Loot, opt-in Clipboard-Historie und Screenshot-Snipping.
- **Report Editor V2:** Markdown-Toolbar, Suchen/Ersetzen, Editor-/Split-/Live-
  Ansicht, Vorlagenverwaltung sowie Dark- und Light-HTML-Export.
- **Exporte:** eigenständiges HTML, Obsidian-Notizen und portable
  CherryTree-HTML-Pakete.
- **Pentest-Modus:** optional verschlüsselte `project_state.json`-Ablage für
  Projekte mit sensiblen Daten.
- **Bedienung & Sicherheit:** einheitliche deutsche/englische Oberfläche,
  Single-Instance-Schutz, atomare Speicherung und umfangreiche adversariale
  Regressionstests.

## Kompatibilität

- Python 3.10 bis 3.13
- Windows und Linux (CI-Matrix)
- Windows-x64-EXE als zusätzliches Release-Artefakt

## Bekannte Einschränkungen

- Unter Wayland können Screenshots abhängig vom Compositor durch die
  Betriebssystem-Sicherheitsregeln eingeschränkt sein. SpectreHUD meldet
  fehlgeschlagene Bildschirmaufnahmen kontrolliert.
- Die Clipboard-Aufzeichnung ist standardmäßig pausiert. Werden Passwörter
  oder personenbezogene Daten kopiert, muss der Nutzer den Recorder bewusst
  aktivieren und die lokale Speicherung verantwortungsvoll behandeln.
- Der Pentest-Modus schützt die Projektstatusdatei. Andere bewusst abgelegte
  Dateien im Projektordner (z. B. eigene Notizen oder Anhänge) werden dadurch
  nicht automatisch verschlüsselt.

## Upgrade-Hinweis

Vor dem Upgrade laufende SpectreHUD-Instanzen schließen. Anschließend kann ein
bestehender Projektordner über die Projektverwaltung importiert werden; vor
umfangreichen Änderungen empfiehlt sich ein ZIP-Archiv des Projektordners.
