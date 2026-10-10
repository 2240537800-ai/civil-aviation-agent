from app.rag.retriever import HybridRetriever
from app.tools.flight import dispatch_tool, get_flight_status


def test_retriever_loads_and_searches():
    r = HybridRetriever()
    assert len(r.chunks) > 0
    hits = r.search("充电宝可以随身携带吗", top_k=3)
    assert len(hits) >= 1
    assert any("行李" in h[0].source or "充电宝" in h[0].text for h in hits)


def test_flight_tool():
    data = get_flight_status("CA1234", "today")
    assert data["flight_no"] == "CA1234"
    assert "status" in data
    raw = dispatch_tool("get_flight_status", '{"flight_no":"MU5100"}')
    assert "MU5100" in raw
