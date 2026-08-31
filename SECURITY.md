# Security Policy

## Supported versions

Security fixes are provided for the latest `2.x` release and the current
`main` branch. Older releases are not maintained.

| Version | Supported |
| --- | --- |
| 2.x | Yes |
| 1.x and earlier | No |

## Reporting a vulnerability

Do not include exploit details, sensitive target data, credentials, or proof-of-
concept payloads in a public issue.

Use GitHub's private vulnerability reporting page:

<https://github.com/m1thraz/SpectreHUD/security/advisories/new>

If private reporting is unavailable, open a minimal public issue stating only
that you need a private security contact. Do not describe the vulnerability in
that issue.

Please include, where possible:

- affected SpectreHUD version and operating system;
- a concise description of the impact and required preconditions;
- reproduction steps using synthetic data;
- whether customer-facing exported files are involved;
- suggested remediation, if known.

Reports will be acknowledged as time permits. Valid reports are investigated
privately, fixed on a coordinated timeline, and credited with the reporter's
permission. This is a volunteer portfolio project and does not offer a response
time SLA.

## Security scope

SpectreHUD is a local, single-user desktop application without a remote service
or multi-tenant boundary. Relevant reports include vulnerabilities affecting:

- project-data integrity or unintended loss during normal operation;
- Pentest Mode confidentiality or key handling;
- customer-facing HTML or other exported artifacts;
- dependency or packaging integrity;
- a boundary explicitly documented in the
  [threat model](docs/threat_model.md).

Malware already running as the user, a compromised operating system, and
intentionally hostile local files outside the documented import/export
boundaries are not part of the supported threat model. Reliability bugs are
still welcome through the normal bug-report template.
