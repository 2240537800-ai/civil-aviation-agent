"""OpenAI-compatible LLM client with offline mock fallback."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app import config

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


def _client():
    if not config.OPENAI_API_KEY or OpenAI is None:
        return None
    return OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)


def chat(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Return {"content": str, "tool_calls": list|None, "raw": ...}."""
    client = _client()
    if client is None:
        return _mock_reply(messages, tools)

    kwargs: Dict[str, Any] = {
        "model": config.OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    tool_calls = None
    if getattr(msg, "tool_calls", None):
        tool_calls = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in msg.tool_calls
        ]
    return {"content": msg.content or "", "tool_calls": tool_calls, "raw": resp}


def chat_text(system: str, user: str, temperature: float = 0.2) -> str:
    out = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return out["content"]


def _mock_reply(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """No API key: rule-based demo so the pipeline still runs."""
    user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user = m.get("content", "")
            break
    text = user.lower()

    # Intent-style mock when system asks for JSON intent
    sys = messages[0].get("content", "") if messages else ""
    if "意图" in sys or "intent" in sys.lower():
        if any(k in user for k in ("航班", "起飞", "延误", "CA", "MU", "状态")):
            intent = "flight_status"
        elif any(k in user for k in ("退票", "改签", "退改")):
            intent = "policy_refund"
        elif any(k in user for k in ("行李", "托运", "充电宝")):
            intent = "policy_baggage"
        elif any(k in user for k in ("值机", "安检", "登机")):
            intent = "policy_checkin"
        else:
            intent = "chitchat"
        return {
            "content": json.dumps(
                {"intent": intent, "reason": "mock-router"}, ensure_ascii=False
            ),
            "tool_calls": None,
            "raw": None,
        }

    if tools:
        # Prefer flight tool when query looks like status
        if any(k in user for k in ("航班", "状态", "延误", "起飞")):
            import re

            m = re.search(r"([A-Z]{2}\d{3,4}|[A-Z]{1}\d{3,4})", user.upper())
            fn = m.group(1) if m else "CA1234"
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_mock_1",
                        "name": "get_flight_status",
                        "arguments": json.dumps({"flight_no": fn, "date": "today"}),
                    }
                ],
                "raw": None,
            }

    # Default polish / answer
    if "检索结果" in sys or "根据以下" in sys:
        return {
            "content": (
                "根据知识库内容，我已整理如下答复（离线演示模式）：\n"
                + user[-400:]
            ),
            "tool_calls": None,
            "raw": None,
        }

    return {
        "content": (
            "【离线演示】未配置 OPENAI_API_KEY，系统以规则模式回复。"
            "请在 .env 中配置 API Key 以启用完整大模型能力。\n"
            "您的问题：" + user
        ),
        "tool_calls": None,
        "raw": None,
    }
