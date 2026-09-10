# CherryTree Export

SpectreHUD exports a portable HTML package for CherryTree. It **never**
writes directly to a CherryTree `.ctb` file or its SQLite database.

In the report editor, select **Export CherryTree package...** and choose a
destination folder. This creates the following structure:

```text
<destination_folder>/<project>/
├── report.html
├── loot.html
└── images/
```

`report.html` contains the current report, while `loot.html` contains the current session.
Screenshots and other local images are copied to the `images/` folder and
referenced using relative paths. The package can be imported into CherryTree or
opened independently in a web browser.

The export is a snapshot. It does not monitor subsequent changes and offers
no synchronization with CherryTree.