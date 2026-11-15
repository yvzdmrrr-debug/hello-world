"""Model orkestrasyonu: Claude bağlantısı (isteğe bağlı).

`pip install anthropic` yapılmış ve ANTHROPIC_API_KEY tanımlıysa etkinleşir.
Bağlantı yoksa JARVIS çevrimdışı çalışır ve LLM gerektiren işleri ENGELLENDİ diye bildirir.
"""
import json
import os

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM = (
    "Sen JARVIS SUPREME V40.0'sın: kullanıcının hedeflerine hizmet eden tek merkezli bir "
    "dijital zekâ. Doğal ve kısa Türkçe konuş. Yapmadığın işi yapılmış gösterme, "
    "doğrulanmamış bilgiyi kesin gerçek gibi sunma, kazanç garantisi verme. Dosya, para "
    "veya dış sistem üzerinde işlem yapamazsın; yalnızca metin üretirsin."
)

SKILL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "code": {"type": "string"},
        "tests": {"type": "array", "items": {
            "type": "object",
            "properties": {"input": {"type": "string"}, "expected": {"type": "string"}},
            "required": ["input", "expected"], "additionalProperties": False}},
    },
    "required": ["name", "description", "code", "tests"],
    "additionalProperties": False,
}


class LLMUnavailable(Exception):
    pass


class LLM:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("JARVIS_MODEL", DEFAULT_MODEL)
        self._client = None

    @property
    def available(self) -> bool:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _call(self, prompt: str, system: str, **extra):
        if not self.available:
            raise LLMUnavailable("LLM bağlantısı yok (anthropic paketi + ANTHROPIC_API_KEY gerekli)")
        import anthropic
        if self._client is None:
            self._client = anthropic.Anthropic()
        try:
            resp = self._client.beta.messages.create(
                model=self.model, max_tokens=16000, system=system,
                betas=[FALLBACK_BETA], fallbacks="default",
                messages=[{"role": "user", "content": prompt}], **extra)
        except anthropic.AuthenticationError as e:
            raise LLMUnavailable(f"API anahtarı geçersiz: {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMUnavailable(f"Kullanım limiti aşıldı: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMUnavailable(f"API hatası ({e.status_code}): {e}") from e
        except anthropic.APIConnectionError as e:
            raise LLMUnavailable(f"Bağlantı hatası: {e}") from e
        if resp.stop_reason == "refusal":
            raise LLMUnavailable("Model bu isteği yanıtlamayı reddetti")
        return "".join(b.text for b in resp.content if b.type == "text")

    def ask(self, prompt: str, context: str = "") -> str:
        system = SYSTEM + (f"\n\nHafızadan ilgili kayıtlar:\n{context}" if context else "")
        return self._call(prompt, system)

    def draft_skill(self, need: str) -> dict:
        """İhtiyaç tanımından Skill adayı üretir. Aday yine fabrikadaki testlerden geçmelidir."""
        text = self._call(
            "Şu ihtiyaç için bir JARVIS Skill'i yaz: " + need + "\n\n"
            "Kurallar: tek Python dosyası; `run(girdi: str) -> str` fonksiyonu olmalı; "
            "yalnızca şu modüller kullanılabilir: math, re, json, statistics, datetime, "
            "collections, itertools, functools, string, textwrap, decimal, fractions, "
            "unicodedata, ast, operator. Dosya, ağ, open/eval/exec yok. `name` geçerli bir "
            "Python tanımlayıcısı olsun. En az üç test ver; `expected`, run çıktısıyla "
            "birebir aynı metin olmalı.",
            SYSTEM, output_config={"format": {"type": "json_schema", "schema": SKILL_SCHEMA}})
        return json.loads(text)
