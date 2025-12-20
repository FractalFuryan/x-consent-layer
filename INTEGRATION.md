# Platform Integration Guide

## Universal Consent Enforcement for Image Generators

This guide shows how **any image generation platform** can integrate the X Identity Shield consent layer, regardless of the underlying model architecture.

---

## Core Principle

> **This system does not depend on how images are generated.**

The consent layer operates as a **cryptographic firewall** that sits **before** the generation process. It works with:

- Stable Diffusion (all variants)
- DALL·E-style hosted APIs
- Midjourney-like services  
- Custom diffusion pipelines
- Local inference tools
- GAN-based generators
- Future architectures not yet invented

---

## Universal Enforcement Contract

Every image generator integrates the same way:

### 1. Before Generation: Call `/check`

```http
POST https://consent-layer.example.com/check
Content-Type: application/json

{
  "fractal_id": "user's biometric identity",
  "prompt": "requested generation prompt",
  "capsule": "signed consent token (optional)"
}
```

### 2. Response: Binary Allow/Deny

```json
{
  "allowed": true,
  "reason": "consent_granted"
}
```

**OR**

```json
{
  "allowed": false,
  "reason": "explicit_18_generation_denied"
}
```

### 3. Enforcement Rule

```
if response["allowed"] == true:
    proceed with generation
else:
    return error to user, log reason, do NOT generate
```

**No exceptions. No creative interpretation. No "I think this is okay" logic.**

---

## Integration Checklist

- [ ] Obtain user's `fractal_id` (POST selfie to `/fractal-id`)
- [ ] Obtain signed consent `capsule` (user issues via `/capsule/issue`)
- [ ] Call `/check` **before every generation**
- [ ] Block generation if `allowed == false`
- [ ] Log denial reason for audit trail
- [ ] Surface denial reason to user
- [ ] Never cache "allow" responses (consent can be revoked)

---

## Example Integrations

### Example 1: Stable Diffusion WebUI Extension

```python
# scripts/consent_firewall.py
import requests
import gradio as gr

CONSENT_API = "https://consent-layer.example.com"

def on_before_image_generation(p):
    """Hook called before SD pipeline runs"""
    
    # Get user's fractal_id and capsule from session
    fractal_id = gr.context.user.fractal_id
    capsule = gr.context.user.consent_capsule
    
    # Check consent
    response = requests.post(f"{CONSENT_API}/check", json={
        "fractal_id": fractal_id,
        "prompt": p.prompt,
        "capsule": capsule
    })
    
    result = response.json()
    
    if not result["allowed"]:
        raise gr.Error(f"Generation denied: {result['reason']}")
    
    # If allowed, continue to generation
    return p

# Register hook
script_callbacks.on_before_image_generated(on_before_image_generation)
```

---

### Example 2: Cloud API Gateway (Platform-Wide)

```python
# api_gateway/middleware.py
from fastapi import Request, HTTPException
import httpx

async def consent_middleware(request: Request, call_next):
    """Global middleware for all generation endpoints"""
    
    if request.url.path.startswith("/v1/generate"):
        body = await request.json()
        
        # Extract identity and consent from request
        fractal_id = request.headers.get("X-Fractal-ID")
        capsule = request.headers.get("X-Consent-Capsule")
        prompt = body.get("prompt")
        
        # Check consent layer
        async with httpx.AsyncClient() as client:
            check = await client.post(
                "https://consent-layer.internal/check",
                json={
                    "fractal_id": fractal_id,
                    "prompt": prompt,
                    "capsule": capsule
                }
            )
        
        result = check.json()
        
        if not result["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Consent required: {result['reason']}"
            )
    
    return await call_next(request)

# Apply globally
app.middleware("http")(consent_middleware)
```

---

### Example 3: ComfyUI Custom Node

