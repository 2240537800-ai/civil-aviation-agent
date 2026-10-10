"""External tool APIs (mocked flight / weather / delay)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_flight_status",
            "description": "查询航班实时状态（起飞/到达/延误/取消）",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_no": {
                        "type": "string",
                        "description": "航班号，如 CA1234",
                    },
                    "date": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD 或 today",
                    },
                },
                "required": ["flight_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_airport_weather",
            "description": "查询机场天气，用于解释延误原因",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {
                        "type": "string",
                        "description": "机场三字码，如 PEK / TSN / SHA",
                    }
                },
                "required": ["airport_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_delay_summary",
            "description": "查询某机场当日大面积延误概况",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string"},
                },
                "required": ["airport_code"],
            },
        },
    },
]


def _stable_int(s: str, mod: int) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16) % mod


def get_flight_status(flight_no: str, date: str = "today") -> Dict[str, Any]:
    flight_no = flight_no.upper().replace(" ", "")
    if date in ("", "today", None):
        date = datetime.now().strftime("%Y-%m-%d")
    seed = _stable_int(flight_no + date, 100)
    statuses = ["正点", "延误", "登机中", "起飞", "到达", "取消"]
    status = statuses[seed % len(statuses)]
    dep = "PEK" if seed % 2 == 0 else "TSN"
    arr = "SHA" if dep == "PEK" else "CAN"
    sched = datetime.now().replace(hour=8 + seed % 10, minute=(seed * 7) % 60, second=0)
    delay_min = 0 if status == "正点" else (15 + seed % 90)
    actual = sched + timedelta(minutes=delay_min)
    return {
        "flight_no": flight_no,
        "date": date,
        "status": status,
        "departure_airport": dep,
        "arrival_airport": arr,
        "scheduled_departure": sched.strftime("%H:%M"),
        "estimated_departure": actual.strftime("%H:%M"),
        "delay_minutes": delay_min,
        "gate": "A{}".format(10 + seed % 20),
        "source": "mock_api",
    }


def get_airport_weather(airport_code: str) -> Dict[str, Any]:
    code = airport_code.upper()
    seed = _stable_int(code + datetime.now().strftime("%Y%m%d"), 5)
    weathers = ["晴", "多云", "小雨", "雷暴", "大风"]
    return {
        "airport_code": code,
        "weather": weathers[seed],
        "temperature_c": 10 + seed * 3,
        "visibility_km": 8 - seed,
        "wind_level": 2 + seed,
        "source": "mock_api",
    }


def get_delay_summary(airport_code: str) -> Dict[str, Any]:
    code = airport_code.upper()
    seed = _stable_int(code, 40)
    return {
        "airport_code": code,
        "delayed_flights": seed,
        "cancelled_flights": seed // 8,
        "avg_delay_minutes": 20 + seed,
        "main_reason": "流量控制" if seed % 2 == 0 else "天气原因",
        "source": "mock_api",
    }


_DISPATCH = {
    "get_flight_status": get_flight_status,
    "get_airport_weather": get_airport_weather,
    "get_delay_summary": get_delay_summary,
}


def dispatch_tool(name: str, arguments: str) -> str:
    fn = _DISPATCH.get(name)
    if not fn:
        return json.dumps({"error": "unknown tool: {}".format(name)}, ensure_ascii=False)
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}
    try:
        result = fn(**args)
        return json.dumps(result, ensure_ascii=False)
    except TypeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
