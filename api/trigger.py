"""
Trin 7: Serverless trigger-funktion (Vercel Python)

Modtager POST { "marked": "optik" } fra landing page,
validerer input og kalder GitHub repository_dispatch for at starte pipelinen.

Miljøvariabler (sættes i Vercel dashboard — aldrig i kode):
  GITHUB_TOKEN   — Personal Access Token med `repo` scope
  GITHUB_REPO    — f.eks. "margearu/agent"
  ALLOWED_ORIGIN — f.eks. "https://margearu.github.io" (eller "*" til test)
"""

import json
import os
import re
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

GITHUB_API = "https://api.github.com"
MAX_MARKED_LEN = 80
# Tillader kun bogstaver, tal, mellemrum, bindestreg og æøå
MARKED_PATTERN = re.compile(r"^[\w\s\-æøåÆØÅ]{1,80}$", re.UNICODE)


def _cors_headers(origin: str) -> dict:
    allowed = os.environ.get("ALLOWED_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _dispatch(marked: str) -> tuple[int, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "margearu/agent")

    if not token:
        return 500, "GITHUB_TOKEN ikke konfigureret"

    payload = json.dumps({
        "event_type": "generate-analysis",
        "client_payload": {"marked": marked},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{GITHUB_API}/repos/{repo}/dispatches",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 204 No Content = success
            if resp.status == 204:
                return 204, ""
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body
    except Exception as e:
        return 500, str(e)


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # undertrykker Vercels standard request-log

    def _send(self, status: int, body: str, extra_headers: dict = None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin", "")
        for k, v in _cors_headers(origin).items():
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_OPTIONS(self):
        # CORS preflight
        self._send(204, "")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            data = json.loads(raw)
        except Exception:
            self._send(400, json.dumps({"error": "Ugyldigt JSON"}))
            return

        marked = str(data.get("marked", "")).strip()

        if not marked:
            self._send(400, json.dumps({"error": "Felt 'marked' mangler"}))
            return

        if len(marked) > MAX_MARKED_LEN:
            self._send(400, json.dumps({"error": f"Markedsnavn må max være {MAX_MARKED_LEN} tegn"}))
            return

        if not MARKED_PATTERN.match(marked):
            self._send(400, json.dumps({"error": "Ugyldige tegn i markedsnavn"}))
            return

        status, body = _dispatch(marked)

        if status == 204:
            self._send(200, json.dumps({"ok": True, "marked": marked}))
        else:
            self._send(502, json.dumps({"error": f"GitHub API fejl ({status})", "detail": body}))
