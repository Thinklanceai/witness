"""xAI observation engine for Witness.

This module performs one job: send a query to the xAI Responses API with the
real-time search tools enabled, and capture the raw response faithfully. It does
not summarize, filter, score, or interpret anything. The captured payload is
handed verbatim to the attestation core, so the resulting attestation says only:

    "at this time, this exact query, with these exact parameters, returned
     this exact payload from this endpoint."

Security:
- The xAI API key is read only from the environment (XAI_API_KEY). It is never
  placed on the command line and never written into an attestation.
- All network calls have a timeout and explicit error handling.

The HTTP layer uses only the standard library (urllib), so the engine adds no
dependency beyond what the attestation core already needs.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

XAI_RESPONSES_URL = os.environ.get("XAI_RESPONSES_URL", "https://api.x.ai/v1/responses")
DEFAULT_MODEL = "grok-4.3"
DEFAULT_TIMEOUT = 60


def _ssl_context() -> ssl.SSLContext:
    """Build a TLS context with a trusted CA store.

    Prefers the certifi bundle, which is portable and avoids the common macOS
    issue where the system Python has no usable CA store. Falls back to the
    platform default trust store if certifi is unavailable.

    TLS verification is never disabled. An observation tool whose purpose is
    traceability must not weaken transport security.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class ObservationError(Exception):
    """Raised when the observation request fails or returns an unusable shape."""


def build_request_payload(
    *,
    query: str,
    model: str,
    use_x_search: bool,
    use_web_search: bool,
    x_search_params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the exact request body sent to the xAI Responses API.

    This body is also recorded inside the attestation parameters, so the
    observation is fully reproducible as an instruction (even though live
    results will naturally differ when replayed later).
    """
    tools: list[dict[str, Any]] = []
    if use_x_search:
        x_tool: dict[str, Any] = {"type": "x_search"}
        if x_search_params:
            x_tool.update(x_search_params)
        tools.append(x_tool)
    if use_web_search:
        tools.append({"type": "web_search"})

    if not tools:
        raise ObservationError(
            "at least one of x_search or web_search must be enabled"
        )

    return {
        "model": model,
        "input": [{"role": "user", "content": query}],
        "tools": tools,
    }


def _post_json(url: str, body: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ObservationError(f"xAI API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ObservationError(f"network error contacting xAI API: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ObservationError("xAI API returned non-JSON response") from exc


def extract_observation(response_json: dict[str, Any]) -> dict[str, Any]:
    """Pull the faithful observation payload out of the raw API response.

    Captures the answer text, the complete citation list, and the structured
    inline-citation annotations. The full raw response is also kept under
    'raw_response' so nothing the API said is lost or paraphrased.
    """
    answer_text_parts: list[str] = []
    annotations: list[dict[str, Any]] = []

    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                answer_text_parts.append(content.get("text", ""))
                for ann in content.get("annotations", []):
                    annotations.append(
                        {
                            "type": ann.get("type"),
                            "url": ann.get("url"),
                            "title": ann.get("title"),
                            "start_index": ann.get("start_index"),
                            "end_index": ann.get("end_index"),
                        }
                    )

    return {
        "answer_text": "".join(answer_text_parts),
        "citations": response_json.get("citations", []),
        "annotations": annotations,
        "raw_response": response_json,
    }


def observe(
    *,
    query: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    use_x_search: bool = True,
    use_web_search: bool = False,
    x_search_params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    url: str = XAI_RESPONSES_URL,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run an observation against the xAI API.

    Returns (observed, parameters):
      observed    the faithful payload to attest
      parameters  the exact request parameters, for the attestation record

    Raises ObservationError on any failure. The api_key argument is never
    included in either returned dict.
    """
    if not api_key:
        raise ObservationError("xAI API key is empty")

    request_payload = build_request_payload(
        query=query,
        model=model,
        use_x_search=use_x_search,
        use_web_search=use_web_search,
        x_search_params=x_search_params,
    )

    response_json = _post_json(url, request_payload, api_key, timeout)
    observed = extract_observation(response_json)

    parameters = {
        "endpoint": url,
        "model": model,
        "tools": request_payload["tools"],
    }
    return observed, parameters
