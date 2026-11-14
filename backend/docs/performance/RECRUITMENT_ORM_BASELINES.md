# Recruitment ORM Query Baselines

**Project:** Secure HR Platform  
**Module:** Recruitment  
**Status:** Initial baseline and post-optimization results documented  
**Scope:** JobPosting, Candidate, and JobApplication service-level and API-level SQL query measurements

## 1. Purpose

This document records SQL query baselines for the Recruitment module.

These measurements provide a reference for identifying unnecessary ORM queries, detecting N+1 query problems, and evaluating future optimizations.

The measurements are diagnostic baselines, not absolute performance limits.

## 2. Measurement Methodology

Measurements were collected using Django's `CaptureQueriesContext`:

```python
with CaptureQueriesContext(connection) as queries:
    response = client.get(url)
```

API-level measurements capture SQL queries executed during the complete HTTP request, including applicable permission checks, serializers, service calls, and response serialization.

Service-level measurements capture queries executed during direct service invocation.

Tests use the existing Django test database and `--keepdb`.

## 3. JobPosting Baselines

### 3.1 HR_ADMIN

| Operation | API-level queries | Service-level queries |
|---|---:|---:|
| Create | 13 | Not measured |
| Update | 13 | 13 |
| Publish | 13 | 13 |
| Close | 13 | 13 |
| Cancel | 13 | 13 |

### 3.2 HR_MANAGER

| Operation | API-level queries | Service-level queries |
|---|---:|---:|
| Create | 14 | Not measured |
| Update | 14 | 14 |
| Publish | 14 | 14 |
| Close | 14 | 14 |
| Cancel | 14 | 14 |

HR_MANAGER operations require one additional SQL query compared with HR_ADMIN in these measured scenarios. This is consistent with the additional department-scoping access check.

### 3.3 Public JobPosting Listing

| Number of postings | SQL queries |
|---:|---:|
| 1 | 2 |
| 10 | 2 |

The query count remained constant when the result set increased from one to ten postings.

No N+1 query behavior was detected in these tested public-listing scenarios.

### 3.4 Post-Optimization Results

The JobPosting service methods were optimized using `select_related()` for the `department` and `position` foreign-key relationships.

The queries also use `select_for_update(of=("self",))` to restrict row locking to the JobPosting model.

#### Service-level measurements

| Role | Operation | Before | After | Reduction |
|---|---|---:|---:|---:|
| HR_ADMIN | Update | 13 | 11 | 2 |
| HR_ADMIN | Publish | 13 | 11 | 2 |
| HR_ADMIN | Close | 13 | 11 | 2 |
| HR_ADMIN | Cancel | 13 | 11 | 2 |
| HR_MANAGER | Update | 14 | 12 | 2 |
| HR_MANAGER | Publish | 14 | 12 | 2 |
| HR_MANAGER | Close | 14 | 12 | 2 |
| HR_MANAGER | Cancel | 14 | 12 | 2 |

Across the eight measured service operations, the total query count decreased from 108 to 92, representing a reduction of approximately 14.8%.

#### API-level measurements

| Role | Operation | Before | After | Reduction |
|---|---|---:|---:|---:|
| HR_ADMIN | Create | 13 | 13 | 0 |
| HR_ADMIN | Update | 13 | 11 | 2 |
| HR_ADMIN | Publish | 13 | 11 | 2 |
| HR_ADMIN | Close | 13 | 11 | 2 |
| HR_ADMIN | Cancel | 13 | 11 | 2 |
| HR_MANAGER | Create | 14 | 14 | 0 |
| HR_MANAGER | Update | 14 | 12 | 2 |
| HR_MANAGER | Publish | 14 | 12 | 2 |
| HR_MANAGER | Close | 14 | 12 | 2 |
| HR_MANAGER | Cancel | 14 | 12 | 2 |

Create operations were not affected by this optimization.

#### SQL analysis

The joined query now retrieves JobPosting, Department, and Position together, eliminating separate relationship-loading queries.

The foreign-key existence checks triggered by model validation remain unchanged.

HR_MANAGER department-scoping checks also remain in place.

The generated PostgreSQL query uses:

```sql
FOR UPDATE OF "recruitment_jobposting"
```

This preserves row-level locking on the JobPosting record without unnecessarily locking the joined Department and Position rows.

#### Public listing comparison

Public listing measurements remained unchanged:

- 2 queries for 1 posting.
- 2 queries for 10 postings.

No additional optimization was necessary for these tested listing scenarios.

#### Verification after optimization

- `JobPostingORMBaselineTests`: 20 tests passed.
- HR_MANAGER cross-department update denial: passed.
- HR_MANAGER cross-department publish denial: passed.
- Django system check: no issues reported.

The optimization reduced unnecessary relationship-loading queries while preserving the tested departmental access restrictions.

## 4. Test Coverage

Test class:

`recruitment.tests.JobPostingORMBaselineTests`

Verified scenarios:

