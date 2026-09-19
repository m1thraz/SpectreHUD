<!-- spectre:section:start:header_metadata -->

# Security Assessment Report: Northstar Research Portal

| Property | Value |
|---|---|
| Client / Organization | Northstar Research Labs (Fictional) |
| Lead Tester | Example Security Team |
| Scope / Target | portal.example.test / 192.0.2.0/24 |
| Assessment Period | 2026-09-08 - 2026-09-12 |
| Report Date | 2026-09-19 |
| Classification | DEMO - SYNTHETIC DATA |
| Report Version | v1.0 |

<!-- spectre:section:end:header_metadata -->

<!-- spectre:section:start:executive_summary -->

## 1. Executive Summary

This demonstration report presents a fictional external assessment of the Northstar
Research Portal. All organizations, systems, accounts, observations, and evidence are
synthetic and exist only to illustrate SpectreHUD's Professional Print output.

### Findings Matrix

| ID | Finding | Severity | Phase | Status |
|---|---|---|---|---|
| 1 | Administrative Export Authorization Bypass | CRITICAL | access | Open |
| 2 | Stored Operator Note Injection | HIGH | access | In Progress |
| 3 | Shared Deployment Credential | MEDIUM | privesc | Accepted Risk |
| 4 | Verbose Build Metadata | LOW | recon | Resolved |

**Total:** <span class="severity-pill severity-critical">CRITICAL</span> 1 · <span class="severity-pill severity-high">HIGH</span> 1 · <span class="severity-pill severity-medium">MEDIUM</span> 1 · <span class="severity-pill severity-low">LOW</span> 1

### Key Highlights

- **Initial Access Vector:** An unauthenticated preview route exposed administrative export behavior.
- **Privilege Escalation:** A shared deployment credential expanded access to the background worker.
- **Business Impact & Risk:** A successful chain could expose synthetic research records and alter queued exports.
- **Recommended Remediation:** Enforce server-side authorization, isolate service credentials, and apply contextual output encoding.

<!-- spectre:section:end:executive_summary -->

<!-- spectre:section:start:scope_limitations -->

## 2. Scope & Methodology

Testing covered the fictional public portal, its documented API, and one representative
worker host. Activities combined authenticated and unauthenticated application testing,
configuration review, and controlled validation of the identified attack path.

| Target | Purpose | Test perspective |
|---|---|---|
| `portal.example.test` | Public research portal | External / unauthenticated |
| `api.portal.example.test` | Portal API | External / authenticated |
| `192.0.2.45` | Demonstration worker | Internal validation |

The example intentionally excludes denial-of-service testing, social engineering, and
third-party infrastructure. No real systems were contacted.

<!-- spectre:section:end:scope_limitations -->

<!-- spectre:section:start:attack_path -->

## 3. Attack Path

The demonstration chain shows how individually understandable observations can combine
into a material business risk.

### Attack Chain

1. **Reconnaissance & Enumeration**: Public portal routes identified
   - *Description:* Build metadata disclosed an internal export route and worker naming convention.
   - *Finding:* Verbose Build Metadata <!-- finding:finding-004 -->
2. **Initial Access & Exploitation**: Administrative export requested without authorization
   - *Description:* The preview route accepted a crafted export identifier before enforcing an authenticated role.
   - *Finding:* Administrative Export Authorization Bypass <!-- finding:finding-001 -->
3. **Privilege Escalation**: Worker context accessed through a shared credential
   - *Description:* A credential reused across demonstration services expanded access to the export worker.
   - *Finding:* Shared Deployment Credential <!-- finding:finding-003 -->

<!-- spectre:section:end:attack_path -->

<!-- spectre:section:start:finding_section -->

<!-- spectre:pagebreak -->

## 4. Technical Findings

<!-- spectre:finding:start:finding-001 -->
### Administrative Export Authorization Bypass

**Severity:** <span class="severity-pill severity-critical">CRITICAL</span>  
**CVSS Score:** `9.1`  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`  
**Target:** `api.portal.example.test, 192.0.2.45`  
**Phase:** Initial Access & Exploitation  
**Observed:** `2026-09-09 10:24:00`  
**Status:** Open

#### Description

The synthetic export-preview endpoint accepted an administrative export identifier before
verifying the caller's role. A controlled request returned a demonstration record belonging
to another fictional tenant.

```http
GET /api/v1/exports/demo-1042/preview HTTP/1.1
Host: api.portal.example.test
Accept: application/json

HTTP/1.1 200 OK
Content-Type: application/json

