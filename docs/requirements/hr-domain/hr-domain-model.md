# Secure HR Platform — HR Domain Model

## 1. Purpose

This document defines the core business entities and relationships of the Secure HR Platform.

The domain model establishes the foundation for the future database schema, REST API resources, authorization rules, and HR workflows.

The model is intentionally designed to separate:

* Identity
* HR information
* Organizational structure
* HR requests
* Security and authorization

---

## 2. Domain Overview

The initial HR domain consists of the following core entities:

```text
User
 │
 ├── Role / Permissions
 │
 └── Employee
       │
       ├── Department
       │
       ├── Position
       │
       └── Leave Requests
```

The security domain will additionally track activities performed by users through audit and security events.

---

## 3. User

### Purpose

The `User` entity represents an account that can authenticate to the platform.

A user is primarily an identity and authentication object.

### Responsibilities

A user is responsible for:

* Authentication.
* Account status.
* Password management.
* Role assignment.
* Access to protected API resources.

### Conceptual Attributes

```text
User
├── id
├── email
├── password
├── is_active
├── created_at
└── updated_at
```

The password shall never be stored in plaintext.

Django's secure password hashing mechanisms shall be used.

---

## 4. Employee

### Purpose

The `Employee` entity represents a person employed by the organization.

An employee record contains HR information that is distinct from authentication credentials.

### Conceptual Attributes

```text
Employee
├── id
├── user
├── employee_number
├── first_name
├── last_name
├── date_of_birth
├── phone
├── address
├── hire_date
├── employment_status
├── department
├── position
├── created_at
└── updated_at
```

### Security Considerations

Employee information is sensitive.

Access shall therefore be controlled using:

* Authentication.
* RBAC.
* Object-level authorization.
* Least privilege.

Employees should normally be able to access their own permitted information.

HR personnel may access employee information according to their assigned permissions.

---

## 5. Department

### Purpose

The `Department` entity represents an organizational unit.

Examples:

* Human Resources
* Information Technology
* Finance
* Security
* Operations

### Conceptual Attributes

```text
Department
├── id
├── name
├── description
├── manager
├── is_active
├── created_at
└── updated_at
```

### Relationships

A department may contain multiple employees.

```text
Department
    │
    ├── Employee
    ├── Employee
    └── Employee
```

A department may also contain multiple positions.

---

## 6. Position

### Purpose

The `Position` entity represents a job or role within the organization's organizational structure.

Examples:

* Software Engineer
* Security Analyst
* HR Manager
* Accountant
* Network Administrator

A position is not the same as an application security role.

For example:

```text
Position:
Security Analyst

Application Role:
Security Administrator
```

A person may hold a job position without receiving the corresponding administrative permissions in the application.

### Conceptual Attributes

```text
Position
├── id
├── title
├── description
├── department
├── level
├── is_active
├── created_at
└── updated_at
```

### Security Consideration

Application permissions shall not be automatically granted solely because of a job position.

Application roles and HR job positions must remain separate concepts.

---

## 7. Leave Request

### Purpose

The `LeaveRequest` entity represents an employee request to be absent from work for an approved reason.

Examples include:

* Vacation
* Sick leave
* Personal leave
* Parental leave
* Bereavement leave

### Conceptual Attributes

```text
LeaveRequest
├── id
├── employee
├── leave_type
├── start_date
├── end_date
├── reason
├── status
├── reviewed_by
├── reviewed_at
├── created_at
└── updated_at
```

### Possible Statuses

```text
PENDING
APPROVED
REJECTED
CANCELLED
```

### Workflow

```text
Employee
   │
   │ Submit request
   ▼
LeaveRequest
   │
   │ PENDING
   ▼
Authorized HR User
   │
   ├── APPROVE
   │
   └── REJECT
```

Employees should only be able to view and manage their own leave requests unless their role provides broader access.

Authorized HR users may review requests according to their permissions.

---

## Payroll Domain

The Payroll domain manages employee compensation, payroll calculations, deductions, earnings, and payment records.

### Payroll

Represents an employee's payroll record for a specific pay period.

A payroll record may contain:

- Base salary
- Total earnings
- Total deductions
- Net pay
- Payroll status
- Pay period
- Processing and approval information

Payroll records contain highly sensitive financial information and require strict access control and auditability.

### PayPeriod

Represents a defined period for payroll processing.

Examples:

- September 1–15
- September 16–30
- Monthly payroll period

A pay period may contain payroll records for multiple employees.

### Earning

Represents an amount added to an employee's compensation.

Examples:

- Base salary
- Overtime
- Bonus
- Commission
- Allowance

### Deduction

Represents an amount deducted from an employee's compensation.

Examples:

- Taxes
- Insurance
- Retirement contributions
- Other authorized deductions

### Payment

Represents the actual payment associated with a payroll record.

A payment may contain:

- Payment date
- Payment amount
- Payment status
- Payment method
- Transaction reference

The Payment entity is intentionally separated from Payroll.

Payroll represents the calculation and financial record, while Payment represents the actual disbursement.

### Payroll Relationships

