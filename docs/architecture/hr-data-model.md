# HR Data Model and Relationships

## 1. Purpose

This document describes the current data model of the Secure HR Platform and identifies the proposed relationships required for future HR document management and employee onboarding.

It distinguishes implemented functionality from planned architecture.

## 2. Existing Data Model

### Organization

* **Department**: represents an HR department.
* **Position**: represents a job position belonging to a department.
* **EmployeeProfile**: stores HR information associated with a user account, department, and position.

### Employee lifecycle and HR operations

* **LeaveRequest**: records leave requests, their status, and review information.
* **PerformanceReview**: records employee performance reviews and their reviewer.
* **BankAccount**: stores employee banking information with encrypted sensitive fields.
* **Payroll**: represents payroll processing.
* **PayPeriod**: represents a payroll period.
* **PayrollRecord**: associates payroll processing with employee-related records.
* **Earning**: represents a payroll earning.
* **Deduction**: represents a payroll deduction.
* **Payment**: represents a payment record.

### Security and auditability

* **User**: represents an authenticated account and its role.
* **AuditLog**: records audit information.
* **SecurityEvent**: stores security-related events.

## 3. Implemented Relationships

| Relationship                        | Cardinality | Purpose                                         |
| ----------------------------------- | ----------- | ----------------------------------------------- |
| User → EmployeeProfile              | One-to-one  | Associates an account with an employee profile  |
| Department → Position               | One-to-many | Organizes positions by department               |
| Department → EmployeeProfile        | One-to-many | Associates employees with departments           |
| Position → EmployeeProfile          | One-to-many | Associates employees with positions             |
| EmployeeProfile → LeaveRequest      | One-to-many | Records employee leave requests                 |
| User → LeaveRequest review          | One-to-many | Identifies the user who reviewed a request      |
| EmployeeProfile → BankAccount       | One-to-many | Associates banking records with an employee     |
| EmployeeProfile → PerformanceReview | One-to-many | Associates performance reviews with an employee |
| User → PerformanceReview reviewer   | One-to-many | Identifies the reviewer                         |
| PayPeriod → Payroll | One-to-one | Associates a payroll with one pay period |
| User → Payroll processor | One-to-many | Identifies the user who processed payroll; optional until processing is completed |
| Payroll → PayrollRecord | One-to-many | Groups employee payroll records under a payroll |
| EmployeeProfile → PayrollRecord | One-to-many | Associates payroll records with employees |
| PayrollRecord → Earning | One-to-many | Records additional earnings |
| PayrollRecord → Deduction | One-to-many | Records payroll deductions |
| PayrollRecord → Payment | One-to-many | Records payments associated with a payroll record |

Payroll relationships must be documented in detail against the actual model definitions before finalizing the payroll portion of this diagram.

## 4. Proposed HR Document Management

**Status: Planned — not currently identified in the models examined.**

A future HR document module may support:

* Employment contracts
* Policy acknowledgments
* Employee-provided documents
* Onboarding forms
* Document metadata, versioning, and retention

Proposed logical relationship:

* EmployeeProfile → HRDocument: one-to-many
* HRDocument → uploaded file: one protected storage object or private storage reference

The final model must define document categories, ownership, access permissions, retention, and deletion rules before implementation.

Sensitive documents must not be publicly accessible. File access must be authorized server-side for every request.

## 5. Proposed Employee Onboarding

**Status: Planned — not currently identified in the models examined.**

A future onboarding module may represent:

* An onboarding process associated with an employee
* Required onboarding tasks
* Task status, deadlines, and completion timestamps
* The user responsible for each task
* References to required HR documents

Proposed logical relationships:

* EmployeeProfile → OnboardingProcess: one-to-many if repeat onboarding processes are supported; otherwise one-to-one
* OnboardingProcess → OnboardingTask: one-to-many
* OnboardingTask → assigned User: optional or required, depending on the workflow
* OnboardingTask → HRDocument: optional reference when a task requires a document

These relationships are proposals and must be confirmed against the intended business workflow.

## 6. Security Requirements

* Enforce role-based and object-level authorization.
* Prevent employees from accessing another employee's records.
* Apply least privilege to HR documents and onboarding tasks.
* Keep uploaded files in private storage.
* Validate file size, file type, and content where applicable.
* Avoid logging document contents, banking information, or other sensitive personal data.
* Record relevant administrative actions in the audit and security-event systems.
* Define retention and secure deletion policies before production deployment.

## 7. Implementation Boundaries

This document does not introduce database models, migrations, API endpoints, or storage infrastructure.

Before implementing the planned modules, define their lifecycle, permissions, audit events, file-storage approach, API contracts, and migration strategy.