```python
# custom_nodes/consent_check.py
class ConsentCheckNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "fractal_id": ("STRING",),
                "prompt": ("STRING",),
                "capsule": ("STRING",),
            }
        }
    
    RETURN_TYPES = ("BOOL", "STRING")
    FUNCTION = "check_consent"
    CATEGORY = "consent"
    
    def check_consent(self, fractal_id, prompt, capsule):
        import requests
        
        response = requests.post(
            "https://consent-layer.example.com/check",
            json={
                "fractal_id": fractal_id,
                "prompt": prompt,
                "capsule": capsule if capsule else None
            }
        )
        
        result = response.json()
        
        if result["allowed"]:
            return (True, "consent_granted")
        else:
            # Block entire workflow
            raise Exception(f"Generation blocked: {result['reason']}")

NODE_CLASS_MAPPINGS = {
    "ConsentCheck": ConsentCheckNode
}
```

---

### Example 4: Local CLI Tool (Invoke AI)

```bash
#!/bin/bash
# generate.sh - Wrapper around invokeai with consent check

FRACTAL_ID="$1"
CAPSULE="$2"
PROMPT="$3"

# Check consent first
RESULT=$(curl -s -X POST https://consent-layer.example.com/check \
  -H "Content-Type: application/json" \
  -d "{
    \"fractal_id\": \"$FRACTAL_ID\",
    \"prompt\": \"$PROMPT\",
    \"capsule\": \"$CAPSULE\"
  }")

ALLOWED=$(echo "$RESULT" | jq -r '.allowed')

if [ "$ALLOWED" != "true" ]; then
  REASON=$(echo "$RESULT" | jq -r '.reason')
  echo "ERROR: Generation denied - $REASON"
  exit 1
fi

# Consent granted - proceed
invokeai-batch --prompt "$PROMPT"
```

---

## Generator Compatibility Matrix

| Platform/Tool         | Integration Method                    | Deployment Type     | Notes                          |
|-----------------------|---------------------------------------|---------------------|--------------------------------|
| Stable Diffusion WebUI| Extension script hook                 | Self-hosted         | Use `on_before_image_generated`|
| ComfyUI               | Custom node (pre-generation)          | Self-hosted         | Block workflow on deny         |
| Invoke AI             | CLI wrapper script                    | Self-hosted         | Wrap generate command          |
| Midjourney            | Bot command interceptor               | Managed service     | Requires bot permissions       |
| DALL·E / GPT Image    | API proxy/middleware                  | Cloud API           | Wrap OpenAI client             |
| Replicate             | Custom model wrapper                  | Cloud API           | Pre-generation hook            |
| Hugging Face Spaces   | Gradio/Streamlit intercept            | Cloud/self-hosted   | Validate before `diffusers`    |
| Custom FastAPI        | Middleware (as shown above)           | Self-hosted/cloud   | Global route protection        |
| Fooocus               | Modify generation script              | Self-hosted         | Edit `modules/async_worker.py` |
| Automatic1111         | Extension API                         | Self-hosted         | `scripts/` directory           |

---

## Model-Agnostic Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                         │
│  "Generate image of [person] doing [activity]"          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│             Consent Layer (/check)                      │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ 1. Verify fractal_id exists             │            │
│  │ 2. Verify capsule signature             │            │
│  │ 3. Check capsule not revoked            │            │
│  │ 4. Classify prompt (art/erotic/explicit)│            │
│  │ 5. Match category against scope         │            │
│  └─────────────────────────────────────────┘            │
│                                                         │
│  Decision: ALLOW or DENY (+ reason)                     │
└────────────────────┬────────────────────────────────────┘
                     │
            ┌────────┴────────┐
            │                 │
         ALLOW              DENY
            │                 │
            ▼                 ▼
   ┌────────────────┐   ┌──────────────────┐
   │  Generate with:│   │  Return error:   │
   │                │   │  "No consent for │
   │ • SD 1.5       │   │   explicit_18"   │
   │ • SDXL         │   │                  │
   │ • DALL·E       │   │  Do NOT generate │
   │ • Midjourney   │   └──────────────────┘
   │ • Flux         │
   │ • Custom model │
   └────────────────┘
