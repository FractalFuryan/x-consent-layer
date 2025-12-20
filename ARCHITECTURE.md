# Architecture Overview

## System Architecture

This document provides a visual reference for the X Identity Shield consent layer architecture, data flows, and cryptographic primitives.

---

## High-Level Flow

```mermaid
graph TB
    User[👤 User] -->|1. Upload selfie| FractalID[Fractal ID Generation]
    FractalID -->|BLAKE2s hash of face embedding| ID[Fractal ID: XYZ123...]
    
    User -->|2. Issue consent| Capsule[Capsule Issuance]
    ID --> Capsule
    Capsule -->|ECDSA-SHA384 signature| Token[Signed Capsule Token]
    
    User -->|3. Request generation| Platform[Image Generation Platform]
    Platform -->|Check consent| Enforcement[/check Endpoint]
    Token --> Enforcement
    ID --> Enforcement
    
    Enforcement -->|Verify signature| Crypto[Cryptographic Verification]
    Enforcement -->|Check revocation| Revocation[(Revocation List)]
    Enforcement -->|Match scope| Scope[Scope Enforcement]
    
    Scope -->|ALLOW| Generator[🎨 Image Generator]
    Scope -->|DENY| Block[❌ Block Generation]
    
    Generator -->|Output| Image[Generated Image]
    Block -->|Error + Reason| User
    
    User -->|4. Revoke consent| Revoke[/capsule/revoke]
    Revoke --> Revocation
    
    style FractalID fill:#4A90E2
    style Capsule fill:#4A90E2
    style Enforcement fill:#E74C3C
    style Generator fill:#2ECC71
    style Block fill:#E74C3C
```

---

## Detailed Component Architecture

```mermaid
graph LR
    subgraph Client Side
        A[User Device] -->|Selfie| B[/fractal-id API]
        A -->|Consent params| C[/capsule/issue API]
    end
    
    subgraph Consent Layer
        B --> D[Face Recognition]
        D -->|InsightFace model| E[512-dim embedding]
        E -->|BLAKE2s| F[Fractal ID]
        
        C --> G[Issuer Private Key]
        G -->|ECDSA-SHA384| H[Signed Capsule]
        
        I[/check API] --> J{Validate Capsule}
        J -->|Invalid sig| K[DENY: invalid_capsule]
        J -->|Valid| L{Check Revocation}
        L -->|Revoked| M[DENY: capsule_revoked]
        L -->|Active| N{Match Scope}
        N -->|Out of scope| O[DENY: category_denied]
        N -->|In scope| P[ALLOW: consent_granted]
    end
    
    subgraph Platform
        Q[Image Generator] -->|Before gen| I
        P --> Q
        K --> R[Return Error]
        M --> R
        O --> R
    end
    
    style D fill:#9B59B6
    style G fill:#E67E22
    style J fill:#F39C12
    style L fill:#F39C12
    style N fill:#F39C12
```

---

## Cryptographic Primitives

```mermaid
graph TD
    subgraph Identity Layer
        A[Selfie Image] -->|InsightFace| B[Face Embedding<br/>512 floats]
        B -->|Serialize| C[Binary Blob<br/>2048 bytes]
        C -->|BLAKE2s-256| D[Fractal ID<br/>32 bytes]
        D -->|Base64url| E[Fractal ID String<br/>43 chars]
    end
    
    subgraph Capsule Structure
        F[Payload JSON] -->|Stringify| G[Payload Bytes]
        G -->|BLAKE2s-256| H[Digest<br/>32 bytes]
        H -->|ECDSA-SHA384| I[Signature<br/>96 bytes]
        G -->|Base64url| J[Payload B64]
        I -->|Base64url| K[Signature B64]
        J --> L[Token: payload.signature]
        K --> L
    end
    
    subgraph Verification
        M[Received Token] -->|Split on '.'| N[Payload B64]
        M --> O[Signature B64]
        N -->|Decode| P[Payload Bytes]
        O -->|Decode| Q[Signature Bytes]
        P -->|BLAKE2s-256| R[Recompute Digest]
        Q -->|ECDSA-SHA384| S[Verify Signature]
        R --> S
        S -->|Public Key| T{Valid?}
        T -->|Yes| U[Extract Scope]
        T -->|No| V[Reject]
    end
    
    style B fill:#3498DB
    style H fill:#E74C3C
    style I fill:#E74C3C
    style S fill:#2ECC71
```

---

## Consent Capsule Anatomy

