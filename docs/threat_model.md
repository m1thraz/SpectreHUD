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

## Review queue for adversarial-style tests

The following tests are intentionally retained for now. They require an
explicit keep, simplify, or remove decision before future cleanup; their
presence alone is not a claim that SpectreHUD has a hostile-file threat model.

| Test | Why it needs a decision |
| --- | --- |
| `test_adversarial_regressions.py::test_project_name_cannot_escape_workspace` | Treats local project names as an attack vector; it may be sufficient as ordinary input validation. |
| `test_adversarial_regressions.py::test_registry_purge_persists_single_instance_state_and_restart` | Models a manipulated symlink registry entry, which assumes local hostile file access. |
| `test_adversarial_regressions.py::test_cross_project_screenshot_resolution_isolation` | Could be kept as ordinary project-isolation correctness rather than spoofing defence. |
| `test_adversarial_regressions.py::test_report_document_blocks_path_traversal_and_absolute_outside_images` | Better classified as report-image resolver behaviour than local file-disclosure defence. |
| `test_adversarial_regressions.py::test_invalid_project_lookup_does_not_mutate_default` | Overlaps invalid-name handling and uses traversal-style input. |
| `test_html_report_exporter.py::test_sandbox_path_traversal_image_blocked` | Uses a local image path outside a user-selected project. |
| `test_html_report_exporter.py::test_xss_prevention_in_images_and_links` | Uses browser payloads in locally authored report content. |
| `test_html_report_exporter.py::test_download_filename_is_safe_for_the_inline_script` | Uses script injection through a self-chosen project name. |
| `test_html_report_exporter.py::test_protocol_relative_urls_blocked` | Assumes web-payload input in a local report. |
| `test_html_report_exporter.py::test_image_embedding_budget_limit` | Tests an artificial image-volume limit; this is performance policy, not an attacker boundary. |
| `test_html_report_exporter.py::test_code_fence_language_is_html_escaped` | Uses browser attribute injection through local Markdown. |
| `test_obsidian_exporter.py::test_obsidian_export_rejects_unsafe_paths_and_symlink_attachment` | Assumes a symlink or unsafe export path was planted locally. |
| `test_cherrytree_exporter.py::test_cherrytree_export_rejects_missing_project_and_unsafe_name` | The missing-folder case is normal recovery; the unsafe-name case is a separate local-path scenario. |
| `test_snippet_importer.py::test_import_oversized_file_rejected` | Treats a self-imported five-megabyte file as a denial-of-service input. |
| `test_report_file_manager.py::test_save_rejects_report_larger_than_its_read_limit` | Defines a product-size limit rather than a security boundary. |
| `test_report_file_manager.py::test_failed_oversized_save_preserves_previous_report` | Combines a useful rollback assertion with an artificial size-limit trigger. |
| `test_validators.py::test_size_and_count_bounding_limits` | Uses intentionally huge strings and collections as a resource-exhaustion scenario. |
| `test_validators.py::test_is_file_size_valid` | Is a utility boundary test unless hostile files are explicitly in scope. |
