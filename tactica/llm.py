"""OpenAI-compatible HTTP client. Stdlib only.

Default target is the LiteLLM gateway at 192.168.1.7:4000/v1 (the cockroach
server), which proxies to llama-swap on the DGX. Routing through LiteLLM
gives unified auth, model aliases, and per-call logging in its admin UI.

Surfaces `reasoning_content` separately for reasoning models like
Nemotron-3-Nano-Omni.
"""

import json
import os
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://192.168.1.7:4000/v1"


class LLMError(Exception):
    pass


def _default_api_key():
    """Look up the LiteLLM master key from env or a local protected file."""
    k = os.environ.get("LITELLM_MASTER_KEY") or os.environ.get("TACTICA_API_KEY")
    if k:
        return k
    path = os.path.expanduser("~/.tactica/litellm.env")
    if os.path.exists(path):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("LITELLM_MASTER_KEY="):
                        v = line.split("=", 1)[1].strip()
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        elif v.startswith("'") and v.endswith("'"):
                            v = v[1:-1]
                        return v
        except OSError:
            pass
    return None


class LLMClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = None,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else _default_api_key()

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_models(self):
        req = urllib.request.Request(
            f"{self.base_url}/models",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            raise LLMError(
                f"HTTP {e.code} listing models from {self.base_url}: {body}"
            )
        except urllib.error.URLError as e:
            raise LLMError(f"Failed to list models from {self.base_url}: {e}")
        return [m["id"] for m in data.get("data", [])]

    def chat(
        self,
        messages,
        model,
        temperature: float = 0.6,
        max_tokens: int = 12000,
        extra: dict = None,
    ):
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra:
            body.update(extra)

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise LLMError(
                f"HTTP {e.code} from {self.base_url}: {body_text[:500]}"
            )
        except urllib.error.URLError as e:
            raise LLMError(f"Connection failed to {self.base_url}: {e}")

        elapsed = time.perf_counter() - t0
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"Non-JSON response: {e}: {raw[:500]!r}")

        if "choices" not in data or not data["choices"]:
            raise LLMError(f"Response missing choices: {data}")

        msg = data["choices"][0]["message"]
        return {
            "content": msg.get("content", "") or "",
            "reasoning_content": msg.get("reasoning_content", "") or "",
            "usage": data.get("usage", {}),
            "elapsed_s": elapsed,
            "finish_reason": data["choices"][0].get("finish_reason"),
        }