```
┌─────────────────────────────────────────────────────────────┐
│                    Consent Capsule Token                     │
│                                                              │
│  Format: {payload_b64}.{signature_b64}                       │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────┐
│         Payload (JSON)           │
├──────────────────────────────────┤
│ iss: "did:key:..."              │ ← Issuer DID (public key)
│ sub: "XYZ123..."                │ ← Fractal ID (subject)
│ scope: {                        │
│   "art": "allow",               │ ← Granular permissions
│   "erotic": "deny",             │
│   "explicit_18": "deny"         │
│ }                               │
│ iat: 1703001234                 │ ← Issued at (timestamp)
│ exp: 1703004834                 │ ← Expires (timestamp)
│ cid: "uuid-v4"                  │ ← Capsule ID (for revocation)
└──────────────────────────────────┘
          │
          ▼ (BLAKE2s hash)
┌──────────────────────────────────┐
│     32-byte Digest               │
└──────────────────────────────────┘
          │
          ▼ (ECDSA-SHA384 sign)
┌──────────────────────────────────┐
│     96-byte Signature            │
│  (SECP384R1 curve, r + s)        │
└──────────────────────────────────┘
```

---

## Data Flow: Complete Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant C as Consent Layer
    participant P as Platform
    participant G as Generator
    
    Note over U,G: Phase 1: Identity Establishment
    U->>C: POST /fractal-id (selfie)
    C->>C: Extract face embedding
    C->>C: Hash to Fractal ID
    C-->>U: {"fractal_id": "XYZ123"}
    
    Note over U,G: Phase 2: Consent Grant
    U->>C: POST /capsule/issue
    Note right of U: scope: {art: allow, explicit_18: deny}
    C->>C: Sign with issuer key
    C-->>U: {"capsule": "eyJ..."}
    
    Note over U,G: Phase 3: Generation Request
    U->>P: Generate "portrait of me"
    P->>C: POST /check
    Note right of P: {fractal_id, prompt, capsule}
    
    C->>C: Verify ECDSA signature
    C->>C: Check not revoked
    C->>C: Classify prompt → "art"
    C->>C: Match against scope
    C-->>P: {"allowed": true}
    
    P->>G: Run inference
    G-->>P: Generated image
    P-->>U: Image returned
    
    Note over U,G: Phase 4: Revocation
    U->>C: POST /capsule/revoke/{cid}
    C->>C: Add to revocation list
    C-->>U: {"revoked": "cid"}
    
    Note over U,G: Phase 5: Subsequent Request (Post-Revoke)
    U->>P: Generate "another portrait"
    P->>C: POST /check (same capsule)
    C->>C: Check revocation → FOUND
    C-->>P: {"allowed": false, "reason": "capsule_revoked"}
    P-->>U: Error: Consent revoked
```

---

## Scope Enforcement Logic

```mermaid
graph TD
    A[Prompt Received] --> B{Contains explicit terms?}
    B -->|Yes| C[Category: explicit_18]
    B -->|No| D{Contains erotic terms?}
    D -->|Yes| E[Category: erotic]
    D -->|No| F[Category: art]
    
    C --> G{Capsule scope?}
    E --> G
    F --> G
    
    G -->|explicit_18: allow| H[ALLOW]
    G -->|explicit_18: deny| I[DENY: explicit_18_generation_denied]
    G -->|erotic: allow| H
    G -->|erotic: deny| J[DENY: erotic_generation_denied]
    G -->|art: allow| H
    G -->|art: deny| K[DENY: art_generation_denied]
    G -->|Not specified| L[DENY: {category}_generation_denied]
    
    style H fill:#2ECC71
    style I fill:#E74C3C
    style J fill:#E74C3C
    style K fill:#E74C3C
    style L fill:#E74C3C
```

**Keyword Sets:**

- **Explicit:** `nude`, `naked`, `nsfw`, `porn`, `sex`, `explicit`, `bare`, `uncensored`, `topless`, `bottomless`, `genital`, `x-rated`
- **Erotic:** `lingerie`, `bikini`, `sensual`, `erotic`, `seductive`, `bedroom`, `boudoir`
- **Art:** Everything else (default)

---

## Deployment Architectures

### Single-Instance Deployment

```mermaid
graph LR
    A[Load Balancer] --> B[Consent Layer]
    B --> C[(Issuer Key PEM)]
    B --> D[(Revocation List)]
    
    E[Platform 1] --> A
    F[Platform 2] --> A
    G[Platform 3] --> A
    
    style B fill:#3498DB
```

### High-Availability Deployment

```mermaid
graph TB
    A[Load Balancer] --> B[Consent Layer 1]
    A --> C[Consent Layer 2]
    A --> D[Consent Layer 3]
    
    B --> E[(Shared Issuer Key)]
    C --> E
    D --> E
    
    B --> F[(Redis: Revocation)]
    C --> F
    D --> F
    
    G[Platform API Gateway] --> A
    
    style B fill:#3498DB
    style C fill:#3498DB
    style D fill:#3498DB
    style E fill:#E67E22
    style F fill:#E74C3C
```

### Federated Network (Future)

```mermaid
graph TB
    subgraph Platform A
        A1[Consent Layer A] --> A2[(Issuer Key A)]
    end
    
    subgraph Platform B
        B1[Consent Layer B] --> B2[(Issuer Key B)]
    end
    
    subgraph Platform C
        C1[Consent Layer C] --> C2[(Issuer Key C)]
    end
    
    A1 --> DID[DID Registry<br/>W3C Standard]
    B1 --> DID
    C1 --> DID
    
    DID --> Cross[Cross-Platform<br/>Capsule Verification]
    
    style DID fill:#9B59B6
