# consent_core.py - X Identity Shield Core Library v0.5
import os
import json
import time
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature
import hashlib
# NOTE: heavy ML deps are imported lazily to keep simple imports fast (CI-friendly)

# lazy-loaded face app
_face_app = None

def get_face_app():
    global _face_app
    if _face_app is not None:
        return _face_app
    try:
        from insightface.app import FaceAnalysis
    except Exception as e:
        raise ImportError("insightface is required for face analysis: " + str(e))

    # import torch here so missing heavy deps don't break CI/test collection
    try:
        import torch
        ctx_id = 0 if torch.cuda.is_available() else -1
    except Exception:
        ctx_id = -1

    _face_app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    _face_app.prepare(ctx_id=ctx_id, det_size=(640, 640))
    return _face_app

# ============================
# 1. Persistent Issuer Key
# ============================
def load_or_create_issuer_key(path: str = "issuer_key.pem") -> ec.EllipticCurvePrivateKey:
    if os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = ec.generate_private_key(ec.SECP384R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(path, "wb") as f:
        f.write(pem)
    print(f"[Consent Layer] New issuer key generated → {path}")
    return key

ISSUER_PRIVATE_KEY = load_or_create_issuer_key()
ISSUER_PUBLIC_PEM = ISSUER_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
ISSUER_DID = "did:key:" + ISSUER_PUBLIC_PEM.hex()

# ============================
# 2. Face → Fractal ID
# ============================

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def fract_hash(data: bytes) -> bytes:
    return hashlib.blake2s(data, digest_size=32).digest()

def fractal_id_from_image(img_bytes: bytes, chunks: int = 8) -> str:
    import cv2, numpy as np
    app = get_face_app()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    faces = app.get(img)
    if not faces:
        raise ValueError("No face detected")
    embedding = faces[0].normed_embedding.tobytes()

    h = b""
    step = max(1, len(embedding) // chunks)
    for i in range(chunks):
        start = i * step
        end = len(embedding) if i == chunks - 1 else start + step
        chunk = embedding[start:end]
        h = fract_hash(chunk + h)
    return "fract:v0:" + b64url(h)

# ============================
# 3. Capsule & Enforcement (same as v0.5)
# ============================
def issue_consent_capsule(
    fractal_id: str,
    scope: Dict[str, str],
    holder_did: str,
    price_usd: float = 0.0,
    friends_allowlist: Optional[List[str]] = None,
    audience: Optional[List[str]] = None,
    expires: Optional[int] = None
) -> str:
    payload = {
        "id": "consent:" + os.urandom(10).hex(),
        "iss": ISSUER_DID,
        "sub": fractal_id,
        "holder": holder_did,
        "scope": scope,
        "price": price_usd,
        "friends": friends_allowlist or [],
        "aud": audience or ["x"],
        "iat": int(time.time()),
        "exp": expires or int(time.time()) + 10 * 365 * 24 * 3600,
        "meta": {
            "age_verified": scope.get("explicit_18") == "allow",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    sig = ISSUER_PRIVATE_KEY.sign(payload_bytes, ec.ECDSA(hashes.SHA384()))
    return f"{b64url(payload_bytes)}.{b64url(sig)}"

# Revocation
REVOKED_CAPSULE_IDS = set()
try:
    with open("revoked_capsules.txt", "r") as f:
        REVOKED_CAPSULE_IDS = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    pass

def revoke_capsule(capsule_id: str) -> None:
    REVOKED_CAPSULE_IDS.add(capsule_id)
    with open("revoked_capsules.txt", "a") as f:
        f.write(capsule_id + "\n")

def is_revoked(capsule_id: str) -> bool:
    return capsule_id in REVOKED_CAPSULE_IDS

EXPLICIT_TERMS = {"nude", "naked", "nsfw", "porn", "sex", "explicit", "bare", "uncensored", "topless", "bottomless", "genital", "x-rated"}
EROTIC_TERMS   = {"lingerie", "bikini", "sensual", "erotic", "seductive", "bedroom", "boudoir"}

def verify_capsule_and_get_scope(token: str, target_fid: str) -> Dict[str, Any]:
    if "." not in token:
        raise ValueError("Invalid token format")
    payload_b64, sig_b64 = token.split(".", 1)
    payload_bytes = b64url_decode(payload_b64)
    payload = json.loads(payload_bytes)

    pubkey = serialization.load_pem_public_key(ISSUER_PUBLIC_PEM)
    try:
        pubkey.verify(b64url_decode(sig_b64), payload_bytes, ec.ECDSA(hashes.SHA384()))
    except InvalidSignature:
        raise ValueError("Invalid signature")

    if is_revoked(payload["id"]):
        raise ValueError("Capsule revoked")
    if payload["exp"] < time.time():
        raise ValueError("Capsule expired")
    if "x" not in payload.get("aud", []):
        raise ValueError("Capsule not valid for platform X")
    if payload["sub"] != target_fid:
        raise ValueError("Face does not match capsule subject")
    return payload

def check_generation_allowed(
    capsule_token: Optional[str],
    reference_image_bytes: bytes,
    prompt: str,
    requester_fid: Optional[str] = None
) -> Dict[str, Any]:
    target_fid = fractal_id_from_image(reference_image_bytes)
    prompt_lower = prompt.lower()
    is_explicit = any(term in prompt_lower for term in EXPLICIT_TERMS)
    is_erotic   = any(term in prompt_lower for term in EROTIC_TERMS)
    is_sexual   = is_explicit or is_erotic

    if not capsule_token:
        return {"allowed": False, "reason": "no_consent_capsule", "price": 0.0}

    try:
        capsule = verify_capsule_and_get_scope(capsule_token, target_fid)
    except Exception as e:
        return {"allowed": False, "reason": f"invalid_capsule: {str(e)}", "price": 0.0}

    scope = capsule.get("scope", {})

    if requester_fid == target_fid and scope.get("self") == "deny":
        return {"allowed": False, "reason": "self_generation_disabled", "price": 0.0}

    if requester_fid and requester_fid != target_fid:
        if capsule.get("friends") and requester_fid not in capsule["friends"]:
            return {"allowed": False, "reason": "not_in_friends_allowlist", "price": 0.0}

    if not is_sexual:
        if scope.get("art") == "deny":
            return {"allowed": False, "reason": "art_generation_denied", "price": 0.0}
        if scope.get("art") != "allow":
            return {"allowed": False, "reason": "art_not_explicitly_allowed", "price": 0.0}

    if is_explicit and scope.get("explicit_18") != "allow":
        return {"allowed": False, "reason": "explicit_content_denied", "price": 0.0}
    if is_erotic and scope.get("erotic") != "allow":
        return {"allowed": False, "reason": "erotic_content_denied", "price": 0.0}

    return {
        "allowed": True,
        "reason": "consent_granted",
        "scope": scope,
        "price": capsule.get("price", 0.0),
        "capsule_id": capsule["id"],
        "holder": capsule["holder"]
    }
