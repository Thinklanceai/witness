"""End-to-end test of the witness flow against the local fake xAI server.

Proves, without a real API key or network, that:
  - witness queries the endpoint, captures the response faithfully
  - the resulting attestation verifies
  - the API key never appears in the attestation
  - altering the captured response breaks verification

Run directly: python tests/test_witness_flow.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import attestation as att  # noqa: E402

FAKE_KEY = "fake-test-key-do-not-use"
FAKE_URL = "http://127.0.0.1:8724/v1/responses"


def _run(cmd, env, **kw):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, **kw)


def main() -> int:
    env = dict(os.environ)
    priv, _pub = att.generate_keypair()
    env["XAI_API_KEY"] = FAKE_KEY
    env["ATTEST_PRIVATE_KEY"] = priv
    env["XAI_RESPONSES_URL"] = FAKE_URL

    server_src = (ROOT / "tests" / "fake_xai_server.py").read_text()
    server_src = server_src.replace("8723", "8724")
    tmp_server = ROOT / "tests" / "_fake_server_8724.py"
    tmp_server.write_text(server_src)

    server = subprocess.Popen(
        [sys.executable, str(tmp_server)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1.0)
        out_path = ROOT / "tests" / "_witness_out.json"

        result = _run(
            [
                sys.executable,
                str(ROOT / "witness.py"),
                "--query",
                "what are people saying about a topic",
                "--out",
                str(out_path),
            ],
            env=env,
        )
        assert result.returncode == 0, f"witness failed: {result.stderr}"

        document = json.loads(out_path.read_text())
        report = att.verify_attestation(document)
        assert report["verified"] is True
        print("PASS witness_attestation_verifies")

        text = out_path.read_text()
        assert FAKE_KEY not in text, "API key leaked into attestation"
        print("PASS api_key_not_leaked")

        observed = document["body"]["observed"]
        assert observed["citations"], "no citations captured"
        assert observed["annotations"], "no annotations captured"
        assert "raw_response" in observed, "raw response not captured"
        print("PASS observation_captured_faithfully")

        tampered = json.loads(out_path.read_text())
        tampered["body"]["observed"]["answer_text"] += "."
        try:
            att.verify_attestation(tampered)
        except att.VerificationError:
            print("PASS tampered_witness_rejected")
        else:
            raise AssertionError("tampered witness attestation was accepted")

        print("\nAll witness flow tests passed.")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)
        for f in (tmp_server, ROOT / "tests" / "_witness_out.json"):
            if f.exists():
                f.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