```

---

## Security Model

```mermaid
graph TD
    subgraph Threat Surface
        A[Signature Forgery] -->|Protected by| B[ECDSA-SHA384<br/>SECP384R1]
        C[Capsule Replay] -->|Protected by| D[Expiration Timestamp]
        E[Identity Spoofing] -->|Protected by| F[Face Embeddings<br/>InsightFace]
        G[Revocation Bypass] -->|Protected by| H[Centralized<br/>Revocation List]
        I[Scope Escalation] -->|Protected by| J[Signed Scope<br/>in Payload]
    end
    
    subgraph Trust Assumptions
        K[Issuer Key Security] -->|Critical| L[Issuer must protect<br/>private key]
        M[Platform Enforcement] -->|Critical| N[Platform must honor<br/>/check response]
        O[User Device Security] -->|Important| P[User must protect<br/>capsule tokens]
    end
    
    style B fill:#2ECC71
    style D fill:#2ECC71
    style F fill:#2ECC71
    style H fill:#2ECC71
    style J fill:#2ECC71
    style L fill:#E74C3C
    style N fill:#E74C3C
```

---

## Performance Profile

```
┌──────────────────────────────────────────────────────────────┐
│                 Endpoint Latency (p50)                        │
├──────────────────────────────────────────────────────────────┤
│  /fractal-id       ████████████████ 150ms (face detection)   │
│  /capsule/issue    █ 2ms (ECDSA sign)                        │
│  /check            █ 0.5ms (verify + scope match)            │
│  /capsule/revoke   █ 1ms (append to file)                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  Memory Footprint                             │
├──────────────────────────────────────────────────────────────┤
│  Reference Spec:   ███ 50 MB (no ML models)                  │
│  Production:       ████████████ 520 MB (InsightFace loaded)  │
└──────────────────────────────────────────────────────────────┘
```

---

## Cryptographic Strength

| Primitive         | Algorithm        | Key Size | Security Level |
|-------------------|------------------|----------|----------------|
| Face ID Hashing   | BLAKE2s          | 256-bit  | 128-bit        |
| Capsule Signing   | ECDSA            | 384-bit  | 192-bit        |
| Curve             | SECP384R1 (P-384)| 384-bit  | 192-bit        |
| Digest (capsule)  | SHA-384          | 384-bit  | 192-bit        |

**Resistance:**
- Quantum resistance: ❌ (ECDSA vulnerable to Shor's algorithm)
- Collision resistance: ✅ (2^128 for BLAKE2s)
- Forgery resistance: ✅ (2^192 for ECDSA)

**Post-Quantum Migration Path:** Replace ECDSA with Dilithium (NIST PQC standard)

---

## API Contract Summary

### Endpoints

| Endpoint                    | Method | Auth | Purpose                          |
|-----------------------------|--------|------|----------------------------------|
| `/fractal-id`               | POST   | None | Generate biometric identity      |
| `/capsule/issue`            | POST   | None | Issue signed consent token       |
| `/check`                    | POST   | None | Verify consent before generation |
| `/capsule/revoke/{cid}`     | POST   | None | Revoke existing capsule          |

### Response Codes

- `200 OK` - Success
- `403 Forbidden` - Consent denied
- `422 Unprocessable Entity` - Invalid request
- `500 Internal Server Error` - System failure

---

## Design Principles

1. **Cryptographic Enforcement** - Trust math, not promises
2. **Default Deny** - No consent = no generation
3. **Instant Revocation** - User retains control
4. **Generator Agnostic** - Works with any image model
5. **Minimal Trust Surface** - Only issuer key is critical
6. **Auditable** - All denials logged with reasons
7. **Portable** - Standard REST API, no vendor lock-in

---

## Future Enhancements

```mermaid
graph LR
    A[Current v0.6] --> B[v0.7: Zero-Knowledge Proofs]
    A --> C[v0.8: Federated DIDs]
    A --> D[v0.9: Post-Quantum Crypto]
    A --> E[v1.0: On-Chain Revocation]
    
    B --> F[Privacy-preserving verification]
    C --> G[Cross-platform capsules]
    D --> H[Quantum-safe signatures]
    E --> I[Decentralized trust]
    
    style A fill:#3498DB
    style B fill:#9B59B6
    style C fill:#9B59B6
    style D fill:#9B59B6
    style E fill:#9B59B6
```

---

## System Guarantees

✅ **Guaranteed:**
- Valid signature → consent was granted by issuer
- Revoked capsule → always denied (no exceptions)
- Expired capsule → always denied
- Scope mismatch → always denied

❌ **NOT Guaranteed:**
- Platform will honor `/check` response (trust required)
- User device security (capsule theft possible)
- Face liveness detection (photo-of-photo attack)
- Legal compliance in your jurisdiction

---

This architecture is designed to be **simple, secure, and universal**. It does one thing well: cryptographic consent enforcement.
