"""Named OpenAI-compatible inference provider presets.

The presets intentionally contain endpoints and environment-variable names,
not credentials.  Users must supply their own provider key at runtime.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class InferenceProvider:
    name: str
    display_name: str
    base_url: str
    api_key_env: tuple[str, ...]
    example_models: tuple[str, ...]

    def api_key(self) -> str:
        """Return the first configured key without persisting or printing it."""
        for env_name in self.api_key_env:
            value = os.getenv(env_name, "").strip()
            if value:
                return value
        return _opencode_options(self.name).get("apiKey", "").strip()


_PROVIDERS = {
    "minimax": InferenceProvider(
        name="minimax",
        display_name="MiniMax",
        base_url="https://api.minimax.io/v1",
        api_key_env=("MINIMAX_API_KEY",),
        example_models=("MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1"),
    ),
    "qwen": InferenceProvider(
        name="qwen",
        display_name="Qwen",
        base_url="https://llm-cr38z61sr5aor5jj.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        api_key_env=("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
        example_models=("qwen3-max", "qwen-plus", "qwen-turbo"),
    ),
}


def get_provider(name: str) -> InferenceProvider:
    key = name.strip().lower()
    try:
        return _PROVIDERS[key]
    except KeyError as exc:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown inference provider '{name}'. Choose: {available}") from exc


def list_providers() -> Iterable[InferenceProvider]:
    return tuple(_PROVIDERS[name] for name in sorted(_PROVIDERS))


def _opencode_config_path() -> Path:
    configured = os.getenv("OPENCODE_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "opencode" / "opencode.jsonc"


def _opencode_options(name: str) -> dict[str, object]:
    """Read one provider's options from OpenCode without exposing credentials."""
    path = _opencode_config_path()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return {}
    options = data.get("provider", {}).get(name, {}).get("options", {})
    return options if isinstance(options, dict) else {}


def provider_client_kwargs(name: Optional[str]) -> dict[str, str]:
    """Resolve CLI provider selection into safe InferenceClient kwargs."""
    if not name:
        return {}
    provider = get_provider(name)
    options = _opencode_options(name)
    return {
        "inference_url": str(
            os.getenv("QWEN_BASE_URL", "").strip()
            if name.strip().lower() == "qwen" and os.getenv("QWEN_BASE_URL", "").strip()
            else options.get("baseURL") or provider.base_url
        ),
        "api_key": provider.api_key(),
    }
