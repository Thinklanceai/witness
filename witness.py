"""Witness: observe a live query through Grok and seal it into an attestation.

This ties the engine (observe_xai) to the attestation core (attestation).
It queries the xAI Responses API with real-time search, captures the raw
response faithfully, and writes a signed, offline-verifiable attestation.

Usage:
    python witness.py \\
        --query "what are people saying about X" \\
        --out attestation.json

    # options:
    --model grok-4.3
    --web-search            also enable web_search (x_search is on by default)
    --no-x-search           disable x_search
    --from-date 2026-05-20  restrict X search start (ISO8601)
    --to-date   2026-05-26  restrict X search end (ISO8601)

Secrets, both read only from the environment, never from the command line:
    XAI_API_KEY          your xAI API key
    ATTEST_PRIVATE_KEY   your Ed25519 signing key (see keygen.py)
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import attestation as att  # noqa: E402
import observe_xai  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Observe a Grok query and seal it into an attestation."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=observe_xai.DEFAULT_MODEL)
    parser.add_argument("--web-search", action="store_true")
    parser.add_argument("--no-x-search", action="store_true")
    parser.add_argument("--from-date", default=None)
    parser.add_argument("--to-date", default=None)
    parser.add_argument("--timeout", type=int, default=observe_xai.DEFAULT_TIMEOUT)
    parser.add_argument(
        "--vantage",
        default=None,
        help="optional override for the vantage label; defaults to model+tools",
    )
    args = parser.parse_args()

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        sys.stderr.write("error: environment variable XAI_API_KEY is not set\n")
        return 2

    private_b64 = os.environ.get("ATTEST_PRIVATE_KEY")
    if not private_b64:
        sys.stderr.write("error: environment variable ATTEST_PRIVATE_KEY is not set\n")
        return 2

    x_search_params: dict[str, str] = {}
    if args.from_date:
        x_search_params["from_date"] = args.from_date
    if args.to_date:
        x_search_params["to_date"] = args.to_date

    try:
        observed, parameters = observe_xai.observe(
            query=args.query,
            api_key=api_key,
            model=args.model,
            use_x_search=not args.no_x_search,
            use_web_search=args.web_search,
            x_search_params=x_search_params or None,
            timeout=args.timeout,
        )
    except observe_xai.ObservationError as exc:
        sys.stderr.write(f"observation failed: {exc}\n")
        return 1

    tool_names = "+".join(t["type"] for t in parameters["tools"])
    vantage = args.vantage or f"{parameters['model']}/{tool_names}"

    document = att.create_attestation(
        query=args.query,
        vantage=vantage,
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
    sys.stderr.write(f"citations captured: {len(observed['citations'])}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
