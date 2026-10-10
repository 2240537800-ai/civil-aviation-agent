"""
Multi-agent pipeline:
  IntentRouter -> (RAG Agent | Tool Agent) -> ReplyPolisher
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Generator, List, Optional

from app.llm import chat, chat_text
from app.memory import SessionMemory
from app.rag.retriever import HybridRetriever
from app.tools.flight import TOOL_SCHEMAS, dispatch_tool


INTENT_LABELS = {
    "flight_status": "航班状态查询",
    "policy_refund": "退改签政策",
    "policy_baggage": "行李规定",
    "policy_checkin": "值机安检",
    "chitchat": "闲聊/其他",
}


class MultiAgentPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.memory = SessionMemory()

    # ---------- Agent 1: Intent Router ----------
    def intent_router(self, user_query: str, history_text: str) -> Dict[str, str]:
        system = (
            "你是民航客服意图路由 Agent。请判断用户意图，只输出 JSON："
            '{"intent":"flight_status|policy_refund|policy_baggage|policy_checkin|chitchat","reason":"..."}'
        )
        user = "历史对话摘要:\n{}\n\n当前问题:\n{}".format(history_text or "无", user_query)
        raw = chat_text(system, user)
        intent = "chitchat"
        reason = raw
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                data = json.loads(m.group(0))
                intent = data.get("intent", intent)
                reason = data.get("reason", reason)
        except Exception:
            # heuristic fallback
            if any(k in user_query for k in ("航班", "延误", "起飞", "到达")):
                intent = "flight_status"
            elif any(k in user_query for k in ("退", "改签")):
                intent = "policy_refund"
            elif any(k in user_query for k in ("行李", "托运", "充电宝")):
                intent = "policy_baggage"
            elif any(k in user_query for k in ("值机", "安检")):
                intent = "policy_checkin"
        return {"intent": intent, "reason": reason, "label": INTENT_LABELS.get(intent, intent)}

    # ---------- Agent 2: Retrieval Agent ----------
    def retrieval_agent(self, user_query: str, intent: str) -> Dict[str, Any]:
        hits = self.retriever.search(user_query, top_k=4)
        context = self.retriever.format_context(hits)
        return {
            "context": context,
            "sources": [
                {"source": c.source, "score": score, "preview": c.text[:80]}
                for c, score in hits
            ],
        }

    # ---------- Agent 3: Tool Agent ----------
    def tool_agent(self, user_query: str, history_text: str) -> Dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是航班工具调用 Agent。根据用户问题决定是否调用工具查询航班/天气/延误。"
                    "需要实时信息时必须调用工具；调用后根据工具结果作答。"
                ),
            },
            {
                "role": "user",
                "content": "对话摘要:\n{}\n\n问题:{}".format(history_text or "无", user_query),
            },
        ]
        traces = []
        answer_parts = []
        for _ in range(3):  # max tool rounds
            out = chat(messages, tools=TOOL_SCHEMAS)
            if out.get("tool_calls"):
                messages.append(
                    {
                        "role": "assistant",
                        "content": out.get("content") or "",
                        # openai python may need tool_calls in specific format; we append tool results only for mock simplicity
                    }
                )
                for tc in out["tool_calls"]:
                    result = dispatch_tool(tc["name"], tc["arguments"])
                    traces.append(
                        {"tool": tc["name"], "arguments": tc["arguments"], "result": result}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": "工具 {} 返回:\n{}".format(tc["name"], result),
                        }
                    )
                continue
            if out.get("content"):
                answer_parts.append(out["content"])
            break

        if not answer_parts and traces:
            # synthesize from last tool result
            answer_parts.append("已查询到以下信息：\n" + traces[-1]["result"])

        return {"answer_draft": "\n".join(answer_parts), "tool_traces": traces}

    # ---------- Agent 4: Reply Polisher ----------
    def reply_polisher(
        self,
        user_query: str,
        intent: str,
        draft: str,
        context: str = "",
        tool_traces: Optional[List] = None,
    ) -> str:
        system = (
            "你是民航客服回复润色 Agent。要求："
            "1) 语气专业友好；2) 有依据时标明来源文件名；"
            "3) 不确定处明确说明；4) 不要编造未给出的航班数据；5) 中文回答。"
        )
        user = (
            "用户问题: {}\n意图: {}\n\n知识库片段:\n{}\n\n工具结果草稿:\n{}\n\n"
            "请给出最终对客回复。"
        ).format(user_query, intent, context or "无", draft or "无")
        return chat_text(system, user)

    # ---------- Orchestration ----------
    def run(self, session_id: str, user_query: str) -> Dict[str, Any]:
        history_text = self.memory.summarize_if_long(session_id)
        route = self.intent_router(user_query, history_text)

        context = ""
        sources: List[Dict] = []
        tool_traces: List[Dict] = []
        draft = ""

        if route["intent"] == "flight_status":
            tool_out = self.tool_agent(user_query, history_text)
            draft = tool_out["answer_draft"]
            tool_traces = tool_out["tool_traces"]
            # also pull delay-related policy if delayed
            rag = self.retrieval_agent(user_query + " 延误 退改", route["intent"])
            context = rag["context"]
            sources = rag["sources"]
        elif route["intent"] in (
            "policy_refund",
            "policy_baggage",
            "policy_checkin",
        ):
            rag = self.retrieval_agent(user_query, route["intent"])
            context = rag["context"]
            sources = rag["sources"]
            draft = (
                "请严格依据下列检索结果回答用户政策问题。\n检索结果:\n" + context
            )
            # let polisher + LLM produce final; for no-key, polisher will echo
            draft = chat_text(
                "你是政策问答 Agent，只根据检索结果回答，列出要点，并标注来源文件。",
                "问题: {}\n\n{}".format(user_query, context),
            )
        else:
            draft = chat_text(
                "你是民航智能客服，简短友好地回答；若与航空无关可礼貌引导。",
                user_query,
            )

        final = self.reply_polisher(
            user_query, route["intent"], draft, context=context, tool_traces=tool_traces
        )

        self.memory.append(session_id, "user", user_query)
        self.memory.append(session_id, "assistant", final)

        return {
            "answer": final,
            "intent": route,
            "sources": sources,
            "tool_traces": tool_traces,
            "session_id": session_id,
        }

    def run_stream(self, session_id: str, user_query: str) -> Generator[Dict[str, Any], None, None]:
        """Yield step events then final answer (for SSE)."""
        yield {"event": "step", "data": {"stage": "intent_router", "message": "正在识别意图…"}}
        history_text = self.memory.summarize_if_long(session_id)
        route = self.intent_router(user_query, history_text)
        yield {
            "event": "step",
            "data": {
                "stage": "intent_router",
                "message": "意图: {} ({})".format(route["label"], route["intent"]),
                "intent": route,
            },
        }

        context = ""
        sources: List[Dict] = []
        tool_traces: List[Dict] = []
        draft = ""

        if route["intent"] == "flight_status":
            yield {"event": "step", "data": {"stage": "tool_agent", "message": "正在调用航班工具…"}}
            tool_out = self.tool_agent(user_query, history_text)
            draft = tool_out["answer_draft"]
            tool_traces = tool_out["tool_traces"]
            yield {
                "event": "step",
                "data": {
                    "stage": "tool_agent",
                    "message": "工具调用完成 ({} 次)".format(len(tool_traces)),
                    "tool_traces": tool_traces,
                },
            }
            rag = self.retrieval_agent(user_query + " 延误 退改", route["intent"])
            context, sources = rag["context"], rag["sources"]
        elif route["intent"] in ("policy_refund", "policy_baggage", "policy_checkin"):
            yield {"event": "step", "data": {"stage": "retrieval_agent", "message": "正在检索知识库…"}}
            rag = self.retrieval_agent(user_query, route["intent"])
            context, sources = rag["context"], rag["sources"]
            yield {
                "event": "step",
                "data": {
                    "stage": "retrieval_agent",
                    "message": "命中 {} 条片段".format(len(sources)),
                    "sources": sources,
                },
            }
            draft = chat_text(
                "你是政策问答 Agent，只根据检索结果回答，列出要点，并标注来源文件。",
                "问题: {}\n\n{}".format(user_query, context),
            )
        else:
            draft = chat_text(
                "你是民航智能客服，简短友好地回答；若与航空无关可礼貌引导。",
                user_query,
            )

        yield {"event": "step", "data": {"stage": "reply_polisher", "message": "正在生成最终回复…"}}
        final = self.reply_polisher(user_query, route["intent"], draft, context=context)
        self.memory.append(session_id, "user", user_query)
        self.memory.append(session_id, "assistant", final)

        # fake token stream for UI
        chunk_size = 18
        for i in range(0, len(final), chunk_size):
            yield {"event": "token", "data": {"text": final[i : i + chunk_size]}}

        yield {
            "event": "final",
            "data": {
                "answer": final,
                "intent": route,
                "sources": sources,
                "tool_traces": tool_traces,
                "session_id": session_id,
            },
        }
