# Obsidian-Export

SpectreHUD kann einen aktiven CTF-/Pentest-Report in einen bestehenden Obsidian-
Vault exportieren. Die Integration ist bewusst ein **einseitiger Export**:

```text
SpectreHUD → Obsidian
```

Sie überwacht den Vault nicht, liest keine Obsidian-Datenbank und versucht keine
zweiwegige Synchronisierung oder Konfliktauflösung.

## Einrichtung

Unter **Settings → General & Behavior** einen vorhandenen Vault auswählen und
optional den relativen Zielordner festlegen. Standard ist
`CTF/SpectreHUD`. Der Vault selbst wird nie automatisch angelegt; nur der
gewählte Export-Unterordner entsteht beim ersten Export.

## Report-Export

Im Report-Editor **Export to Obsidian...** wählen. Der Export erzeugt eine
Markdown-Notiz unter:

```text
<Vault>/CTF/SpectreHUD/<Projekt>/<Projekt>.md
```

Eine bereits vorhandene Notiz wird standardmäßig nicht überschrieben. Stattdessen
entsteht eine nummerierte Kopie wie `<Projekt>_2.md`. Der Report erhält
Frontmatter mit Projekt, vorhandener Target-/Attacker-IP, Zeitstempel und den
Tags `ctf` und `spectrehud`. Passwörter und Credentials werden nie als
Frontmatter übernommen.

Lokale Markdown-Bilder aus dem Projekt werden nach `attachments/` kopiert und
ihre Referenzen entsprechend umgeschrieben. Fehlende oder unsichere Anhänge
(beispielsweise Symlinks oder Pfade außerhalb des Projekts) werden übersprungen;
der Report bleibt exportierbar und meldet eine Warnung.

## Loot senden

Im Loot-Bereich hängt **Obsidian** die komplette aktuelle Session an die bereits
exportierte Projektnotiz an. Die `O`-Schaltfläche einer Loot-Karte exportiert nur
diesen Eintrag. SpectreHUD schreibt dafür eindeutige Eintragsmarker in die
Markdown-Datei und überspringt identische Einträge bei einem erneuten Export.
Manuell bearbeiteter Inhalt der Notiz wird nicht neu generiert oder überschrieben.

Wenn die Option **Open exported note in Obsidian** aktiv ist, wird der
Obsidian-URI erst nach dem erfolgreichen Dateiexport geöffnet. Ist Obsidian nicht
installiert oder kann die URI nicht öffnen, bleibt der Export dennoch erfolgreich.
