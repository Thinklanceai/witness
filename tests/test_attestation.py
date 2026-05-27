"""Tests for the core attestation primitive.

These tests are the credibility surface of the tool. They prove, without
hand-waving, that:
  - a freshly created attestation verifies
  - altering a single character of the observed payload breaks verification
  - reordering keys in the body does NOT break verification (canonicalization)
  - a signature from a different key is rejected
  - the recorded digest is independently reproducible from the body
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import attestation as att  # noqa: E402


def _sample():
    priv, _pub = att.generate_keypair()
    doc = att.create_attestation(
        query="who is posting about example topic",
        vantage="reference-engine/manual",
        observed={
            "results": [
                {"id": "1", "text": "first observed item", "author": "alice"},
                {"id": "2", "text": "second observed item", "author": "bob"},
            ],
            "citations": ["https://example.com/a", "https://example.com/b"],
        },
        parameters={"from_date": "2026-05-01", "to_date": "2026-05-26"},
        private_key_b64=priv,
    )
    return priv, doc


def test_roundtrip_verifies():
    _priv, doc = _sample()
    report = att.verify_attestation(doc)
    assert report["verified"] is True
    assert report["digest"] == doc["seal"]["digest"]
    print("PASS roundtrip_verifies")


def test_single_byte_alteration_rejected():
    _priv, doc = _sample()
    tampered = copy.deepcopy(doc)
    original = tampered["body"]["observed"]["results"][0]["text"]
    tampered["body"]["observed"]["results"][0]["text"] = original[:-1] + (
        "X" if original[-1] != "X" else "Y"
    )
    try:
        att.verify_attestation(tampered)
    except att.VerificationError as exc:
        assert "altered" in str(exc)
        print("PASS single_byte_alteration_rejected")
        return
    raise AssertionError("tampered attestation was accepted")


def test_key_reorder_does_not_break():
    _priv, doc = _sample()
    reordered = copy.deepcopy(doc)
    body = reordered["body"]
    reordered["body"] = {k: body[k] for k in reversed(list(body.keys()))}
    report = att.verify_attestation(reordered)
    assert report["verified"] is True
    print("PASS key_reorder_does_not_break")


def test_foreign_signature_rejected():
    _priv, doc = _sample()
    other_priv, _ = att.generate_keypair()
    forged = copy.deepcopy(doc)
    resealed = att.seal(forged["body"], other_priv)
    forged["seal"]["signature"] = resealed["seal"]["signature"]
    try:
        att.verify_attestation(forged)
    except att.VerificationError as exc:
        assert "signature is invalid" in str(exc)
        print("PASS foreign_signature_rejected")
        return
    raise AssertionError("forged signature was accepted")


def test_digest_independently_reproducible():
    _priv, doc = _sample()
    independent = att.digest_hex(doc["body"])
    assert independent == doc["seal"]["digest"]
    print("PASS digest_independently_reproducible")


if __name__ == "__main__":
    test_roundtrip_verifies()
    test_single_byte_alteration_rejected()
    test_key_reorder_does_not_break()
    test_foreign_signature_rejected()
    test_digest_independently_reproducible()
    print("\nAll tests passed.")
