# Enterprise AI Orchestrator - System Architecture & Flow Documentation

## 1. System Overview

The Enterprise AI Orchestrator is a Django-based web application that combines a LangGraph-powered AI agent with task management capabilities. It uses Redis for state management and WebSockets for real-time communication.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE AI ORCHESTRATOR                               │
│                                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Frontend  │◄──►│   Django    │◄──►│  LangGraph  │◄──►│   LLM API   │       │
│  │  (Chat UI)  │    │   Web App   │    │   Agent     │    │ Qwen 2.5-7B │       │
│  │  + WebSocket│    └──────┬──────┘    └──────┬──────┘    └─────────────┘       │
│  └─────────────┘           │                   │                                   │
│         │                  │                   │                                   │
│         │          ┌──────▼──────┐    ┌──────▼──────┐                           │
│         │          │   Redis     │    │   Tools     │                           │
│         │          │  State Mgmt  │    │  (7 tools)  │                           │
│         │          └─────────────┘    └─────────────┘                           │
│         │                  │                                                     │
│         └──────────────────┘                                                     │
│                    WebSocket Channels                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Architecture

### 2.1 Core Modules

| Module | File(s) | Purpose |
|--------|---------|---------|
| **Web Server** | `core/settings.py`, `core/urls.py`, `core/asgi.py` | Django + Channels configuration, routing, ASGI application |
| **Agent Logic** | `agents/logic/graph.py` | LangGraph agent initialization and execution with checkpointing |
| **Tools** | `agents/logic/tools.py` | Tool definitions (7 tools: web search, task CRUD, statistics) |
| **Models** | `agents/models.py` | Django ORM model for InternalTask |
| **Views/API** | `agents/views.py` | REST endpoints for chat and task management |
| **Services** | `agents/services/redis_manager.py` | Redis state management for prompts |
| **Consumers** | `agents/consumers.py` | WebSocket consumer for real-time communication |
| **Routing** | `agents/routing.py` | WebSocket URL routing |
| **Frontend** | `templates/index.html` | Tailwind CSS chat UI with WebSocket support |
| **Container** | `Dockerfile`, `docker-compose.yml` | Docker deployment with Redis |

### 2.2 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | Django | 6.0.3 | Web framework, ORM, routing |
| **ASGI Server** | Daphne | 4.1.2 | ASGI server for WebSocket support |
| **Channels** | Django Channels | 4.2.0 | WebSocket handling |
| **Channel Layer** | Channels Redis | 4.2.1 | Redis-backed channel layer |
| **AI Agent** | LangGraph | 1.1.3 | Agent orchestration with checkpoints |
| **State Management** | Redis | 7-alpine | Prompt state storage |
| **LLM** | Qwen2.5-7B-Instruct | - | HuggingFace hosted model |
| **LLM Integration** | langchain-huggingface | 1.2.1 | ChatHuggingFace wrapper |
| **Checkpoints** | langgraph-checkpoint-sqlite | 3.0.3 | SQLite-based state persistence |
| **Web Search** | Tavily Search | - | langchain_tavily tool |
| **Database** | SQLite3 | - | Task storage + agent checkpoints |

---

## 3. Flow Charts

### 3.1 User Request Flow with Redis State Management

```
┌──────────────┐
│ User Input   │
│ "Create a    │
│  task"       │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 1. Frontend (index.html)                                                         │
│    - User types message in chat input                                             │
│    - Generates prompt_id (UUID)                                                  │
│    - Sends POST to '/' with {message, prompt_id}                                 │
│    - Connects to WebSocket /ws/agent/                                            │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 2. Django Views (views.py) - chat_view()                                          │
│    - Receive POST request with JSON body                                          │
│    - Extract 'message', 'prompt_id', 'action' parameters                        │
│    - Create/update prompt state in Redis via PromptStateManager                 │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 3. Redis State (PromptStateManager)                                               │
│    - create_prompt_state(prompt_id, user_input, thread_id)                       │
│    - Sets status: PENDING → PROCESSING                                           │
│    - Stores in Redis hash: prompt:{prompt_id}                                    │
│    - TTL: 3600 seconds                                                           │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 4. LangGraph Agent (graph.py) - run_agent_step()                                  │
│    - Create config with thread_id                                                │
│    - Invoke graph with user input                                                 │
│    - Check if response is pending (tool approval needed)                         │
│    - Return response + is_pending flag                                           │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ Agent responds    │  │ Agent needs      │
         │ (no tools)       │  │ tool execution   │
         │                  │  │ (interrupt)      │
         └────────┬─────────┘  └────────┬─────────┘
                  │                      │
                  ▼                      ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ Update Redis     │  │ Update Redis     │
         │ status: COMPLETED│  │ status: PENDING │
         │ + response       │  │ _APPROVAL        │
         └────────┬─────────┘  └────────┬─────────┘
                  │                      │
                  ▼                      ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ WebSocket push    │  │ Show approval    │
         │ to frontend       │  │ buttons on UI    │
         └──────────────────┘  └──────────────────┘
```

