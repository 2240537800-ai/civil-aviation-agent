"""Demo run of the full multi-agent pipeline (two representative routes)."""
from __future__ import annotations

import json
import time
import uuid

from app.agents.pipeline import MultiAgentPipeline


def show(pipe, sid, query):
    print("=" * 60)
    print("用户问题:", query)
    t0 = time.time()
    result = pipe.run(sid, query)
    dt = time.time() - t0
    print("意图: {} ({})".format(result["intent"]["label"], result["intent"]["intent"]))
    if result["sources"]:
        for s in result["sources"][:3]:
            print("  检索来源: {} (score={:.3f})".format(s["source"], s["score"]))
    if result["tool_traces"]:
        for t in result["tool_traces"]:
            print("  工具调用: {} args={}".format(t["tool"], t["arguments"]))
            print("  工具结果: {}".format(json.dumps(t["result"], ensure_ascii=False)[:200]))
    print("--- 客服回复 ---")
    print(result["answer"][:600])
    print("[耗时 {:.1f}s]".format(dt))


if __name__ == "__main__":
    pipe = MultiAgentPipeline()
    sid = str(uuid.uuid4())
    show(pipe, sid, "CA1234 今天延误了吗？")
    show(pipe, sid, "起飞前 3 小时退票收多少手续费？")
    show(pipe, sid, "随身可以带多大充电宝？")
