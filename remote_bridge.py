"""Lightweight live command and hot-reload bridge for Kaggle Cloud Gaming."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
from pathlib import Path
import subprocess
import sys

PORT = 9000

class RemoteBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"7BZ Remote Bridge Active")

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        cmd = self.rfile.read(length).decode("utf-8")
        try:
            res = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=120,
                env=os.environ.copy()
            )
            output = res.stdout + res.stderr
            code = res.returncode
        except Exception as exc:
            output = f"EXEC_ERROR: {exc}"
            code = 1

        self.send_response(200 if code == 0 else 500)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(output.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("0.0.0.0", PORT), RemoteBridgeHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
