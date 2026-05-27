"""Render a temporal-diff report as a standalone, shareable HTML card.

The HTML is self-contained (no external assets, no scripts) so it can be opened
anywhere or screenshotted for sharing. All dynamic content (URLs, queries,
timestamps) is HTML-escaped: the diff data ultimately originates from an
external source, so it is treated as untrusted and never injected raw.

This module only formats a report produced by diff.diff_attestations. It does
not itself verify anything; the caller is expected to have produced the report
through the verifying diff path.
"""

from __future__ import annotations

import html
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_diff_html(report: dict[str, Any]) -> str:
    """Return a complete HTML document string for a diff report."""
    counts = report.get("citation_counts", {})
    added = report.get("citations_added", [])
    removed = report.get("citations_removed", [])
    stable_count = counts.get("stable", 0)

    same_query = report.get("same_query", True)
    query_earlier = _esc(report.get("query_earlier", ""))
    query_later = _esc(report.get("query_later", ""))
    ts_earlier = _esc(report.get("observed_at_earlier", ""))
    ts_later = _esc(report.get("observed_at_later", ""))
    text_changed = report.get("answer_text_changed", False)

    added_rows = "".join(
        f'<div class="row add"><span class="sign">+</span>'
        f'<span class="url">{_esc(url)}</span></div>'
        for url in added
    )
    removed_rows = "".join(
        f'<div class="row remove"><span class="sign">&minus;</span>'
        f'<span class="url">{_esc(url)}</span></div>'
        for url in removed
    )
    stable_row = (
        f'<div class="row stable"><span class="sign">=</span>'
        f'<span class="url">{_esc(stable_count)} source(s) stable</span></div>'
        if stable_count
        else ""
    )

    query_block = (
        f'<div class="query">{query_later}</div>'
        if same_query
        else (
            '<div class="warn">queries differ between the two attestations</div>'
            f'<div class="query">earlier: {query_earlier}</div>'
            f'<div class="query">later: {query_later}</div>'
        )
    )

    tags = []
    if text_changed:
        tags.append("answer text changed")
    tags.append(f"+{counts.get('added', 0)} appeared &nbsp; &minus;{counts.get('removed', 0)} disappeared")
    tags.append("both signatures valid")
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>witness diff</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #ffffff; color: #1a1a1a;
    margin: 0; padding: 32px;
  }}
  .card {{ max-width: 600px; margin: 0 auto; }}
  .head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
  .label {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px; color: #666; }}
  .query {{ font-size: 15px; font-weight: 500; margin-bottom: 2px; }}
  .meta {{ font-size: 13px; color: #666; margin-bottom: 16px; }}
  .warn {{ font-size: 13px; color: #A32D2D; margin-bottom: 6px; }}
  .snapshots {{ display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }}
  .snap {{ flex: 1; background: #f4f3ee; border-radius: 8px; padding: 12px 14px; }}
  .snap .k {{ font-size: 12px; color: #999; }}
  .snap .v {{ font-size: 14px; font-weight: 500; }}
  .snap .c {{ font-size: 13px; color: #666; margin-top: 4px; }}
  .arrow {{ color: #999; font-size: 18px; }}
  .row {{ display: flex; align-items: center; gap: 8px; padding: 8px 12px;
          background: #f4f3ee; margin-bottom: 4px; }}
  .row.stable {{ background: transparent; }}
  .sign {{ font-family: ui-monospace, monospace; font-weight: 500; width: 12px; }}
  .url {{ font-size: 13px; font-family: ui-monospace, monospace; word-break: break-all; }}
  .row.add {{ border-left: 3px solid #1D9E75; }}
  .row.add .sign {{ color: #0F6E56; }}
  .row.remove {{ border-left: 3px solid #E24B4A; }}
  .row.remove .sign {{ color: #A32D2D; }}
  .row.stable {{ border-left: 3px solid #d0cec4; }}
  .row.stable .sign, .row.stable .url {{ color: #999; }}
  .tags {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
  .tag {{ background: #f4f3ee; padding: 4px 10px; border-radius: 8px;
          font-size: 12px; color: #666; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1a1a1a; color: #e8e6df; }}
    .label, .meta, .snap .c {{ color: #999; }}
    .snap, .row, .tag {{ background: #2a2a28; }}
    .row.stable {{ background: transparent; }}
    .tag {{ color: #b0aea4; }}
  }}
</style>
</head>
<body>
<div class="card">
  <div class="head">
    <span class="label">witness diff</span>
  </div>
  {query_block}
  <div class="meta">both observations verified before comparison</div>
  <div class="snapshots">
    <div class="snap">
      <div class="k">earlier</div>
      <div class="v">{ts_earlier}</div>
      <div class="c">{counts.get('earlier', 0)} sources</div>
    </div>
    <div class="arrow">&rarr;</div>
    <div class="snap">
      <div class="k">later</div>
      <div class="v">{ts_later}</div>
      <div class="c">{counts.get('later', 0)} sources</div>
    </div>
  </div>
  {added_rows}
  {removed_rows}
  {stable_row}
  <div class="tags">{tags_html}</div>
</div>
</body>
</html>
"""
