# Enterprise AI Orchestrator - System Architecture & Flow Documentation

## 1. System Overview

The Enterprise AI Orchestrator is a Django-based web application that combines a LangGraph-powered AI agent with task management capabilities. It uses **Redis** for prompt state management and **WebSockets** for real-time communication between the backend and frontend.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ENTERPRISE AI ORCHESTRATOR                                      │
│                                                                                                    │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐              │
│   │   Frontend   │◄────►│    Django    │◄────►│   LangGraph  │◄────►│   LLM API     │              │
│   │  (Chat UI)   │      │   Web App    │      │    Agent     │      │ Qwen 2.5-7B   │              │
│   │              │      │   + ASGI     │      │              │      │              │              │
│   │  + WebSocket │      └──────┬───────┘      └──────┬───────┘      └──────────────┘              │
│   │  Connection │             │                    │                                         │
│   └──────┬───────┘             │                    │                                         │
│          │                    │                    │                                         │
│          │             ┌──────▼───────┐      ┌──────▼───────┐                                  │
│          │             │    Redis     │      │    Tools     │                                  │
│          │             │ State Mgmt   │◄────►│  (7 tools)   │                                  │
│          │             │              │      │              │                                  │
│          │             └──────────────┘      └──────────────┘                                  │
│          │                    ▲                                                         │
│          │                    │                                                         │
│          └────────────────────┘                                                         │
│                        WebSocket Channels (Django Channels + Redis)                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | Django | 6.0.3 | Web framework, ORM, routing |
| **ASGI Server** | Daphne | 4.1.2 | ASGI server for HTTP + WebSocket |
| **Channels** | Django Channels | 4.2.0 | WebSocket handling |
| **Channel Layer** | Channels Redis | 4.2.1 | Redis-backed channel layer |
| **State Management** | Redis | 7-alpine | Prompt state storage |
| **AI Agent** | LangGraph | 1.1.3 | Agent orchestration with checkpoints |
| **LLM** | Qwen2.5-7B-Instruct | - | HuggingFace hosted model |
| **LLM Integration** | langchain-huggingface | 1.2.1 | ChatHuggingFace wrapper |
| **Web Search** | Tavily Search | - | langchain_tavily tool |
| **Database** | SQLite3 | - | Task storage + agent checkpoints |

---

## 3. Module Architecture

### 3.1 Core Modules

| Module | File(s) | Purpose |
|--------|---------|---------|
| **Web Server** | `core/settings.py`, `core/urls.py`, `core/asgi.py` | Django + Channels + ASGI configuration |
| **Agent Logic** | `agents/logic/graph.py` | LangGraph agent with checkpointing |
| **Tools** | `agents/logic/tools.py` | 7 tool definitions (web search, task CRUD, statistics) |
| **Models** | `agents/models.py` | Django ORM model for InternalTask |
| **Views/API** | `agents/views.py` | REST endpoints + Redis state management |
| **Services** | `agents/services/redis_manager.py` | PromptStateManager for Redis operations |
| **Consumers** | `agents/consumers.py` | WebSocket consumer (AgentConsumer) |
| **Routing** | `agents/routing.py` | WebSocket URL routing |
| **Frontend** | `templates/index.html` | Chat UI with WebSocket + status indicators |

### 3.2 File Structure

```
Enterprise-AI-Orchestrator/
├── agents/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                 ← InternalTask Django model
│   ├── views.py                  ← REST endpoints + Redis state
│   ├── consumers.py              ← WebSocket consumer
│   ├── routing.py                ← WebSocket URL routing
│   ├── logic/
│   │   ├── graph.py              ← LangGraph agent + error handling
│   │   └── tools.py              ← 7 tool definitions
│   ├── services/
│   │   └── redis_manager.py      ← PromptStateManager (Redis)
│   └── migrations/
├── core/
│   ├── __init__.py
│   ├── settings.py               ← Django + Channels + Redis settings
│   ├── urls.py                   ← URL routing
│   ├── wsgi.py
│   └── asgi.py                   ← ASGI app with ProtocolRouter
├── templates/
│   └── index.html                ← Chat UI with WebSocket support
├── Dockerfile                    ← Container build with Daphne
├── docker-compose.yml            ← Redis + Web services
├── requirements.txt            ← Python dependencies
├── flow.md                      ← This documentation
└── .env                        ← API keys + Redis config
```

---

## 4. Redis State Management

### 4.1 What is Redis?

Redis is an in-memory data store used here for:
1. **Prompt State Management** - Tracking the status and data of each prompt
2. **Channel Layer** - Real-time WebSocket message routing via Django Channels

### 4.2 Prompt State Structure

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     REDIS DATA STRUCTURE                                          │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  Key: prompt:{prompt_id}                                                                           │
│  Type: Redis Hash                                                                                  │
│  TTL: 3600 seconds (1 hour)                                                                        │
│                                                                                                    │
│  Fields:                                                                                           │
│  ┌─────────────────┬────────────────────────────────────────────────────────────────────────────┐   │
│  │ Field           │ Value                                                                  │   │
│  ├─────────────────┼────────────────────────────────────────────────────────────────────────────┤   │
│  │ id              │ UUID of the prompt (string)                                              │   │
│  │ user_input      │ Original user message (string)                                           │   │
│  │ thread_id       │ LangGraph thread ID (string)                                            │   │
│  │ status          │ PENDING | PROCESSING | PENDING_APPROVAL | COMPLETED | ERROR (string)    │   │
│  │ created_at      │ ISO timestamp (string)                                                   │   │
│  │ updated_at      │ ISO timestamp (string)                                                   │   │
│  │ response        │ Agent response content (string)                                          │   │
│  │ is_pending      │ 'true' or 'false' (string)                                               │   │
│  │ error           │ Error message if status=ERROR (string)                                   │   │
│  └─────────────────┴────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                    │
│  Key: prompt:{prompt_id}:stream                                                                   │
│  Type: Redis List (for streaming chunks)                                                         │
│  TTL: 3600 seconds                                                                                │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Prompt State Status Values

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PROMPT STATUS VALUES                                          │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  Status             │ Description                                                                │
│  ───────────────────┼───────────────────────────────────────────────────────────────────────────  │
│  PENDING            │ Initial state when prompt is received                                      │
│  PROCESSING         │ Agent is processing the request                                           │
│  PENDING_APPROVAL   │ Agent wants to execute tool, waiting for user approval                     │
│  COMPLETED          │ Agent finished processing, response ready                                 │
│  ERROR              │ An error occurred during processing                                       │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 PromptStateManager API

```python
class PromptStateManager:
    # Create new prompt state in Redis
    create_prompt_state(prompt_id, user_input, thread_id) -> state
    
    # Get prompt state by ID from Redis
    get_prompt_state(prompt_id) -> state_dict
    
    # Update prompt state (any fields) in Redis
    update_prompt_state(prompt_id, **kwargs)
    
    # Set status
    set_status(prompt_id, status)
    
    # Set response (when complete)
    set_response(prompt_id, response, is_pending=False)
    
    # Set error
    set_error(prompt_id, error)
    
    # Streaming helpers
    append_stream(prompt_id, chunk)
    get_stream(prompt_id) -> list
    clear_stream(prompt_id)
    
    # Cleanup
    delete_prompt_state(prompt_id)
    
    # Query by thread
    get_thread_prompts(thread_id) -> list of states
```

---

## 5. WebSocket Architecture

### 5.1 What is WebSocket?

WebSocket provides persistent, bidirectional communication between frontend and backend. Unlike HTTP (request-response), WebSocket stays connected and allows server to push messages to client.

