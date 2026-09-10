# SpectreHUD v2.0.6 – Release Notes

SpectreHUD v2.0.6 is a tactical feature and usability release delivering
embedded 1-click circular copy buttons, 5 new community dark HUD themes,
expanded typography options, and an enhanced Scope & Auth variable popover
suite including Subnet, DNS Server, and unified Hash/File support.

## Highlights

### 1-Click Circular Copy Buttons for Variable Inputs

- Embedded subtle circular vector copy buttons directly inside Target IP, LHOST,
  and all Popover input fields (Port, Domain, Hash / File, Wordlist, URL, Subnet, DNS Server).
- Renders a crisp vector copy icon with smooth hover glow and transitions into a glowing
  green circular checkmark upon click for clear visual confirmation.
- Built without layout overhead or extra button spacing (setTextMargins).
- Fully localized tooltips in English and German with instant dynamic retranslation (
etranslate()).

### 5 New Built-in HUD Themes

Expanded the built-in theme roster from 9 to 14 complete themes, offering popular
dark-mode palettes for every pentesting environment:
- **Blue Team**: Cool defensive cobalt blue accents for blue teamers and SOC analysts.
- **Catppuccin Mocha**: Soothing pastel dark palette with warm lavender and mauve accents.
- **Dracula**: Classic high-contrast dark theme with vibrant purple, pink, and cyan highlights.
- **Gruvbox**: Warm retro groove palette with earthy amber, green, and orange tones.
- **Tokyo Night**: Clean modern neon cyberpunk dark palette celebrating downtown Tokyo vibes.

### Expanded Scope & Auth Variable Popovers

- **Port in Auth Popover**: Relocated the Port field from the horizontal main bar into the
  Auth Popover, making the main HUD header even more compact on narrow and split-screen setups.
- **Subnet & DNS Server**: Added dedicated persistent inputs for {{SUBNET}} and {{DNS_SERVER}}
  (with {{DNS}} alias) inside the Scope Popover for streamlined network pivoting and AD engagements.
- **Unified Hash / File Field**: Renamed the Hash field to Hash / File:, supporting both raw
  NTLM hash strings and hash list file paths ({{NTLM_HASH}}, {{HASH}}, {{HASH_FILE}}).
- **Calmed Active Badge Styling**: Refined VarBadgeBtnActive so buttons with active variables
  (e.g., [👤 admin ▾]) match the clean, non-intrusive border and background of default badge buttons.

### Expanded Typography Stacks in Settings

Added curated UI, Code, and Report font stacks with resilient native fallbacks:
- **App UI**: Added *IBM Plex Sans* (industrial technical Grotesk) and *Manrope* (crisp semi-geometric dark-mode font).
- **Code & Snippets**: Added *IBM Plex Mono*, *Iosevka* (condensed monospace allowing ~25% more characters per line in payload snippets), and *Hack* (high-contrast terminal standard).
- **Reports & Exports**: Added *Source Serif 4 / Pro* (executive report serif), *Lato* (modern pentest agency standard sans), and *Cambria* (native Windows print serif).

## Compatibility and upgrade

- Python 3.10 through 3.13
- Windows and Linux (X11 & Wayland)
- Fully compatible with existing v2.0.x project configurations, cheat sheets, reports, and pentest mode sessions.