### 3.2 WebSocket Real-Time Communication Flow

```
┌───────────────┐
│ User Request  │
│ "Create a     │
│  new task"    │
└───────┬───────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ HTTP POST / {message, prompt_id}                                                 │
│                                                                                 │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ Django chat_view()                                                         │ │
│ │ 1. Create prompt state in Redis (PENDING)                                  │ │
│ │ 2. Invoke LangGraph agent                                                   │ │
│ │ 3. Update Redis state (PROCESSING → COMPLETED/PENDING_APPROVAL)             │ │
│ │ 4. Send to Channel Layer via group_send()                                   │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Channel Layer (Channels Redis)                                                  │
│                                                                                 │
│ - Routes message to prompt_{prompt_id} group                                   │
│ - WebSocket consumers subscribed to this group                                  │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ WebSocket /ws/agent/                                                            │
│                                                                                 │
│ ┌─────────────────────────────────────────────────────────────────────────────┐ │
│ │ AgentConsumer (agents/consumers.py)                                        │ │
│ │  - Receives 'prompt_update' event                                          │ │
│ │  - Sends JSON to WebSocket client                                           │ │
│ │    {type: 'response', response: '...', is_pending: bool}                    │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Frontend JavaScript                                                             │
│                                                                                 │
│ - Receives WebSocket message                                                    │
│ - Updates chat UI with response                                                 │
│ - Shows/hides approval buttons based on is_pending                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Human-in-the-Loop Tool Execution with Redis State

```
┌───────────────┐
│ User Request  │
│ "Create a     │
│  new task"    │
└───────┬───────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Agent analyzes request → decides to call create_new_task()                      │
│                                                                                 │
│ Tool called: create_new_task(title="...")                                      │
└──────────────────────────┬────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ LangGraph interrupt_before=["tools"]                                          │
│ → Execution PAUSES before tool executes                                         │
│ → Returns is_pending=true                                                      │
│ → Django updates Redis: status = PENDING_APPROVAL                              │
│ → WebSocket pushes state to frontend                                           │
│ → User sees Approve/Reject buttons                                             │
└──────────────────────────┬────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌──────────────────┐               ┌──────────────────┐
│ User clicks      │               │ User clicks      │
│ APPROVE         │               │ REJECT           │
└───────┬─────────┘               └───────┬─────────┘
        │                                 │
        ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ POST / {action: 'approve', prompt_id: '...'}                                   │
│                                                                                 │
│ Django chat_view():                                                             │
│   - invoke graph.invoke(None, config) - continues execution                    │
│   - Tool executes (create_new_task writes to SQLite)                          │
│   - Redis updated: status = COMPLETED, response = result                       │
│   - WebSocket pushes final response to frontend                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Redis State Management

### 4.1 Prompt State Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              REDIS DATA STRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Key: prompt:{prompt_id}                                                         │
│  Type: Hash                                                                     │
│  TTL: 3600 seconds (1 hour)                                                     │
│                                                                                  │
│  Fields:                                                                        │
│  ┌────────────────┬──────────────────────────────────────────────────────────┐ │
│  │ Field          │ Value                                                   │ │
│  ├────────────────┼──────────────────────────────────────────────────────────┤ │
│  │ id             │ UUID of the prompt                                      │ │
│  │ user_input     │ Original user message                                    │ │
│  │ thread_id      │ LangGraph thread ID (e.g., "aakarsh_session")            │ │
│  │ status         │ PENDING | PROCESSING | PENDING_APPROVAL | COMPLETED |   │ │
│  │                │ ERROR                                                  │ │
│  │ created_at     │ ISO timestamp                                          │ │
│  │ updated_at     │ ISO timestamp                                          │ │
│  │ response       │ Agent response content                                  │ │
│  │ is_pending     │ true/false - needs approval                            │ │
│  │ error          │ Error message if status=ERROR                           │ │
│  └────────────────┴──────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  Key: prompt:{prompt_id}:stream                                                 │
│  Type: List (for streaming chunks)                                              │
│  TTL: 3600 seconds                                                              │
│                                                                                  │
│  Usage:                                                                          │
│  - rpush chunks during streaming                                               │
│  - lrange to retrieve all chunks                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Prompt State Status Values

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PROMPT STATUS VALUES                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Status             │ Description                                               │
│  ───────────────────┼─────────────────────────────────────────────────────────  │
│  PENDING            │ Initial state when prompt is received                     │
│  PROCESSING         │ Agent is processing the request                          │
│  PENDING_APPROVAL   │ Agent wants to execute tool, waiting for user approval   │
│  COMPLETED          │ Agent finished processing, response ready                 │
│  ERROR              │ An error occurred during processing                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 PromptStateManager API

