"""
GET /api/config
Reads config.json from your GitHub repo and returns it.
"""

import json
import os
import base64
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


def get_github_config():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")  # e.g. "yourusername/reverb-arbitrage"

    if not token or not repo:
        return None, "Missing GITHUB_TOKEN or GITHUB_REPO environment variables"

    url = f"https://api.github.com/repos/{repo}/contents/config.json"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            config = json.loads(content)
            # Attach the SHA so we can update it later
            config["_sha"] = data["sha"]
            return config, None
    except urllib.error.HTTPError as e:
        return None, f"GitHub API error: {e.code} {e.reason}"
    except Exception as e:
        return None, str(e)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        config, error = get_github_config()

        if error:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": error}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "config": config}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass
