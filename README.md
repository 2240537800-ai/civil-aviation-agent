# 民航智能客服 Multi-Agent 系统

面向航班查询、退改签、行李与值机政策的多智能体客服 Demo。

## 架构

```
用户问题
   │
   ▼
Intent Router Agent（意图路由）
   │
   ├─ flight_status ──────► Tool Agent（航班/天气/延误 API）
   │                              │
   └─ policy_* ───────────► Retrieval Agent（BM25 + 向量混合检索 + 轻量 rerank）
                                  │
                                  ▼
                          Reply Polisher Agent（最终对客回复）
```

## 技术栈

Python · FastAPI · SSE · BM25(rank_bm25) · jieba · 简易向量混合检索 · OpenAI Compatible API · Redis（可选）· Streamlit · pytest

## 快速开始

### 1. 安装依赖

```bash
cd projects/aviation-cs-agent
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
copy .env.example .env
```

编辑 `.env`，填入你的 API Key（DeepSeek / 通义 / OpenAI 均可）。

> **不配置 Key 也能跑**：系统会进入离线规则演示模式，便于先看清 Agent 流水线。

### 3. 三种启动方式

**A. 命令行对话**

```bash
python cli.py
```

**B. Streamlit 可视化**

```bash
streamlit run streamlit_app.py
```

**C. FastAPI 服务**

```bash
python -m app.main
# 或: uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口：

- `GET /health`
- `POST /chat`  body: `{"query":"起飞前3小时退票手续费？","session_id":"demo"}`
- `POST /chat/stream`  SSE 流式步骤 + token

### 4. 运行测试

```bash
pytest -q
```

## 示例问题

- `CA1234 今天延误了吗？`
- `起飞前 3 小时退票收多少手续费？`
- `随身可以带多大充电宝？`
- `国内航班最晚什么时候值机？`

## 目录结构

```
aviation-cs-agent/
├── app/
│   ├── agents/pipeline.py   # 四 Agent 编排
│   ├── rag/retriever.py     # 混合检索
│   ├── tools/flight.py      # Function Calling 工具（Mock API）
│   ├── memory.py            # Redis/内存会话
│   ├── llm.py               # LLM 客户端 + 离线兜底
│   └── main.py              # FastAPI
├── data/knowledge/          # 政策知识库 Markdown
├── cli.py
├── streamlit_app.py
└── tests/
```

## 说明

- 航班/天气接口为 **可替换的 Mock**，接入真实航司/飞常准 API 时只需改 `app/tools/flight.py`。
- 知识库在 `data/knowledge/`，增删 `.md` 文件后重启即可生效。
