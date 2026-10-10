"""FastAPI server with JSON chat + SSE streaming."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agents.pipeline import MultiAgentPipeline

app = FastAPI(title="民航智能客服 Multi-Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = MultiAgentPipeline()


class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则自动生成")


@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(pipeline.retriever.chunks)}


@app.post("/chat")
def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    result = pipeline.run(sid, req.query)
    return result


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())

    async def gen():
        for item in pipeline.run_stream(sid, req.query):
            yield {"event": item["event"], "data": json.dumps(item["data"], ensure_ascii=False)}

    return EventSourceResponse(gen())


def run():
    import uvicorn
    from app import config

    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)


if __name__ == "__main__":
    run()