```

**Key Point:** The consent layer doesn't care what happens in the "Generate" box. It only controls the gate.

---

## Default Safety Posture

### No Consent = No Generation

```json
// Missing capsule
{
  "fractal_id": "abc123",
  "prompt": "beautiful sunset",
  "capsule": null
}
→ {"allowed": false, "reason": "no_consent_capsule"}
```

**Even for innocent art, consent is required.** This removes ambiguity.

### Explicit Deny = Immediate Block

```json
// Capsule with explicit_18: deny
{
  "scope": {
    "art": "allow",
    "erotic": "deny",
    "explicit_18": "deny"
  }
}

// Later request
{
  "prompt": "nude portrait of user"
}
→ {"allowed": false, "reason": "explicit_18_generation_denied"}
```

**No "creative interpretation" loopholes.** Deny means deny.

### Scope Not Specified = Deny

```json
// Capsule with only art scope
{
  "scope": {
    "art": "allow"
  }
}

// Request for erotic content
{
  "prompt": "seductive pose in lingerie"
}
→ {"allowed": false, "reason": "erotic_generation_denied"}
```

**Default stance: restrictive.** User must explicitly grant each category.

---

## Prompt Classification Logic

The consent layer uses keyword-based classification:

### Category: `explicit_18`
Triggers on: `nude`, `naked`, `nsfw`, `porn`, `sex`, `explicit`, `bare`, `uncensored`, `topless`, `bottomless`, `genital`, `x-rated`

### Category: `erotic`  
Triggers on: `lingerie`, `bikini`, `sensual`, `erotic`, `seductive`, `bedroom`, `boudoir`

### Category: `art` (default)
Everything else that doesn't match above

### Why This Matters

Platforms can **customize** the classification logic, but the default is **intentionally conservative**:

- Reduces false positives (allowing harmful content)
- Accepts false negatives (blocking innocent content)
- Prioritizes consent enforcement over convenience

**Example Override:**

```python
# Custom classifier (platform-specific)
def custom_classify(prompt: str) -> str:
    if platform_ml_model.is_explicit(prompt):
        return "explicit_18"
    if platform_ml_model.is_suggestive(prompt):
        return "erotic"
    return "art"

# Use in /check endpoint
category = custom_classify(request.prompt)
```

---

## Revocation Enforcement

Consent can be **instantly revoked**:

```http
POST /capsule/revoke/{capsule_id}
```

**Effect:** All subsequent `/check` calls with that capsule fail, even if signature is valid.

**Platform Responsibility:**
- Do NOT cache "allow" results
- Call `/check` on **every generation**
- Honor revocation immediately

---

## Integration Testing

### Test 1: No Capsule
```bash
curl -X POST https://consent-layer.example.com/check \
  -H "Content-Type: application/json" \
  -d '{
    "fractal_id": "test_user",
    "prompt": "portrait of test_user",
    "capsule": null
  }'

# Expected: {"allowed": false, "reason": "no_consent_capsule"}
```

### Test 2: Valid Art Consent
```bash
# First, issue capsule
CAPSULE=$(curl -X POST https://consent-layer.example.com/capsule/issue \
  -H "Content-Type: application/json" \
  -d '{
    "fractal_id": "test_user",
    "scope": {"art": "allow", "explicit_18": "deny"}
  }' | jq -r '.capsule')

# Then check
curl -X POST https://consent-layer.example.com/check \
  -H "Content-Type: application/json" \
  -d "{
    \"fractal_id\": \"test_user\",
    \"prompt\": \"beautiful landscape\",
    \"capsule\": \"$CAPSULE\"
  }"

# Expected: {"allowed": true, "reason": "consent_granted"}
```

### Test 3: Explicit Content Denied
```bash
curl -X POST https://consent-layer.example.com/check \
  -H "Content-Type: application/json" \
  -d "{
    \"fractal_id\": \"test_user\",
    \"prompt\": \"nude portrait\",
    \"capsule\": \"$CAPSULE\"
  }"

# Expected: {"allowed": false, "reason": "explicit_18_generation_denied"}
```

### Test 4: Revocation
```bash
# Extract capsule ID
CAPSULE_ID=$(echo "$CAPSULE" | base64 -d | jq -r '.cid' 2>/dev/null || echo "extract_from_jwt")

# Revoke
curl -X POST https://consent-layer.example.com/capsule/revoke/$CAPSULE_ID

# Re-check
curl -X POST https://consent-layer.example.com/check \
  -H "Content-Type: application/json" \
  -d "{
    \"fractal_id\": \"test_user\",
    \"prompt\": \"beautiful landscape\",
    \"capsule\": \"$CAPSULE\"
  }"

# Expected: {"allowed": false, "reason": "capsule_revoked"}
```

---

## Production Deployment

### Option 1: Shared Consent Service (Multi-Tenant)

```
Platform A ──┐
             ├──> Consent Layer (shared)
Platform B ──┤
             └──> Single issuer_key.pem
Platform C ──┘
```

**Pros:** Centralized revocation, unified identity  
**Cons:** Single point of failure, trust in operator

### Option 2: Per-Platform Deployment

```
Platform A ──> Consent Layer A (issuer_key_A.pem)
Platform B ──> Consent Layer B (issuer_key_B.pem)
Platform C ──> Consent Layer C (issuer_key_C.pem)
```

**Pros:** Isolated security, platform control  
**Cons:** Capsules not portable between platforms

### Option 3: Federated Network (Future)

```
Platform A ──> Consent Layer A ──┐
                                  ├──> DID Registry (W3C)
Platform B ──> Consent Layer B ──┤
                                  └──> Cross-verify capsules
Platform C ──> Consent Layer C ──┘
```

**Pros:** Portable consent, decentralized trust  
**Cons:** Complex, requires DID infrastructure

---

## Performance Considerations

### Latency Budget

- **Fractal ID generation:** ~150ms (face detection + embedding)
- **Capsule issuance:** ~2ms (ECDSA sign)
- **Consent check:** ~0.5ms (signature verify + scope match)

**Total overhead per generation:** <200ms (acceptable for most use cases)

### Scaling Strategy

- **Horizontal:** Run multiple consent layer instances behind load balancer
- **Caching:** Do NOT cache "allow" results (consent can change)
- **Database:** For high-revocation workloads, use Redis for revocation list

---

## Security Best Practices

1. **Always use HTTPS** for consent layer API
2. **Validate capsule on every request** (no caching)
3. **Log all denials** for audit/compliance
4. **Rate-limit** capsule issuance to prevent abuse
5. **Rotate issuer keys** periodically (advanced)
6. **Monitor revocation list size** (grows unbounded)

---

## Compliance & Legal

This system provides:

- ✅ **Provable consent** (cryptographic signatures)
- ✅ **Instant revocation** (user control)
- ✅ **Audit trail** (denial reasons logged)
- ✅ **Scope limitation** (granular permissions)

**Not provided:**
- ❌ Legal advice on consent laws
- ❌ GDPR/CCPA compliance guarantees
- ❌ Age verification (18+ check)
- ❌ Content moderation (post-generation)

**Consult your legal team** for jurisdiction-specific requirements.

---

## Summary

**Integration is model-agnostic:**
1. Call `/check` before generation
2. Block if `allowed == false`
3. Never bypass the firewall

**Works with any generator:**
- Diffusion models
- GANs
- Hosted APIs
- Local tools

**Default behavior: secure by design:**
- No consent = no generation
- Revocation is instant
- Scope enforcement is strict

This is a **cryptographic gate**, not a policy document. It enforces consent mechanically, regardless of the generation technology behind it.

---

## Next Steps

1. Deploy consent layer (see [COMPARISON.md](COMPARISON.md) for version choice)
2. Integrate `/check` endpoint into your platform
3. Test with sample capsules
4. Monitor denial rates and adjust prompt classification if needed
5. Educate users on consent capsule issuance

**Questions?** Open an issue at https://github.com/FractalFuryan/x-consent-layer
