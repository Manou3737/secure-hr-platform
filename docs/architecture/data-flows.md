# Data Flows

## 1. Purpose

This document defines the main data flows within the Secure HR Platform.

The objective is to identify:

- Where data originates
- Where data is processed
- Where data is stored
- Which trust boundaries are crossed
- Which security controls must be applied
- Which activities generate security events

The data-flow model will be used to support the system architecture, threat model, security controls, and SIEM integration.

---

## 2. High-Level Data Flow

The platform follows this general flow:

```text
User
 |
 | HTTPS
 v
Reverse Proxy
 |
 | Internal HTTP/HTTPS
 v
Django REST API
 |              \
 |               \
 |                \
 v                 v
PostgreSQL       Security Event Pipeline
                    |
                    v
               Elasticsearch
                    |
                    v
                 Kibana
                    |
                    v
            Security Administrator

            User
             |
             | Credentials
             v
            Reverse Proxy
             |
             v
            Django REST API
             |
             | Validate credentials
             v
            User Authentication
             |
             | Authentication result
             +--------------------+
             |                    |
             v                    v
            Success              Failure
             |                    |
             v                    v
            JWT Token          Security Event
             |                    |
             v                    v
            User                SIEM


            3.3 Failed Authentication

            A failed authentication attempt should generate a security event.

            Example:

            User
             |
             | Invalid credentials
             v
            Django REST API
             |
             | LOGIN_FAILED
             v
            Security Event Pipeline
             |
             v
            Elasticsearch
             |
             v
            Kibana

            Repeated failed authentication attempts may trigger brute-force detection.

            4. HR Data Access Flow
            4.1 Employee Profile Access

            A typical employee profile request follows:

            Employee
             |
             | HTTPS + JWT
             v
            Reverse Proxy
             |
             v
            Django REST API
             |
             | Authentication
             v
            Authorization
             |
             | Object-level permission check
             v
            PostgreSQL
             |
             | Employee data
             v
            Django REST API
             |
             v
            Employee

            The API must verify both:

            The user's identity
            The user's authorization to access the requested employee record

            Authentication alone is insufficient.

            5. HR Data Creation Flow

            For example, when HR creates an employee record:

            HR Staff
             |
             | Authenticated API Request
             v
            Reverse Proxy
             |
             v
            Django REST API
             |
             | Authentication
             v
            Role / Permission Check
             |
             | Authorized
             v
            Input Validation
             |
             v
            Business Logic
             |
             v
            PostgreSQL
             |
             +--------------------+
             |
             v
            Security / Audit Event

            The system should record significant administrative operations for accountability.

            6. Leave Request Flow

            The leave request workflow is:

            Employee
             |
             | Submit leave request
             v
            Django REST API
             |
             | Validate request
             v
            Authorization
             |
             v
            PostgreSQL
             |
             | Leave request
             v
            HR Staff
             |
             | Review
             +----------+
             |          |
             v          v
            Approve    Reject
             |          |
             +----+-----+
                  |
                  v
             PostgreSQL

            Security-relevant actions should generate appropriate audit or security events.

            7. Authorization Flow

            Authorization is enforced inside the Django REST API.

            API Request
             |
             v
            Authentication
             |
             +---- No ----> Deny
             |
             Yes
             |
             v
            Account Status Check
             |
             +---- Inactive ----> Deny
             |
             Active
             |
             v
            Role Check
             |
             +---- Unauthorized ----> Deny + Security Event
             |
             Authorized
             |
             v
            Object-Level Permission Check
             |
             +---- Unauthorized ----> Deny + Security Event
             |
             Authorized
             |
             v
            Business Operation

            This ensures that authorization decisions are made server-side.

            8. Unauthorized Access Flow

            When a user attempts to access a resource they are not authorized to access:

            User
             |
             | Unauthorized request
             v
            Django REST API
             |
             v
            Authorization Check
             |
             | DENIED
             +----------------+
             |                |
             v                v
            HTTP Error     Security Event
                              |
                              v
                             SIEM

            The security event should contain enough information to investigate the attempt without exposing unnecessary sensitive data.

            9. Security Event Flow

            Security events originate inside the Django application.

            Django REST API
             |
             | Structured Security Event
             v
            Security Event Pipeline
             |
             v
            Elasticsearch
             |
             v
            Kibana
             |
             v
            Security Administrator

            Example security events include:

            LOGIN_SUCCESS
            LOGIN_FAILED
            BRUTE_FORCE_DETECTED
            UNAUTHORIZED_ACCESS
            PASSWORD_CHANGED
            ACCOUNT_ACTIVATED
            ACCOUNT_DEACTIVATED
            ACCOUNT_CHANGE
            Privileged administrative actions
            10. Brute-Force Detection Flow

            Repeated failed authentication attempts may trigger brute-force detection.

            Login Attempt
             |
             v
            LOGIN_FAILED Event
             |
             v
            Detection Logic
             |
             | Threshold exceeded?
             +-------------+
             |             |
             No            Yes
             |             |
             v             v
            Continue    BRUTE_FORCE_DETECTED
                            |
                            v
                       SIEM Pipeline
                            |
                            v
                       Elasticsearch
                            |
                            v
                          Kibana

            The detection mechanism should record:

            Source IP
            Time window
            Number of failed attempts
            Related user account when available
            Detection event
            Relevant request metadata
            11. Audit and Security Logging Flow

            Not every application event has the same security importance.

            The platform separates normal business activity from security-relevant events.

            Business activity

            Examples:

            Employee profile update
            Leave request creation
            Department modification
            Security activity

            Examples:

            Failed login
            Brute-force detection
            Unauthorized access
            Password change
            Account activation/deactivation
            Privileged operation

            Security-relevant events should be structured for SIEM ingestion.

            12. Sensitive Data Flow

            Sensitive HR information may include:

            Employee personal information
            Contact information
            Employment information
            Leave information
            Authentication-related information
            Authorization information

            Sensitive data must only flow through authorized components.

            The following flow is prohibited:

            Client
             |
             X
             +------------------+
             | Direct Database  |
             | Access           |
             +------------------+

            The correct architecture is:

            Client
             |
             v
            Django REST API
             |
             v
            Authorization
             |
             v
            PostgreSQL
            13. SIEM Data Minimization

            Security events should contain the information necessary for detection and investigation.

            The following information should not be unnecessarily written to logs:

            Passwords
            Authentication secrets
            JWT tokens
            Session secrets
            Full sensitive HR records
            Unnecessary personal information

            Security events should prefer identifiers and metadata over complete sensitive objects.

            14. Administrative Activity Flow

            Privileged operations require additional monitoring.

            Example:

            HR Administrator
             |
             | Administrative Request
             v
            Django REST API
             |
             v
            Authentication
             |
             v
            RBAC
             |
             v
            Permission Check
             |
             v
            Business Operation
             |
             +----------------------+
             |
             v
            Security / Audit Event
             |
             v
            SIEM

            Privileged operations should be traceable to an authenticated administrative identity.

            15. Security Investigation Flow

            When a security event is generated:

            Application
             |
             v
            Security Event
             |
             v
            Elasticsearch
             |
             v
            Kibana
             |
             v
            Security Administrator
             |
             v
            Investigation
             |
             +----------------------+
             |
             v
            Detection / Incident Response

            The SIEM environment should allow security administrators to correlate:

            User
            Source IP
            Timestamp
            Event type
            Request path
            User agent
            Related security events
            16. Trust Boundaries in Data Flows

            The main trust boundaries crossed by platform data are:

            Flow	Trust Boundary	Primary Risk
            User → Reverse Proxy	External → Application	Malicious requests
            Reverse Proxy → API	Network → Application	Request manipulation
            API → PostgreSQL	Application → Data	Unauthorized data access
            API → SIEM	Application → Security	Log tampering / data leakage
            SIEM → Kibana	Security infrastructure → Admin	Unauthorized monitoring access
            Admin → Application	Privileged user → Application	Privilege abuse
            17. Security Controls by Data Flow
            Data Flow	Main Controls
            User → API	TLS, authentication, rate limiting
            API → Database	Least privilege, ORM, validation, network isolation
            API → SIEM	Structured events, data minimization, controlled transport
            SIEM → Kibana	RBAC, authentication, secure access
            Admin → API	Strong authentication, RBAC, audit logging
            Unauthorized request → SIEM	Security event generation and detection
            18. Data Flow Security Principles

            The platform follows these principles:

            Data should flow through controlled interfaces.
            Clients must not bypass the API.
            Authentication must occur before protected operations.
            Authorization must occur for every protected operation.
            Sensitive data must be minimized.
            Security events must be structured.
            Security-relevant activity must be auditable.
            Logs must not contain secrets.
            Security monitoring infrastructure must be protected.
            Administrative operations must be traceable.
            19. Future Data Flow Extensions

            Future versions may introduce:

            Email notification services
            Object storage
            Background workers
            Message queues
            External identity providers
            HR reporting services
            Additional SIEM integrations
            Automated incident response

            Any new component must have its own trust boundary and security requirements documented before integration.

            20. Conclusion

            The data-flow model establishes how information moves through the Secure HR Platform and where security controls must be applied.

            The most important architectural principle is:

            Sensitive HR data must flow through controlled, authenticated, and authorized application services rather than directly between users and infrastructure components.

            Security events follow a separate monitoring path:

            Application
                |
                v
            Security Events
                |
                v
            SIEM
                |
                v
            Detection
                |
                v
            Security Investigation
