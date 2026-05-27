"""Local fake of the xAI Responses API, shaped exactly like the documented
response, so the full witness flow can be exercised without a real key or
network. Not shipped in the TAR; this lives only in the build sandbox.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

FAKE_RESPONSE = {
    "output": [
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "People are discussing the topic actively.[[1]](https://x.com/i/status/111)[[2]](https://x.ai/news)",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url": "https://x.com/i/status/111",
                            "title": "1",
                            "start_index": 44,
                            "end_index": 79,
                        },
                        {
                            "type": "url_citation",
                            "url": "https://x.ai/news",
                            "title": "2",
                            "start_index": 79,
                            "end_index": 104,
                        },
                    ],
                }
            ],
        }
    ],
    "citations": [
        "https://x.com/i/status/111",
        "https://x.ai/news",
        "https://x.com/i/user/222",
    ],
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"missing bearer"}')
            return
        payload = json.dumps(FAKE_RESPONSE).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8723), Handler)
    server.serve_forever()
