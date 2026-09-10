# SpectreHUD v2.0.2 – Release Notes

SpectreHUD v2.0.2 is a focused desktop usability and presentation patch. It
keeps the v2.0.1 project format and concentrates on predictable runtime styling,
bounded card geometry, and consistent window controls.

## Highlights

### Runtime typography

- Application and code font changes become visible immediately after
  **Save & Apply**; restarting SpectreHUD is no longer required for font-only
  changes.
- Font choices that are not installed locally are clearly marked and disabled
  instead of silently appearing identical to a fallback font.
- Report typography remains independent and continues to control report preview
  and export output only.
- Theme changes still use the controlled restart path.

### Loot and Kanban workflow

- Kanban cards now show a bounded five-line preview derived from the active font
  metrics. Long multi-line content, unbroken values, and large entries are
  ellipsized without nested scrollbars or extremely tall cards.
- Full Loot content remains available through the existing detail/edit and copy
  actions.
- The direct Loot-window button is now the single control for switching between
  classic and Kanban views; the redundant Appearance setting was removed.
- The Markdown export tooltip follows the active English or German locale.

### Window and layout fixes

- Added a header close button that uses the same transactional shutdown path as
  tray quit and Ctrl+Q.
- Reordered the main modes to Cheatsheet · History · Loot · Report.
- Corrected tooltip and combo-popup rendering in light themes such as Daylight.
- Restored transparent scroll-area glass surfaces without local stylesheets.
- Cheatsheet content height and scrollbar ranges now shrink immediately after
  filtering, avoiding empty scrolling below the final result.
- Late mouse events during a theme restart no longer raise errors after the
  window has been destroyed.

## Compatibility and upgrade

- Python 3.10 through 3.13
- Windows and Linux
- No project-state, registry, template, or Pentest-Mode migration is required
  from v2.0.0 or v2.0.1.

Close a running SpectreHUD instance before replacing the executable. Existing
projects and custom themes can be reused without conversion.

For the complete change history, see the repository [changelog](../CHANGELOG.md).