```python
class PromptStateManager:
    # Create new prompt state
    create_prompt_state(prompt_id, user_input, thread_id) -> state
    
    # Get prompt state by ID
    get_prompt_state(prompt_id) -> state_dict
    
    # Update prompt state (any fields)
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
    
    # Query
    get_thread_prompts(thread_id) -> list of states
```

---

## 5. WebSocket Protocol

### 5.1 Connection Flow

```
Client                          Server
  │                               │
  │──── WebSocket Connect ────────►
  │      /ws/agent/               │
  │                               │
  │◄─── Connection Accepted ──────
  │      {type: 'connected'}      │
  │                               │
  │──── Send init message ────────►
  │   {type: 'init',              │
  │    prompt_id: 'xxx'}          │
  │                               │
  │◄─── Group joined ──────────────
  │   {type: 'connected',         │
  │    prompt_id: 'xxx'}          │
```

### 5.2 Message Types (Client → Server)

```json
// Initialize connection to prompt
{"type": "init", "prompt_id": "uuid"}

// Poll for state updates
{"type": "poll", "prompt_id": "uuid"}

// Send action (approve/reject)
{"type": "action", "prompt_id": "uuid", "action": "approve", "user_input": ""}
```

### 5.3 Message Types (Server → Client)

```json
// Connected confirmation
{"type": "connected", "prompt_id": "uuid"}

// State update
{"type": "state_update", "state": {...}}

// Streaming chunk
{"type": "stream", "chunk": "..."}

// Final response
{"type": "response", "response": "...", "is_pending": false}

// Error
{"type": "error", "message": "..."}
```

---

## 6. Database Schema

### 6.1 SQLite Databases

| Database | File | Purpose |
|----------|------|---------|
| **Application DB** | `db.sqlite3` | Django default - stores InternalTask records |
| **Checkpoint DB** | `checkpoints.db` | LangGraph SqliteSaver - persists agent conversation state |
| **Redis** | redis:7-alpine | Prompt state management, Channel layer backend |

### 6.2 InternalTask Model

```
┌─────────────────────────────────────────────────────────────┐
│                    InternalTask Table                       │
├─────────────────────────────────────────────────────────────┤
│  Column      │  Type          │  Description               │
│──────────────┼────────────────┼─────────────────────────────│
│  id          │  INTEGER (PK) │  Auto-increment primary key │
│  title       │  VARCHAR(200) │  Task title/description     │
│  status      │  VARCHAR(50)  │  Status value              │
│  created_at  │  DATETIME     │  Auto-set on creation       │
└──────────────┴────────────────┴─────────────────────────────┘

Status Values:
┌────────────────────────────────────────────────┐
│  Status       │  Description                   │
│───────────────┼─────────────────────────────────│
│  Pending      │  Task created, not started     │
│  In Progress  │  Task is being worked on       │
│  Completed    │  Task finished successfully    │
│  Cancelled    │  Task cancelled/abandoned       │
└────────────────────────────────────────────────┘
```

---

## 7. API Endpoints

| Endpoint | Method | Purpose | Request Body | Response |
|----------|--------|---------|--------------|----------|
| `/` | GET | Render chat UI | - | HTML page |
| `/` | POST | Send message to agent | `{"message": str, "prompt_id": str, "action": str?}` | `{"prompt_id": str, "response": str, "is_pending": bool}` |
| `/api/tasks/history/` | GET | Get all tasks | - | `{"tasks": [{id, title, status, created_at}]}` |
| `/api/tasks/stats/` | GET | Get task statistics | - | `{"total", "pending", "in_progress", "completed", "cancelled"}` |
| `/api/prompt/<prompt_id>/state/` | GET | Get prompt state from Redis | - | Prompt state hash |
| `/api/prompt/<prompt_id>/stream/` | GET | Get prompt stream chunks | - | `{"stream": [chunks]}` |

