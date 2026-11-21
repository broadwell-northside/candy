# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""OpenAI-compatible text providers. One class, three fixed hosts. Text only: an image part is refused."""
import re

from . import guard
from .base import Provider, ProviderError

_MODEL_RE = re.compile(r"[A-Za-z0-9._:/\-]{1,80}")
MAX_CHARS = 60000


class OpenAICompat(Provider):
    kind = "text"
    path = "/v1/chat/completions"

    def chat(self, messages, model=None):
        if not isinstance(messages, list) or not messages or len(messages) > 60:
            raise ProviderError("Send between 1 and 60 messages.")
        clean = []
        for m in messages:
            if (not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant")
                    or not isinstance(m.get("content"), (str, list))):
                raise ProviderError("A message needs a role and content.")
            clean.append({"role": m["role"], "content": m["content"]})
        model = model or self.default_model
        if not isinstance(model, str) or not _MODEL_RE.fullmatch(model):
            raise ProviderError("Pick a model name.")
        texts = guard.message_texts(clean)
        if sum(len(t) for t in texts) > MAX_CHARS:
            raise ProviderError("That is too long to send.")
        guard.check_text(texts)
        data = self._send("POST", self.path, {"model": model, "messages": clean, "stream": False})
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise ProviderError(f"{self.label} answered in a form this app does not read.") from None


class OpenRouter(OpenAICompat):
    name, label, host, default_model = "openrouter", "OpenRouter", "openrouter.ai", "openrouter/auto"
    path = "/api/v1/chat/completions"


class DeepSeek(OpenAICompat):
    name, label, host, default_model = "deepseek", "DeepSeek", "api.deepseek.com", "deepseek-chat"
    path = "/chat/completions"


class DashScopeText(OpenAICompat):
    name, label, host, default_model = "dashscope_text", "Alibaba Model Studio (text)", "dashscope-intl.aliyuncs.com", "qwen-plus"
    key_name = "dashscope"   # one Model Studio key serves text and video
    path = "/compatible-mode/v1/chat/completions"
