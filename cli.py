"""Command-line chat for quick demo."""
from __future__ import annotations

import uuid

from app.agents.pipeline import MultiAgentPipeline


def main():
    pipe = MultiAgentPipeline()
    sid = str(uuid.uuid4())
    print("=" * 56)
    print("民航智能客服 Multi-Agent（输入 quit 退出）")
    print("会话 ID:", sid)
    print("=" * 56)
    while True:
        try:
            q = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            break
        result = pipe.run(sid, q)
        print("\n意图:", result["intent"]["label"])
        if result["sources"]:
            print("检索来源:", ", ".join(s["source"] for s in result["sources"][:3]))
        if result["tool_traces"]:
            print("工具调用:", len(result["tool_traces"]), "次")
        print("\n客服:", result["answer"])


if __name__ == "__main__":
    main()