## 7. User and Employee Relationship

**Status: Implemented**

The `User` model represents an authentication identity, while `EmployeeProfile` stores the employee's HR information.

The relationship is one-to-one:

* `EmployeeProfile.user` references `settings.AUTH_USER_MODEL`.
* Each employee profile is associated with exactly one user.
* A user can have at most one employee profile.
* The employee profile uses `on_delete=models.CASCADE`; deleting a user therefore deletes the associated employee profile.
* Department and position relationships are protected from deletion while referenced by employee profiles.

The application must not assume that every user account represents an employee. Administrative accounts or other non-employee accounts may exist without an `EmployeeProfile`.

**Security requirements**

* Authentication must be based on the user account, not on an employee ID supplied by the client.
* Employee ownership must be resolved from the authenticated user's relationship to their employee profile.
* Employee IDs and profile IDs must not be treated as authorization credentials.
* Changes to account-to-profile relationships must be authorized and auditable.

## 8. HRDocument

**Status: Planned — not currently implemented**

`HRDocument` will represent a document associated with an employee. It will store document metadata and a reference to a private storage object, not the document's contents directly in the database.

### 8.1 Proposed relationships

* `HRDocument.employee` → `EmployeeProfile`, many-to-one, required.
* `HRDocument.uploaded_by` → `settings.AUTH_USER_MODEL`, many-to-one, required.
* `HRDocument.verified_by` → `settings.AUTH_USER_MODEL`, optional; identifies the user who verified the document.

The employee relationship identifies whose HR record the document belongs to. The uploader and verifier identify the actors responsible for submitting and validating it.

### 8.2 Proposed fields

| Field                      | Purpose                                        |
| -------------------------- | ---------------------------------------------- |
| `employee`                 | Employee to whom the document belongs          |
| `document_type`            | Controlled category of document                |
| `title`                    | Human-readable document title                  |
| `original_filename`        | Sanitized original filename                    |
| `storage_key`              | Private storage identifier; never a public URL |
| `mime_type`                | Validated media type                           |
| `size_bytes`               | File size                                      |
| `checksum`                 | Optional integrity verification value          |
| `status`                   | Document workflow status                       |
| `uploaded_by`              | User who uploaded the document                 |
| `verified_by`              | User who verified the document, if applicable  |
| `uploaded_at`              | Upload timestamp                               |
| `verified_at`              | Verification timestamp                         |
| `expires_at`               | Optional expiration date                       |
| `created_at`, `updated_at` | Record timestamps                              |

The document type should use controlled choices, such as identity document, employment agreement, tax form, certification, or other approved HR document. The final list must reflect actual business requirements.

Proposed statuses:

* `UPLOADED`
* `UNDER_REVIEW`
* `APPROVED`
* `REJECTED`
* `EXPIRED`
* `ARCHIVED`

Status transitions must be validated by the application. For example, only an authorized reviewer may approve or reject a document.

### 8.3 Document storage and metadata protection

* Store files in private storage, outside publicly served static or media directories.
* Use opaque storage keys rather than user-controlled paths.
* Validate file size, extension, actual content type, and allowed formats.
* Apply malware scanning before a document becomes available for normal use.
* Generate download access only after server-side authorization.
* If signed download URLs are used, make them short-lived and avoid logging them.
* Never expose storage keys, filesystem paths, secrets, or unnecessary sensitive metadata through the API.
* Do not store document contents, access tokens, or unnecessary personal information in application logs.
* Define retention, archival, deletion, backup, and incident-response procedures before production deployment.
* Record security-relevant upload, download, verification, status-change, and deletion events without logging file contents.

The database record and storage object must be kept consistent. Deletion and retention workflows must account for both, including failed storage operations and audit requirements.

## 9. HRDocument Permissions and Visibility

**Status: Proposed policy — implementation pending**

Access must be enforced on the server for list, retrieve, upload, update, verification, download, and deletion operations. Hiding a link in the frontend is not an authorization control.

| Role          | Proposed access                                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `SUPER_ADMIN` | Administrative access subject to least-privilege controls and audit logging                                  |
| `HR_ADMIN`    | Manage employee documents and perform authorized verification                                                |
| `HR_MANAGER`  | Access only document categories and employee records explicitly permitted for the manager's responsibilities |
| `EMPLOYEE`    | View their own approved documents and submit documents when permitted or requested                           |

Additional rules:

