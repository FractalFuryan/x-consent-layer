import re
import time
import pytest
from unittest.mock import patch
from consent_core import (
    issue_consent_capsule,
    verify_capsule_and_get_scope,
    revoke_capsule,
    is_revoked,
    check_generation_allowed,
)


def test_issue_and_verify_capsule():
    fid = "fract:test:dummy"
    scope = {"art": "allow", "explicit_18": "deny", "erotic": "deny", "self": "allow"}
    holder = "did:example:holder123"
    token = issue_consent_capsule(fractal_id=fid, scope=scope, holder_did=holder)

    # token format: base64.payload.base64.sig
    assert token.count(".") == 1

    payload = verify_capsule_and_get_scope(token, fid)
    assert payload["sub"] == fid
    assert payload["holder"] == holder
    assert payload["scope"] == scope


def test_revoke_capsule():
    fid = "fract:test:revoke"
    scope = {"art": "allow"}
    token = issue_consent_capsule(fractal_id=fid, scope=scope, holder_did="did:test")
    payload = verify_capsule_and_get_scope(token, fid)
    capsule_id = payload["id"]

    # should work before revocation
    assert not is_revoked(capsule_id)

    # revoke it
    revoke_capsule(capsule_id)
    assert is_revoked(capsule_id)

    # should fail after revocation
    with pytest.raises(ValueError, match="revoked"):
        verify_capsule_and_get_scope(token, fid)


def test_scope_enforcement_art():
    """Test that art generation is denied when scope.art='deny'."""
    fid = "fract:test:art"
    scope = {"art": "deny"}
    token = issue_consent_capsule(fractal_id=fid, scope=scope, holder_did="did:test")

    # Mock fractal_id_from_image to return the same fid without loading ML models
    with patch("consent_core.fractal_id_from_image", return_value=fid):
        result = check_generation_allowed(token, b"dummy_image", "a nice portrait of you")
    
    assert result["allowed"] is False
    assert "art_generation_denied" in result["reason"]


def test_scope_enforcement_explicit():
    """Test that explicit content is denied when scope.explicit_18='deny'."""
    fid = "fract:test:explicit"
    scope = {"explicit_18": "deny", "art": "allow"}
    token = issue_consent_capsule(fractal_id=fid, scope=scope, holder_did="did:test")

    # "nude" is an explicit term
    with patch("consent_core.fractal_id_from_image", return_value=fid):
        result = check_generation_allowed(token, b"dummy_image", "nude portrait of you")
    
    assert result["allowed"] is False
    assert "explicit_content_denied" in result["reason"]


def test_no_capsule():
    """Test that generation is denied with no capsule."""
    fid = "fract:test:nocap"
    with patch("consent_core.fractal_id_from_image", return_value=fid):
        result = check_generation_allowed(None, b"dummy_image", "any prompt")
    
    assert result["allowed"] is False
    assert result["reason"] == "no_consent_capsule"


def test_valid_generation_allowed():
    """Test that generation is allowed when scope permits it."""
    fid = "fract:test:allow"
    scope = {"art": "allow", "explicit_18": "deny"}
    token = issue_consent_capsule(fractal_id=fid, scope=scope, holder_did="did:test")

    with patch("consent_core.fractal_id_from_image", return_value=fid):
        result = check_generation_allowed(token, b"dummy_image", "a nice portrait")
    
    assert result["allowed"] is True
    assert result["reason"] == "consent_granted"


