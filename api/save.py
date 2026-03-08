"""
POST /api/save
Commits updated config.json directly to your GitHub repo.
Body: { config: {...}, sha: "..." }
"""

import json
import os
import base64
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
from datetime import datetime, timezone


def save_github_config(config: dict, sha: str) -> tuple[bool, str]:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")

    if not token or not repo:
        return False, "Missing GITHUB_TOKEN or GITHUB_REPO environment variables"

    # Strip internal fields before saving
    clean_config = {k: v for k, v in config.items() if not k.startswith("_")}
    content = json.dumps(clean_config, indent=2)
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = f"https://api.github.com/repos/{repo}/contents/config.json"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload = json.dumps({
        "message": f"Dashboard update {timestamp}",
        "content": encoded,
        "sha": sha,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
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
        return False, f"GitHub API error {e.code}: {body[:200]}"
    except Exception as e:
        return False, str(e)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
            config = payload.get("config", {})
            sha = payload.get("sha") or config.get("_sha", "")
        except Exception:
            self._respond(400, {"ok": False, "error": "Invalid JSON body"})
            return

        if not sha:
            self._respond(400, {"ok": False, "error": "Missing SHA — reload the page and try again"})
            return

        ok, error = save_github_config(config, sha)
        if ok:
            self._respond(200, {"ok": True, "message": "Config saved and committed to GitHub"})
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
