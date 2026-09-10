# SpectreHUD v2.1.0 – Release Notes

SpectreHUD v2.1.0 introduces a centralized, headless Pentest Phase Taxonomy with standardized badge rendering across all cards, an elevated tactile Kanban Loot Board with interactive drag-and-drop feedback and right-edge scroll fade, robust badge truncation protection with elided card titles, and expanded simulated glass depth controls.

---

## Highlights

### Centralized Pentest Phase Taxonomy & Standardized Badges

- **Single Source of Truth (`core/phases.py`)**:
  - Centralized dataclass `Phase(key, short, long, order, icon)` defining the 6 canonical pentesting phases: `recon`, `access`, `privesc`, `postex`, `scripts`, and `misc`.
  - Strict headless, Zero-Qt core isolation adhering to Tier 1 architectural decoupling.
  - Robust normalization (`normalize_phase_key()` and `get_phase()`) resolving synonyms (e.g. `initial` → `access`, `lateral` → `postex`, `poc` → `scripts`), numeric order indices, and legacy full titles (e.g. `1. Reconnaissance & Enumeration`) with fallback to `misc`.
- **Standardized Badge Labels & Tooltips**:
  - `LootCard` and `QuickNoteCard` badges now consistently render uppercase short labels (`RECON`, `ACCESS`, `PRIVESC`, `POSTEX`, `SCRIPTS`, `MISC`) and provide the full phase title on hover via tooltips.
- **Resilient Data Migration**:
  - `LootMigrator` and `QuickNoteManager` automatically normalize legacy titles and variant keys during persistence and migration without loss of categorization.

### Tactile Kanban Loot Board & Drag Affordances

- **Elevated Card Appearance (`QFrame#lootCard`)**:
  - Distinct theme surface backgrounds (`{SURFACE_A85}`), 10px rounded borders, and subtle hover elevation ensure loot entries stand out as tactile, movable objects on the darker column background.
- **Tactile Drag Feedback**:
  - Embedded vertical grip handle icon (`fa5s.grip-vertical`) with localized tooltip.
  - Responsive cursor state transitions (`OpenHandCursor` on hover, `ClosedHandCursor` on grab/drag).
  - 60% opacity effect during active drag operations.
- **Scroll Fade & Column Indicator**:
  - Subtle right-edge gradient fade visually indicates horizontal column overflow.
  - Dynamic visible column count indicator ("Spalte 1–3 von 6") in the board footer, updating automatically on scroll and window resize.

### Badge Truncation Protection & Elided Titles

- **Dynamic Font-Metric Badge Sizing**:
  - Replaced rigid badge label widths with dynamic font-metric calculations (`configure_badge_label`), guaranteeing badges such as `TARGET` or category tags are never clipped.
- **Graceful Card Title Elision**:
  - Integrated `ElidedLabel` across `LootCard`, `QuickNoteCard`, `HistoryCard`, and `SnippetCard` to ensure card titles truncate cleanly with an ellipsis (`…`) without crowding or truncating adjacent metadata badges.

### Visual Depth & Glass Intensity Refinement

- **Multi-Layer Simulated Glass**:
  - Fine-tuned glass intensity controls affecting gradient depth, soft light reflection, and cached noise grain textures over the opaque base without requiring desktop compositor translucency.
- **Command Card Auto-Height**:
  - Maintained full text wrapping for command cards across window resizes, font alterations, and multiline variable substitutions.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Fully backwards compatible with existing SpectreHUD project directories and reports.
- Existing loot and note entries automatically normalize to canonical phase keys without requiring manual database or schema migrations.