{"record":"synthetic-study-07","classification":"DEMO"}
```

No bulk extraction was attempted. The response above was sufficient to confirm the missing
object-level authorization check.

#### Recommendation

Apply deny-by-default authorization to every export operation, verify tenant ownership on
the server, and add negative authorization tests for direct object references.

#### References

- OWASP API Security Top 10: Broken Object Level Authorization
- CWE-639: Authorization Bypass Through User-Controlled Key

<!-- spectre:finding:end:finding-001 -->

<!-- spectre:finding:start:finding-002 -->
### Stored Operator Note Injection

**Severity:** <span class="severity-pill severity-high">HIGH</span>  
**CVSS Score:** `8.0`  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:H/A:H`  
**Target:** `portal.example.test`  
**Phase:** Initial Access & Exploitation  
**Observed:** `2026-09-09 13:40:00`  
**Status:** In Progress

#### Description

Operator notes were stored without contextual output encoding. A benign demonstration marker
was rendered as markup when an administrator opened the queued export review.

```html
<strong data-demo="synthetic">Review marker</strong>
```

The validation used a non-executable marker and did not attempt session access or browser
interaction beyond confirming that stored markup was interpreted.

#### Recommendation

Encode untrusted notes for the destination context, enforce a restrictive content security
policy, and sanitize previously stored values before displaying them to operators.

#### References

- OWASP Cross Site Scripting Prevention Cheat Sheet
- CWE-79: Improper Neutralization of Input During Web Page Generation

<!-- spectre:finding:end:finding-002 -->

<!-- spectre:finding:start:finding-003 -->
### Shared Deployment Credential

**Severity:** <span class="severity-pill severity-medium">MEDIUM</span>  
**CVSS Score:** `6.5`  
**CVSS Vector:** `CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N`  
**Target:** `192.0.2.45`  
**Phase:** Privilege Escalation  
**Observed:** `2026-09-10 09:18:00`  
**Status:** Accepted Risk

#### Description

A fictional deployment credential was shared by two worker services. Compromise of either
service would therefore provide unnecessary access to the other's queue. The value itself is
intentionally omitted from this public example.

#### Recommendation

Issue unique, scoped credentials per service and rotate the shared demonstration value.

<!-- spectre:finding:end:finding-003 -->

<!-- spectre:pagebreak -->

<!-- spectre:finding:start:finding-004 -->
### Verbose Build Metadata

**Severity:** <span class="severity-pill severity-low">LOW</span>  
**CVSS Score:** `3.7`  
**CVSS Vector:** `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N`  
**Target:** `portal.example.test`  
**Phase:** Reconnaissance & Enumeration  
**Observed:** `2026-09-08 14:05:00`  
**Status:** Resolved

#### Description

The public diagnostics response disclosed a build label and an internal worker alias. The
information reduced the effort required to identify the synthetic export workflow.

```json
{"build":"demo-2026.09","worker":"northstar-export-01"}
```

#### Recommendation

Return only a generic health indicator to unauthenticated callers and keep deployment metadata
in authenticated operational tooling.

#### References

- CWE-200: Exposure of Sensitive Information to an Unauthorized Actor

<!-- spectre:finding:end:finding-004 -->

<!-- spectre:section:end:finding_section -->

<!-- spectre:pagebreak -->

<!-- spectre:section:start:remediation_table -->

## 5. Remediation & Action Plan

Address authorization and stored-output handling first, then separate service identities and
remove unnecessary diagnostic detail.

| Severity | Vulnerability | Recommended Action | Status |
|---|---|---|---|
| CRITICAL | F-001 · Administrative Export Authorization Bypass | Enforce object- and tenant-level authorization on every export route. | Open |
| HIGH | F-002 · Stored Operator Note Injection | Encode stored notes and deploy a restrictive content security policy. | In Progress |
| MEDIUM | F-003 · Shared Deployment Credential | Issue scoped per-service credentials and rotate the shared value. | Accepted Risk |
| LOW | F-004 · Verbose Build Metadata | Keep build and worker identifiers out of public diagnostics. | Resolved |

### Suggested Validation Sequence

1. Add negative authorization tests for cross-tenant export identifiers.
2. Re-test stored notes in every operator rendering context.
3. Verify each service can access only its own queue and secret.
4. Confirm unauthenticated diagnostics contain no deployment metadata.

<!-- spectre:section:end:remediation_table -->

<!-- spectre:section:start:appendix -->

## 6. Appendix & Evidence

### Appendix A: Executed Demonstration Commands

```bash
curl -sS -H "Accept: application/json" \
  https://api.portal.example.test/api/v1/exports/demo-1042/preview

curl -sS https://portal.example.test/health
```

### Appendix B: Evidence Handling

- All identifiers and responses in this report are synthetic.
- `192.0.2.0/24` is reserved for documentation and examples.
- The `.test` top-level domain is reserved for testing.
- No credentials, customer names, production endpoints, or real assessment data are included.

### Appendix C: Report Notice

This file is a product demonstration generated by SpectreHUD. It must not be interpreted as
evidence of an assessment against a real organization or system.

<!-- spectre:section:end:appendix -->
