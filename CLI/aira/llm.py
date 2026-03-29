"""
AIRA LLM routing for optional provider-assisted scans.

The CLI remains useful in pure static mode, but this module lets advanced users
plug AIRA into local or cloud-backed model endpoints using a normalized JSON
contract.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib import error, parse, request


AUTO_PROVIDER_ORDER = (
    "openai-compatible",
    "ollama",
    "groq",
    "gemini",
    "openrouter",
)
MAX_ATTEMPTS_PER_PROVIDER = 2
DEFAULT_TIMEOUT_SECONDS = 45


class LLMRoutingError(RuntimeError):
    """Raised when no provider can successfully complete the request."""


@dataclass
class LLMConfig:
    provider: str = "auto"
    model: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_context_chars: int = 120_000
    system_prompt: str = ""
    user_prompt: str = ""


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _provider_model(provider: str, config: Optional[LLMConfig] = None) -> Optional[str]:
    if config and config.model:
        return config.model

    if provider == "openai-compatible":
        return _env("AIRA_OPENAI_MODEL", "OPENAI_MODEL")
    if provider == "ollama":
        return _env("AIRA_OLLAMA_MODEL", "OLLAMA_MODEL")
    if provider == "groq":
        return _env("AIRA_GROQ_MODEL", "GROQ_MODEL")
    if provider == "gemini":
        return _env("AIRA_GEMINI_MODEL", "GEMINI_MODEL") or "gemini-2.5-flash"
    if provider == "openrouter":
        return _env("AIRA_OPENROUTER_MODEL", "OPENROUTER_MODEL")
    return None


def _provider_base_url(provider: str, config: Optional[LLMConfig] = None) -> Optional[str]:
    if config and config.base_url:
        return config.base_url.rstrip("/")

    if provider == "openai-compatible":
        return _env("AIRA_OPENAI_BASE_URL", "OPENAI_BASE_URL")
    if provider == "ollama":
        return (_env("AIRA_OLLAMA_HOST", "OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    return None


def _provider_api_key(provider: str) -> Optional[str]:
    if provider == "openai-compatible":
        return _env("AIRA_OPENAI_API_KEY", "OPENAI_API_KEY")
    if provider == "groq":
        return _env("AIRA_GROQ_API_KEY", "GROQ_API_KEY")
    if provider == "gemini":
        return _env("AIRA_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
    if provider == "openrouter":
        return _env("AIRA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")
    return None


def _is_configured(provider: str, config: Optional[LLMConfig] = None) -> bool:
    if provider == "openai-compatible":
        return bool(_provider_base_url(provider, config) and _provider_model(provider, config))
    if provider == "ollama":
        return bool(_provider_model(provider, config))
    if provider == "groq":
        return bool(_provider_api_key(provider) and _provider_model(provider, config))
    if provider == "gemini":
        return bool(_provider_api_key(provider))
    if provider == "openrouter":
        return bool(_provider_api_key(provider) and _provider_model(provider, config))
    return False


def provider_health_snapshot(config: Optional[LLMConfig] = None) -> Dict[str, Any]:
    configured = [provider for provider in AUTO_PROVIDER_ORDER if _is_configured(provider, config)]
    return {
        "ok": bool(configured),
        "recommended_provider": "openai-compatible or ollama" if configured and configured[0] in {"openai-compatible", "ollama"} else "openai-compatible",
        "auto_provider_order": list(AUTO_PROVIDER_ORDER),
        "configured_providers": configured,
        "static_fallback": True,
        "providers": {
            provider: {
                "configured": provider in configured,
                "model": _provider_model(provider, config),
                "base_url": _provider_base_url(provider, config),
            }
            for provider in AUTO_PROVIDER_ORDER
        },
    }


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_seconds: int) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw or "{}")
            message = parsed.get("error", {}).get("message") or parsed.get("message") or raw
        except Exception:
            message = raw or str(exc)
        raise LLMRoutingError(f"{exc.code}: {message}") from exc
    except error.URLError as exc:
        raise LLMRoutingError(str(exc.reason)) from exc


def _parse_openai_compatible_content(data: Dict[str, Any]) -> str:
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
    return ""


def _ensure_json_text(text: str) -> str:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    json.loads(cleaned)
    return cleaned


def _build_messages(system: str, prompt: str) -> List[Dict[str, str]]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _call_openai_compatible(config: LLMConfig, provider: str) -> Dict[str, Any]:
    base_url = _provider_base_url(provider, config)
    model = _provider_model(provider, config)
    if not base_url or not model:
        raise LLMRoutingError(f"{provider} is not configured.")

    headers = {"Content-Type": "application/json"}
    api_key = _provider_api_key(provider)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": _build_messages(config.system_prompt, config.user_prompt),
    }
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        headers,
        config.timeout_seconds,
    )
    return {
        "provider": provider,
        "model": model,
        "text": _ensure_json_text(_parse_openai_compatible_content(data)),
    }


def _call_ollama(config: LLMConfig) -> Dict[str, Any]:
    base_url = _provider_base_url("ollama", config)
    model = _provider_model("ollama", config)
    if not base_url or not model:
        raise LLMRoutingError("ollama is not configured.")

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": _build_messages(config.system_prompt, config.user_prompt),
        "options": {"temperature": 0},
    }
    data = _post_json(
        f"{base_url}/api/chat",
        payload,
        {"Content-Type": "application/json"},
        config.timeout_seconds,
    )
    content = ((data.get("message") or {}).get("content") or "").strip()
    return {
        "provider": "ollama",
        "model": model,
        "text": _ensure_json_text(content),
    }


def _call_groq(config: LLMConfig) -> Dict[str, Any]:
    base_url = "https://api.groq.com/openai/v1"
    model = _provider_model("groq", config)
    api_key = _provider_api_key("groq")
    if not api_key or not model:
        raise LLMRoutingError("groq is not configured.")

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": _build_messages(config.system_prompt, config.user_prompt),
    }
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        config.timeout_seconds,
    )
    return {
        "provider": "groq",
        "model": model,
        "text": _ensure_json_text(_parse_openai_compatible_content(data)),
    }


def _call_openrouter(config: LLMConfig) -> Dict[str, Any]:
    model = _provider_model("openrouter", config)
    api_key = _provider_api_key("openrouter")
    if not api_key or not model:
        raise LLMRoutingError("openrouter is not configured.")

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": _build_messages(config.system_prompt, config.user_prompt),
    }
    data = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        config.timeout_seconds,
    )
    return {
        "provider": "openrouter",
        "model": model,
        "text": _ensure_json_text(_parse_openai_compatible_content(data)),
    }


def _call_gemini(config: LLMConfig) -> Dict[str, Any]:
    model = _provider_model("gemini", config)
    api_key = _provider_api_key("gemini")
    if not api_key or not model:
        raise LLMRoutingError("gemini is not configured.")

    payload = {
        "systemInstruction": {"parts": [{"text": config.system_prompt}]} if config.system_prompt else None,
        "contents": [{"role": "user", "parts": [{"text": config.user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{parse.quote(model)}:generateContent?key={parse.quote(api_key)}",
        payload,
        {"Content-Type": "application/json"},
        config.timeout_seconds,
    )
    text = "".join(
        part.get("text", "")
        for candidate in (data.get("candidates") or [])
        for part in ((candidate.get("content") or {}).get("parts") or [])
        if isinstance(part, dict)
    ).strip()
    return {
        "provider": "gemini",
        "model": model,
        "text": _ensure_json_text(text),
    }


def _resolved_provider_order(config: LLMConfig) -> List[str]:
    if config.provider != "auto":
        return [config.provider]
    return [provider for provider in AUTO_PROVIDER_ORDER if _is_configured(provider, config)]


def _runner_for(provider: str):
    if provider == "openai-compatible":
        return lambda cfg: _call_openai_compatible(cfg, "openai-compatible")
    if provider == "ollama":
        return _call_ollama
    if provider == "groq":
        return _call_groq
    if provider == "gemini":
        return _call_gemini
    if provider == "openrouter":
        return _call_openrouter
    raise LLMRoutingError(f"Unsupported provider: {provider}")


def run_llm_json_audit(config: LLMConfig, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    if not user_prompt.strip():
        raise LLMRoutingError("No scan prompt provided.")

    provider_order = _resolved_provider_order(config)
    if not provider_order:
        raise LLMRoutingError(
            "No LLM providers are configured. Set local OpenAI-compatible or Ollama settings, or configure Groq/Gemini/OpenRouter."
        )

    config.system_prompt = system_prompt
    config.user_prompt = user_prompt

    errors: List[str] = []
    for provider in provider_order:
        runner = _runner_for(provider)
        for attempt in range(1, MAX_ATTEMPTS_PER_PROVIDER + 1):
            try:
                return runner(config)
            except Exception as exc:
                errors.append(f"{provider} attempt {attempt}: {exc}")

    raise LLMRoutingError("All configured providers failed. " + " | ".join(errors))