---

## 8. Agent Configuration

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            LANGGRAPH AGENT CONFIG                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Model: ChatHuggingFace                                                           │
│  ├── LLM: HuggingFaceEndpoint                                                    │
│  │   ├── repo_id: "Qwen/Qwen2.5-7B-Instruct"                                    │
│  │   ├── max_new_tokens: 512                                                    │
│  │   └── huggingfacehub_api_token: from .env                                    │
│                                                                                  │
│  Tools: [web_search, fetch_user_tasks, get_task_by_id,                           │
│          create_new_task, update_task_status, delete_task,                        │
│          get_task_statistics]                                                    │
│                                                                                  │
│  Checkpointer: SqliteSaver                                                       │
│  ├── Connection: sqlite3.connect("checkpoints.db")                             │
│  └── thread_id: "aakarsh_session" (configurable)                                │
│                                                                                  │
│  interrupt_before: ["tools"]  ← Human-in-the-loop enabled                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Docker Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE SETUP                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  docker-compose.yml                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  services:                                                                 │  │
│  │    redis:                                                                  │  │
│  │      image: redis:7-alpine                                                  │  │
│  │      ports: "6379:6379"                                                    │  │
│  │      volumes: redis_data:/data                                             │  │
│  │      healthcheck: redis-cli ping                                          │  │
│  │                                                                          │  │
│  │    web:                                                                    │  │
│  │      build: .                                                              │  │
│  │      ports: "8000:8000"                                                   │  │
│  │      volumes: .:/app                      ← Project files (live reload)   │  │
│  │      env_file: .env                     ← Environment variables          │  │
│  │      environment:                                                        │  │
│  │        - REDIS_HOST=redis                                                │  │
│  │        - REDIS_PORT=6379                                                 │  │
│  │      depends_on: redis                                                   │  │
│  │      restart: unless-stopped                                              │  │
│  │                                                                          │  │
│  │  volumes:                                                                 │  │
│  │    redis_data:                                                            │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Dockerfile                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  FROM python:3.12-slim                                                     │  │
│  │  WORKDIR /app                                                            │  │
│  │  RUN apt-get update && apt-get install -y gcc                             │  │
│  │  COPY requirements.txt .                                                  │  │
│  │  RUN pip install --no-cache-dir -r requirements.txt                       │  │
│  │  RUN pip install daphne==4.1.2       ← ASGI server for WebSocket          │  │
│  │  RUN touch checkpoints.db         ← Pre-create empty checkpoints DB       │  │
│  │  COPY . .                                                                  │  │
│  │  RUN python manage.py migrate --noinput    ← Run migrations at build      │  │
│  │  EXPOSE 8000                                                               │  │
│  │  CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  .env                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  TAVILY_API_KEY=tvly-dev-...                                               │  │
│  │  HUGGINGFACEHUB_API_TOKEN=hf_...                                          │  │
│  │  REDIS_HOST=localhost          ← Local dev (redis in compose for prod)   │  │
│  │  REDIS_PORT=6379                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 9.1 Build & Run Commands

```bash
# Build and run all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f web
docker-compose logs -f redis

# Stop services
docker-compose down

# Execute shell in web container
docker-compose exec web bash

# Connect to Redis CLI
docker-compose exec redis redis-cli

# Rebuild specific service
docker-compose up -d --build web
```

---

## 10. Available Tools Reference

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AVAILABLE TOOLS                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  TOOL                   │ INPUT                  │ DESCRIPTION                 │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  web_search             │ query: str             │ Search web via Tavily        │
│                         │                        │ Returns search results       │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  fetch_user_tasks       │ query: str = ""        │ Query InternalTask table     │
│                         │                        │ Returns matching/all tasks   │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  get_task_by_id         │ task_id: int           │ Get single task by ID        │
│                         │                        │ Returns task details         │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  create_new_task        │ title: str             │ Create new InternalTask      │
│                         │                        │ Returns confirmation         │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  update_task_status     │ task_id: int,          │ Update task status           │
│                         │ new_status: str        │ Valid: Pending/In Progress/   │
│                         │                        │        Completed/Cancelled   │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  delete_task            │ task_id: int           │ Delete task by ID            │
│                         │                        │ Returns confirmation         │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  get_task_statistics    │ (none)                 │ Get counts by status         │
│                         │                        │ Returns statistics string    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Complete Request Lifecycle

