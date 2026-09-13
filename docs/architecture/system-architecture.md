# Secure HR Platform — System Architecture

## 1. Purpose

This document defines the high-level technical architecture of the Secure HR Platform.

The architecture combines:

- Secure HR application services
- REST API architecture
- Application security
- Role-Based Access Control (RBAC)
- PostgreSQL data storage
- Security event collection
- SIEM integration
- Detection engineering
- SOC monitoring
- MITRE ATT&CK-based threat analysis

The architecture is designed according to defense-in-depth, least privilege, zero-trust, and secure-by-design principles.

---

# 2. Architectural Overview

The platform is divided into four major security zones:

1. External / User Zone
2. Application Zone
3. Data Zone
4. Security Monitoring Zone

```mermaid
flowchart TB

    subgraph EXT["External / User Zone"]
        Employee["Employee"]
        HRStaff["HR Staff"]
        HRAdmin["HR Administrator"]
        SecAdmin["Security Administrator"]
        SysAdmin["System Administrator"]
        Attacker["External Attacker"]
    end

    subgraph APP["Application Zone"]
        Proxy["Reverse Proxy / Web Server"]
        API["Django REST API"]
        Auth["Authentication & Authorization"]
        RBAC["RBAC / Object-Level Authorization"]
        HRLogic["HR Business Logic"]
        SecurityEvents["Security Event Generator"]
    end

    subgraph DATA["Data Zone"]
        DB[("PostgreSQL")]
    end

    subgraph SIEM["Security Monitoring Zone"]
        Collector["Log Collector / Agent"]
        ES[("Elasticsearch")]
        Kibana["Kibana"]
        Detection["Detection Rules"]
        SOC["Security Investigation / SOC"]
    end

    Employee --> Proxy
    HRStaff --> Proxy
    HRAdmin --> Proxy
    SecAdmin --> Proxy
    SysAdmin --> Proxy
    Attacker --> Proxy

    Proxy --> API

    API --> Auth
    Auth --> RBAC
    RBAC --> HRLogic
    HRLogic --> DB

    API --> SecurityEvents
    SecurityEvents --> Collector
    Collector --> ES
    ES --> Kibana
    Kibana --> Detection
    Detection --> SOC

    SecAdmin --> Kibana
    SysAdmin --> API
    3. Architectural Zones
    3.1 External / User Zone

    This zone contains users interacting with the platform.

    Actors include:

    Employees
    HR Staff
    HR Administrators
    Security Administrators
    System Administrators
    External attackers

    This zone is considered untrusted.

    All requests entering the platform must pass through the external application entry point.

    3.2 Application Zone

    The application zone contains the main application services.

    Components include:

    Reverse Proxy
    Django REST API
    Authentication
    Authorization
    RBAC
    HR business logic
    Security event generation

    The Django API is responsible for enforcing application security controls.

    3.3 Data Zone

    The data zone contains PostgreSQL.

    PostgreSQL stores:

    User information
    Employee information
    Departments
    Positions
    Leave requests
    Roles
    Permissions
    Security events
    Audit information

    The database must not be directly accessible from the Internet.

    3.4 Security Monitoring Zone

    The security monitoring zone contains the components responsible for collecting, storing, analyzing, and investigating security events.

    Components include:

    Log Collector / Elastic Agent
    Elasticsearch
    Kibana
    Detection Rules
    Security Investigation / SOC

    This zone is logically separated from normal HR application functionality.

    4. Application Architecture

    The Django application follows a layered architecture.

    Client
       |
       v
    Reverse Proxy
       |
       v
    REST API
       |
       +----------------------+
       |                      |
       v                      v
    Authentication        Authorization
                               |
                               v
                        RBAC / Permissions
                               |
                               v
                        Business Logic
                               |
                               v
                           Database

    The application must enforce authorization server-side.

    The client must never be trusted to determine whether an operation is allowed.

    5. Authentication Architecture

    Authentication establishes the identity of the requesting user.

    The platform will use token-based authentication.

    Conceptually:

    User
     |
     | Credentials
     v
    Django Authentication
     |
     | Success
     v
    JWT Access Token
     |
     v
    Protected API Requests

    Authentication must include:

    Secure password storage
    Password validation
    Authentication throttling
    Account status validation
    Token expiration
    Secure token handling
    Security event generation
    6. Authorization Architecture

    Authentication and authorization are separate security controls.

    Authentication
          |
          v
    Who are you?
          |
          v
    Authorization
          |
          v
    What are you allowed to do?

    Authorization includes:

    Role-Based Access Control
    Permission checks
    Object-level authorization
    Account status validation
    Least privilege

    Example:

    Employee
       |
       +--> Own Profile        ALLOWED
       |
       +--> Own Leave Request  ALLOWED
       |
       +--> Other Employee     DENIED
       |
       +--> Admin Functions    DENIED
    7. HR Domain Architecture

    The core HR domain contains:

    User
     |
     +---- Employee
              |
              +---- Department
              |
              +---- Position
              |
              +---- Leave Requests

    Authorization roles remain separate from HR positions.

    For example:

    Employee
     |
     +-- HR Position: Security Analyst
     |
     +-- Application Role: Employee

    A job position must not automatically grant application administrator privileges.

    8. Database Architecture

    The application communicates with PostgreSQL through the Django data-access layer.

    Django REST API
           |
           v
    Django ORM
           |
           v
    PostgreSQL

    Security requirements include:

    Database authentication
    Least-privilege database account
    Network isolation
    Secure credentials
    Parameterized queries through the ORM
    Database backups
    Migration management
    Monitoring