- HR_ADMIN create, update, publish, close, and cancel API operations.
- HR_MANAGER create, update, publish, close, and cancel API operations.
- HR_ADMIN service-level update, publish, close, and cancel operations.
- HR_MANAGER service-level update, publish, close, and cancel operations.
- Public JobPosting listing with one posting.
- Public JobPosting listing with ten postings.

**Latest verification:** 20 tests passed.

```text
Ran 20 tests
OK
```

Django system check:

```text
System check identified no issues (0 silenced).
```

No migrations were required.

## 5. Candidate and JobApplication ORM Baselines

### 5.1 Candidate

Measurements cover 11 candidates.

| Operation | HR_ADMIN | HR_MANAGER |
|---|---:|---:|
| List — service-level | 1 | 2 |
| List — API-level | 2 | 3 |
| Detail — service-level | 1 | 2 |
| Detail — API-level | 1 | 2 |

#### SQL analysis

- HR_ADMIN candidate listing retrieves all authorized candidates in one SQL query.
- HR_MANAGER candidate listing uses two queries: one to retrieve the manager's EmployeeProfile and Department, and one to retrieve candidates filtered by `department_id`.
- Candidate detail uses one query for HR_ADMIN.
- HR_MANAGER candidate detail uses two queries: candidate retrieval followed by the manager's department access check.
- Candidate serialization does not generate additional queries in the measured scenarios.

The generated candidate-list query applies departmental filtering directly in SQL.

No N+1 behavior was detected.

### 5.2 JobApplication

Measurements cover 10 applications.

| Operation | HR_ADMIN | HR_MANAGER |
|---|---:|---:|
| List — service-level | 1 | 2 |
| List — API-level | 2 | 3 |
| Detail — service-level | 1 | 2 |
| Detail — API-level | 1 | 2 |

#### SQL analysis

- HR_ADMIN application listing retrieves applications and their related Candidate, JobPosting, Department, Position, and assigned User data in one joined query.
- HR_MANAGER application listing uses two queries: one to retrieve the manager's department and one to retrieve applications filtered through their JobPosting department.
- Application detail uses one query for HR_ADMIN.
- HR_MANAGER application detail uses two queries: application retrieval and departmental access verification.
- Application serialization does not generate additional queries in the measured scenarios.

The HR_MANAGER application-list query applies departmental filtering directly in SQL.

The detail service performs its department authorization check before returning the application. Existing service and API tests verify that cross-department access is denied.

No N+1 behavior was detected.

### 5.3 Department Isolation and Security Verification

The following cross-department access restrictions are covered by existing tests:

| Resource | Service-level expected result | API-level expected result |
|---|---|---|
| Candidate | PermissionDenied | HTTP 403 Forbidden |
| JobApplication | PermissionDenied | HTTP 403 Forbidden |

These checks must be preserved during future ORM optimizations.

### 5.4 Optimization Decision

No additional production ORM optimization is justified by the measured Candidate and JobApplication scenarios.

The additional HR_MANAGER query is used for retrieving the manager's department and enforcing departmental access restrictions.

The measured list queries apply department filtering at the database level.

The detail operations retrieve the requested object and then perform the department authorization check before returning it.

The current query counts are stable for the tested datasets, and no N+1 behavior was observed.

### 5.5 Verification

Test class:

`recruitment.tests.JobApplicationORMBaselineTests`

Coverage includes:

- HR_ADMIN Candidate list and detail service operations.
- HR_ADMIN Candidate list and detail API operations.
- HR_MANAGER Candidate list and detail service operations.
- HR_MANAGER Candidate list and detail API operations.
- HR_ADMIN JobApplication list and detail service operations.
- HR_ADMIN JobApplication list and detail API operations.
- HR_MANAGER JobApplication list and detail service operations.
- HR_MANAGER JobApplication list and detail API operations.

**Initial baseline verification:** 16 tests passed.

The service and API cross-department access restrictions are also covered by dedicated security tests.

## 6. Initial Findings

1. API-level and service-level query counts are identical for the four measured update/action operations.
2. HR_MANAGER operations use one additional query compared with HR_ADMIN.
3. Public listing uses two queries for both one and ten postings.
4. No N+1 behavior was observed in the tested public listing scenarios.

## 7. Limitations

- Measurements cover the tested scenarios and current fixtures only.
- Query counts do not measure query execution time, database load, or response latency.
- The public-listing scaling test covers ten postings, not large production datasets.
- Stable query counts do not guarantee optimal query execution plans.
- Create operations were measured at API level only.

## 8. Future Optimization Guidelines

When optimizing Recruitment ORM operations:

- Preserve role-based access control and department isolation.
- Avoid introducing additional database queries during serialization.
- Use `select_related()` and `prefetch_related()` where appropriate.
- Compare query counts before and after each optimization.
- Re-run the relevant functional, permission, and ORM baseline tests.
- Update this document whenever a verified baseline changes.

## 9. Next Coverage Targets

- Recruitment dashboard aggregation query baselines.
- Larger dataset tests to assess query scaling.
- Recruitment dashboard aggregation query baselines.
- Larger dataset tests to assess query scaling.

---

**Baseline owner:** Secure HR Platform development  
**Last verified:** November 6, 2026
