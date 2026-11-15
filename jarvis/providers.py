"""Evrensel LLM sağlayıcı adaptörleri.

API anahtarları yalnızca ortam değişkenlerinden okunur; veritabanına, günlüklere,
hafızaya veya promptlara yazılmaz. Veritabanında sadece değişkenin ADI tutulur.
"""
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

YEREL, BULUT = "yerel", "bulut"
_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{10,}|Bearer\s+[A-Za-z0-9._\-]{8,})")


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read: int = 0
    cache_write: int = 0
    reasoning: int = 0
    estimated: bool = False  # True: sağlayıcı kullanım verisi vermedi, sayı tahmindir


class ProviderError(Exception):
    pass


class QuotaError(ProviderError):
    pass


def est_tokens(text: str) -> int:
    """Kaba tahmin (4 karakter ≈ 1 token). Kesin tüketim olarak gösterilmez."""
    return max(1, len(text) // 4)


def scrub(text: str, secrets=()) -> str:
    """Metinden API anahtarlarını ve anahtar biçimli dizgileri temizler."""
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, "[GİZLENDİ]")
    return _SECRET.sub("[GİZLENDİ]", text)


def guess_tier(model: str, kind: str) -> int:
    """Model adından başlangıç seviyesi tahmini (1-4). Kullanıcı sonradan değiştirebilir."""
    m = model.lower()
    if kind == YEREL:
        return 1
    if any(k in m for k in ("opus", "fable", "mythos", "ultra", "o1", "o3", "gpt-5")):
        return 4
    if any(k in m for k in ("haiku", "flash", "mini", "nano", "lite", "small")):
        return 2
    return 3


class Provider:
    name, kind, base_url, auth_env = "", BULUT, "", ""

    def key(self) -> str:
        return os.environ.get(self.auth_env, "") if self.auth_env else ""

    def list_models(self) -> list[dict]:
        """[{id, context, max_output}] — ücretli çıkarım çağrısı yapmadan."""
        raise NotImplementedError

    def complete(self, model: str, prompt: str, system: str, timeout: float) -> Completion:
        raise NotImplementedError


def _http(url: str, headers: dict, body: dict | None, timeout: float) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code == 429:
            raise QuotaError(f"kota/hız sınırı (429): {detail}") from e
        raise ProviderError(f"HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError(f"bağlantı hatası: {e}") from e


class OpenAICompatProvider(Provider):
    """OpenAI, OpenRouter, llama.cpp sunucusu, Ollama ve diğer OpenAI uyumlu uçlar."""

    def __init__(self, name: str, base_url: str, auth_env: str = "", kind: str = BULUT):
        self.name, self.base_url, self.auth_env, self.kind = name, base_url.rstrip("/"), auth_env, kind

    def _headers(self):
        return {"Authorization": f"Bearer {self.key()}"} if self.key() else {}

    def list_models(self):
        data = _http(f"{self.base_url}/models", self._headers(), None, 20)
        return [{"id": m["id"], "context": m.get("context_length"), "max_output": None}
                for m in data.get("data", [])]

    def complete(self, model, prompt, system, timeout):
        data = _http(f"{self.base_url}/chat/completions", self._headers(), {
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}]}, timeout)
        text = (data["choices"][0]["message"].get("content") or "")
        u = data.get("usage") or {}
        if "prompt_tokens" in u:
            details = u.get("completion_tokens_details") or {}
            cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
            return Completion(text, u["prompt_tokens"], u.get("completion_tokens", 0),
                              cache_read=cached, reasoning=details.get("reasoning_tokens", 0) or 0)
        return Completion(text, est_tokens(system + prompt), est_tokens(text), estimated=True)


class GeminiProvider(Provider):
    name, auth_env = "gemini", "GEMINI_API_KEY"

    def __init__(self, base_url="https://generativelanguage.googleapis.com/v1beta"):
        self.base_url = base_url.rstrip("/")

    def _headers(self):
        return {"x-goog-api-key": self.key()}

    def list_models(self):
        out, token = [], ""
        while True:
            url = f"{self.base_url}/models?pageSize=100" + (f"&pageToken={token}" if token else "")
            data = _http(url, self._headers(), None, 20)
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    out.append({"id": m["name"].split("/", 1)[-1],
                                "context": m.get("inputTokenLimit"),
                                "max_output": m.get("outputTokenLimit")})
            token = data.get("nextPageToken", "")
            if not token:
                return out

    def complete(self, model, prompt, system, timeout):
        data = _http(f"{self.base_url}/models/{model}:generateContent", self._headers(), {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout)
        cands = data.get("candidates") or []
        parts = (cands[0].get("content") or {}).get("parts", []) if cands else []
        text = "".join(p.get("text", "") for p in parts)
        u = data.get("usageMetadata") or {}
        if "promptTokenCount" in u:
            return Completion(text, u["promptTokenCount"], u.get("candidatesTokenCount", 0),
                              cache_read=u.get("cachedContentTokenCount", 0),
                              reasoning=u.get("thoughtsTokenCount", 0))
        return Completion(text, est_tokens(system + prompt), est_tokens(text), estimated=True)


class AnthropicProvider(Provider):
    name, auth_env = "anthropic", "ANTHROPIC_API_KEY"
    base_url = "https://api.anthropic.com"
    _FALLBACK_OK = ("claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5",
                    "claude-sonnet-5-5")

    def __init__(self):
        import anthropic  # yoksa ImportError: sağlayıcı kaydedilmez
        self._sdk = anthropic
        self._client = anthropic.Anthropic()

    def list_models(self):
        return [{"id": m.id, "context": getattr(m, "max_input_tokens", None),
                 "max_output": getattr(m, "max_tokens", None)}
                for m in self._client.models.list()]

    def complete(self, model, prompt, system, timeout):
        sdk, extra = self._sdk, {}
        if model in self._FALLBACK_OK:  # politika reddinde sunucu tarafı yedek model
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        try:
            resp = self._client.with_options(timeout=timeout).beta.messages.create(
                model=model, max_tokens=16000, system=system,
                messages=[{"role": "user", "content": prompt}], **extra)
        except sdk.RateLimitError as e:
            raise QuotaError(f"kullanım limiti: {e}") from e
        except sdk.APIStatusError as e:
            raise ProviderError(f"API hatası ({e.status_code}): {e}") from e
        except sdk.APIConnectionError as e:
            raise ProviderError(f"bağlantı hatası: {e}") from e
        if resp.stop_reason == "refusal":
            raise ProviderError("model isteği reddetti")
        u = resp.usage
        return Completion("".join(b.text for b in resp.content if b.type == "text"),
                          u.input_tokens, u.output_tokens,
                          cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                          cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0)


def from_env() -> list[Provider]:
    """Ortam değişkenlerine göre kullanılabilir sağlayıcıları kurar."""
    out: list[Provider] = []
    env = os.environ
    if env.get("JARVIS_LOCAL_URL"):  # örn. http://localhost:11434/v1 (Ollama) ya da llama.cpp
        out.append(OpenAICompatProvider("yerel", env["JARVIS_LOCAL_URL"], kind=YEREL))
    if env.get("GEMINI_API_KEY"):
        out.append(GeminiProvider())
    if env.get("ANTHROPIC_API_KEY"):
        try:
            out.append(AnthropicProvider())
        except ImportError:
            pass
    if env.get("OPENAI_API_KEY"):
        out.append(OpenAICompatProvider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"))
    if env.get("OPENROUTER_API_KEY"):
        out.append(OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1",
                                        "OPENROUTER_API_KEY"))
    return out
