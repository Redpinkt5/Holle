"""Tests for holle_music.ai_provider."""

from __future__ import annotations

import pytest

from holle_music import ai_provider
from holle_music.ai_provider import (
    OpenAICompatibleService,
    PROVIDERS,
    create_ai_service,
    detect_provider,
)


@pytest.fixture
def no_network(monkeypatch):
    """Prevent real network calls in provider detection tests."""
    monkeypatch.setattr(ai_provider, "_test_provider", lambda config, key: False)


def test_providers_table_has_required_fields():
    for name, config in PROVIDERS.items():
        assert "base_url" in config, name
        assert "model" in config, name
        assert "test_endpoint" in config, name


def test_detect_provider_empty_returns_none(no_network):
    assert detect_provider("") is None
    assert detect_provider("   ") is None


def test_detect_provider_invalid_returns_none(no_network):
    assert detect_provider("not-a-real-key") is None


def test_detect_provider_priority_order(monkeypatch):
    """When multiple providers respond, priority order wins."""
    called = []

    def _fake_test(config, key):
        called.append(config["test_endpoint"])
        # Make every provider succeed.
        return True

    monkeypatch.setattr(ai_provider, "_test_provider", _fake_test)
    result = detect_provider("sk-abc")
    # DeepSeek is first in priority.
    assert result == "deepseek"
    assert called[0] == PROVIDERS["deepseek"]["test_endpoint"]


def test_detect_provider_ark_probed_last(monkeypatch):
    """Ark is probed only after all other providers fail."""
    called = []

    def _fake_test(config, key):
        called.append(config.get("test_endpoint"))
        return config.get("test_endpoint") == PROVIDERS["ark"]["test_endpoint"]

    monkeypatch.setattr(ai_provider, "_test_provider", _fake_test)
    result = detect_provider("ark-key")
    assert result == "ark"
    assert called[-1] == PROVIDERS["ark"]["test_endpoint"]


def test_create_ai_service_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_ai_service("sk-abc", "not-a-provider")


def test_create_ai_service_minimax():
    service = create_ai_service("sk-abc", "minimax")
    from holle_music.minimax_api import MiniMaxService

    assert isinstance(service, MiniMaxService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS["minimax"]["base_url"]
    assert service.model == PROVIDERS["minimax"]["model"]


def test_create_ai_service_ark():
    service = create_ai_service("ark-key", "ark")
    from holle_music.pet.ark_api import ArkService

    assert isinstance(service, ArkService)
    assert service.api_key == "ark-key"
    assert service.base_url == PROVIDERS["ark"]["base_url"]
    assert service.model == PROVIDERS["ark"]["model"]


def test_create_ai_service_deepseek():
    service = create_ai_service("sk-abc", "deepseek")
    from holle_music.pet.deepseek_api import DeepSeekService

    assert isinstance(service, DeepSeekService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS["deepseek"]["base_url"]
    assert service.model == PROVIDERS["deepseek"]["model"]


@pytest.mark.parametrize("provider", ["openai", "siliconflow", "kimi", "qwen", "zhipu"])
def test_create_ai_service_openai_compatible(provider):
    service = create_ai_service("sk-abc", provider)
    assert isinstance(service, OpenAICompatibleService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS[provider]["base_url"]
    assert service.model == PROVIDERS[provider]["model"]


def test_openai_compatible_service_uses_custom_config(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # Ensure openai module is loaded before patching.
    import openai
    import sys

    monkeypatch.setattr(sys.modules["openai"], "OpenAI", FakeOpenAI)

    service = OpenAICompatibleService(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="my-model",
    )
    _ = service.client
    assert captured["api_key"] == "sk-test"
    assert captured["base_url"] == "https://example.com/v1"
