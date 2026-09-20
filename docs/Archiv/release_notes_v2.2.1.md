# SpectreHUD v2.2.1 – Release Notes

SpectreHUD v2.2.1 delivers the Quick-Find Spotlight HUD for lightning-fast command
searching and copying, accompanied by live variable interpolation and interactive
parameter prompt integration.

---

## Highlights

### Quick-Find Spotlight HUD

- **Global Hotkey Access:** Pressing `Ctrl+Alt+F` opens a focused, lightweight spotlight
  search popup centered at the active cursor position.
- **Cheatsheet-Wide Search:** Queries existing snippets across all categories without
  requiring view switching or navigation away from external terminal / browser workflows.
- **Glass HUD Layout & Styling:** Styled with the SpectreHUD glass theme, 520x320 dimensions,
  custom scrollbars, keyboard navigation (Arrow Up/Down, Enter to copy, Esc to close).
- **Reliable Dismissal:** Dismisses seamlessly on Esc, clicking outside the card, or
  switching focus to another application.

### Live Variable Interpolation in Quick-Find

- **Rendered Command Previews:** Command preview lines in search results render active project
  variables (`TARGET_IP`, `LHOST`, `PORT`, `URL`, `WORDLIST`, etc.) live via `TemplateEngine.render`.
- **Dynamic Synchronization:** Reads values directly from the active `VariableBar` and
  session cache, reflecting live updates without restarting or reloading.

### Interactive Parameter Prompting & Session Cache Integration

- **Inline Parameter Prompting:** Selecting a snippet with unresolved command placeholders
  (`{{INTERFACE}}`, `{{FILE}}`, `{{DIR}}`, `{{PAYLOAD}}`, etc.) seamlessly triggers
  `ParamPromptDialog` to enter or confirm parameters.
- **Session Cache Synchronization:** Presets and previously entered parameters are stored in
  `session_param_cache` and reused automatically across subsequent copies and searches.

---

## Verification & Compatibility

- **Pure Core Isolation:** Maintained strict decoupling between `core/` and UI layers.
- **Multi-Platform Support:** Works consistently across Windows and Linux (X11 & Wayland).
- **Packaging:** Full compatibility verified with PyInstaller one-file executable, Debian package,
  and wheel distributions.