### 5.2 WebSocket Connection Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      WEBSOCKET CONNECTION                                         │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  Client (Browser)                                           Server (Django + Channels)           │
│       │                                                           │                                │
│       │──── WebSocket Connect ─────────────────────────────────►│                                │
│       │        /ws/agent/                                         │                                │
│       │                                                           │                                │
│       │◄─── Connection Accepted ─────────────────────────────────│                                │
│       │        {type: 'connected', prompt_id: 'xxx'}              │                                │
│       │                                                           │                                │
│       │──── Send init message ──────────────────────────────────►│                                │
│       │   {type: 'init', prompt_id: 'uuid'}                      │                                │
│       │                                                           │                                │
│       │◄─── Group joined ────────────────────────────────────────│                                │
│       │   {type: 'connected', prompt_id: 'xxx'}                   │                                │
│       │                                                           │                                │
│       │                    (Connection stays open for real-time updates)                          │
│       │                                                           │                                │
│       │◄─── Server pushes updates ───────────────────────────────│                                │
│       │   {type: 'response', response: '...', is_pending: false} │                                │
│       │   {type: 'stream', chunk: '...'}                         │                                │
│       │   {type: 'state_update', state: {...}}                   │                                │
│       │                                                           │                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 WebSocket Message Types

**Client → Server:**
```json
{"type": "init", "prompt_id": "uuid"}
{"type": "poll", "prompt_id": "uuid"}
{"type": "action", "prompt_id": "uuid", "action": "approve", "user_input": ""}
```

**Server → Client:**
```json
{"type": "connected", "prompt_id": "uuid"}
{"type": "state_update", "state": {...}}
{"type": "stream", "chunk": "..."}
{"type": "response", "response": "...", "is_pending": false}
{"type": "error", "message": "..."}
```

### 5.4 How WebSocket Works with Django Channels

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              DJANGO CHANNELS + REDIS LAYER                                         │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│   Browser                    Daphne                     Django Channels                         │
│   (WebSocket)                  │                            │                                    │
│       │                       │                            │                                    │
│       │══════════════════════►│                            │                                    │
│       │  WS Connection        │                            │                                    │
│       │                       │═══════════════════════════►│                                    │
│       │                       │  HTTP/WS Request          │                                    │
│       │                       │                            │                                    │
│       │                       │                            │═══════════════════════════════════►   │
│       │                       │                            │  Redis Channel Layer                  │
│       │                       │                            │  (pub/sub for group messaging)       │
│       │                       │                            │                                    │
│       │                       │◄════════════════════════════│                                    │
│       │  WS Response          │  Channel response          │                                    │
│       │◄══════════════════════│                            │                                    │
│                                                                                                    │
│   AgentConsumer               Channel Layer              Redis                                  │
│        │                            │                       │                                    │
│        │  group_add(prompt_xxx)     │                       │                                    │
│        │───────────────────────────►│                       │                                    │
│        │                            │ group_add────────────►│                                    │
│        │                            │                       │                                    │
│        │  group_send({type, data}) │                       │                                    │
│        │───────────────────────────►│                       │                                    │
│        │                            │ group_send──────────►│                                    │
│        │                            │                       │                                    │
│        │◄───────────────────────────│                       │                                    │
│        │  Deliver to channel       │                       │                                    │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Complete Request Flow (with Redis + WebSocket)

### 6.1 User Sends Prompt

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FULL REQUEST FLOW                                              │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  1. User types message in chat UI                                                                 │
│                                                                                                    │
│  2. Frontend generates prompt_id (UUID) and sends POST to '/'                                     │
│     Request: {message: "Create a task", prompt_id: "xxx-xxx"}                                     │
│                                                                                                    │
│  3. Django chat_view() receives the request                                                        │
│                                                                                                    │
│  4. PromptStateManager creates state in Redis:                                                     │
│     - Key: prompt:xxx-xxx                                                                        │
│     - Status: PENDING                                                                             │
│     - TTL: 3600 seconds                                                                           │
│                                                                                                    │
│  5. PromptStateManager sets status to PROCESSING                                                  │
│                                                                                                    │
│  6. LangGraph agent processes the request                                                         │
│     - If no tools needed → goes to step 8                                                        │
│     - If tools needed → interrupts at interrupt_before=["tools"]                                  │
│                                                                                                    │
│  7. If interrupted:                                                                               │
│     - Status → PENDING_APPROVAL                                                                   │
│     - Redis updated with is_pending: 'true'                                                       │
│     - WebSocket pushes state to frontend (approval UI shown)                                       │
│                                                                                                    │
│  8. If completed:                                                                                 │
│     - Status → COMPLETED                                                                         │
│     - Response stored in Redis                                                                   │
│     - WebSocket pushes final response to frontend                                                │
│                                                                                                    │
│  9. Frontend receives via WebSocket and updates UI                                                │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Flow Diagram

