"""
Trin 7 + 9: Serverless trigger-funktion med rate limiting (Vercel Python)

Modtager POST { "marked": "optik" } fra landing page,
validerer input, tjekker rate limit og kalder GitHub repository_dispatch.

Miljøvariabler (sættes i Vercel dashboard — aldrig i kode):
  GITHUB_TOKEN      — Personal Access Token med `repo` og `actions:read` scope
  GITHUB_REPO       — f.eks. "margearu/agent"
  ALLOWED_ORIGIN    — f.eks. "https://margearu.github.io" (eller "*" til test)
  MAX_RUNS_PER_HOUR — max antal workflow-kørsler pr. time globalt (default: 5)
  MAX_ACTIVE_RUNS   — max antal samtidige aktive kørsler (default: 1)
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

GITHUB_API = "https://api.github.com"
MAX_MARKED_LEN = 80
MARKED_PATTERN = re.compile(r"^[\w\s\-æøåÆØÅ]{1,80}$", re.UNICODE)
WORKFLOW_FILE = "generate-analysis.yml"


def _cors_headers() -> dict:
    allowed = os.environ.get("ALLOWED_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _gh_get(path: str, token: str) -> tuple[int, dict | list]:
    repo = os.environ.get("GITHUB_REPO", "margearu/agent")
    url = f"{GITHUB_API}/repos/{repo}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 500, {}


def _check_rate_limit(token: str) -> tuple[bool, str]:
    """
    Returnerer (tilladt, fejlbesked).
    Tjekker to ting via GitHub Actions API:
      1. Antal kørsler startet inden for den seneste time (global cap)
      2. Antal aktive kørsler lige nu (concurrency cap)
    """
    max_per_hour = int(os.environ.get("MAX_RUNS_PER_HOUR", "5"))
    max_active = int(os.environ.get("MAX_ACTIVE_RUNS", "1"))

    # Hent de seneste 20 kørsler af vores workflow
    status, data = _gh_get(
        f"/actions/workflows/{WORKFLOW_FILE}/runs?per_page=20",
        token,
    )
    if status != 200:
        # Kan ikke verificere — lad gennemgå (fail open) for ikke at blokere legitime kald
        return True, ""

    runs = data.get("workflow_runs", [])
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Kørsler i det seneste time
    recent = [
        r for r in runs
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > one_hour_ago
    ]

    # Aktive kørsler (queued eller in_progress)
    active = [r for r in runs if r["status"] in ("queued", "in_progress")]

    if len(active) >= max_active:
        return False, f"Der kører allerede en analyse. Prøv igen om et øjeblik."

    if len(recent) >= max_per_hour:
        oldest = min(
            datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in recent
        )
        reset_in = int((oldest + timedelta(hours=1) - now).total_seconds() / 60) + 1
        return False, f"For mange analyser startet. Prøv igen om ca. {reset_in} minutter."

    return True, ""


def _dispatch(marked: str, token: str) -> tuple[int, str]:
    repo = os.environ.get("GITHUB_REPO", "margearu/agent")

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
            if resp.status == 204:
                return 204, ""
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 500, str(e)


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status: int, body: str, extra_headers: dict = None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_OPTIONS(self):
        self._send(204, "")

    def do_POST(self):
        # ── Parse body ──────────────────────────────────────────────────────
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            data = json.loads(raw)
        except Exception:
            self._send(400, json.dumps({"error": "Ugyldigt JSON"}))
            return

        # ── Valider input ───────────────────────────────────────────────────
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

        # ── Token ───────────────────────────────────────────────────────────
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            self._send(500, json.dumps({"error": "Server ikke konfigureret korrekt"}))
            return

        # ── Rate limit-tjek ─────────────────────────────────────────────────
        allowed, reason = _check_rate_limit(token)
        if not allowed:
            self._send(
                429,
                json.dumps({"error": reason}),
                {"Retry-After": "300"},
            )
            return

        # ── Dispatch ────────────────────────────────────────────────────────
        status, body = _dispatch(marked, token)

        if status == 204:
            self._send(200, json.dumps({"ok": True, "marked": marked}))
        else:
            self._send(502, json.dumps({"error": f"GitHub API fejl ({status})", "detail": body}))
