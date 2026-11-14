# API Conventions — Secure HR Platform

## 1. Purpose

This document defines the API conventions for the Secure HR Platform.

Its objectives are to ensure consistent API behavior, predictable client integration, secure access to HR data, and maintainable API contracts.

These conventions cover:

* URL naming and versioning
* Request and response formats
* HTTP status codes and error handling
* Pagination, filtering, and ordering
* Authentication and authorization
* Object-level access control
* API schema and documentation

## 2. URL Naming and Versioning

* API endpoints must use the `/api/v1/` prefix.
* Resource paths should use plural nouns.
* Resource names should use lowercase letters and hyphens when needed.
* HTTP methods must express the intended operation.
* New API versions must be introduced when a breaking change requires them.

Examples:

* `/api/v1/employees/`
* `/api/v1/departments/`
* `/api/v1/leave-requests/`

## 3. Request and Response Formats

* JSON is the standard request and response format.
* Request bodies must be validated before data is persisted.
* Responses must not expose passwords, authentication tokens, encryption keys, or unmasked banking details.
* List endpoints must use the configured pagination format.
* Detail endpoints return a single resource representation.

### 3.1 Paginated Responses

List endpoints use page-number pagination.

The default page size is 20 records. Clients may request a different page size using `page_size`, up to a maximum of 100.

Example:

```json
{
  "count": 42,
  "next": "https://example.com/api/v1/employees/?page=2",
  "previous": null,
  "results": []
}
```

The example illustrates the response structure; actual values depend on the request.

## 4. HTTP Status Codes

The API should use standard HTTP status codes consistently.

| Status                    | Meaning                                      |
| ------------------------- | -------------------------------------------- |
| 200 OK                    | Request completed successfully               |
| 201 Created               | Resource created successfully                |
| 204 No Content            | Request succeeded without a response body    |
| 400 Bad Request           | Invalid request or validation failure        |
| 401 Unauthorized          | Authentication is missing or invalid         |
| 403 Forbidden             | Authenticated user lacks permission          |
| 404 Not Found             | Resource does not exist or is not accessible |
| 405 Method Not Allowed    | HTTP method is not supported                 |
| 429 Too Many Requests     | Rate limit exceeded                          |
| 500 Internal Server Error | Unexpected server error                      |

The implementation must determine the actual status code for each operation.

## 5. Error Handling

* Validation errors must identify the fields or inputs that failed validation where appropriate.
* Error responses must not expose stack traces, secrets, database credentials, or sensitive HR information.
* Unexpected server errors must be logged securely.
* Error response formats should remain consistent across endpoints.
* Security-related errors must not reveal whether sensitive resources exist when doing so could enable enumeration.

A single global error envelope must not be assumed until the actual Django REST Framework exception handling is verified.

## 6. Pagination, Filtering, and Ordering

### 6.1 Pagination

* Default page size: 20.
* Client parameter: `page_size`.
* Maximum page size: 100.
* List clients must read records from the `results` property.

### 6.2 Filtering

Filtering must be explicitly configured for each endpoint.

Only documented fields should be filterable. Sensitive fields, encrypted values, credentials, and full banking details must not be exposed through filtering.

### 6.3 Ordering

Ordering must be explicitly configured for each endpoint.

Only approved fields should be sortable. Ordering parameters must not allow clients to access sensitive fields or bypass authorization.

## 7. Authentication and Authorization

* Protected endpoints require authentication by default.
* JWT authentication uses the HTTP `Authorization: Bearer <token>` header.
* Authentication does not automatically grant permission to access every resource.
* Authorization must be enforced server-side for every protected operation.
* Users must not be able to elevate their privileges by modifying request payloads.

## 8. Role-Based and Object-Level Access Control

The platform defines the following roles:

* `SUPER_ADMIN`
* `HR_ADMIN`
* `HR_MANAGER`
* `EMPLOYEE`

Permissions must be enforced according to the role, operation, and resource ownership.

Object-level access controls must prevent insecure direct object reference (IDOR) vulnerabilities. Employees must not gain access to another employee's private records by changing an object identifier.

Write operations must validate both role permissions and applicable business rules.

The exact permissions for each resource must be maintained in a resource-specific permission matrix and verified against the implementation.

## 9. API Schema and Documentation

The API schema is generated with `drf-spectacular`.

* API endpoints should have accurate operation summaries and descriptions.
* Request and response schemas should reflect serializer behavior.
* Authentication requirements and permission-sensitive operations should be documented.
* Query parameters for pagination, filtering, and ordering should be documented.
* The generated schema should be checked for errors after API changes.

## 10. Security Requirements

* Validate all untrusted input.
* Use Django ORM parameterization rather than unsafe dynamic SQL.
* Apply object-level authorization to sensitive resources.
* Prevent mass assignment by explicitly defining serializer fields.
* Avoid exposing personal, payroll, or banking information in logs and error responses.
* Apply appropriate rate limits to authentication-sensitive endpoints.
* Test authorization failures as well as successful requests.

## 11. Change Management

API changes must include appropriate tests and updated documentation.

Breaking changes must be reviewed before implementation. Changes to serializers, permissions, pagination, filtering, or ordering must be checked for their impact on existing clients.

The API contract must remain consistent with the implementation and the generated schema.