```
USER                      FRONTEND                 REST API                  REDIS               LANGGRAPH              WEBSOCKET
  │                         │                       │                        │                     │                       │
  │ "Create a task"         │                       │                        │                     │                       │
  │────────────────────────►│                       │                        │                     │                       │
  │                         │ POST / {message,     │                        │                     │                       │
  │                         │      prompt_id}      │                        │                     │                       │
  │                         │──────────────────────│                        │                     │                       │
  │                         │                      │ create_prompt_state()  │                     │                       │
  │                         │                      │────────────────────────►│                     │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ set_status(PENDING)    │                     │                       │
  │                         │                      │────────────────────────►│                     │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ set_status(PROCESSING) │                     │                       │
  │                         │                      │────────────────────────►│                     │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ run_agent_step()       │                     │                       │
  │                         │                      │─────────────────────────────────────────────►│                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │                        │   Agent analyzes    │                       │
  │                         │                      │                        │   ──────────────    │                       │
  │                         │                      │                        │   INTERRUPT!        │                       │
  │                         │                      │                        │   is_pending=true   │                       │
  │                         │                      │◄─────────────────────────────────────────────│                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ set_response(          │                     │                       │
  │                         │                      │   status=PENDING_APPROVAL)                  │                       │
  │                         │                      │────────────────────────►│                     │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ group_send()          │                     │                       │
  │                         │                      │──────────────────────────────────────────────►│                       │
  │                         │◄─────────────────────────────────────────────────────────────────│                       │
  │                         │                      │                        │                     │                       │
  │ Shows approval UI      │                      │                        │                     │                       │
  │◄────────────────────────│                       │                        │                     │                       │
  │                         │                      │                        │                     │                       │
  │ [APPROVE] clicked      │                      │                        │                     │                       │
  │────────────────────────►│                      │                        │                     │                       │
  │                         │ POST / {action:     │                        │                     │                       │
  │                         │      "approve",     │                        │                     │                       │
  │                         │      prompt_id}      │                        │                     │                       │
  │                         │──────────────────────│                        │                     │                       │
  │                         │                      │ invoke(action=approve)│                     │                       │
  │                         │                      │─────────────────────────────────────────────►│                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │                        │   Execute tool      │                       │
  │                         │                      │                        │   ──────────────    │                       │
  │                         │                      │                        │   create_new_task() │                       │
  │                         │                      │                        │   → SQLite          │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ set_response(         │                     │                       │
  │                         │                      │   COMPLETED)           │                     │                       │
  │                         │                      │────────────────────────►│                     │                       │
  │                         │                      │                        │                     │                       │
  │                         │                      │ group_send()          │                     │                       │
  │                         │                      │──────────────────────────────────────────────►│                       │
  │                         │◄─────────────────────────────────────────────────────────────────│                       │
  │                         │                      │                        │                     │                       │
  │ "Task created with      │                      │                        │                     │                       │
  │  ID: 1"                │                      │                        │                     │                       │
  │◄────────────────────────│                       │                        │                     │                       │
```

---

## 7. Human-in-the-Loop Tool Execution

### 7.1 What is Human-in-the-Loop?

When the AI agent wants to execute a tool (like creating a task in the database), it pauses and asks for human approval. This prevents the AI from making unwanted changes.

