# Logging and SIEM Requirements

## 1. Purpose

This document defines the logging, security event, monitoring, and SIEM requirements for the Secure HR Platform.

The objective is to provide reliable security visibility across the application and infrastructure while minimizing the exposure of sensitive HR information.

The logging architecture must support:

- Security monitoring
- Threat detection
- Incident investigation
- Auditability
- Compliance-oriented traceability
- MITRE ATT&CK mapping
- Detection engineering
- SOC operations

---

# 2. Logging Objectives

The platform must provide sufficient visibility to answer the following questions:

1. Who performed an action?
2. What action was performed?
3. When did it occur?
4. From where did it originate?
5. What resource was affected?
6. Was the action authorized?
7. Was the action successful?
8. Was the activity suspicious?
9. What security events occurred before and after the activity?

Logs must support investigation without unnecessarily storing sensitive HR information.

---

# 3. Logging Categories

The platform will use several categories of logs.

## 3.1 Authentication Events

Examples:

- LOGIN_SUCCESS
- LOGIN_FAILED
- LOGOUT
- TOKEN_REFRESH
- ACCOUNT_LOCKED
- ACCOUNT_DEACTIVATED

Authentication events are critical for detecting credential attacks.

---

## 3.2 Authorization Events

Examples:

- UNAUTHORIZED_ACCESS
- FORBIDDEN_OPERATION
- OBJECT_ACCESS_DENIED
- PRIVILEGE_ESCALATION_ATTEMPT

These events help detect authorization bypass attempts.

---

## 3.3 Account Management Events

Examples:

- ACCOUNT_CREATED
- ACCOUNT_ACTIVATED
- ACCOUNT_DEACTIVATED
- ACCOUNT_CHANGE
- PASSWORD_CHANGED
- PASSWORD_RESET_REQUESTED
- PASSWORD_RESET_COMPLETED

---

## 3.4 HR Administrative Events

Examples:

- EMPLOYEE_CREATED
- EMPLOYEE_UPDATED
- EMPLOYEE_DELETED
- DEPARTMENT_CREATED
- DEPARTMENT_UPDATED
- POSITION_CREATED
- POSITION_UPDATED
- LEAVE_APPROVED
- LEAVE_REJECTED

These events provide accountability for sensitive HR operations.

---

## 3.5 Security Detection Events

Examples:

- BRUTE_FORCE_DETECTED
- SUSPICIOUS_IP_DETECTED
- MULTIPLE_UNAUTHORIZED_ACCESS
- PRIVILEGE_ESCALATION_DETECTED
- SUSPICIOUS_ADMIN_ACTIVITY

These events represent higher-level detections rather than individual application actions.

---

# 4. Security Event Structure

Security events should use a structured format.

A conceptual event should contain fields such as:

```json
{
  "@timestamp": "2026-09-13T00:00:00Z",
  "event.action": "LOGIN_FAILED",
  "event.category": "authentication",
  "event.outcome": "failure",
  "source.ip": "192.0.2.10",
  "url.path": "/api/login/",
  "user.id": "123",
  "user_agent.original": "Mozilla/5.0",
  "message": "Authentication attempt failed"
}

## Payroll and Payment Security Monitoring

Payroll and payment operations shall be monitored because they involve highly sensitive financial information and potentially high-impact actions.

### Payroll Events

The platform shall generate structured security or audit events for sensitive payroll operations, including:

- `PAYROLL_VIEWED`
- `PAYROLL_CREATED`
- `PAYROLL_MODIFIED`
- `PAYROLL_APPROVED`
- `PAYROLL_FINALIZED`
- `PAYMENT_INITIATED`
- `PAYMENT_PROCESSED`
- `PAYMENT_FAILED`
- `PAYMENT_STATUS_CHANGED`
- `UNAUTHORIZED_PAYROLL_ACCESS`

### Payroll Event Context

Where applicable, payroll security events should contain:

- `@timestamp`
- `event.action`
- `event.category`
- `event.outcome`
- `source.ip`
- `url.path`
- `user.id`
- `user_agent.original`
- `message`
- Relevant object or employee identifier
- Authorization context

Security events should provide sufficient information for investigation while minimizing unnecessary exposure of financial data.

### Sensitive Payroll Data Protection

SIEM events shall not contain unnecessary sensitive financial information.

The logging system shall never store:

- Passwords
- Authentication tokens
- API keys
- Database credentials
- Full payment credentials
- Full bank account information
- Unnecessary salary or financial details

Where financial information is required for investigation, the system should use identifiers or summarized information instead of exposing complete sensitive values.

### Payroll Detection Rules

The SIEM should support detection rules for suspicious payroll activity.

#### Unauthorized Payroll Access

Detect attempts to access payroll information without sufficient authorization.

Example event:

```text
event.action: UNAUTHORIZED_PAYROLL_ACCESS