```
USER                    FRONTEND               REST API                 REDIS               LANGGRAPH              WEBSOCKET
 │                         │                      │                        │                     │                       │
 │  "Create a task"         │                      │                        │                     │                       │
 │────────────────────────►│                      │                        │                     │                       │
 │                         │  POST / {message,    │                        │                     │                       │
 │                         │       prompt_id}      │                        │                     │                       │
 │                         │──────────────────────│                        │                     │                       │
 │                         │                      │  create_prompt_state()  │                     │                       │
 │                         │                      │────────────────────────►│                     │                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │  set_status(PENDING)   │                     │                       │
 │                         │                      │────────────────────────►│                     │                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │  run_agent_step()      │                     │                       │
 │                         │                      │────────────────────────────────────────────►│                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │                        │  Agent analyzes      │                       │
 │                         │                      │                        │  ────────────────    │                       │
 │                         │                      │                        │  Needs create_new_task│                       │
 │                         │                      │                        │                       │                       │
 │                         │                      │                        │  INTERRUPT           │                       │
 │                         │                      │                        │  is_pending=true     │                       │
 │                         │                      │◄─────────────────────────────────────────────│                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │  set_response(         │                     │                       │
 │                         │                      │    status=PENDING_APPROVAL                    │                       │
 │                         │                      │────────────────────────►│                     │                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │  group_send()          │                     │                       │
 │                         │                      │──────────────────────────────────────────────►│                       │
 │                         │◄─────────────────────────────────────────────────────────────────│                       │
 │                         │                      │                        │                     │                       │
 │  Shows approval UI      │                      │                        │                     │                       │
 │◄────────────────────────│                       │                        │                     │                       │
 │                         │                      │                        │                     │                       │
 │  [APPROVE] clicked      │                      │                        │                     │                       │
 │────────────────────────►│                      │                        │                     │                       │
 │                         │  POST / {action:    │                        │                     │                       │
 │                         │       "approve",     │                        │                     │                       │
 │                         │       prompt_id}     │                        │                     │                       │
 │                         │──────────────────────│                        │                     │                       │
 │                         │                      │  invoke(action=approve)│                     │                       │
 │                         │                      │────────────────────────────────────────────►│                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │                        │  Execute tool        │                       │
 │                         │                      │                        │  ────────────────    │                       │
 │                         │                      │                        │  create_new_task()   │                       │
 │                         │                      │                        │  → SQLite            │                       │
 │                         │                      │                        │                       │                       │
 │                         │                      │  set_response(COMPLETED│                     │                       │
 │                         │                      │────────────────────────►│                     │                       │
 │                         │                      │                        │                     │                       │
 │                         │                      │  group_send()          │                     │                       │
 │                         │                      │──────────────────────────────────────────────►│                       │
 │                         │◄─────────────────────────────────────────────────────────────────│                       │
 │                         │                      │                        │                     │                       │
 │  "Task created with    │                      │                        │                     │                       │
 │   ID: 1"               │                      │                        │                     │                       │
 │◄────────────────────────│                       │                        │                     │                       │
```

---

## 12. File Structure

```
Enterprise-AI-Orchestrator/
├── agents/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                 ← InternalTask Django model
│   ├── views.py                  ← REST endpoints + Redis state management
│   ├── consumers.py              ← WebSocket consumer (AgentConsumer)
│   ├── routing.py                ← WebSocket URL routing
│   ├── logic/
│   │   ├── graph.py              ← LangGraph agent + error handling
│   │   └── tools.py              ← 7 tool definitions
│   ├── services/
│   │   └── redis_manager.py      ← PromptStateManager for Redis
│   └── migrations/
├── core/
│   ├── __init__.py
│   ├── settings.py               ← Django + Channels + Redis settings
│   ├── urls.py                   ← URL routing (REST + WebSocket)
│   ├── wsgi.py
│   └── asgi.py                   ← ASGI app with ProtocolRouter
├── templates/
│   └── index.html                ← Chat UI with WebSocket support
├── db.sqlite3                    ← SQLite database
├── checkpoints.db               ← LangGraph checkpoints
├── Dockerfile                    ← Container build with Daphne
├── docker-compose.yml          ← Container orchestration with Redis
├── requirements.txt            ← Python dependencies
├── flow.md                      ← This documentation
└── .env                        ← API keys + Redis config (not committed)
```

---

## 13. Quick Reference

### Prompts for Testing

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

### Docker Commands

```bash
# Start all services (Django + Redis)
docker-compose up --build

# Check Redis is running
docker-compose exec redis redis-cli ping

# View WebSocket logs
docker-compose logs -f web | grep websocket

# Rebuild after code changes
docker-compose up -d --build web
```