```text
Employee 1 ─ * Payroll
PayPeriod 1 ─ * Payroll
Payroll 1 ─ * Earning
Payroll 1 ─ * Deduction
Payroll 1 ─ 1 Payment

## 8. Application Role

### Purpose

Application roles define what actions a user is authorized to perform inside the platform.

Initial roles include:

```text
EMPLOYEE
HR_STAFF
HR_ADMIN
SECURITY_ADMIN
SYSTEM_ADMIN
```

### Important Separation

Application roles are separate from HR job positions.

For example:

```text
Employee
   │
   ├── Position: Security Analyst
   │
   └── Application Role: Employee
```

A Security Analyst does not automatically become a Security Administrator.

This separation supports the principle of least privilege.

---

## 9. Permission

Permissions define specific actions that a user may perform.

Examples:


employee.view_self
employee.view_all
employee.create
employee.update
employee.deactivate

department.view
department.create
department.update

position.view
position.create
position.update

leave.create
leave.view_self
leave.view_all
leave.approve
leave.reject

security_event.view
audit_log.view

user.role_change
user.deactivate

Permissions shall be enforced server-side.

10. Security Event

The SecurityEvent entity belongs primarily to the security/audit domain rather than the HR domain.

It records security-relevant application activity.

Examples:

LOGIN_SUCCESS
LOGIN_FAILED
BRUTE_FORCE_DETECTED
UNAUTHORIZED_ACCESS
PASSWORD_CHANGED
ACCOUNT_ACTIVATED
ACCOUNT_DEACTIVATED
ACCOUNT_CHANGE
ROLE_CHANGED
PRIVILEGE_CHANGE
Conceptual Attributes
SecurityEvent
├── id
├── event_type
├── user
├── ip_address
├── user_agent
├── request_path
├── details
└── created_at

Security events shall be designed for SIEM ingestion.

11. Relationships
User → Employee

A user account may be associated with an employee record.

User 1 ───── 0..1 Employee

This allows authentication identity to remain separate from HR information.

Department → Employee

A department may contain many employees.

Department 1 ───── * Employee
Department → Position

A department may contain multiple positions.

Department 1 ───── * Position
Position → Employee

A position may be assigned to multiple employees depending on the organization's structure.

Position 1 ───── * Employee
Employee → LeaveRequest

An employee may submit multiple leave requests.

Employee 1 ───── * LeaveRequest
User → SecurityEvent

A user may generate multiple security events.

User 1 ───── * SecurityEvent

Security events may also exist without an authenticated user, for example a failed authentication attempt against a nonexistent account.

12. Domain Separation

The platform should maintain a clear separation between the following domains:

Identity Domain
│
├── User
├── Authentication
└── Account Status

HR Domain
│
├── Employee
├── Department
├── Position
└── LeaveRequest

Authorization Domain
│
├── Roles
└── Permissions

Security Domain
│
├── SecurityEvent
├── Audit
└── Detection

Infrastructure Domain
│
├── Application
├── Database
├── SIEM
└── Monitoring

This separation will help maintain a clean architecture as the application grows.

13. Sensitive Data Classification

The following data should be considered sensitive:

High Sensitivity
Password hashes
Authentication tokens
Employee personal information
Date of birth
Address
Security events
Authentication activity
Authorization information
Moderate Sensitivity
Employee number
Department
Position
Employment status
Leave information
Lower Sensitivity
Public organizational information
Generic department descriptions
Generic position descriptions

Actual classification may be refined according to organizational requirements.

14. Data Access Principles

The platform shall apply the following rules:

Employee

May access:

Own permitted profile.
Own leave requests.
Other information explicitly authorized.
HR Staff

May access:

Employee information required for HR responsibilities.
HR requests.
Organizational information.
HR Administrator

May access:

Broader HR records.
Employee management functions.
Organizational management.
Authorized user-management functions.
Security Administrator

May access:

Security events.
Audit information.
Security monitoring information.

Access to HR information shall not automatically be granted unless explicitly required.

System Administrator

May manage:

System configuration.
Infrastructure-related operations.
Authorized administrative functions.

System administration privileges shall not automatically imply unrestricted access to HR data.

15. Future Domain Extensions

The architecture should allow future entities such as:

Payroll
Benefits
Performance Review
Recruitment
Training
Employee Documents
Attendance
Timesheets

These entities are outside the initial implementation scope.

16. Initial Domain Model

The initial implementation will focus on:

                    ┌──────────────┐
                    │     User     │
                    └──────┬───────┘
                           │
                           │ 0..1
                           ▼
                    ┌──────────────┐
                    │   Employee   │
                    └──────┬───────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
      ┌────────────┐ ┌───────────┐ ┌──────────────┐
      │ Department │ │ Position  │ │ LeaveRequest │
      └────────────┘ └───────────┘ └──────────────┘
                           │
                           │
                           ▼
                    Authorization
                    Roles / Permissions

User ──────────────────────────────► SecurityEvent

This model provides the initial foundation for the database schema and API design.

17. Domain Model Principles

The HR domain shall follow these principles:

1.Keep authentication separate from HR information.
2.Keep job positions separate from application 3.security roles.
4.Apply least privilege to HR information.
5.Enforce object-level authorization for employee data.
6.Treat employee information as sensitive.
7.Maintain auditability for sensitive operations.
8.Design security events for SIEM integration.
9.Keep the domain extensible for future HR capabilities.
