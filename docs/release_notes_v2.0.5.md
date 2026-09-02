# SpectreHUD v2.0.5 – Release Notes

SpectreHUD v2.0.5 is a usability and desktop-integration release focused on
responsive UI layouts, a streamlined variable bar with popover flyouts, and
seamless Linux X11 compositor adaptation. It preserves all v2.0.x project,
registry, template, and Pentest Mode formats.

## Highlights

### Responsive Cheatsheet Category Pills Bar

- Category filter buttons now dynamically adapt to the available window width.
- Computes visible button capacity in real-time and dynamically places an adaptive
  "Mehr ▾" ("More ▾") dropdown button as the last visible item for remaining categories.
- Automatically expands to show all categories directly when running on wide
  or fullscreen monitors, seamlessly hiding the overflow button.
- Built-in zero-thrashing threshold detection ensures resizing the window remains
  silky-smooth, performant, and flicker-free.
- When an overflow category is selected, the "Mehr ▾" button dynamically adopts
  its name and highlights in active cyan.

### Hybrid Variable Bar with Auth & Scope Popovers

- Compact redesign reducing minimum width from >850px down to ~680px, fitting comfortably
  even on smaller screens or narrow tiling layouts.
- Preserved direct live editing for high-frequency connection variables:
  `Target IP`, `LHOST` (with auto-detection), and `Port` remain instantly accessible on the bar.
- Secondary variables are neatly grouped into sleek, frameless cyber-dark popover flyouts:
  - **`[👤 Auth ▾]`**: Manages Username, Password (with 👁 show/hide toggle), Domain/Realm,
    and NTLM Hash for Pass-the-Hash workflows.
  - **`[📁 Scope ▾]`**: Manages Wordlist (with integrated file browser dialog) and Target URL/Endpoint.
- Visual status badges: Buttons dynamically highlight in cyan and display active values
  (e.g., `[👤 admin ▾]`) when values are set.
- Privacy & usability: Sensitive passwords and hashes are no longer permanently exposed
  on the screen. Popovers dismiss automatically when clicking outside without blocking the application.

### Linux X11 Compositor Awareness & Border Rendering

- Automatically detects running X11 compositors via `_NET_WM_CM_S0` atom check or
  `SPECTREHUD_COMPOSITOR` environment override.
- Eliminates black rectangular borders and transparent margin artifacts on systems
  running without a compositor (e.g. Linux Mint / XFCE / MATE with compositing disabled)
  by dynamically toggling `WA_TranslucentBackground` and enforcing crisp square borders.

### Report Editor & UI Fixes

- **High-Contrast Template Dropdowns**: Fixed unreadable dropdown text in `ReportGenerationDialog`
  by adding explicit item styles and enforcing viewport rendering against light GTK themes.
- **Kanban Board Scrollbars**: Cleaned up vertical scrollbar clutter on individual Kanban
  columns and cards while retaining smooth mouse wheel scrolling.
- **Unified Palette**: Single canonical source of truth for color palette tokens under
  `core.theme_palette`.
- **Public Overlay API**: Added explicit public API for overlay view factory registration.

## Compatibility and upgrade

- Python 3.10 through 3.13
- Windows and Linux (X11 & Wayland)
- Fully compatible with existing v2.0.x projects, report templates, custom themes, and pentest mode states.

For the complete change history, see the repository [changelog](../CHANGELOG.md).