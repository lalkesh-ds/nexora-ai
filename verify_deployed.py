"""
Quick smoke-test for deployed Nexora AI endpoints.
Run after Render build completes (3-5 min after push).

Usage:
  python verify_deployed.py
"""
import urllib.request
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://nexora-ai-2-foxj.onrender.com"

def get(path):
    try:
        req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "NexoraDeployTest/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = str(e)
        return e.code, body
    except Exception as e:
        return None, str(e)

print("=== Nexora AI Deployment Smoke Test ===\n")

status, body = get("/health")
print(f"[1] GET /health -> {status} {body}")

status, body = get("/conversations")
# Without auth token, should return 401/403/422, NOT 404
print(f"[2] GET /conversations (no token) -> {status} {body}")

status, body = get("/conversation/recent")
print(f"[3] GET /conversation/recent -> {status} {body}")