### 7.2 Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              HUMAN-IN-THE-LOOP FLOW                                               │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  User Request: "Create a task called 'Finish report'"                                            │
│                                                                                                    │
│  ┌─────────────────┐      Agent analyzes request                                                  │
│  │ Agent decides  │──────────► Needs to call create_new_task() tool                              │
│  └─────────────────┘                                                                               │
│                                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  │ LangGraph interrupt_before=["tools"]                                       │                 │
│  │                                                                          │                 │
│  │   1. Execution PAUSES before tool executes                               │                 │
│  │   2. Returns is_pending=true                                              │                 │
│  │   3. Redis updated: status = PENDING_APPROVAL                            │                 │
│  │   4. WebSocket pushes to frontend                                        │                 │
│  │   5. User sees approval buttons (Approve/Reject)                          │                 │
│  └─────────────────────────────────────────────────────────────────────────────┘                 │
│                                                                                                    │
│  ┌─────────────────┐      ┌─────────────────┐                                                    │
│  │ User clicks     │      │ User clicks     │                                                    │
│  │ APPROVE         │      │ REJECT          │                                                    │
│  └────────┬────────┘      └────────┬────────┘                                                    │
│           │                        │                                                             │
│           ▼                        ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐                                 │
│  │ graph.invoke(None, config) - CONTINUES execution           │                                 │
│  │                                                              │                                 │
│  │   • Tool executes (create_new_task writes to SQLite)        │                                 │
│  │   • Result returned to user                                 │                                 │
│  │   • Redis updated: status = COMPLETED                      │                                 │
│  │   • WebSocket pushes final response                        │                                 │
│  └─────────────────────────────────────────────────────────────┘                                 │
│                                                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐                                 │
│  │ graph.invoke({"messages": [("user", "User denied...")]})  │                                 │
│  │                                                              │                                 │
│  │   • Tool does NOT execute                                   │                                 │
│  │   • User receives denial message                            │                                 │
│  │   • Redis updated: status = COMPLETED                      │                                 │
│  │   • WebSocket pushes denial response                        │                                 │
│  └─────────────────────────────────────────────────────────────┘                                 │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Docker Architecture

### 8.1 Services

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      DOCKER SERVICES                                              │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │  Redis Service                                                                              │ │
│  │  ┌───────────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ image: redis:7-alpine                                                                  │ │ │
│  │  │ ports: 6379:6379                                                                        │ │ │
│  │  │ volumes: redis_data:/data                                                              │ │ │
│  │  │ healthcheck: redis-cli ping                                                            │ │ │
│  │  │ purpose: Prompt state storage + Channel layer backend                                   │ │ │
│  │  └───────────────────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                              │ │
│  │  ┌───────────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Web Service (Django + Daphne)                                                          │ │ │
│  │  │ build: .                                                                               │ │ │
│  │  │ ports: 8000:8000                                                                       │ │ │
│  │  │ volumes: .:/app (live reload)                                                         │ │ │
│  │  │ env_file: .env                                                                         │ │ │
│  │  │ environment: REDIS_HOST=redis, REDIS_PORT=6379                                        │ │ │
│  │  │ depends_on: redis                                                                       │ │ │
│  │  │ purpose: Django app + ASGI server (HTTP + WebSocket)                                    │ │ │
│  │  └───────────────────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                              │ │
│  │  volumes: redis_data                                                                        │ │
│  └─────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install daphne==4.1.2          # ASGI server for WebSocket

RUN touch checkpoints.db               # Pre-create LangGraph checkpoint DB

COPY . .

RUN python manage.py migrate --noinput

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
```

### 8.3 Build & Run Commands

```bash
# Start all services (Redis + Django)
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f
docker-compose logs -f web
docker-compose logs -f redis

# Check Redis
docker-compose exec redis redis-cli ping

# Access shell
docker-compose exec web bash

