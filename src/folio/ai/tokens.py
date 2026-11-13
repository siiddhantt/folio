"""Model-specific admission estimates and conservative billing reservations."""

import json
import re
from decimal import Decimal, InvalidOperation
from importlib.metadata import version

import tiktoken

from . import deepseek


class BudgetError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def tokenizer_name(model_id: str) -> str:
    """Use only upstream mappings, never a guessed fallback for a new model."""
    if model_id == deepseek.MODEL_ID:
        return deepseek.TOKENIZER_NAME
    if not isinstance(model_id, str) or not re.fullmatch(
        r"openai/[A-Za-z0-9][A-Za-z0-9._-]*", model_id
    ):
        raise BudgetError("SUMMARY_TOKENIZER_UNSUPPORTED")
    try:
        return tiktoken.encoding_name_for_model(model_id.removeprefix("openai/"))
    except KeyError:
        raise BudgetError("SUMMARY_TOKENIZER_UNSUPPORTED") from None


def count_tokens(text: str, model_id: str) -> int:
    """Use the same supported tokenizer for history and complete provider inputs."""
    name = tokenizer_name(model_id)
    try:
        if model_id == deepseek.MODEL_ID:
            return deepseek.count_tokens(text)
        return len(tiktoken.get_encoding(name).encode_ordinary(text))
    except Exception:
        raise BudgetError("SUMMARY_TOKENIZER_UNAVAILABLE") from None


def check_budget(messages: list[dict], schema: dict, policy: dict, profile: dict) -> dict:
    """Count complete text/schema; wrapper allowance is estimated, never exact.

    New policies reserve Folio's stage input allowance plus maximum output.
    Frozen legacy policies retain their provider-ceiling calculation.
    """
    if (
        not isinstance(messages, list)
        or not messages
        or not isinstance(schema, dict)
        or any(
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or not isinstance(message["role"], str)
            or message["role"] not in {"system", "user", "assistant"}
            or not isinstance(message["content"], str)
            for message in messages
        )
    ):
        raise BudgetError("SUMMARY_INPUT_INVALID")
    name = tokenizer_name(policy.get("model_id"))
    if profile.get("model_id") != policy["model_id"] or profile.get("tokenizer") != name:
        raise BudgetError("SUMMARY_TOKENIZER_UNSUPPORTED")
    if profile.get("provider") != policy.get("provider") or profile.get(
        "gateway", "openrouter"
    ) != policy.get("gateway", "openrouter"):
        raise BudgetError("SUMMARY_PROFILE_INVALID")
    try:
        reservation_version = policy.get("reservation_version", 1)
        if type(reservation_version) is not int or reservation_version not in (1, 2):
            raise ValueError
        prompt_limit = profile["max_prompt_tokens"]
        if prompt_limit is None and policy["model_id"] == deepseek.MODEL_ID:
            prompt_limit = profile["context_tokens"]
        limits = [
            policy["input_limit_tokens"],
            policy["max_output_tokens"],
            policy["token_margin"],
            profile["context_tokens"],
            prompt_limit,
            profile["max_completion_tokens"],
        ]
        if any(type(value) is not int or value <= 0 for value in limits):
            raise ValueError
        if prompt_limit > profile["context_tokens"]:
            raise ValueError
        input_price = Decimal(profile["input_price_per_million"])
        output_price = Decimal(profile["output_price_per_million"])
        if any(not price.is_finite() or price < 0 for price in (input_price, output_price)):
            raise ValueError
        # JSON serialization accounts for message roles, source labels and schema text.
        # Provider message framing is not public; the separate margin covers that uncertainty.
        serialized = json.dumps({"messages": messages, "schema": schema}, ensure_ascii=False)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise BudgetError("SUMMARY_PROFILE_INVALID") from None
    try:
        token_count = count_tokens(serialized, policy["model_id"])
        tokenizer_version = version(
            "tokenizers" if policy["model_id"] == deepseek.MODEL_ID else "tiktoken"
        )
    except Exception:
        # A missing/corrupt vocabulary cache must fail before paid work starts.
        raise BudgetError("SUMMARY_TOKENIZER_UNAVAILABLE") from None
    estimated = token_count + policy["token_margin"]
    if estimated > policy["input_limit_tokens"]:
        raise BudgetError("SUMMARY_INPUT_LIMIT")
    if (
        estimated > prompt_limit
        or policy["max_output_tokens"] > profile["max_completion_tokens"]
        or estimated + policy["max_output_tokens"] > profile["context_tokens"]
    ):
        raise BudgetError("SUMMARY_CONTEXT_LIMIT")
    reserved_input = prompt_limit
    if reservation_version == 2:
        reserved_input = min(
            policy["input_limit_tokens"],
            prompt_limit,
            profile["context_tokens"] - policy["max_output_tokens"],
        )
    reservation = (
        reserved_input * input_price + policy["max_output_tokens"] * output_price
    ) / Decimal(1_000_000)
    budget = {
        "input_tokens_estimate": estimated,
        "input_tokens_reserved": reserved_input,
        "output_tokens_reserved": policy["max_output_tokens"],
        "reservation_usd": str(reservation),
        "tokenizer": name,
        "tokenizer_version": tokenizer_version,
    }
    if policy["model_id"] == deepseek.MODEL_ID:
        budget.update(tokenizer_revision=deepseek.REVISION, tokenizer_sha256=deepseek.SHA256)
    return budget
