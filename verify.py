"""Verify an attestation, fully offline.

Usage:
    python verify.py attestation.json

Exit code 0 and a short report on success. Exit code 1 and an error on any
integrity or signature failure. Requires no API key and no network access:
a skeptic can verify your attestation with nothing but this file and the
attestation itself.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import attestation as att  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: python verify.py <attestation.json>\n")
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        sys.stderr.write(f"error: file not found: {path}\n")
        return 2

    document = json.loads(path.read_text(encoding="utf-8"))

    try:
        report = att.verify_attestation(document)
    except att.VerificationError as exc:
        sys.stderr.write(f"VERIFICATION FAILED: {exc}\n")
        return 1

    print("VERIFIED")
    print(f"  digest      {report['digest']}")
    print(f"  public_key  {report['public_key']}")
    print(f"  observed_at {report['observed_at']}")
    print(f"  vantage     {report['vantage']}")
    print(f"  query       {report['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
