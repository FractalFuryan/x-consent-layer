import re
from consent_core import issue_consent_capsule, verify_capsule_and_get_scope


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
