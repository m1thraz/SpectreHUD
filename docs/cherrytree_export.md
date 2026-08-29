# CherryTree-Export

SpectreHUD exportiert für CherryTree ein portables HTML-Paket. Es schreibt
**niemals** direkt in eine CherryTree-`.ctb`-Datei oder deren SQLite-Datenbank.

Im Report-Editor **CherryTree-Paket exportieren...** wählen und einen
Zielordner auswählen. Daraus entsteht:

```text
<Zielordner>/<Projekt>/
├── report.html
├── loot.html
└── images/
```

`report.html` enthält den aktuellen Report, `loot.html` die aktuelle Session.
Screenshots und andere sichere lokale Bilder werden nach `images/` kopiert und
mit relativen Pfaden referenziert. Das Paket kann in CherryTree importiert oder
unabhängig in einem Browser geöffnet werden.

Der Export ist ein Snapshot. Er überwacht keine späteren Änderungen und bietet
keine Synchronisierung mit CherryTree.
