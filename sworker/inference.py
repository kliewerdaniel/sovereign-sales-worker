"""Inference: local-first, provider-visible, never silently cloud.

The client is Hermes Atlas's ``InferenceClient`` (an OpenAI-compatible HTTP
client with no hard dependency on Ollama) when Atlas is importable, and an
identical stdlib fallback otherwise. Either way the contract is the same:

* default target is ``http://localhost:8080/v1``, overridable with
  ``SWORKER_LLM_URL`` / ``--llm-url``;
* ``complete()`` NEVER raises and returns ``None`` on any failure, so a missing
  model degrades a run rather than crashing it;
* any non-localhost base URL is a **boundary crossing** and is reported by
  ``describe()`` so the CLI can print it before a single byte is sent.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFAULT_URL = "http://localhost:8080/v1"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}


# --- the underlying HTTP client -------------------------------------------
try:  # pragma: no cover - exercised by whether atlas is on the path
    from hermes_atlas.inference import InferenceClient, coerce_json  # type: ignore

    ATLAS_INFERENCE = True
except Exception:  # pragma: no cover
    ATLAS_INFERENCE = False

    def coerce_json(raw: str):  # type: ignore[misc]
        """Extract the first complete JSON value from a model response."""
        for opener, closer in (("{", "}"), ("[", "]")):
            first = raw.find(opener)
            if first < 0:
                continue
            depth, in_str, esc = 0, False, False
            for i in range(first, len(raw)):
                ch = raw[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[first : i + 1])
                        except json.JSONDecodeError:
                            break
        return None

    class InferenceClient:  # type: ignore[no-redef]
        def __init__(self, base_url=DEFAULT_URL, model="local", timeout=600, max_tokens=2048):
            self.base_url = base_url.rstrip("/")
            self.model = model
            self.timeout = timeout
            self.max_tokens = max_tokens

        def available(self) -> bool:
            try:
                with urllib.request.urlopen(self.base_url + "/models", timeout=5) as r:
                    return r.status == 200
            except Exception:
                return False

        def resolve_model(self) -> Optional[str]:
            try:
                with urllib.request.urlopen(self.base_url + "/models", timeout=5) as r:
                    data = json.loads(r.read())
                ids = [m["id"] for m in data.get("data", [])]
                if ids and self.model in ("local", "auto"):
                    self.model = ids[0]
                return self.model
            except Exception:
                return None

        def complete(self, prompt, *, system="", max_tokens=None) -> Optional[str]:
            messages = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ]
            body = json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens or self.max_tokens,
                    "temperature": 0.2,
                }
            ).encode()
            req = urllib.request.Request(
                self.base_url + "/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                content = (data["choices"][0]["message"].get("content") or "").strip()
            except Exception:
                return None
            return content or None

        def complete_json(self, prompt, *, system="", max_tokens=None):
            raw = self.complete(prompt, system=system, max_tokens=max_tokens)
            return coerce_json(raw) if raw else None


# --- sovereignty-aware wrapper --------------------------------------------


@dataclass
class ProviderInfo:
    base_url: str
    model: str
    local: bool
    available: bool
    backend: str

    def banner(self) -> str:
        where = "LOCAL" if self.local else "!! EXTERNAL !!"
        state = "up" if self.available else "unreachable"
        return f"inference: {where} {self.base_url} model={self.model} ({state}, {self.backend})"


class Inference:
    """Thin sovereignty layer over the HTTP client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        *,
        timeout: int = 600,
        allow_external: bool = False,
    ):
        self.base_url = (base_url or os.environ.get("SWORKER_LLM_URL") or DEFAULT_URL).rstrip("/")
        self.model = model or os.environ.get("SWORKER_LLM_MODEL") or "local"
        self.allow_external = allow_external or os.environ.get("SWORKER_ALLOW_EXTERNAL") == "1"
        if not self.is_local and not self.allow_external:
            raise PermissionError(
                f"refusing to use non-local inference endpoint {self.base_url!r}: "
                "company data would leave this machine. Pass --allow-external "
                "or set SWORKER_ALLOW_EXTERNAL=1 to acknowledge this explicitly."
            )
        self.client = InferenceClient(base_url=self.base_url, model=self.model, timeout=timeout)
        self.calls = 0

    @property
    def is_local(self) -> bool:
        host = urllib.parse.urlparse(self.base_url).hostname or ""
        return host in LOCAL_HOSTS

    def describe(self) -> ProviderInfo:
        avail = self.client.available()
        if avail:
            self.client.resolve_model()
        return ProviderInfo(
            base_url=self.base_url,
            model=self.client.model,
            local=self.is_local,
            available=avail,
            backend="hermes-atlas" if ATLAS_INFERENCE else "builtin",
        )

    def available(self) -> bool:
        return self.client.available()

    def complete(self, prompt: str, *, system: str = "", max_tokens: Optional[int] = None):
        self.calls += 1
        return self.client.complete(prompt, system=system, max_tokens=max_tokens)

    def complete_json(self, prompt: str, *, system: str = "", max_tokens: Optional[int] = None):
        self.calls += 1
        return self.client.complete_json(prompt, system=system, max_tokens=max_tokens)

    @classmethod
    def from_env(cls, *, allow_external: bool = False) -> "Inference":
        """Build from SWORKER_LLM_URL / SWORKER_LLM_MODEL; raise if unset or remote.

        Default behaviour refuses remote endpoints so company data can never
        silently leave the machine. Callers must opt in with allow_external.
        """
        url = os.environ.get("SWORKER_LLM_URL")
        model = os.environ.get("SWORKER_LLM_MODEL")
        if not url:
            raise RuntimeError("SWORKER_LLM_URL not set (no local model configured)")
        return cls(url, model, allow_external=allow_external)


class NullInference(Inference):
    """Explicit 'no model' mode. Used by tests and by --no-llm runs.

    It does not pretend: every completion returns None, which forces the engine
    down its deterministic fallback path instead of fabricating text.
    """

    def __init__(self):  # noqa: D107
        self.base_url = "null://"
        self.model = "none"
        self.allow_external = False
        self.client = None  # type: ignore[assignment]
        self.calls = 0

    @property
    def is_local(self) -> bool:
        return True

    def describe(self) -> ProviderInfo:
        return ProviderInfo("null://", "none", True, False, "null")

    def available(self) -> bool:
        return False

    def complete(self, prompt: str, *, system: str = "", max_tokens: Optional[int] = None):
        self.calls += 1
        return None

    def complete_json(self, prompt: str, *, system: str = "", max_tokens: Optional[int] = None):
        self.calls += 1
        return None


def default_inference(**kw: Any) -> Inference:
    return Inference(**kw)
