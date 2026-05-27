"""Create an attestation from an observation payload.

This morceau does not call any external API yet. It seals an observation you
provide, so the integrity and signature machinery can be exercised end to end
before any engine is wired in. The engine that fills 'observed' from a live
source is a later, separate piece.

Usage:
    python attest.py \\
        --query "the exact request that produced the observation" \\
        --vantage "label for where/how it was observed" \\
        --observed-file path/to/observed.json \\
        --private-key-env ATTEST_PRIVATE_KEY \\
        --out attestation.json

The private key is read from an environment variable, never from the command
line, so it does not leak into shell history or process listings.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import attestation as att  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a signed attestation.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--vantage", required=True)
    parser.add_argument(
        "--observed-file",
        required=True,
        help="path to a JSON file holding the raw observed payload",
    )
    parser.add_argument(
        "--parameters-file",
        default=None,
        help="optional path to a JSON file holding the observation parameters",
    )
    parser.add_argument(
        "--private-key-env",
        default="ATTEST_PRIVATE_KEY",
        help="name of the env var holding the base64 Ed25519 private key",
    )
    parser.add_argument("--out", required=True, help="path to write the attestation")
    args = parser.parse_args()

    private_b64 = os.environ.get(args.private_key_env)
    if not private_b64:
        sys.stderr.write(
            f"error: environment variable {args.private_key_env} is not set\n"
        )
        return 2

    observed_path = Path(args.observed_file)
    if not observed_path.is_file():
        sys.stderr.write(f"error: observed file not found: {observed_path}\n")
        return 2
    observed = json.loads(observed_path.read_text(encoding="utf-8"))

    parameters = None
    if args.parameters_file:
        params_path = Path(args.parameters_file)
        if not params_path.is_file():
            sys.stderr.write(f"error: parameters file not found: {params_path}\n")
            return 2
        parameters = json.loads(params_path.read_text(encoding="utf-8"))

    document = att.create_attestation(
        query=args.query,
        vantage=args.vantage,
        observed=observed,
        parameters=parameters,
        private_key_b64=private_b64,
    )

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sys.stderr.write(f"attestation written to {out_path}\n")
    sys.stderr.write(f"digest {document['seal']['digest']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
