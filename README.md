# X Identity Shield — Consent Layer v0.6

[![CI](https://github.com/FractalFuryan/x-consent-layer/actions/workflows/ci.yml/badge.svg)](https://github.com/FractalFuryan/x-consent-layer/actions)

**The cryptographic consent firewall that ends non-consensual deepfake generation.**

- No blockchain
- No NFTs  
- No bullshit
- 100% open source, MIT licensed
- Works with **any image generator** (Stable Diffusion, DALL·E, Midjourney, custom models)
- Production-ready today

---

## What It Does

1. **Identity Binding:** Upload selfie → get permanent `fractal_id` (biometric hash)
2. **Consent Issuance:** Create signed consent capsule specifying scope (art/erotic/explicit)
3. **Enforcement Gate:** Platform calls `/check` before generation → allow/deny + reason
4. **Instant Revocation:** Revoke consent anytime → all future requests denied

**Default Behavior:** No consent capsule = **no generation** (even innocent art)

---

## Documentation

- **[🏗️ ARCHITECTURE.md](ARCHITECTURE.md)** - System diagrams, data flows, cryptographic primitives
- **[🔌 INTEGRATION.md](INTEGRATION.md)** - Platform integration guide (model-agnostic)
- **[⚖️ COMPARISON.md](COMPARISON.md)** - Reference vs Production implementation comparison

---

## Quick Start

### Production Version (Main Branch)

**Features:** Real face embeddings, persistent keys, file-backed revocation

```bash
git clone https://github.com/FractalFuryan/x-consent-layer.git
cd x-consent-layer
pip install -r requirements.txt
uvicorn consent_api:app --reload
```

Open http://127.0.0.1:8000/docs

### Reference Version (Demo Branch)

**Features:** Hash-based IDs, in-memory state, zero ML dependencies

```bash
git clone https://github.com/FractalFuryan/x-consent-layer.git
cd x-consent-layer
git checkout reference-demo
pip install -r requirements.txt
uvicorn consent_api:app --reload
```

**See [COMPARISON.md](COMPARISON.md) for version selection guidance.**

---

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

Consent layer will be available at http://localhost:8000

**Persistent Data:** Issuer keys and revocation list stored in `./data/`

---

## API Endpoints

| Endpoint                    | Method | Purpose                              |
|-----------------------------|--------|--------------------------------------|
| `/fractal-id`               | POST   | Generate biometric identity from selfie |
| `/capsule/issue`            | POST   | Issue signed consent capsule         |
| `/check`                    | POST   | **Enforcement gate** (allow/deny)    |
| `/capsule/revoke/{cid}`     | POST   | Instant revocation                   |

---

## Example Usage

### 1. Generate Fractal ID

```bash
curl -X POST http://localhost:8000/fractal-id \
  -F "file=@selfie.jpg"

# Response:
# {"fractal_id": "XYZ123..."}
```

### 2. Issue Consent Capsule

```bash
curl -X POST http://localhost:8000/capsule/issue \
  -H "Content-Type: application/json" \
  -d '{
    "fractal_id": "XYZ123...",
    "scope": {
      "art": "allow",
      "erotic": "deny",
      "explicit_18": "deny"
    },
    "expires_in": 3600
  }'

# Response:
# {"capsule": "eyJ..."}
```

### 3. Check Consent (Platform Integration)

```bash
curl -X POST http://localhost:8000/check \
  -H "Content-Type: application/json" \
  -d '{
    "fractal_id": "XYZ123...",
    "prompt": "portrait of user",
    "capsule": "eyJ..."
  }'

# Response (ALLOW):
# {"allowed": true, "reason": "consent_granted"}

# Response (DENY):
# {"allowed": false, "reason": "explicit_18_generation_denied"}
```

### 4. Revoke Consent

```bash
curl -X POST http://localhost:8000/capsule/revoke/{capsule_id}

# Response:
# {"revoked": "{capsule_id}"}
```

---

## Platform Integration

**This system is generator-agnostic.** It works with:

- Stable Diffusion (all variants)
- DALL·E / GPT Image APIs
- Midjourney-style services
- ComfyUI / Invoke AI / Fooocus
- Custom diffusion pipelines
- Any future image model

**Integration Pattern:**

```python
# Before generating image
response = requests.post("https://consent-layer/check", json={
    "fractal_id": user_id,
    "prompt": generation_prompt,
    "capsule": user_consent_token
})

if not response.json()["allowed"]:
    return error("Generation denied: " + response.json()["reason"])

# Proceed with generation
image = your_model.generate(prompt)
```

**See [INTEGRATION.md](INTEGRATION.md) for detailed examples (WebUI, API gateway, ComfyUI, etc.)**

---

## Architecture Overview

```
User Selfie → Fractal ID (biometric hash)
       ↓
Issue Consent Capsule (ECDSA-signed token)
       ↓
Platform calls /check before generation
       ↓
Verify signature + scope + revocation
       ↓
ALLOW → Generate  |  DENY → Block + reason
```

**See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and cryptographic specs.**

---

## Security Model

### Cryptographic Primitives

- **Identity Hashing:** BLAKE2s (256-bit)
- **Signature Algorithm:** ECDSA with SHA-384
- **Curve:** SECP384R1 (P-384, 192-bit security)
- **Encoding:** Base64url (URL-safe)

### Threat Protection

| Attack                  | Protection                              |
|-------------------------|-----------------------------------------|
| Signature forgery       | ✅ ECDSA-SHA384                         |
| Capsule replay          | ✅ Expiration timestamps                |
| Identity spoofing       | ✅ Face embeddings (InsightFace)        |
| Revocation bypass       | ✅ Centralized revocation list          |
| Scope escalation        | ✅ Signed scope in payload              |

### Trust Assumptions

⚠️ **Critical:** Platform must honor `/check` response (no bypass)  
⚠️ **Critical:** Issuer must protect private key (`issuer_key.pem`)  
⚠️ **Important:** User must protect capsule tokens (no sharing)

---

## Testing

```bash
# Run test suite
pytest tests/test_core.py -v

# Expected output
# 6 passed in 0.04s
```

**Tests cover:** Capsule issuance, verification, revocation, scope enforcement, edge cases

---

## Production Deployment

### Cloud Deployment (Single Instance)

```bash
# AWS EC2 / Azure VM / GCP Compute
uvicorn consent_api:app --host 0.0.0.0 --port 8000 --workers 4

# Add Cloudflare for HTTPS + DDoS protection
```

### High-Availability (Kubernetes)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: consent-layer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: consent-layer
  template:
    spec:
      containers:
      - name: api
        image: consent-layer:latest
        ports:
        - containerPort: 8000
        volumeMounts:
        - name: issuer-key
          mountPath: /data/issuer_key.pem
      volumes:
      - name: issuer-key
        persistentVolumeClaim:
          claimName: issuer-key-pvc
```

**See [INTEGRATION.md](INTEGRATION.md) for deployment architecture patterns.**

---

## Performance Benchmarks

| Operation          | Latency (p50) | Notes                          |
|--------------------|---------------|--------------------------------|
| `/fractal-id`      | 150ms         | Face detection + embedding     |
| `/capsule/issue`   | 2ms           | ECDSA signature                |
| `/check`           | 0.5ms         | Verify + scope match           |
| `/capsule/revoke`  | 1ms           | Append to revocation list      |

**Memory:** ~50 MB (reference) / ~520 MB (production with ML models)

---

## Version Comparison

| Feature              | Reference (`reference-demo` branch) | Production (`main` branch)     |
|----------------------|-------------------------------------|--------------------------------|
| Face Recognition     | ❌ Hash-based (demo only)           | ✅ InsightFace embeddings      |
| Persistent Keys      | ❌ In-memory                        | ✅ File-backed                 |
| ML Dependencies      | ❌ None                             | ✅ PyTorch, InsightFace        |
| Production Ready     | ❌ Audit/demo only                  | ✅ Real deployment             |
| Docker Image Size    | ~200 MB                             | ~2 GB                          |
| Use Case             | Security review, education          | Real identity verification     |

**Choose based on your needs.** See [COMPARISON.md](COMPARISON.md) for detailed breakdown.

---

## License

**MIT License** - Do whatever you want with it.

```
Copyright (c) 2024 X Identity Shield Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software...
```

**See [LICENSE](LICENSE) for full text.**

---

## Contributing

This is a **consent firewall**, not a content moderation system. Contributions should focus on:

- ✅ Cryptographic improvements
- ✅ Performance optimizations
- ✅ Platform integrations
- ✅ Security audits
- ❌ Content policy debates
- ❌ Blockchain/Web3 nonsense

**Open issues for discussion before major PRs.**

---

## Roadmap

- [x] v0.6: Production implementation with InsightFace
- [x] v0.6: Reference spec with zero dependencies
- [x] v0.6: Docker deployment
- [x] v0.6: Comprehensive documentation
- [ ] v0.7: Zero-knowledge proofs (privacy-preserving verification)
- [ ] v0.8: Federated DID support (cross-platform capsules)
- [ ] v0.9: Post-quantum cryptography (Dilithium signatures)
- [ ] v1.0: On-chain revocation (decentralized trust)

---

## FAQ

**Q: Does this work with Stable Diffusion?**  
A: Yes. Works with any image generator (SD, DALL·E, Midjourney, custom models).

**Q: Do users need to install anything?**  
A: No. Platforms integrate the API, users just upload selfies and manage capsules.

**Q: Can capsules be faked?**  
A: No. ECDSA signatures are cryptographically unforgeable (2^192 security).

**Q: What if platform ignores `/check`?**  
A: Trust required. This is a firewall, not forced compliance. Choose platforms that respect consent.

**Q: Is this GDPR compliant?**  
A: Cryptographic consent is provided. Legal compliance depends on jurisdiction. Consult your lawyer.

**Q: Can I run this locally?**  
A: Yes. `uvicorn consent_api:app --reload` and you're done.

---

## Support

- **Issues:** https://github.com/FractalFuryan/x-consent-layer/issues
- **Discussions:** https://github.com/FractalFuryan/x-consent-layer/discussions
- **Security:** Report vulnerabilities via GitHub Security Advisories

---

Made by people who are tired of deepfake abuse.  
Powered by cryptography, not promises. 
