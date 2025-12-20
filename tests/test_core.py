from consent_core import (
    issue_capsule,
    revoke_capsule,
    is_revoked,
    verify_and_enforce,
)

TEST_ID = "test_fractal_id"

def test_issue_and_verify_capsule():
    token = issue_capsule(TEST_ID, {"art": "allow"})
    assert "." in token

    result = verify_and_enforce(
        TEST_ID,
        "a nice portrait",
        token,
    )
    assert result["allowed"] is True

def test_revoke_capsule():
    token = issue_capsule(TEST_ID, {"art": "allow"})
    payload_b64, _ = token.split(".")
    import json, base64
    payload = json.loads(
        base64.urlsafe_b64decode(payload_b64 + "==")
    )
    cid = payload["cid"]

    assert not is_revoked(cid)
    revoke_capsule(cid)
    assert is_revoked(cid)

    result = verify_and_enforce(
        TEST_ID,
        "a nice portrait",
        token,
    )
    assert result["allowed"] is False

def test_scope_enforcement_art():
    token = issue_capsule(TEST_ID, {"art": "deny"})
    result = verify_and_enforce(
        TEST_ID,
        "a nice portrait of you",
        token,
    )
    assert result["allowed"] is False

def test_scope_enforcement_explicit():
    token = issue_capsule(
        TEST_ID,
        {"art": "allow", "explicit_18": "deny"},
    )
    result = verify_and_enforce(
        TEST_ID,
        "nude portrait of you",
        token,
    )
    assert result["allowed"] is False

def test_no_capsule():
    result = verify_and_enforce(
        TEST_ID,
        "a nice portrait",
        None,
    )
    assert result["allowed"] is False
    assert result["reason"] == "no_consent_capsule"

def test_valid_generation_allowed():
    token = issue_capsule(
        TEST_ID,
        {"art": "allow", "explicit_18": "deny"},
    )
    result = verify_and_enforce(
        TEST_ID,
        "a nice portrait",
        token,
    )
    assert result["allowed"] is True


