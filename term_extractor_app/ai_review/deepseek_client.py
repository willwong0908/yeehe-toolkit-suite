from __future__ import annotations

import json
from typing import Any
from urllib import error, request

BASE_URL = "https://api.deepseek.com"


class DeepSeekError(Exception):
    pass


def list_models(api_key: str) -> list[str]:
    data = _request_json("GET", "/models", api_key)
    models = data.get("data", [])
    model_ids = [item.get("id", "") for item in models if item.get("id")]
    return sorted(model_ids)


def _thinking_config(enabled: bool) -> dict[str, str]:
    return {"type": "enabled" if enabled else "disabled"}


def test_chat(api_key: str, model: str, enable_thinking: bool = False) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise API health checker."},
            {"role": "user", "content": "Return exactly: OK"},
        ],
        "thinking": _thinking_config(enable_thinking),
        "max_tokens": 64 if enable_thinking else 16,
        "temperature": 0,
        "stream": False,
    }
    data = _request_json("POST", "/chat/completions", api_key, payload)
    choices = data.get("choices") or []
    if not choices:
        raise DeepSeekError("API 有响应，但没有返回 choices")
    content = choices[0].get("message", {}).get("content", "")
    return content.strip()


def review_chat(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    enable_thinking: bool = False,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "thinking": _thinking_config(enable_thinking),
        "temperature": 0,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    data = _request_json("POST", "/chat/completions", api_key, payload)
    choices = data.get("choices") or []
    if not choices:
        raise DeepSeekError("API 有响应，但没有返回 choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content.strip():
        raise DeepSeekError("API 返回内容为空")
    return content


def _request_json(method: str, path: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not api_key:
        raise DeepSeekError("请先填写 DeepSeek API Key")

    body = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers=headers,
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeepSeekError(f"DeepSeek API 请求失败：HTTP {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise DeepSeekError(f"DeepSeek API 网络错误：{exc.reason}") from exc
    except TimeoutError as exc:
        raise DeepSeekError("DeepSeek API 请求超时") from exc

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DeepSeekError("DeepSeek API 返回内容不是有效 JSON") from exc
