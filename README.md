# Witness

A small tool that turns a single observation into a **signed, timestamped,
offline-verifiable record**.

It makes exactly one claim, and no more:

> At the recorded time, from the recorded vantage point, this query returned
> this payload — and this record has not been altered since it was signed.

It says **nothing** about whether the observed content is true. It is a
traceability layer, not an arbiter. The analogy is closer to a notarized
snapshot than to a fact-check: it records *what was observed*, not *what is
real*. What a public key *means* — whose it is, whether you trust them — is
deliberately outside this tool's scope.

## Why this exists

The hard problem in 2026 is not that models hallucinate. It is that no one can
reconstruct where an assertion came from, or prove that a record of it hasn't
been quietly edited. Witness addresses the narrow, tractable corner of that
problem: making a single observation tamper-evident and independently
verifiable by anyone, with no API key and no network access.

Grok is currently the one widely available model with native, real-time access
to X. That makes it uniquely able to *observe* the live information graph, but
an observation is only worth something if it can be trusted and re-examined.
Witness is the layer that makes a Grok observation tamper-evident.

It deliberately does **not** try to be a platform, a dashboard, or a verdict
engine. It is one primitive, done carefully.

## How it works

- **Canonicalization:** RFC 8785 (JSON Canonicalization Scheme), so the hash is
  stable regardless of key order, whitespace, or platform.
- **Hash:** SHA-256 over the canonical body bytes.
- **Signature:** Ed25519 over the digest. The public key is embedded, so
  verification needs nothing external.

A single altered byte in the body changes the digest and fails verification.
Reordering keys does not, because canonicalization removes ordering as a
variable.

On reproducibility, honestly: replaying the same query later will **not** give
the same results, because the live graph changes, posts are deleted, and the
model is non-deterministic. Witness does not pretend otherwise. What it attests
is the *observation*, not the world: a faithful, signed record of what one
query returned at one moment. Comparing two attestations of the same query over
time is itself useful signal, but that comparison layer is intentionally not
built here yet.

## Layout

- src/attestation.py - the core: create and verify attestations
- src/observe_xai.py - the engine: query xAI's Responses API, capture the raw
  response faithfully (no summarizing, no filtering, no scoring)
- keygen.py - generate an Ed25519 signing keypair
- witness.py - observe a live Grok query and seal it into an attestation
- attest.py - seal an observation payload you supply yourself (no API needed)
- verify.py - verify an attestation, fully offline
- src/diff.py - the temporal diff: compare two attestations of the same
  query over time and surface what changed (verifies both first)
- diff.py - CLI to diff two attestation files
- tests/ - proves the core properties and the full witness flow

## Install

    pip install -r requirements.txt

Dependencies: cryptography and rfc8785. The engine uses only the standard
library for HTTP, so it adds nothing further.

## Use

Generate a signing key once:

    python keygen.py
    export ATTEST_PRIVATE_KEY=<the private_key value printed above>

Set your xAI key (read only from the environment, never the command line):

    export XAI_API_KEY=<your xAI API key>

Observe a live query and seal it:

    python witness.py \
      --query "what are people saying about a topic" \
      --from-date 2026-05-20 --to-date 2026-05-26 \
      --out attestation.json

Verify it, offline, no key, no network:

    python verify.py attestation.json

Options: --model, --web-search (also enable web_search), --no-x-search,
--from-date, --to-date, --vantage.

## Try it without an xAI key

A local fake of the xAI API is included so you can exercise the whole flow with
no key and no network:

    python tests/test_witness_flow.py

This starts the fake server, runs witness against it, and checks that the
attestation verifies, that the API key never leaks into the record, that the
observation is captured faithfully, and that tampering is detected.

## Compare observations over time

A single attestation is a snapshot. The signal often lives in how an
observation of the same query changes between two points in time: which sources
appear, which disappear, whether the answer shifts. This is the closest thing to
a "git diff" for a live query.

    python diff.py earlier-attestation.json later-attestation.json

Both attestations are verified before anything is compared. If either fails
verification, no diff is produced. The diff compares two observations to each
other, never to "the truth": the mutation between them is the signal.

## Verify someone else's attestation

You need only this tool and their attestation.json:

    python verify.py their-attestation.json

If it prints VERIFIED, the record is intact and the signature matches the
embedded public key.

## Security notes

- The xAI API key and the Ed25519 private key are both read only from the
  environment. Neither is ever placed on the command line or written into an
  attestation.
- Treat the private key as an identity: anyone holding it can sign as you.
- Network calls have a timeout and explicit error handling.

## Status

Early. The format version is attestation/0.1 and may change. This is a
foundation piece published to be inspected, not a finished standard.

## License

MIT.
