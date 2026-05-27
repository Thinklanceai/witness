"""Show how an observation of the same query changed between two attestations.

Usage:
    python diff.py earlier-attestation.json later-attestation.json
    python diff.py earlier.json later.json --html diff.html

Both attestations are verified before being compared. If either fails, no diff
is produced. Order does not have to be correct: if the two are reversed in time,
they are reordered by their recorded timestamps and the report notes it.

With --html, a standalone, shareable HTML card is written from the same verified
report. The HTML is self-contained and escapes all dynamic content.

This compares two observations to each other, never to "the truth".
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import diff as diffmod  # noqa: E402
import render_html  # noqa: E402


def _load(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        sys.stderr.write(f"error: file not found: {path}\n")
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def _print_text(report: dict) -> None:
    if not report["same_query"]:
        print("WARNING: the two attestations are for different queries")
        print(f"  earlier query: {report['query_earlier']}")
        print(f"  later query:   {report['query_later']}")
        print()

    if report["reordered_by_timestamp"]:
        print("(note: inputs were reordered by timestamp)\n")

    print("TEMPORAL DIFF")
    print(f"  from  {report['observed_at_earlier']}")
    print(f"  to    {report['observed_at_later']}")
    print()
    counts = report["citation_counts"]
    print(f"  citations earlier: {counts['earlier']}")
    print(f"  citations later:   {counts['later']}")
    print(f"  added:   {counts['added']}")
    print(f"  removed: {counts['removed']}")
    print(f"  stable:  {counts['stable']}")
    print(f"  answer text changed: {report['answer_text_changed']}")

    if report["citations_added"]:
        print("\n  + appeared:")
        for url in report["citations_added"]:
            print(f"      {url}")
    if report["citations_removed"]:
        print("\n  - disappeared:")
        for url in report["citations_removed"]:
            print(f"      {url}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff two attestations of the same query over time."
    )
    parser.add_argument("earlier", help="path to the earlier attestation")
    parser.add_argument("later", help="path to the later attestation")
    parser.add_argument(
        "--html",
        metavar="PATH",
        default=None,
        help="also write a standalone HTML card to PATH",
    )
    args = parser.parse_args()

    earlier = _load(args.earlier)
    later = _load(args.later)

    try:
        report = diffmod.diff_attestations(earlier, later)
    except diffmod.DiffError as exc:
        sys.stderr.write(f"diff refused: {exc}\n")
        return 1

    _print_text(report)

    if args.html:
        html_doc = render_html.render_diff_html(report)
        out_path = Path(args.html)
        out_path.write_text(html_doc, encoding="utf-8")
        sys.stderr.write(f"\nHTML card written to {out_path}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
