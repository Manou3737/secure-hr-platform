# Application Boundaries and Trust Boundaries

## 1. Purpose

This document defines the application boundaries, system components, responsibilities, and trust boundaries of the Secure HR Platform.

The objective is to establish a clear security architecture before application development begins.

The platform follows a defense-in-depth approach in which each component has a defined responsibility and each trust boundary is protected by explicit security controls.

---

## 2. System Boundary

The Secure HR Platform consists of the following major components:

- Client applications
- Reverse proxy / web server
- Django REST API
- PostgreSQL database
- Security event and audit logging
- SIEM pipeline
- Elasticsearch
- Kibana
- Security administration interfaces

The client must never communicate directly with the PostgreSQL database or Elasticsearch.

All business operations must go through the application API.

---

## 3. External Actors

### 3.1 Employee

Employees use the platform to:

- Authenticate
- View their profile
- View authorized HR information
- Submit leave requests
- View their own leave requests

Employees must not access other employees' protected HR records.

### 3.2 HR Staff

HR staff manage authorized HR operations such as:

- Employee records
- Departments
- Positions
- Leave requests

Access is controlled through application roles and permissions.

### 3.3 HR Administrator

HR administrators have elevated HR privileges.

They may perform administrative HR operations but should not automatically receive security administration privileges.

### 3.4 Security Administrator

Security administrators are responsible for:

- Security event monitoring
- Security investigations
- Detection management
- Reviewing suspicious activity
- Investigating unauthorized access

Security administration is separated from normal HR responsibilities.

### 3.5 System Administrator

System administrators are responsible for:

- Application infrastructure
- Containers
- Database infrastructure
- Deployment
- System configuration

Infrastructure privileges must not automatically provide unrestricted application-level HR access.

### 3.6 External Attacker

An external attacker represents an unauthenticated or unauthorized actor attempting to compromise the platform.

Potential activities include:

- Credential attacks
- Brute-force authentication
- API enumeration
- Authorization bypass
- Unauthorized data access
- Exploitation of application vulnerabilities

---

## 4. Application Components

### 4.1 Client

The client may be:

- Web browser
- REST API client
- Administrative interface

Responsibilities:

- Send authenticated API requests
- Present application data to authorized users
- Store minimal client-side information

The client is considered untrusted.

---

### 4.2 Reverse Proxy

The reverse proxy will provide the external entry point to the application.

Potential responsibilities include:

- TLS termination
- HTTP routing
- Request forwarding
- Security headers
- Basic request filtering
- Protection of the application server

The reverse proxy is exposed to the Internet and therefore represents an important security boundary.

---

### 4.3 Django REST API

The Django REST API is the main application and security enforcement layer.

Responsibilities include:

- Authentication
- Authorization
- RBAC
- Object-level access control
- HR business logic
- Input validation
- Data validation
- Rate limiting
- Security event generation
- Audit logging
- API documentation

The API must never trust authorization decisions made exclusively by the client.

---

### 4.4 PostgreSQL Database

PostgreSQL stores application and HR data.

Potential data includes:

- Users
- Employees
- Departments
- Positions
- Leave requests
- Roles
- Permissions
- Security events
- Audit information

The database is inside the protected application environment.

Clients must never have direct database access.

---

### 4.5 Security Event Pipeline

The application generates structured security events for important activities.

Examples include:

- Successful authentication
- Failed authentication
- Brute-force detection
- Unauthorized access
- Password changes
- Account activation/deactivation
- Privileged operations
- Suspicious administrative activity

Security events are forwarded to the SIEM pipeline for monitoring and detection.

---

### 4.6 Elasticsearch

Elasticsearch stores and indexes security and application logs used for investigation and detection.

Elasticsearch must not be directly exposed to normal application users.

Access should be restricted to authorized security and infrastructure components.

---

### 4.7 Kibana

Kibana provides the security monitoring and investigation interface.

Security administrators can use Kibana to:

- Search security events
- Investigate suspicious activity
- Review alerts
- Monitor detection rules
- Analyze attack patterns
- Support incident investigation

---

## 5. Trust Boundaries

### Trust Boundary 1 — External User → Reverse Proxy

**Risk: High**

Traffic enters the platform from an untrusted external environment.

Security controls:

