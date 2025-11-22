# Security Policy

## Status

**⚠️ LEARNING PROJECT / PROOF OF CONCEPT ⚠️**

This is a proof-of-concept voting system built to demonstrate an idea and share it with the community.

**Important Context:**
- Built by a non-developer as a learning project ("vibe coding")
- Demonstrates architecture concepts, not production-ready code
- Has **not** undergone professional security audits
- Should **not** be used in real elections without complete rewrite by professionals

**Current Status**: Functional demo sharing an idea with the security community.

**Goal**: Share this concept so others can learn from it, improve it, or use it as inspiration. If this can serve as a foundation for something better, that's the objective.

---

## Table of Contents

1. [Reporting Vulnerabilities](#reporting-vulnerabilities)
2. [Security Architecture](#security-architecture)
3. [Threat Model](#threat-model)
4. [Known Limitations](#known-limitations)
5. [Security Assumptions](#security-assumptions)
6. [Out of Scope](#out-of-scope)
7. [Roadmap to Production](#roadmap-to-production)

---

## Reporting Vulnerabilities

We welcome security researchers to review this system and report vulnerabilities.

### How to Report

**For non-critical issues:**
- Open a GitHub Issue with label `security`
- Email: [your-email-here] with subject "SECURITY: [brief description]"

**For critical vulnerabilities:**
- Email: [your-email-here] with subject "CRITICAL SECURITY"
- Include:
  - Detailed description of the vulnerability
  - Steps to reproduce
  - Potential impact
  - Proof of concept (if available)
  - Your recommended remediation

**Response Timeline:**
- Best effort response - this is a learning project by a non-developer
- Issues will be documented but fixes may take time or require community help
- **Community contributions for security fixes are strongly encouraged**

**Disclosure Policy:**
- This is a public learning project - all issues are welcome to be disclosed publicly
- Credit will be given to security researchers (unless anonymity requested)
- **Feel free to fork and fix** - no need to wait for me!

### Hall of Fame

Contributors who responsibly disclose security issues will be listed here:
- *Be the first!*

---

## Security Architecture

### Core Security Principles

1. **Zero PII Storage**
   - No personally identifiable information stored
   - Voter identity not linkable to vote choice
   - Only cryptographic hashes stored

2. **Hash-Based Authentication**
   - SHA-256 hashing: `hash = SHA-256(NAS|CODE|LAW_ID)`
   - Offline hash generation (air-gapped security model)
   - Pre-computed hash database prevents vote fabrication

3. **Duplicate Detection**
   - Redis SET tracking voted hashes
   - Duplicate attempt counter per hash
   - Audit trail of all duplicate attempts

4. **Complete Audit Trail**
   - PostgreSQL `vote_audit` table (immutable)
   - Every vote logged with timestamp
   - Full traceability without compromising anonymity

5. **Separation of Concerns**
   - Stateless validation workers (horizontal scaling)
   - Message queue buffering (RabbitMQ)
   - No single point of failure

### Data Flow Security

```
┌─────────────┐
│   Voter     │
│ (NAS+CODE)  │
└──────┬──────┘
       │ HTTPS (production)
       ▼
┌─────────────────┐
│ Ingestion API   │ ← Rate limiting
│   (FastAPI)     │ ← Input validation
└──────┬──────────┘
       │ Internal network
       ▼
┌─────────────────┐
│   RabbitMQ      │ ← Message queue isolation
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Validation      │ ← Hash verification (Redis)
│   Workers       │ ← Duplicate check (Redis)
└──────┬──────────┘
       │
       ├──→ PostgreSQL (audit log)
       └──→ RabbitMQ (aggregation queue)
```

### Cryptographic Components

**Hashing:**
- Algorithm: SHA-256
- Purpose: Voter authentication without PII
- Implementation: Python `hashlib`

**TLS/SSL (Production):**
- Currently: Not implemented in demo
- Production requirement: TLS 1.3
- Certificate management: Let's Encrypt (recommended)

---

## Threat Model

### Threat Actors

1. **External Attackers**
   - Motivation: Disrupt election, manipulate results
   - Capabilities: Network access, DDoS, injection attacks
   - Likelihood: High during actual elections

2. **Malicious Insiders**
   - Motivation: Manipulate votes, leak voter data
   - Capabilities: Database access, system knowledge
   - Likelihood: Low (requires multi-party validation)

3. **State-Level Adversaries**
   - Motivation: Election interference
   - Capabilities: Advanced persistent threats, zero-days
   - Likelihood: Medium for national elections

4. **Opportunistic Script Kiddies**
   - Motivation: Chaos, reputation
   - Capabilities: Automated tools, known exploits
   - Likelihood: High if publicly accessible

### Attack Vectors & Mitigations

#### 1. Vote Manipulation

**Attack:** Submit fake votes with fabricated hashes
- **Mitigation**: Offline hash generation, pre-validated hash database in Redis
- **Status**: ✅ Implemented
- **Residual Risk**: Hash generation process must be secured

**Attack:** Replay valid votes (duplicate submission)
- **Mitigation**: Redis `voted_hashes` SET, duplicate detection
- **Status**: ✅ Implemented
- **Residual Risk**: Redis compromise could disable deduplication

**Attack:** Modify vote in transit
- **Mitigation**: TLS encryption (production), message integrity checks
- **Status**: ⚠️ TLS not implemented in demo
- **Residual Risk**: High without TLS

#### 2. Denial of Service

**Attack:** Overwhelm API with requests
- **Mitigation**: Rate limiting, RabbitMQ queue buffering, CDN (production)
- **Status**: ⚠️ Basic rate limiting, no DDoS protection
- **Residual Risk**: High - needs WAF and DDoS mitigation

**Attack:** Exhaust database connections
- **Mitigation**: Connection pooling, worker scaling limits
- **Status**: ⚠️ Connection pooling implemented, no hard limits
- **Residual Risk**: Medium - needs connection limits

**Attack:** Fill RabbitMQ queue (queue flooding)
- **Mitigation**: Queue size limits, message TTL, dead letter queues
- **Status**: ❌ Not implemented
- **Residual Risk**: High - unlimited queue growth possible

#### 3. Data Exfiltration

**Attack:** Steal hash database from Redis
- **Mitigation**: Network isolation, Redis authentication, encryption at rest
- **Status**: ⚠️ No Redis authentication in demo
- **Residual Risk**: High - Redis exposed without auth

**Attack:** Access PostgreSQL vote audit logs
- **Mitigation**: Database authentication, encrypted connections, audit logging
- **Status**: ⚠️ Basic auth, no encrypted connections
- **Residual Risk**: Medium - needs TLS for DB connections

**Attack:** Link voter identity to vote choice
- **Mitigation**: Zero PII storage, hash-based system prevents linkage
- **Status**: ✅ Implemented
- **Residual Risk**: Low - correlation attacks still possible with metadata

#### 4. Injection Attacks

**Attack:** SQL injection
- **Mitigation**: Parameterized queries, ORM usage (SQLAlchemy)
- **Status**: ✅ Implemented
- **Residual Risk**: Low - needs regular audits

**Attack:** NoSQL injection (Redis commands)
- **Mitigation**: Input validation, Redis command whitelisting
- **Status**: ⚠️ Basic validation
- **Residual Risk**: Medium - needs stricter validation

**Attack:** Code injection via message payloads
- **Mitigation**: JSON schema validation, message sanitization
- **Status**: ⚠️ Basic validation
- **Residual Risk**: Medium - needs comprehensive input validation

#### 5. Infrastructure Compromise

**Attack:** Compromise Docker containers
- **Mitigation**: Minimal base images, no root users, security scanning
- **Status**: ⚠️ Standard images, needs hardening
- **Residual Risk**: High - container security not prioritized

**Attack:** Exploit dependencies
- **Mitigation**: Dependency scanning, automated updates, minimal dependencies
- **Status**: ❌ No automated scanning
- **Residual Risk**: High - needs Dependabot/Snyk

**Attack:** Kubernetes cluster compromise (production)
- **Mitigation**: RBAC, network policies, pod security policies
- **Status**: ❌ Not implemented (demo is Docker Compose)
- **Residual Risk**: N/A for demo, critical for production

#### 6. Endpoint Security

**Attack:** Malware on voter device
- **Mitigation**: None (outside system scope)
- **Status**: ❌ No endpoint security
- **Residual Risk**: High - voter devices assumed trusted

**Attack:** Man-in-the-Middle (MITM)
- **Mitigation**: TLS, certificate pinning (mobile apps)
- **Status**: ❌ TLS not implemented in demo
- **Residual Risk**: Critical - all traffic potentially interceptable

---

## Known Limitations

### Critical Gaps

1. **No TLS/SSL in Demo**
   - All traffic unencrypted
   - Credentials/votes visible to network observers
   - **Impact**: Critical vulnerability
   - **Remediation**: Implement TLS 1.3 before any real deployment

2. **No Redis Authentication**
   - Redis accessible without password
   - Hash database exposed
   - **Impact**: Critical vulnerability
   - **Remediation**: Redis AUTH, network isolation

3. **No DDoS Protection**
   - Basic rate limiting insufficient
   - No WAF, no CDN
   - **Impact**: System can be overwhelmed
   - **Remediation**: Cloudflare/AWS Shield, rate limiting per IP/subnet

4. **Hash Generation Process Not Secured**
   - Hash generation script has no security controls
   - No verification of hash uniqueness
   - **Impact**: Potential for duplicate or invalid hashes
   - **Remediation**: Hardware Security Module (HSM) for production

5. **No Intrusion Detection**
   - No monitoring for suspicious activity
   - No alerting on anomalies
   - **Impact**: Attacks may go undetected
   - **Remediation**: IDS/IPS, SIEM integration

### Important Gaps

6. **Limited Input Validation**
   - Basic format checks only
   - No comprehensive sanitization
   - **Remediation**: JSON Schema validation, input sanitization library

7. **No Encrypted Connections to Databases**
   - PostgreSQL connections unencrypted
   - **Remediation**: SSL/TLS for all DB connections

8. **No Container Security Scanning**
   - No vulnerability scanning of Docker images
   - **Remediation**: Trivy, Snyk, Clair integration

9. **No Automated Dependency Scanning**
   - Vulnerable dependencies may exist
   - **Remediation**: Dependabot, Snyk, safety checks

10. **No Security Audit Logs**
    - System events not logged comprehensively
    - **Remediation**: Centralized logging (ELK stack), audit trail

### Design Limitations

11. **Trust Assumptions**
    - Assumes voter devices are secure
    - Assumes hash generation process is trusted
    - Assumes network infrastructure is benign (in demo)

12. **Scalability vs Security Trade-offs**
    - Stateless workers = easier scaling, harder to detect coordinated attacks
    - Message queue buffering = resilience, but potential message loss

13. **Anonymity vs Auditability**
    - Cannot trace vote to voter (by design)
    - Makes forensic investigation difficult
    - Trade-off: privacy vs accountability

---

## Security Assumptions

This system operates under the following assumptions:

### Infrastructure Assumptions

1. **Network Security**
   - Production: Private network or VPN for inter-service communication
   - Demo: Assumes localhost/trusted network

2. **Physical Security**
   - Servers are physically secure
   - No unauthorized physical access to infrastructure

3. **Operator Trust**
   - System administrators are trusted
   - No insider threat from operators (mitigated by multi-party controls in production)

### Hash Generation Assumptions

4. **Offline Hash Generation**
   - Hashes generated in secure, air-gapped environment
   - Hash generation process follows strict protocol
   - No hash leakage before distribution

5. **Hash Distribution**
   - Voters receive NAS+CODE via secure channel (postal mail, secure portal)
   - Distribution process prevents interception

### Voter Assumptions

6. **Voter Device Security**
   - Voter devices free from malware
   - Voters use trusted browsers/applications
   - No keyloggers or screen recorders on voter devices

7. **Voter Behavior**
   - Voters keep credentials confidential
   - Voters do not share NAS+CODE combinations
   - Voters verify they're on correct voting website (phishing awareness)

### Cryptographic Assumptions

8. **Hash Algorithm Security**
   - SHA-256 remains cryptographically secure
   - No practical collision or preimage attacks

9. **Randomness**
   - Hash generation uses cryptographically secure random number generators
   - No predictable patterns in NAS or CODE generation

---

## Out of Scope

The following are explicitly **outside the scope** of this system's security model:

### By Design

1. **Voter Coercion**
   - System cannot prevent coercion or vote selling
   - Voters could be forced to vote in presence of coercer
   - Mitigation: Requires legal and social measures, not technical

2. **Device Compromise**
   - Voter device security is voter's responsibility
   - System assumes endpoint security

3. **Phishing Attacks**
   - Voters may be phished to fake voting sites
   - Mitigation: User education, domain verification

4. **Social Engineering**
   - Attackers may trick voters into revealing credentials
   - Mitigation: User awareness training

### Current Limitations (May Be Addressed Later)

5. **Advanced Persistent Threats (APTs)**
   - No defenses against state-level zero-day exploits
   - Requires ongoing security research and hardening

6. **Quantum Computing Attacks**
   - SHA-256 vulnerable to quantum attacks (theoretical)
   - Post-quantum cryptography not implemented

7. **Supply Chain Attacks**
   - No verification of dependency integrity
   - Needs software bill of materials (SBOM)

---

## What Would Be Needed for Production

**Honest Assessment:** As a learning project by a non-developer, this code needs significant work to be production-ready. Below is what security professionals would need to implement:

### Critical Security Requirements

**If someone wants to fork this and make it production-ready:**

- [ ] **TLS/SSL Implementation**
  - TLS 1.3 for all external connections
  - Certificate management automation
  - HSTS headers

- [ ] **Redis Security**
  - AUTH password
  - Network isolation (internal network only)
  - Encrypted connections (TLS)

- [ ] **Database Security**
  - SSL/TLS for PostgreSQL connections
  - Strong authentication
  - Connection encryption

- [ ] **DDoS Protection**
  - WAF implementation (Cloudflare, AWS WAF)
  - Rate limiting per IP/subnet
  - CDN for static assets

- [ ] **Input Validation**
  - JSON Schema validation
  - Comprehensive sanitization
  - Security audit of all endpoints

### Additional Requirements

- [ ] **Professional Security Audit** - Essential before any real use
- [ ] **Penetration Testing** - By qualified security professionals
- [ ] **Code Review** - By experienced developers
- [ ] **Compliance Assessment** - Electoral standards, data protection laws
- [ ] **Complete Rewrite** - Likely needed for production deployment

### Community Contributions Welcome

**This is a learning project.** If you're a security professional or experienced developer and see potential:

- **Fork it** and improve it
- **Rewrite parts** that need it
- **Use it as inspiration** for a better system
- **Share improvements** back with the community

**I'm still learning** and may not be able to implement complex security fixes quickly, but I'll do my best to:
- Document issues
- Review pull requests
- Share knowledge gained
- Support community efforts

**The goal is to advance the idea, not to be the sole maintainer.**

---

## Security Testing

### Current Testing

- [x] Basic functional testing
- [x] Load testing (8M votes capacity)
- [ ] Security testing (pending)

### Recommended Testing

**Before Production:**

1. **Penetration Testing**
   - External penetration test
   - Internal penetration test
   - Social engineering assessment

2. **Vulnerability Assessment**
   - Automated vulnerability scanning
   - Manual code review
   - Dependency audit

3. **Security Chaos Engineering**
   - Simulated attacks (red team)
   - Failure injection
   - Recovery testing

4. **Compliance Testing**
   - Electoral standards verification
   - Data protection audit
   - Accessibility audit

---

## Security Contact

**Project Creator**: David Marleau (learning developer, not security expert)

**Honest Disclosure**:
- I'm still learning and may not be able to fix complex security issues quickly
- Community contributions and forks are highly encouraged
- If you're a security professional, please help improve this or build something better

**Response Approach**:
- Will respond to issues as able
- May need community help for complex fixes
- Contributions and pull requests very welcome
- Feel free to fork and improve without waiting

---

## Acknowledgments

This security policy was inspired by:
- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [DEF CON Voting Village Reports](https://www.votingvillage.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

## License

This SECURITY.md document is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

**Last Updated**: November 2024
**Version**: 1.0
**Status**: Draft - Seeking Community Review
