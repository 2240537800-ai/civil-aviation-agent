"""Short-term session memory: Redis if available, else in-process."""
from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from app import config

_LOCAL: Dict[str, Dict] = {}


class SessionMemory:
    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        url = redis_url if redis_url is not None else config.REDIS_URL
        if url:
            try:
                import redis

                client = redis.from_url(url, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def _key(self, session_id: str) -> str:
        return "aviation:sess:{}".format(session_id)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        if self._redis:
            raw = self._redis.get(self._key(session_id))
            if not raw:
                return []
            data = json.loads(raw)
            return data.get("messages", [])
        return list(_LOCAL.get(session_id, {}).get("messages", []))

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        # keep last 12 turns
        history = history[-24:]
        payload = {"messages": history, "updated_at": time.time()}
        if self._redis:
            self._redis.setex(self._key(session_id), 3600 * 6, json.dumps(payload, ensure_ascii=False))
        else:
            _LOCAL[session_id] = payload

    def summarize_if_long(self, session_id: str, max_chars: int = 2000) -> str:
        history = self.get_history(session_id)
        text = "\n".join("{}: {}".format(m["role"], m["content"]) for m in history)
        if len(text) <= max_chars:
            return text
        # simple compression: keep head + tail
        head = text[:600]
        tail = text[-1000:]
        return head + "\n…(中间对话已摘要压缩)…\n" + tail
