"""Core attestation primitive.

An attestation is a signed, timestamped record of a single observation. It does
not claim anything about the truth of the observed content. It claims exactly
one thing: that at the recorded time, from the recorded vantage point, a given
query returned a given payload, and that this record has not been altered since
it was signed.

Integrity model:
- The canonical bytes of the attestation body (everything except the seal) are
  produced with RFC 8785 (JSON Canonicalization Scheme). Canonicalization is
  what makes the hash stable across machines, languages, and key orderings.
- The body is hashed with SHA-256.
- The SHA-256 digest is signed with Ed25519.
- The public key is embedded so a third party can verify offline, with no API
  key and no network access.

Verification recomputes the canonical bytes and the digest from the body, then
checks the signature against the embedded public key. A single altered byte in
the body changes the digest and fails verification.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

FORMAT_VERSION = "attestation/0.1"


def _utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_bytes(body: dict[str, Any]) -> bytes:
    """Return the RFC 8785 canonical serialization of an attestation body."""
    return rfc8785.dumps(body)


def digest_hex(body: dict[str, Any]) -> str:
    """SHA-256 of the canonical body, as lowercase hex."""
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair.

    Returns (private_key_b64, public_key_b64) using raw key bytes. The private
    key is returned to the caller only; it is never embedded in an attestation
    and never transmitted by this module.
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_raw = private_key.private_bytes_raw()
    public_raw = public_key.public_bytes_raw()
    return _b64(private_raw), _b64(public_raw)


def build_body(
    *,
    query: str,
    vantage: str,
    observed: Any,
    parameters: dict[str, Any] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Assemble an attestation body (the part that gets hashed and signed).

    query       the exact request that produced the observation
    vantage     a free-form label identifying the observation point/engine
                (e.g. the model and tool used), so a reader knows what produced
                the payload
    observed    the raw payload returned by the observation (kept verbatim;
                this module does not interpret it)
    parameters  the exact parameters used for the observation (optional)
    observed_at ISO-8601 UTC timestamp; defaults to now
    """
    return {
        "format": FORMAT_VERSION,
        "observed_at": observed_at or _utc_now_iso(),
        "vantage": vantage,
        "query": query,
        "parameters": parameters or {},
        "observed": observed,
    }


def seal(body: dict[str, Any], private_key_b64: str) -> dict[str, Any]:
    """Hash and sign a body, returning a complete attestation document.

    The returned document is {"body": ..., "seal": {...}}. The seal carries the
    algorithm identifiers, the hex digest, the base64 signature, and the base64
    public key, so verification needs nothing external.
    """
    private_key = Ed25519PrivateKey.from_private_bytes(_unb64(private_key_b64))
    public_raw = private_key.public_key().public_bytes_raw()

    body_digest = digest_hex(body)
    signature = private_key.sign(bytes.fromhex(body_digest))

    return {
        "body": body,
        "seal": {
            "canonicalization": "RFC8785",
            "hash": "SHA-256",
            "signature_scheme": "Ed25519",
            "digest": body_digest,
            "signature": _b64(signature),
            "public_key": _b64(public_raw),
        },
    }


def create_attestation(
    *,
    query: str,
    vantage: str,
    observed: Any,
    private_key_b64: str,
    parameters: dict[str, Any] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Convenience: build a body and seal it in one call."""
    body = build_body(
        query=query,
        vantage=vantage,
        observed=observed,
        parameters=parameters,
        observed_at=observed_at,
    )
    return seal(body, private_key_b64)


class VerificationError(Exception):
    """Raised when an attestation fails any integrity or signature check."""


def verify_attestation(document: dict[str, Any]) -> dict[str, Any]:
    """Verify an attestation fully offline.

    Checks, in order:
      1. structural shape (body + seal present, expected seal fields)
      2. recomputed canonical digest matches the recorded digest
      3. Ed25519 signature over the digest is valid for the embedded public key

    Returns a small report dict on success. Raises VerificationError on any
    failure. Requires no API key and no network access.
    """
    if not isinstance(document, dict) or "body" not in document or "seal" not in document:
        raise VerificationError("document must contain 'body' and 'seal'")

    body = document["body"]
    sealdata = document["seal"]

    for field in ("digest", "signature", "public_key", "signature_scheme", "canonicalization", "hash"):
        if field not in sealdata:
            raise VerificationError(f"seal missing required field: {field}")

    if sealdata["canonicalization"] != "RFC8785":
        raise VerificationError(f"unsupported canonicalization: {sealdata['canonicalization']}")
    if sealdata["hash"] != "SHA-256":
        raise VerificationError(f"unsupported hash: {sealdata['hash']}")
    if sealdata["signature_scheme"] != "Ed25519":
        raise VerificationError(f"unsupported signature scheme: {sealdata['signature_scheme']}")

    recomputed = digest_hex(body)
    if recomputed != sealdata["digest"]:
        raise VerificationError(
            "digest mismatch: body has been altered since signing"
        )

    public_key = Ed25519PublicKey.from_public_bytes(_unb64(sealdata["public_key"]))
    try:
        public_key.verify(_unb64(sealdata["signature"]), bytes.fromhex(recomputed))
    except InvalidSignature as exc:
        raise VerificationError("signature is invalid for the embedded public key") from exc

    return {
        "verified": True,
        "digest": recomputed,
        "public_key": sealdata["public_key"],
        "observed_at": body.get("observed_at"),
        "vantage": body.get("vantage"),
        "query": body.get("query"),
    }
