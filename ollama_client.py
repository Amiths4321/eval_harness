import requests
import os
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "agent_config",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.py")
)
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)

OLLAMA_BASE_URL  = _cfg.OLLAMA_BASE_URL
GENERATION_MODEL = _cfg.GENERATION_MODEL
REQUEST_TIMEOUT  = _cfg.REQUEST_TIMEOUT


def chat(messages: list, temperature: float = 0.0) -> str:
    """temperature=0.0 by default for evals - we want deterministic outputs,
    not creative ones. Randomness is the enemy of reproducible benchmarks."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": GENERATION_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def check_connection() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return False