* Employees must never access another employee's documents by changing an object ID.
* Employees must not approve their own submissions unless an explicitly approved business policy permits it.
* HR managers must not automatically receive access to every sensitive document.
* Highly sensitive categories require stricter authorization where appropriate.
* Document downloads must repeat the authorization check; access to the metadata record alone is insufficient.
* Unauthorized requests must not disclose whether another employee's confidential document exists.
* Sensitive document actions must produce auditable security events.
* Deletion, archival, and retention overrides must be restricted and audited.

The final access matrix must be reconciled with the project's existing RBAC rules before implementation.

## 10. OnboardingProcess

**Status: Planned — not currently implemented**

`OnboardingProcess` will represent the onboarding workflow for an employee.

### 10.1 Proposed relationships

* `OnboardingProcess.employee` → `EmployeeProfile`, many-to-one, required.
* `OnboardingProcess.created_by` → `settings.AUTH_USER_MODEL`, required.
* `OnboardingProcess.coordinator` → `settings.AUTH_USER_MODEL`, optional; identifies the user responsible for coordinating onboarding.

An employee may have multiple onboarding processes over time if the business rules allow re-onboarding. The design must not impose a one-to-one constraint without an explicit requirement.

### 10.2 Proposed fields

* `employee`
* `title`
* `status`
* `start_date`
* `target_completion_date`
* `completed_at`
* `created_by`
* `coordinator`
* `created_at`
* `updated_at`

Proposed statuses:

* `NOT_STARTED`
* `IN_PROGRESS`
* `COMPLETED`
* `CANCELLED`

The application must validate status transitions and prevent a process from being marked completed while required tasks remain incomplete.

## 11. OnboardingTask

**Status: Planned — not currently implemented**

`OnboardingTask` will represent an individual action within an onboarding process.

### 11.1 Proposed relationships

* `OnboardingTask.process` → `OnboardingProcess`, many-to-one, required.
* `OnboardingTask.assigned_to` → `settings.AUTH_USER_MODEL`, optional.
* `OnboardingTask.completed_by` → `settings.AUTH_USER_MODEL`, optional.

A process can contain multiple tasks. Each task belongs to one process and may be assigned to a responsible user.

### 11.2 Proposed fields

* `process`
* `title`
* `description`
* `status`
* `assigned_to`
* `due_date`
* `is_required`
* `sequence`
* `completed_by`
* `completed_at`
* `created_at`
* `updated_at`

Proposed statuses:

* `PENDING`
* `IN_PROGRESS`
* `COMPLETED`
* `BLOCKED`
* `CANCELLED`

Task completion must be authorized and auditable. Required-task completion must be validated before the parent process can transition to `COMPLETED`.

## 12. Onboarding Permissions and Visibility

**Status: Proposed policy — implementation pending**

| Role          | Proposed access                                                                                                  |
| ------------- | ---------------------------------------------------------------------------------------------------------------- |
| `SUPER_ADMIN` | Administrative oversight subject to audit and least privilege                                                    |
| `HR_ADMIN`    | Create and manage onboarding processes and tasks                                                                 |
| `HR_MANAGER`  | Access and manage tasks for employees or processes within the manager's authorized scope                         |
| `EMPLOYEE`    | View their own onboarding progress and tasks; perform only employee actions explicitly permitted by the workflow |

Additional rules:

* Employees may not view or modify another employee's onboarding process or tasks.
* Employees must not reassign tasks, alter administrative fields, or mark restricted tasks complete.
* A task assignment does not automatically grant access to every document belonging to that employee.
* Access to a document requested by an onboarding task must still be authorized under the document access policy.
* Managers may access only the processes and tasks within their assigned scope.
* Administrative changes, task assignments, completion events, cancellations, and status transitions must be auditable.
* Object-level permissions must be enforced on both collection and individual-object endpoints.

## 13. Implementation Status and Scope

### Implemented

* User authentication identity and employee profile relationship.
* Department and position relationships.
* Employee profiles, leave requests, bank accounts, performance reviews, and payroll-related models.
* Existing role-based and object-level access controls for implemented resources, subject to continued validation.

### Planned 

* `HRDocument` model, storage integration, upload and download endpoints.
* Document verification, lifecycle, retention, and archival workflows.
* `OnboardingProcess` and `OnboardingTask` models.
* Onboarding endpoints, task assignment, workflow transitions, and completion rules.
* Document-specific and onboarding-specific authorization policies and audit events.

These planned components must not be described as existing API capabilities until implemented, tested, and documented in the OpenAPI schema.

Implementation should begin only after the proposed relationships, role permissions, data-retention requirements, and file-storage controls have been reviewed.

## 8. Maintenance

Update this document whenever the data model or its relationships change. Keep the documented relationships consistent with Django models, serializers, API permissions, and OpenAPI documentation.
