"""
POST /api/trigger
Triggers a manual GitHub Actions workflow run (workflow_dispatch event).
This fires the scanner immediately without waiting for the 5-min cron.
"""

import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


def trigger_workflow() -> tuple[bool, str]:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")

    if not token or not repo:
        return False, "Missing GITHUB_TOKEN or GITHUB_REPO"

    url = f"https://api.github.com/repos/{repo}/actions/workflows/scan.yml/dispatches"
    payload = json.dumps({"ref": "main"}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return True, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"GitHub error {e.code}: {body[:200]}"
    except Exception as e:
        return False, str(e)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        ok, error = trigger_workflow()
        if ok:
            self._respond(200, {"ok": True, "message": "Scan triggered — check GitHub Actions for progress"})
        else:
            self._respond(500, {"ok": False, "error": error})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass
