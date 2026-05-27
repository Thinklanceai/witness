"""Tests for the HTML diff renderer.

Proves:
  - a report renders to a complete, self-contained HTML document
  - dynamic content is HTML-escaped (no raw script injection)
  - real URLs from the report appear in the output
  - a query mismatch is surfaced in the HTML
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import attestation as att  # noqa: E402
import diff as diffmod  # noqa: E402
import render_html  # noqa: E402


def _report(citations_a, citations_b, *, query_a="topic", query_b="topic"):
    priv, _ = att.generate_keypair()
    a = att.create_attestation(
        query=query_a, vantage="test", observed={"answer_text": "x", "citations": citations_a, "annotations": []},
        private_key_b64=priv, observed_at="2026-05-20T10:00:00Z",
    )
    b = att.create_attestation(
        query=query_b, vantage="test", observed={"answer_text": "y", "citations": citations_b, "annotations": []},
        private_key_b64=priv, observed_at="2026-05-22T10:00:00Z",
    )
    return diffmod.diff_attestations(a, b)


def test_renders_complete_document():
    report = _report(["https://x.com/a"], ["https://x.com/a", "https://x.com/b"])
    doc = render_html.render_diff_html(report)
    assert doc.lstrip().startswith("<!DOCTYPE html>")
    assert "</html>" in doc
    assert "witness diff" in doc
    print("PASS renders_complete_document")


def test_xss_escaped():
    payload = "<script>alert(1)</script>"
    report = _report(["https://x.com/a"], ["https://x.com/a", payload])
    doc = render_html.render_diff_html(report)
    assert payload not in doc, "raw script injected"
    assert "&lt;script&gt;" in doc
    print("PASS xss_escaped")


def test_real_urls_present():
    report = _report(["https://x.com/a"], ["https://x.com/a", "https://x.ai/news"])
    doc = render_html.render_diff_html(report)
    assert "https://x.ai/news" in doc
    print("PASS real_urls_present")


def test_query_mismatch_surfaced():
    report = _report(["https://x.com/a"], ["https://x.com/a"], query_a="one", query_b="two")
    doc = render_html.render_diff_html(report)
    assert "queries differ" in doc
    print("PASS query_mismatch_surfaced")


def test_self_contained():
    report = _report(["https://x.com/a"], ["https://x.com/b"])
    doc = render_html.render_diff_html(report)
    assert "<script src" not in doc
    assert "cdn" not in doc.lower()
    print("PASS self_contained")


if __name__ == "__main__":
    test_renders_complete_document()
    test_xss_escaped()
    test_real_urls_present()
    test_query_mismatch_surfaced()
    test_self_contained()
    print("\nAll render_html tests passed.")
