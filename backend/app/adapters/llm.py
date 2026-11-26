"""Multi-provider structured JSON completion + pricing catalog."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# USD per 1M tokens — active API models (Nov 2026).
MODELS: dict[str, list[dict[str, Any]]] = {
    "openai": [
        {"id": "gpt-6.1-sol", "label": "GPT-6.1 Sol", "input_per_mtok": 2.00, "output_per_mtok": 10.00},
        {"id": "gpt-6.1-terra", "label": "GPT-6.1 Terra", "input_per_mtok": 1.00, "output_per_mtok": 5.00},
        {"id": "gpt-6-luna", "label": "GPT-6 Luna", "input_per_mtok": 0.10, "output_per_mtok": 0.50},
        {"id": "gpt-6-sol", "label": "GPT-6 Sol", "input_per_mtok": 2.00, "output_per_mtok": 10.00},
        {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra", "input_per_mtok": 2.00, "output_per_mtok": 12.00},
        {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna", "input_per_mtok": 0.20, "output_per_mtok": 1.20},
    ],
    "anthropic": [
        {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "input_per_mtok": 2.00, "output_per_mtok": 10.00},
        {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "input_per_mtok": 4.00, "output_per_mtok": 20.00},
        {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "input_per_mtok": 0.10, "output_per_mtok": 0.50},
        {"id": "claude-fable-5-2", "label": "Claude Fable 5.2", "input_per_mtok": 8.00, "output_per_mtok": 40.00},
    ],
    "google": [
        {"id": "gemini-4-hydrogen", "label": "Gemini 4 Hydrogen", "input_per_mtok": 1.50, "output_per_mtok": 7.50},
        {"id": "gemini-4-carbon", "label": "Gemini 4 Carbon", "input_per_mtok": 2.00, "output_per_mtok": 10.00},
        {"id": "gemini-4-argon", "label": "Gemini 4 Argon", "input_per_mtok": 2.00, "output_per_mtok": 10.00},
        {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "input_per_mtok": 0.75, "output_per_mtok": 3.75},
        {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "input_per_mtok": 0.30, "output_per_mtok": 2.50},
    ],
}


def catalog() -> dict[str, list[dict[str, Any]]]:
    return MODELS


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    for models in MODELS.values():
        for m in models:
            if m["id"] == model:
                return (input_tokens / 1_000_000) * m["input_per_mtok"] + (
                    output_tokens / 1_000_000
                ) * m["output_per_mtok"]
    return 0.0


def provider_for_model(model: str) -> str:
    mid = (model or "").lower()
    if mid.startswith("claude"):
        return "anthropic"
    if mid.startswith("gemini"):
        return "google"
    return "openai"


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


class LlmResult(BaseModel):
    data: dict[str, Any]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


async def complete_json(
    *,
    provider: str,
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    max_tokens: int = 8000,
) -> tuple[T, LlmResult]:
    provider = provider.lower()
    if provider == "openai":
        raw, usage = await _openai_json(model, system, user, schema, max_tokens)
    elif provider == "anthropic":
        raw, usage = await _anthropic_json(model, system, user, schema, max_tokens)
    elif provider == "google":
        raw, usage = await _google_json(model, system, user, schema, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    parsed = schema.model_validate(raw)
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    meta = LlmResult(
        data=raw,
        provider=provider,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_cost(model, in_tok, out_tok),
    )
    return parsed, meta


async def _openai_json(
    model: str, system: str, user: str, schema: Type[BaseModel], max_tokens: int
) -> tuple[dict[str, Any], dict[str, int]]:
    from openai import AsyncOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=300.0)
    try:
        response = await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
            max_completion_tokens=max_tokens,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            content = response.choices[0].message.content or ""
            data = _extract_json(content)
        else:
            data = parsed.model_dump()
        usage = response.usage
        return data, {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI parse failed, falling back to json_object: %s", exc)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system
                    + "\n\nRespond with a single JSON object matching this schema:\n"
                    + json.dumps(schema.model_json_schema()),
                },
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
        )
        data = _extract_json(response.choices[0].message.content or "")
        usage = response.usage
        return data, {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }


async def _anthropic_json(
    model: str, system: str, user: str, schema: Type[BaseModel], max_tokens: int
) -> tuple[dict[str, Any], dict[str, int]]:
    import anthropic

    settings = get_settings()
    key = settings.resolved_anthropic_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    client = anthropic.AsyncAnthropic(api_key=key)
    schema_txt = json.dumps(schema.model_json_schema())
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system + "\n\nReturn ONLY valid JSON matching this schema:\n" + schema_txt,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in message.content if hasattr(block, "text"))
    data = _extract_json(text)
    usage = message.usage
    return data, {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }


async def _google_json(
    model: str, system: str, user: str, schema: Type[BaseModel], max_tokens: int
) -> tuple[dict[str, Any], dict[str, int]]:
    from google import genai
    from google.genai import types

    settings = get_settings()
    key = settings.resolved_google_key
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    client = genai.Client(api_key=key)
    schema_txt = json.dumps(schema.model_json_schema())
    prompt = f"{system}\n\nReturn ONLY valid JSON matching this schema:\n{schema_txt}\n\nUSER:\n{user}"
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    text = response.text or ""
    data = _extract_json(text)
    meta = getattr(response, "usage_metadata", None)
    return data, {
        "input_tokens": getattr(meta, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(meta, "candidates_token_count", 0) or 0,
    }
