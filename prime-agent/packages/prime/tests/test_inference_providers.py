from prime_cli.api.providers import get_provider, list_providers, provider_client_kwargs
from prime_cli.commands.inference import _inference_client


def test_lists_minimax_and_qwen_openai_compatible_presets():
    names = {provider.name for provider in list_providers()}

    assert {"minimax", "qwen"}.issubset(names)


def test_minimax_preset_uses_official_endpoint_and_key_env():
    provider = get_provider("minimax")

    assert provider.base_url == "https://api.minimax.io/v1"
    assert provider.api_key_env == ("MINIMAX_API_KEY",)
    assert "MiniMax-M2.7" in provider.example_models


def test_qwen_preset_accepts_dashscope_or_qwen_key_env():
    provider = get_provider("qwen")

    assert provider.base_url.endswith("/compatible-mode/v1")
    assert provider.api_key_env == ("DASHSCOPE_API_KEY", "QWEN_API_KEY")
    assert "qwen-plus" in provider.example_models


def test_provider_client_uses_provider_endpoint_and_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setenv("OPENCODE_CONFIG", str(tmp_path / "missing-opencode.jsonc"))

    client = _inference_client("minimax")

    assert client.inference_url == "https://api.minimax.io/v1"
    assert client.api_key == "minimax-test-key"


def test_provider_client_falls_back_to_opencode_jsonc(monkeypatch, tmp_path):
    config = tmp_path / "opencode.jsonc"
    config.write_text(
        '{"provider":{"minimax":{"options":{"baseURL":"https://example.test/v1",'
        '"apiKey":"from-opencode"}}}}',
        encoding="utf-8",
    )
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("OPENCODE_CONFIG", str(config))

    kwargs = provider_client_kwargs("minimax")

    assert kwargs == {
        "inference_url": "https://example.test/v1",
        "api_key": "from-opencode",
    }
