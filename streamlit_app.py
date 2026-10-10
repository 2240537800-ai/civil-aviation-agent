"""Streamlit demo console."""
from __future__ import annotations

import uuid

import streamlit as st

from app.agents.pipeline import MultiAgentPipeline

st.set_page_config(page_title="民航智能客服 Multi-Agent", page_icon="✈️", layout="wide")
st.title("✈️ 民航智能客服 Multi-Agent")
st.caption("意图路由 → RAG / 工具调用 → 回复润色 | 支持离线规则演示")

if "pipeline" not in st.session_state:
    st.session_state.pipeline = MultiAgentPipeline()
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.logs = []

with st.sidebar:
    st.subheader("会话")
    st.code(st.session_state.session_id)
    if st.button("新建会话"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.logs = []
        st.rerun()
    st.markdown("---")
    st.markdown("**示例问题**")
    examples = [
        "CA1234 今天延误了吗？",
        "起飞前 3 小时退票收多少手续费？",
        "随身可以带多大充电宝？",
        "国内航班最晚什么时候值机？",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state.pending = ex

query = st.chat_input("请输入航空相关问题…")
if "pending" in st.session_state:
    query = st.session_state.pop("pending")

for item in st.session_state.logs:
    with st.chat_message("user"):
        st.write(item["query"])
    with st.chat_message("assistant"):
        st.write(item["answer"])
        with st.expander("Agent 轨迹"):
            st.json(
                {
                    "intent": item["intent"],
                    "sources": item["sources"],
                    "tool_traces": item["tool_traces"],
                }
            )

if query:
    with st.chat_message("user"):
        st.write(query)
    with st.chat_message("assistant"):
        with st.spinner("多智能体协作中…"):
            steps = []
            final = None
            for ev in st.session_state.pipeline.run_stream(st.session_state.session_id, query):
                if ev["event"] == "step":
                    steps.append(ev["data"].get("message", ""))
                elif ev["event"] == "final":
                    final = ev["data"]
            for s in steps:
                st.caption("• " + s)
            if final:
                st.write(final["answer"])
                with st.expander("Agent 轨迹"):
                    st.json(
                        {
                            "intent": final["intent"],
                            "sources": final["sources"],
                            "tool_traces": final["tool_traces"],
                        }
                    )
                st.session_state.logs.append(
                    {
                        "query": query,
                        "answer": final["answer"],
                        "intent": final["intent"],
                        "sources": final["sources"],
                        "tool_traces": final["tool_traces"],
                    }
                )
