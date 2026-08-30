# SpectreHUD Threat Model

## Deployment and attacker model

SpectreHUD is a single-user desktop application.  It has no HTTP service, no
network listener, and no multi-user or remote-client trust boundary.  The
single-instance lock deliberately prevents two local application processes
from concurrently mutating the same workspace.

The relevant adversary is therefore not a remote user of a running service.
It is untrusted *content* that reaches the application through a local trust
boundary: imported project folders and archives, report templates, snippets,
Markdown, images, and files changed by sync tools or another local program.
An attacker with unrestricted write access to the user's operating-system
account is outside the application's security boundary.

## Security objectives

1. **Data integrity.** A failed write, project switch, screenshot capture, or
   shutdown must not silently lose session state or leave a committed-looking
   partial result.
2. **Filesystem containment.** Names and imported content must not escape the
   active workspace through traversal, absolute paths, archives, symlinks, or
   junctions.
3. **Bounded ingestion.** Malformed, deeply nested, or oversized local files
   must fail closed or recover to a safe default rather than crash or exhaust
   resources.
4. **Safe presentation.** User-controlled strings rendered as HTML-capable UI
   content or report output must be escaped or otherwise treated as data.

## Explicitly out of scope

SpectreHUD does not try to defend against a compromised operating system,
malware running as the same user, physical access to an unlocked machine, or
an attacker who can alter the application executable.  It also cannot make
data confidential after it has been exported to an ordinary HTML, Markdown,
or archive file.

## Test curation policy

Security tests are organized by the boundary they protect, not by every
spelling of an input payload:

| Boundary | What is retained |
| --- | --- |
| Persistence and workflows | Atomic writes, rollback, recovery, and shutdown invariants |
| Project and import filesystem boundary | One comprehensive project-name escape test plus distinct archive, symlink, and external-import checks |
| Independent file loaders | Size/depth recovery checks where separate production loaders own the parse and fallback behaviour |
| Output boundary | Representative HTML/report escaping and the Qt tooltip escaping contract |

Equivalent unit checks are removed when a broader test at the same boundary
already proves the invariant.  Tests are not removed merely because the
application is local: imported folders, templates, and files remain untrusted
input even in a single-user deployment.
