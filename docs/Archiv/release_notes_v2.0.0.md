# SpectreHUD v2.0.0 – Release Notes

## Highlights

- **Project-oriented workflow:** isolated workspaces, safe project switching,
  importing existing projects, and ZIP archiving.
- **Cheatsheet and session data:** searchable commands with variables, session
  loot, opt-in clipboard history, and screenshot snipping.
- **Report Editor V2:** Markdown toolbar, find/replace, editor/split/live-preview
  modes, template management, and Dark and Light HTML export.
- **Exports:** standalone HTML, Obsidian notes, and portable CherryTree HTML
  packages.
- **Pentest Mode:** optional encrypted `project_state.json` storage for projects
  containing sensitive data.
- **Reliability and output safety:** consistent German/English interface,
  single-instance protection, atomic persistence, and inert customer-facing
  report exports.

## Compatibility

- Python 3.10 through 3.13
- Windows and Linux (CI matrix)
- Windows x64 executable as an additional release artifact

## Known Limitations

- On Wayland, screenshot capture may be limited by compositor and operating-system
  security rules. SpectreHUD reports failed screen captures in a controlled way.
- Clipboard recording is paused by default. When passwords or personal data are
  copied, users must enable the recorder deliberately and handle local storage
  responsibly.
- Pentest Mode protects the project-state file only. Other deliberately stored
  project files, such as notes or attachments, are not encrypted automatically.

## Upgrade Note

Close running SpectreHUD instances before upgrading. Existing project folders can
then be imported through Project Management; creating a ZIP archive first is
recommended before making extensive changes.
