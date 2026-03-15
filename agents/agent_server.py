"""
Minimal HTTP server for agent containers (planner, coding-agent, etc.).
Exposes health on GET / and optional readiness on GET /ready.
Used by Docker images when running in Kubernetes habitats.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class AgentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = {
                "status": "ok",
                "agent": os.environ.get("AGENT_ROLE", "agent"),
                "habitat": os.environ.get("HABITAT_NAME", ""),
            }
            self.wfile.write(json.dumps(body).encode())
        elif self.path == "/ready":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ready":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet in containers; override to enable logging


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
