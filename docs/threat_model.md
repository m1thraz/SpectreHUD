# SpectreHUD Threat Model

## Deployment model

SpectreHUD is a single-user CTF and pentest notebook. It has no HTTP service,
network listener, remote-client trust boundary, or multi-user workspace. The
single-instance lock prevents accidental concurrent writes from two local
application processes.

The application is not designed as a hostile-file processing service. Files,
templates, snippets, and reports are normally created, selected, and imported
by the same user who runs the application. A malicious process with write
access to that user's account is outside SpectreHUD's security boundary.

## Security objectives

1. **Data integrity.** A failed write, project switch, screenshot capture, or
   shutdown must not silently lose session state or leave a committed-looking
   partial result.
2. **Usable recovery.** Corrupted or missing application files must result in
   a clear fallback or error, rather than an unusable application state.
3. **Normal input validation.** Project and template names must remain valid
   filenames and must not accidentally select or overwrite another project.
4. **Correct output.** User content such as commands, passwords, and Markdown
   must render as intended in generated reports.

## Explicitly out of scope

SpectreHUD does not try to defend against a compromised operating system,
malware running as the same user, physical access to an unlocked machine, a
malicious project archive, a symlink race, or an intentionally enormous and
deeply nested payload. It also cannot make data confidential after it has
been exported to an ordinary HTML, Markdown, or archive file.

## Test curation policy

Tests are organized by the user-visible failure they prevent, not by a
hypothetical hostile-input matrix:

| Boundary | What is retained |
| --- | --- |
| Persistence and workflows | Atomic writes, rollback, recovery, and shutdown invariants |
| Project handling | Invalid names and name collisions must not overwrite or select another project |
| Local file recovery | Ordinary malformed or missing state files recover safely |
| Report generation | Commands, credentials, and Markdown remain structurally correct |

Equivalent checks are removed when a broader test already proves the
invariant. Deliberately adversarial scenarios belong in a product with a
matching trust boundary; for this local desktop application they would add
noise without increasing confidence in normal use.
