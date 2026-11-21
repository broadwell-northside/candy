# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""Hosted providers (D-C-56). `get(name)` and `list_providers()` are the interface other lanes code against."""
from . import keychain
from .base import Provider, ProviderError, Refused  # noqa: F401
from .dashscope import DashScopeVideo
from .openai_compat import DashScopeText, DeepSeek, OpenRouter

_ALL = {c.name: c for c in (DashScopeVideo, DashScopeText, OpenRouter, DeepSeek)}
KEY_LABELS = {"dashscope": "Alibaba Model Studio (Wan video and Qwen text)", "openrouter": "OpenRouter", "deepseek": "DeepSeek"}


def get(name):
    cls = _ALL.get(name)
    if cls is None:
        raise KeyError("Unknown provider.")
    return cls()


def list_providers():
    """Plain facts only: never a key."""
    return [{"name": c.name, "label": c.label, "kind": c.kind, "key": c.key_name or c.name,
             "configured": c().configured()} for c in _ALL.values()]


def hosted_media_enabled():
    """The hosted-media switch (Setup, API keys). Off until the owner turns it on."""
    from . import guard
    return guard.hosted_media_on()


def key_names():
    return list(KEY_LABELS)
