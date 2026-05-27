"""Temporal diff between two attestations of the same query.

This is the layer that turns a pile of signed snapshots into signal: it shows
how an observation of the same query changed between two points in time.

It does NOT compare an observation to "the truth". It compares two observations
to each other. Each observation is a signed, verifiable record; the diff between
them is what reveals drift, emergence, or disappearance of sources over time.
The mutation is the signal, the way a git diff is the signal between two commits.

Discipline: a diff is only meaningful between two attestations that both verify.
This module verifies both before comparing and refuses to diff if either fails.
"""

from __future__ import annotations

from typing import Any

import attestation as att


class DiffError(Exception):
    """Raised when a diff cannot be produced (e.g. an attestation fails to verify)."""


def _citation_set(observed: dict[str, Any]) -> set[str]:
    citations = observed.get("citations", [])
    return {c for c in citations if isinstance(c, str)}


def diff_attestations(
    earlier: dict[str, Any],
    later: dict[str, Any],
) -> dict[str, Any]:
    """Compare two attestations of (ideally) the same query over time.

    Both attestations are verified first. If either fails verification, no diff
    is produced. The caller is responsible for passing them in chronological
    order; if they are reversed, this function reorders them by observed_at and
    notes that it did so.

    Returns a structured report describing citation churn, whether the answer
    text changed, the time gap, and whether the two attestations share the same
    query (a mismatch is surfaced, not hidden).
    """
    try:
        att.verify_attestation(earlier)
    except att.VerificationError as exc:
        raise DiffError(f"earlier attestation failed verification: {exc}") from exc
    try:
        att.verify_attestation(later)
    except att.VerificationError as exc:
        raise DiffError(f"later attestation failed verification: {exc}") from exc

    body_a = earlier["body"]
    body_b = later["body"]

    ts_a = body_a.get("observed_at", "")
    ts_b = body_b.get("observed_at", "")
    reordered = False
    if ts_a and ts_b and ts_a > ts_b:
        body_a, body_b = body_b, body_a
        ts_a, ts_b = ts_b, ts_a
        reordered = True

    obs_a = body_a.get("observed", {})
    obs_b = body_b.get("observed", {})

    cites_a = _citation_set(obs_a)
    cites_b = _citation_set(obs_b)

    added = sorted(cites_b - cites_a)
    removed = sorted(cites_a - cites_b)
    stable = sorted(cites_a & cites_b)

    text_a = obs_a.get("answer_text", "")
    text_b = obs_b.get("answer_text", "")

    return {
        "same_query": body_a.get("query") == body_b.get("query"),
        "query_earlier": body_a.get("query"),
        "query_later": body_b.get("query"),
        "observed_at_earlier": ts_a,
        "observed_at_later": ts_b,
        "reordered_by_timestamp": reordered,
        "citations_added": added,
        "citations_removed": removed,
        "citations_stable": stable,
        "citation_counts": {
            "earlier": len(cites_a),
            "later": len(cites_b),
            "added": len(added),
            "removed": len(removed),
            "stable": len(stable),
        },
        "answer_text_changed": text_a != text_b,
        "digest_earlier": earlier["seal"]["digest"],
        "digest_later": later["seal"]["digest"],
    }
