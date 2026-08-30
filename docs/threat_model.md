# SpectreHUD Threat Model

## Deployment model

SpectreHUD is a single-user CTF and pentest notebook. It has no HTTP service,
network listener, remote-client session, or multi-user workspace. The
single-instance lock prevents accidental concurrent writes from two local
application processes.

Files, templates, snippets, and projects are normally selected and maintained
by the same user who runs the application. A malicious process with write
access to that user's account is outside SpectreHUD's security boundary.

## Trust boundaries

### Local application and workspace

The local user controls the application configuration and project files.
Validation in this boundary exists to prevent mistakes, ambiguous paths,
corruption, and silent writes to the wrong project. It is not intended to
defend the user from their own operating-system account.

Loot and report content may nevertheless originate in responses from assessed
systems. Such content is data while it remains inside Qt text controls; it must
not become executable merely because it is later rendered into another format.

### Export delivery to third parties

HTML, Obsidian, and CherryTree exports cross a separate boundary. Reports may
be delivered to customers and opened in their browsers or knowledge-base
applications. Consequently, target-derived Markdown is treated as untrusted at
export time even though SpectreHUD itself is a local desktop tool.

The export boundary therefore requires:

- HTML attribute and code-fence metadata escaping;
- rejection of executable and protocol-relative URL schemes;
- image embedding restricted to the active project;
- attachments and generated paths kept inside the selected export destination;
- structurally valid output that remains inert when opened by a recipient.

These controls protect the generated artifact and its recipient. They do not
promise confidentiality after the user intentionally exports or distributes a
report.

## Security and reliability objectives

1. **Data integrity.** A failed write, project switch, screenshot capture, or
   shutdown must not silently lose session state or leave a committed-looking
   partial result.
2. **Usable recovery.** Corrupted or missing application files must result in
   a clear fallback or error rather than an unusable application state.
3. **Normal input validation.** Project and template names must remain valid
   filenames and must not accidentally select or overwrite another project.
4. **Safe transferable output.** Target-derived content must remain inert in
   reports opened by customers, and exports must not copy unrelated local
   files.
5. **Correct output.** Commands, credentials, Markdown, images, and filenames
   must render as intended in generated reports.

## Explicitly out of scope

SpectreHUD does not try to defend against a compromised operating system,
malware running as the same user, physical access to an unlocked machine, a
malicious project archive, local symlink races, or intentionally enormous and
deeply nested payloads. Product size limits exist for predictable performance
and accidental bad inputs, not as denial-of-service defenses against the local
user.

## Test curation policy

Tests are organized by the user-visible failure or explicit trust boundary they
cover, not by a generic hostile-input matrix:

| Boundary | Retained coverage |
| --- | --- |
| Persistence and workflows | Atomic writes, rollback, recovery, and shutdown invariants |
| Project handling | Invalid names and collisions cannot overwrite or select another project |
| Local file recovery | Ordinary malformed, moved, or missing state recovers safely |
| Customer-facing exports | Active-content escaping, safe URLs, project-scoped images, and destination-scoped attachments |
| Product limits | One representative boundary test per meaningful size or count policy |

Equivalent checks are consolidated when one test can exercise every relevant
consumer without obscuring the invariant. Expensive input matrices are kept
only when the deployment model or export boundary justifies them.

## Recorded curation decisions

- HTML escaping, safe-URL, code-fence, image-sandbox, and Obsidian attachment
  checks are retained because exported artifacts can contain target-derived
  content and are opened by third parties.
- Invalid project lookup and failed-save preservation are classified as data
  integrity, not adversarial defense.
- The symlink-specific registry-purge test was removed. Ordinary discovery,
  persistence, corruption recovery, and restart behavior remain covered.
- Loot-card and report-preview image isolation share one project-scoping
  invariant test while still exercising both consumers.
- File-size, list-count, and image-budget checks are product-policy tests. They
  use minimal representative boundaries instead of resource-exhaustion
  scenarios.
