# OWASP Top 10 — Security Control and Test Matrix

## 1. Purpose

This document maps OWASP Top 10 application security categories to implemented controls, verification methods, and available evidence for the Secure HR Platform.

A control shall only be marked PASS when its implementation and relevant verification evidence have been reviewed.

## 2. Status Definitions

* **PASS** — Relevant controls and verification evidence have been reviewed successfully.
* **IN PROGRESS** — Implementation or verification is incomplete.
* **REVIEW REQUIRED** — Further verification is required before assigning a final status.
* **N/A** — Not applicable, with a documented rationale.

## 3. Control and Test Matrix

| OWASP Category                                   | Security Control                                                                                | Verification Method                                                                  | Evidence                                                                                                                            | Status                                                |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| A01 — Broken Access Control                      | RBAC, object-level permissions, protection against IDOR and privilege escalation                | Authorization and permission regression tests                                        | `backend/employees/tests.py`; `backend/accounts/tests.py`                                                                           | PASS — previous test results recorded                 |
| A02 — Cryptographic Failures                     | Protection of sensitive bank account data and secure password hashing                           | Encryption, serialization, and sensitive-data protection tests                       | `backend/employees/encryption.py`; related employee tests                                                                           | PASS — previous test results recorded                 |
| A03 — Injection                                  | Input validation and safe ORM-based database access                                             | Invalid-input and injection regression tests                                         | Employee and account test suites                                                                                                    | PASS — previous test results recorded                 |
| A04 — Insecure Design                            | Server-side business rules and security requirements                                            | Business-rule and authorization tests                                                | `docs/security/security-requirements.md`; relevant application tests                                                                | PASS — previous test results recorded                 |
| A05 — Security Misconfiguration                  | Secure Django configuration and controlled error handling                                       | Django system checks and configuration review                                        | `backend/config/settings.py`; `python manage.py check`                                                                              | PASS — system check succeeded                         |
| A06 — Vulnerable and Outdated Components         | Pinned dependencies, dependency auditing, and hash-verified installation                        | `python -m pip_audit`; installation with `--require-hashes`                          | `requirements.txt`; `requirements.lock`; audit output                                                                               | PASS — no known vulnerabilities reported by the audit |
| A07 — Identification and Authentication Failures | Password security, authentication controls, JWT expiration, rotation, and blacklist             | Authentication and token lifecycle tests                                             | `backend/accounts/tests.py`                                                                                                         | PASS — previous test results recorded                 |
| A08 — Software and Data Integrity Failures       | Dependency integrity, JWT signature validation, migration consistency, and secure data handling | Dependency audit, hash verification, JWT tampering test, and Django migration checks | `requirements.lock`; `backend/accounts/tests.py`; Django migration commands; Section 28 of `docs/security/security-requirements.md` | IN PROGRESS — additional evidence review required     |
| A09 — Security Logging and Monitoring Failures   | Security event generation, structured logging, and SIEM detection                               | Security event tests and SIEM verification                                           | `docs/security/logging-siem-requirements.md`; `backend/accounts/siem.py`; related tests                                             | PASS — previous test results recorded                 |
|A10 — Server-Side Request Forgery (SSRF) | Review of server-side URL fetching and user-controlled outbound requests | Code review and search for outbound HTTP request mechanisms | Backend code review: targeted searches for outbound HTTP calls and user-controlled remote URLs; no application-code matches found for the searched patterns. Full deployment/configuration review remains required. | REVIEW REQUIRED — targeted searches found no matches; full review remains pending |
                                     |

## 4. A08 Verification Evidence

The following checks have been performed during the A08 review:

| Verification                           | Result                                            |
| -------------------------------------- | ------------------------------------------------- |
| Dependency vulnerability audit         | No known vulnerabilities reported                 |
| Lockfile generated with SHA-256 hashes | Completed                                         |
| Hash-verified dependency download      | Successful                                        |
| Tampered JWT access token rejected     | Test passed                                       |
| Token management test class            | 6 tests passed                                    |
| Django migration inspection            | All displayed migrations applied                  |
| Missing model migrations check         | `No changes detected`                             |
| File upload mechanism search           | No matches found for the searched upload patterns |
| Unsafe deserialization search          | No matches found for the searched patterns        |

These results are evidence for the specific checks performed. They do not independently prove that every A08 risk has been eliminated.

## 5. Evidence and Status Maintenance

For each category:

1. Identify the relevant implementation.
2. Run the applicable automated tests or manual checks.
3. Record the command, result, and evidence location.
4. Investigate failures before changing the status.
5. Reassess the status whenever security-sensitive code or dependencies change.

The matrix shall be updated as part of security regression testing and release preparation.
