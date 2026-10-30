import os
import urllib.request

def _resolve_api_url() -> str:
    env_val = os.getenv("API_URL")
    if env_val:
        return env_val.rstrip("/")
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", headers={"User-Agent": "NexoraFrontend"})
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            if resp.status == 200:
                return "http://127.0.0.1:8000"
    except Exception:
        pass
    return "https://nexora-ai-2-foxj.onrender.com"

API_URL = _resolve_api_url()
