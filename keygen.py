"""Generate an Ed25519 keypair for signing attestations.

Usage:
    python keygen.py

Prints the private and public keys (base64, raw bytes). Store the private key
securely; it is the only secret. The public key is embedded in every
attestation you sign, so anyone can verify your attestations offline.

This tool never transmits keys anywhere.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import attestation as att  # noqa: E402


def main() -> int:
    private_b64, public_b64 = att.generate_keypair()
    sys.stderr.write(
        "Keep the private key secret. Anyone with it can sign as you.\n"
        "The public key is safe to share and is embedded in your attestations.\n\n"
    )
    print(f"private_key={private_b64}")
    print(f"public_key={public_b64}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
