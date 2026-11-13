from types import SimpleNamespace

import httpx
import pytest
from test_ai import MESSAGES, POLICY, PROFILE, SCHEMA, catalog, metadata

from folio.ai import BudgetError, check_budget
from folio.ai.routing import generation_client
from folio.conversations.config import ChatSettings, rewrite_policy


def test_chat_policy_keeps_each_generation_service_independent(monkeypatch):
    monkeypatch.setenv("FOLIO_MEMORY_GATEWAY", "openrouter")
    runtime = SimpleNamespace(job_timeout_seconds=600, lease_seconds=720, retry_delays_seconds=[15])
    saved = ChatSettings(_env_file=None, gateway="openai", rewrite_gateway="openrouter").policy(
        runtime
    )
    assert saved["base_url"] == "https://api.openai.com/v1"
    assert saved["provider_profile_version"] == "openai-gpt-5.2-2026-11-13"
    rewrite = rewrite_policy(saved)
    assert rewrite["gateway"] == "openrouter"
    assert rewrite["base_url"] == "https://openrouter.ai/api/v1"
    assert "provider_profile_version" not in rewrite
    assert saved["memory"]["gateway"] == "openrouter"
    assert saved["memory"]["base_url"] == "https://openrouter.ai/api/v1"

    monkeypatch.setenv("FOLIO_CHAT_GATEWAY", "openrouter")
    assert saved["gateway"] == "openai"


def test_token_check_rejects_a_profile_from_another_service():
    with pytest.raises(BudgetError, match="SUMMARY_PROFILE_INVALID"):
        check_budget(MESSAGES, SCHEMA, POLICY | {"gateway": "openai"}, PROFILE)
    assert check_budget(MESSAGES, SCHEMA, POLICY, PROFILE)["reservation_usd"]


def test_rewrite_uses_the_profile_and_endpoint_captured_at_acceptance():
    runtime = SimpleNamespace(job_timeout_seconds=600, lease_seconds=720, retry_delays_seconds=[15])
    saved = ChatSettings(_env_file=None, rewrite_gateway="openai").policy(runtime)
    assert saved["rewrite_provider_profile_version"] == "openai-gpt-5.2-2026-11-13"
    assert saved["rewrite_base_url"] == "https://api.openai.com/v1"
    saved["rewrite_provider_profile_version"] = "previous-reviewed-version"
    assert rewrite_policy(saved)["provider_profile_version"] == "previous-reviewed-version"


def test_legacy_policy_still_calls_openrouter_without_a_direct_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-fixture")
    monkeypatch.setenv("FOLIO_CHAT_GATEWAY", "openai")

    def respond(request):
        assert request.url.host == "openrouter.ai"
        if request.method == "GET":
            return httpx.Response(
                200, json=catalog() if request.url.path.endswith("/models") else metadata()
            )
        assert request.headers["Authorization"] == "Bearer router-fixture"
        return httpx.Response(
            200,
            json={
                "model": POLICY["model_id"],
                "provider": "OpenAI",
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 3, "cost": 0.0000022},
            },
        )

    model = generation_client(POLICY, transport=httpx.MockTransport(respond))
    assert "gateway" not in model.profile()
    assert model.generate(MESSAGES, SCHEMA).finish_reason == "stop"
