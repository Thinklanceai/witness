"""Tests for the temporal diff layer.

Proves:
  - a diff between two valid attestations reports citation churn correctly
  - answer-text change is detected
  - inputs given in reverse chronological order are reordered
  - a diff is REFUSED if either attestation fails verification
  - a query mismatch is surfaced, not hidden
"""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import attestation as att  # noqa: E402
import diff as diffmod  # noqa: E402


def _make(priv, *, query, citations, text, observed_at):
    return att.create_attestation(
        query=query,
        vantage="test/diff",
        observed={"answer_text": text, "citations": citations, "annotations": []},
        private_key_b64=priv,
        observed_at=observed_at,
    )


def test_citation_churn_detected():
    priv, _ = att.generate_keypair()
    earlier = _make(
        priv,
        query="topic",
        citations=["https://x.com/a", "https://x.com/b"],
        text="early state",
        observed_at="2026-05-20T10:00:00Z",
    )
    later = _make(
        priv,
        query="topic",
        citations=["https://x.com/b", "https://x.com/c"],
        text="late state",
        observed_at="2026-05-22T10:00:00Z",
    )
    report = diffmod.diff_attestations(earlier, later)
    assert report["citations_added"] == ["https://x.com/c"]
    assert report["citations_removed"] == ["https://x.com/a"]
    assert report["citations_stable"] == ["https://x.com/b"]
    assert report["answer_text_changed"] is True
    assert report["same_query"] is True
    print("PASS citation_churn_detected")


def test_reorder_by_timestamp():
    priv, _ = att.generate_keypair()
    earlier = _make(
        priv, query="t", citations=["https://x.com/a"], text="x",
        observed_at="2026-05-20T10:00:00Z",
    )
    later = _make(
        priv, query="t", citations=["https://x.com/a", "https://x.com/d"], text="x",
        observed_at="2026-05-25T10:00:00Z",
    )
    report = diffmod.diff_attestations(later, earlier)
    assert report["reordered_by_timestamp"] is True
    assert report["citations_added"] == ["https://x.com/d"]
    assert report["answer_text_changed"] is False
    print("PASS reorder_by_timestamp")


def test_diff_refused_on_tampered():
    priv, _ = att.generate_keypair()
    a = _make(priv, query="t", citations=["https://x.com/a"], text="x",
              observed_at="2026-05-20T10:00:00Z")
    b = _make(priv, query="t", citations=["https://x.com/a"], text="y",
              observed_at="2026-05-21T10:00:00Z")
    tampered = copy.deepcopy(b)
    tampered["body"]["observed"]["answer_text"] = "TAMPERED"
    try:
        diffmod.diff_attestations(a, tampered)
    except diffmod.DiffError as exc:
        assert "failed verification" in str(exc)
        print("PASS diff_refused_on_tampered")
        return
    raise AssertionError("diff was produced from a tampered attestation")


def test_query_mismatch_surfaced():
    priv, _ = att.generate_keypair()
    a = _make(priv, query="topic one", citations=[], text="x",
              observed_at="2026-05-20T10:00:00Z")
    b = _make(priv, query="topic two", citations=[], text="x",
              observed_at="2026-05-21T10:00:00Z")
    report = diffmod.diff_attestations(a, b)
    assert report["same_query"] is False
    print("PASS query_mismatch_surfaced")


if __name__ == "__main__":
    test_citation_churn_detected()
    test_reorder_by_timestamp()
    test_diff_refused_on_tampered()
    test_query_mismatch_surfaced()
    print("\nAll diff tests passed.")