- HTTPS/TLS
- Secure HTTP headers
- Request validation
- Rate limiting
- Network filtering
- Authentication enforcement

---

### Trust Boundary 2 — Reverse Proxy → Application API

**Risk: High**

The reverse proxy forwards requests to the Django application.

Security controls:

- Internal network isolation
- Trusted proxy configuration
- Secure headers
- Request validation
- Application-level authentication
- Application-level authorization

The API must not assume that requests forwarded by the reverse proxy are automatically trusted.

---

### Trust Boundary 3 — Application API → PostgreSQL

**Risk: High**

The API communicates with the database containing sensitive HR information.

Security controls:

- Database authentication
- Least-privilege database account
- Network isolation
- Parameterized queries / ORM
- Input validation
- Encryption in transit where applicable
- Secure secret management
- Database backups

The database must not be publicly accessible.

---

### Trust Boundary 4 — Application API → SIEM

**Risk: High**

Security events generated by the application cross into the security monitoring environment.

Security controls:

- Structured event format
- Controlled log transport
- Event integrity
- Access control
- Sensitive-data filtering
- Reliable log delivery
- Monitoring of the logging pipeline

Security events must contain enough information for investigation without unnecessarily exposing sensitive HR data.

---

### Trust Boundary 5 — SIEM → Security Administrator

**Risk: High**

Security administrators access security monitoring information through Kibana.

Security controls:

- Strong authentication
- Role-based access control
- Least privilege
- Administrative audit logging
- Secure network access
- Separation of security privileges

---

### Trust Boundary 6 — Administrative Access

Administrative users represent a high-value trust boundary.

Administrative privileges must be explicitly granted and monitored.

Security controls include:

- RBAC
- Least privilege
- Strong authentication
- Privileged-operation logging
- Security event generation
- Detection rules
- Periodic access review

---

## 6. Trust Model

The platform follows a zero-trust-oriented model.

Authentication does not automatically imply authorization.

Every sensitive operation must verify:

1. Who is making the request?
2. Is the account active?
3. What role does the user have?
4. What permissions does the user have?
5. Does the user have access to the specific object?
6. Is the requested operation allowed?
7. Should the operation generate a security event?

---

## 7. Network Isolation Principles

The architecture should enforce the following principles:

- The database must not be publicly accessible.
- Elasticsearch must not be publicly accessible.
- Internal services should communicate through controlled networks.
- Only required ports should be exposed.
- Administrative interfaces should have restricted access.
- Security monitoring infrastructure should be isolated from normal application traffic where practical.

---

## 8. Data Access Principles

Sensitive HR data must only be accessible through authorized application workflows.

The system must enforce:

- Least privilege
- Role-based access control
- Object-level authorization
- Data minimization
- Secure defaults
- Deny-by-default access

For example:

An authenticated employee may access their own employee record, but authentication alone must not allow them to access another employee's record.

---

## 9. Security Responsibilities by Component

| Component | Primary Responsibility |
|---|---|
| Client | User interaction |
| Reverse Proxy | Secure external entry point |
| Django API | Business logic and security enforcement |
| PostgreSQL | Secure data storage |
| Security Event Pipeline | Security event collection |
| Elasticsearch | Security log storage and indexing |
| Kibana | Security monitoring and investigation |

---

## 10. Architectural Security Principles

The Secure HR Platform follows these principles:

- Zero Trust
- Defense in Depth
- Least Privilege
- Secure by Design
- Deny by Default
- Separation of Duties
- Fail Securely
- Assume Breach
- Auditability
- Data Minimization
- Explicit Authorization

---

## 11. Future Architecture Direction

The initial architecture will evolve toward an integrated architecture containing:

```text
                         Internet
                            |
                            v
                    +---------------+
                    | Reverse Proxy |
                    +---------------+
                            |
                            v
                    +---------------+
                    | Django REST   |
                    |     API       |
                    +---------------+
                       /          \
                      /            \
                     v              v
              +-----------+   +------------+
              | PostgreSQL|   | SIEM       |
              | Database  |   | Pipeline   |
              +-----------+   +------------+
                                   |
                                   v
                            +-------------+
                            | Elasticsearch|
                            +-------------+
                                   |
                                   v
                              +---------+
                              | Kibana  |
                              +---------+
                                   |
                                   v
                         Security Administrator
