import base64
import json
import time
import uuid
import hashlib
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    encode_dss_signature,
    decode_dss_signature,
)
from cryptography.exceptions import InvalidSignature

# =========================
# Global State
# =========================

_face_app = None  # lazy-loaded face model placeholder

ISSUER_PRIVATE_KEY = ec.generate_private_key(ec.SECP384R1())
ISSUER_PUBLIC_KEY = ISSUER_PRIVATE_KEY.public_key()
ISSUER_PUBLIC_PEM = ISSUER_PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

ISSUER_DID = "did:key:" + ISSUER_PUBLIC_KEY.public_numbers().x.to_bytes(
    48, "big"
).hex()

REVOKED_CAPSULE_IDS: set[str] = set()

EXPLICIT_TERMS = {
    "nude", "naked", "nsfw", "porn", "sex", "explicit", "bare",
    "uncensored", "topless", "bottomless", "genital", "x-rated",
}

EROTIC_TERMS = {
    "lingerie", "bikini", "sensual", "erotic", "seductive",
    "bedroom", "boudoir",
}

# =========================
# Helpers
# =========================

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

# =========================
# Face / Fractal ID
# =========================

def fractal_id_from_image(image_bytes: bytes) -> str:
    """
    Placeholder: hash-based stable identity.
    Swap with real face embedding model.
    """
    h = hashlib.blake2s(image_bytes, digest_size=32).digest()
    return _b64url(h)

# =========================
# Capsule Issuance
# =========================

def issue_capsule(
    fractal_id: str,
    scope: Dict[str, str],
    expires_in: int = 3600,
) -> str:
    capsule_id = str(uuid.uuid4())
    payload = {
        "iss": ISSUER_DID,
        "sub": fractal_id,
        "scope": scope,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
        "cid": capsule_id,
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    digest = hashlib.blake2s(payload_bytes, digest_size=32).digest()

    sig = ISSUER_PRIVATE_KEY.sign(digest, ec.ECDSA(hashes.SHA384()))
    r, s = decode_dss_signature(sig)
    signature = encode_dss_signature(r, s)

    token = f"{_b64url(payload_bytes)}.{_b64url(signature)}"
    return token

# =========================
# Revocation
# =========================

def revoke_capsule(capsule_id: str) -> None:
    REVOKED_CAPSULE_IDS.add(capsule_id)

def is_revoked(capsule_id: str) -> bool:
    return capsule_id in REVOKED_CAPSULE_IDS

# =========================
# Verification & Enforcement
# =========================

def _classify_prompt(prompt: str) -> str:
    p = prompt.lower()
    if any(term in p for term in EXPLICIT_TERMS):
        return "explicit_18"
    if any(term in p for term in EROTIC_TERMS):
        return "erotic"
    return "art"

def verify_and_enforce(
    fractal_id: str,
    prompt: str,
    capsule_token: Optional[str],
) -> Dict[str, Any]:

    if not capsule_token:
        return {"allowed": False, "reason": "no_consent_capsule"}

    try:
        payload_b64, sig_b64 = capsule_token.split(".")
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)

        payload = json.loads(payload_bytes)
        digest = hashlib.blake2s(payload_bytes, digest_size=32).digest()

        ISSUER_PUBLIC_KEY.verify(
            signature,
            digest,
            ec.ECDSA(hashes.SHA384()),
        )
    except (ValueError, InvalidSignature):
        return {"allowed": False, "reason": "invalid_capsule"}

    if payload["sub"] != fractal_id:
        return {"allowed": False, "reason": "identity_mismatch"}

    if payload["exp"] < int(time.time()):
        return {"allowed": False, "reason": "capsule_expired"}

    if is_revoked(payload["cid"]):
        return {"allowed": False, "reason": "capsule_revoked"}

    category = _classify_prompt(prompt)
    scope = payload.get("scope", {})

    if scope.get(category, "deny") != "allow":
        return {
            "allowed": False,
            "reason": f"{category}_generation_denied",
        }

    return {"allowed": True, "reason": "consent_granted"}
