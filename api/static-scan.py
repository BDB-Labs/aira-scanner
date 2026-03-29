from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "CLI"))

from aira.deterministic_scan import scan_inline_source


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length else "{}"
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "Invalid JSON body."}})
            return

        code = str(body.get("code") or "")
        lang = str(body.get("lang") or "")
        if not code.strip():
            self._send_json(400, {"error": {"message": "No code supplied for deterministic scan."}})
            return
        if not lang.strip():
            self._send_json(400, {"error": {"message": "No language supplied for deterministic scan."}})
            return

        try:
            result = scan_inline_source(code, lang)
        except ValueError as exc:
            self._send_json(400, {"error": {"message": str(exc)}})
            return
        except Exception as exc:
            self._send_json(500, {"error": {"message": f"Deterministic scan failed: {exc}"}})
            return

        self._send_json(200, result)
