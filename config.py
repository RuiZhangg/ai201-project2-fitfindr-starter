import os
from dotenv import load_dotenv

load_dotenv()


def ensure_localhost_bypass() -> None:
    """Prevent proxy settings from hijacking local Gradio traffic."""
    localhost_hosts = ["127.0.0.1", "localhost", "::1"]

    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        values = [item.strip() for item in existing.split(",") if item.strip()]

        for host in localhost_hosts:
            if host not in values:
                values.append(host)

        os.environ[key] = ",".join(values)


def ensure_groq_proxy() -> None:
    """Apply the optional Groq proxy to the standard proxy env vars."""
    proxy_url = os.getenv("GROQ_PROXY_URL")
    if not proxy_url:
        return

    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        if not os.environ.get(key):
            os.environ[key] = proxy_url


ensure_localhost_bypass()
ensure_groq_proxy()

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_PROXY_URL = os.getenv("GROQ_PROXY_URL")
LLM_MODEL = "llama-3.3-70b-versatile"

# --- Agent ---
MAX_TOOL_ROUNDS = 5   # Maximum tool-calling loops before stopping
                      # Prevents runaway agent loops

# --- Data ---
DATA_PATH = "./data"
