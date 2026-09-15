# SpectreHUD v2.1.9 - Release Notes

SpectreHUD v2.1.9 restores runtime loading for optional community and external
snippet packs in the Cheatsheet.

## Fixed

- Load `community_snippets.json`, `community_*.json`, and `offensive_*.json`
  packs found in the application's data directory.
- Keep user snippets and favorites aligned with the configured application
  directory.
- Add regression coverage for community-pack loading and production service
  composition.

## Compatibility

Existing projects, settings, reports, and user snippets remain compatible.