# Stop
docker-compose down
```

---

## 9. API Endpoints

| Endpoint | Method | Purpose | Request Body | Response |
|----------|--------|---------|--------------|----------|
| `/` | GET | Render chat UI | - | HTML page |
| `/` | POST | Send message to agent | `{"message": str, "prompt_id": str, "action": str?}` | `{"prompt_id": str, "response": str, "is_pending": bool}` |
| `/api/tasks/history/` | GET | Get all tasks | - | `{"tasks": [{id, title, status, created_at}]}` |
| `/api/tasks/stats/` | GET | Get task statistics | - | `{"total", "pending", "in_progress", "completed", "cancelled"}` |
| `/api/prompt/<prompt_id>/state/` | GET | Get prompt state from Redis | - | Prompt state hash |
| `/api/prompt/<prompt_id>/stream/` | GET | Get prompt stream chunks | - | `{"stream": [chunks]}` |

---

## 10. Available Tools

| Tool | Input | Description |
|------|-------|-------------|
| `web_search` | query: str | Search web via Tavily |
| `fetch_user_tasks` | query: str = "" | Query InternalTask table |
| `get_task_by_id` | task_id: int | Get single task by ID |
| `create_new_task` | title: str | Create new InternalTask |
| `update_task_status` | task_id: int, new_status: str | Update task status |
| `delete_task` | task_id: int | Delete task by ID |
| `get_task_statistics` | (none) | Get counts by status |

---

## 11. Frontend Features

### 11.1 WebSocket Status Indicator

The sidebar shows real-time connection status:
- **CONNECTED** (green) - WebSocket connected to `/ws/agent/`
- **DISCONNECTED** (red) - WebSocket not connected
- **CONNECTING** (yellow) - Attempting to connect

### 11.2 Redis Status Indicator

Shows if Redis is accessible:
- **REDIS OK** (green) - Redis responding
- **REDIS OFF** (red) - Redis not accessible

### 11.3 Prompt Counter

Shows total prompts sent in current session.

---

## 12. Error Handling

### 12.1 Redis None Value Error

Fixed by converting all values to strings before storing in Redis:
- `None` → `""`
- `bool` → `'true'`/`'false'`
- Other types → `str()`

### 12.2 Tool Calls Error

If LangGraph detects corrupted checkpoint state:
1. Catches the exception
2. Removes corrupted `checkpoints.db`
3. Creates fresh checkpoint connection
4. Returns user-friendly error message

---

## 13. Testing Prompts

**Task Management:**
```
Create a task called "Test the AI orchestrator"
Show me all my tasks
What tasks do I have?
Update task 1 to completed
Delete task 1
```

**Statistics:**
```
Show me task statistics
How many tasks are pending?
```

**Web Search:**
```
Search for latest AI news
What is LangGraph?
```

**Combined:**
```
Create a task called "Deploy app", then show me all tasks
```

---

## 14. Quick Reference

### Docker Commands
```bash
# Start all services
docker-compose up --build

# Check Redis is running
docker-compose exec redis redis-cli ping

# View WebSocket logs
docker-compose logs -f web | grep -i websocket

# Rebuild after code changes
docker-compose up -d --build web
```

### Architecture Summary
```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                  │
│   User ──► Frontend ──► Django REST API ──► LangGraph Agent ──► Response                       │
│              │                           │                    │                                 │
│              │                           ▼                    ▼                                 │
│              │                    ┌─────────────┐      ┌─────────────┐                          │
│              │                    │    Redis    │◄────│   Tools     │                          │
│              │                    │  (State)    │     │ (7 tools)   │                          │
│              │                    └─────────────┘      └─────────────┘                          │
│              │                                                                                   │
│              └──────────► WebSocket ◄────────── Django Channels ◄──────── Redis               │
│                                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Components:**
- **Django**: Web framework + REST API
- **Daphne**: ASGI server for HTTP + WebSocket
- **Channels**: WebSocket handling
- **Channels Redis**: Redis-backed channel layer for message routing
- **Redis**: Prompt state storage + pub/sub for WebSocket groups
- **LangGraph**: AI agent with human-in-the-loop interrupts