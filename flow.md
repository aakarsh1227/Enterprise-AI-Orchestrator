# Enterprise AI Orchestrator - System Architecture & Flow Documentation

## 1. System Overview

The Enterprise AI Orchestrator is a Django-based web application that combines a LangGraph-powered AI agent with task management capabilities. Users interact via a modern chat UI, and the AI agent can perform web searches and manage internal tasks.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE AI ORCHESTRATOR                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Frontend │◄──►│   Django    │◄──►│  LangGraph  │◄──►│   LLM API   │    │
│  │  (Chat UI) │    │   Web App   │    │   Agent     │    │  (Qwen 2.5) │    │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘    └─────────────┘    │
│                           │                   │                                │
│                    ┌──────▼──────┐    ┌──────▼──────┐                        │
│                    │   SQLite    │    │   Tools     │                        │
│                    │  Database   │◄──►│  (Tavily,   │                        │
│                    │             │    │  Internal)  │                        │
│                    └─────────────┘    └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Architecture

### 2.1 Core Modules

| Module | File(s) | Purpose |
|--------|---------|---------|
| **Web Server** | `core/settings.py`, `core/urls.py`, `core/wsgi.py` | Django configuration, routing, WSGI application |
| **Agent Logic** | `agents/logic/graph.py` | LangGraph agent initialization and execution |
| **Tools** | `agents/logic/tools.py` | Tool definitions (web search, task CRUD) |
| **Models** | `agents/models.py` | Django ORM model for InternalTask |
| **Views/API** | `agents/views.py` | REST endpoints for chat and task management |
| **Frontend** | `templates/index.html` | Tailwind CSS chat interface |
| **Container** | `Dockerfile`, `docker-compose.yml` | Docker deployment configuration |

---

## 3. Flow Charts

### 3.1 User Request Flow

```
┌──────────────┐
│ User Input   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. Frontend (index.html)                                         │
│    - User types message in chat input                            │
│    - Presses Send button                                         │
│    - JS sends POST to '/' with JSON payload                     │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. Django Views (views.py) - chat_view()                        │
│    - Receive POST request with JSON body                         │
│    - Extract 'message' and 'action' parameters                  │
│    - Call run_agent_step() with thread_id                        │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. LangGraph Agent (graph.py) - run_agent_step()                │
│    - Create config with thread_id                                │
│    - Invoke graph with user input                                │
│    - Check if response is pending (tool approval needed)         │
│    - Return response + is_pending flag                           │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ Agent decides    │  │ Agent needs     │
         │ to respond       │  │ tool execution   │
         │ (no tools)       │  │ (interrupt)      │
         └────────┬─────────┘  └────────┬─────────┘
                  │                      │
                  ▼                      ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ Return response  │  │ Set is_pending  │
         │ to user          │  │ = true          │
         │                  │  │ Show approval   │
         │                  │  │ buttons         │
         └──────────────────┘  └──────────────────┘
```

### 3.2 Tool Execution Flow (Human-in-the-Loop)

```
┌───────────────┐
│ User Request  │
│ "Create a     │
│  new task"    │
└───────┬───────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│ Agent analyzes request → decides to call create_new_task()   │
│                                                                │
│ Tool called: create_new_task(title="...")                      │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ LangGraph interrupt_before=["tools"]                           │
│ → Execution PAUSES before tool executes                        │
│ → Returns is_pending=true to frontend                         │
│ → User sees approval buttons                                  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌──────────────────┐               ┌──────────────────┐
│ User clicks      │               │ User clicks      │
│ APPROVE         │               │ REJECT           │
└───────┬──────────┘               └───────┬──────────┘
        │                                  │
        ▼                                  ▼
┌──────────────────┐               ┌──────────────────┐
│ Invoke with     │               │ Invoke with     │
│ action=approve │               │ action=reject    │
└───────┬──────────┘               └───────┬──────────┘
        │                                  │
        ▼                                  ▼
┌────────────────────────────────────────────────────────────────┐
│ If approved: Tool executes, result returned to user            │
│ If rejected: "User denied tool" message, no changes made      │
└────────────────────────────────────────────────────────────────┘
```

### 3.3 Task Management Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TASK MANAGEMENT TOOLS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐  │
│   │ fetch_user_tasks│◄───►│ get_task_by_id  │◄───►│ create_new_task │  │
│   │                 │     │                 │     │                 │  │
│   │ INPUT: query    │     │ INPUT: task_id  │     │ INPUT: title    │  │
│   │ OUTPUT: tasks  │     │ OUTPUT: details │     │ OUTPUT: confirm │  │
│   └────────┬────────┘     └────────┬────────┘     └────────┬────────┘  │
│            │                       │                       │            │
│            │            ┌──────────┴──────────┐            │            │
│            │            │                     │            │            │
│            ▼            ▼                     ▼            │            │
│   ┌─────────────────────────────────────────────────────┐  │            │
│   │              InternalTask Model (Django ORM)        │  │            │
│   │  ┌──────────────────────────────────────────────┐  │  │            │
│   │  │ id: AutoField (PK)                           │  │  │            │
│   │  │ title: CharField(max_length=200)            │──┼──┘            │
│   │  │ status: CharField(max_length=50)              │  │               │
│   │  │ created_at: DateTimeField(auto_now_add=True) │  │               │
│   │  └──────────────────────────────────────────────┘  │               │
│   └─────────────────────────────────────────────────────┘               │
│                            │                                             │
│            ┌───────────────┴───────────────┐                            │
│            ▼                               ▼                            │
│   ┌─────────────────┐               ┌─────────────────┐               │
│   │update_task_status│               │   delete_task   │               │
│   │                  │               │                 │               │
│   │ INPUT: task_id   │               │ INPUT: task_id  │               │
│   │ INPUT: new_status│              │ OUTPUT: confirm │               │
│   │ OUTPUT: confirm │               └─────────────────┘               │
│   └─────────────────┘                                                    │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              get_task_statistics()                             │   │
│   │  Returns: total, pending, in_progress, completed, cancelled     │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              web_search (Tavily)                               │   │
│   │  INPUT: query string                                            │   │
│   │  OUTPUT: search results from web                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Schema

### 4.1 SQLite Databases

| Database | File | Purpose |
|----------|------|---------|
| **Application DB** | `db.sqlite3` | Django default - stores InternalTask records |
| **Checkpoint DB** | `checkpoints.db` | LangGraph SqliteSaver - persists agent conversation state |

### 4.2 InternalTask Model

```
┌─────────────────────────────────────────────────────────────┐
│                    InternalTask Table                       │
├─────────────────────────────────────────────────────────────┤
│  Column      │  Type          │  Description                │
│──────────────┼────────────────┼─────────────────────────────│
│  id          │  INTEGER (PK) │  Auto-increment primary key │
│  title       │  VARCHAR(200) │  Task title/description     │
│  status      │  VARCHAR(50)  │  Pending / In Progress /    │
│              │               │  Completed / Cancelled     │
│  created_at  │  DATETIME     │  Auto-set on creation       │
└──────────────┴────────────────┴─────────────────────────────┘

Status Values:
┌────────────────────────────────────────────────┐
│  Status       │  Description                  │
│───────────────┼────────────────────────────────│
│  Pending      │  Task created, not started    │
│  In Progress  │  Task is being worked on      │
│  Completed   │  Task finished successfully   │
│  Cancelled   │  Task cancelled/abandoned      │
└────────────────────────────────────────────────┘
```

---

## 5. API Endpoints

| Endpoint | Method | Purpose | Request Body | Response |
|----------|--------|---------|--------------|----------|
| `/` | GET | Render chat UI | - | HTML page |
| `/` | POST | Send message to agent | `{"message": str, "action": str?}` | `{"response": str, "is_pending": bool}` |
| `/api/tasks/history/` | GET | Get all tasks | - | `{"tasks": [{id, title, status, created_at}]}` |
| `/api/tasks/stats/` | GET | Get task statistics | - | `{"total", "pending", "in_progress", "completed", "cancelled"}` |

---

## 6. Agent Configuration

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH AGENT CONFIG                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Model: ChatHuggingFace                                                  │
│  ├── LLM: HuggingFaceEndpoint                                           │
│  │   ├── repo_id: "Qwen/Qwen2.2-7B-Instruct"                            │
│  │   ├── max_new_tokens: 512                                           │
│  │   └── huggingfacehub_api_token: from .env                          │
│  │                                                                       │
│  Tools: [web_search, fetch_user_tasks, get_task_by_id,                  │
│          create_new_task, update_task_status, delete_task,              │
│          get_task_statistics]                                          │
│                                                                          │
│  Checkpointer: SqliteSaver                                              │
│  ├── Connection: sqlite3.connect("checkpoints.db")                    │
│  └── thread_id: "aakarsh_session" (configurable)                       │
│                                                                          │
│  interrupt_before: ["tools"]  ← Human-in-the-loop enabled              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Data Flow (Complete Request Lifecycle)

```
USER                    FRONTEND               DJANGO                  LANGGRAPH               LLM/TOOLS
 │                         │                      │                        │                      │
 │  "Create a task"        │                      │                        │                      │
 │────────────────────────►│                      │                        │                      │
 │                         │  POST / {message}    │                        │                      │
 │                         │──────────────────────│                        │                      │
 │                         │                      │  run_agent_step()      │                      │
 │                         │                      │────────────────────────►│                      │
 │                         │                      │                        │                      │
 │                         │                      │                        │  Agent analyzes       │
 │                         │                      │                        │  ────────────────    │
 │                         │                      │                        │  Think: needs to     │
 │                         │                      │                        │  call create_new_task│
 │                         │                      │                        │                       │
 │                         │                      │                        │  Returns:             │
 │                         │                      │                        │  is_pending=true      │
 │                         │                      │◄────────────────────────│                       │
 │                         │  {response,         │                        │                       │
 │                         │   is_pending: true} │                        │                       │
 │                         │◄────────────────────│                        │                       │
 │                         │                      │                        │                       │
 │  Shows approval UI      │                      │                        │                       │
 │◄────────────────────────│                       │                        │                       │
 │                         │                      │                        │                       │
 │  [APPROVE] clicked      │                      │                        │                       │
 │────────────────────────►│                      │                        │                       │
 │                         │  POST / {action:    │                        │                      │
 │                         │       "approve"}    │                        │                       │
 │                         │──────────────────────│                        │                      │
 │                         │                      │  invoke(action=approve)│                      │
 │                         │                      │────────────────────────►│                      │
 │                         │                      │                        │                       │
 │                         │                      │                        │  Execute tool          │
 │                         │                      │                        │  ────────────────     │
 │                         │                      │                        │  create_new_task()    │
 │                         │                      │                        │  → Django ORM         │
 │                         │                      │                        │  → SQLite db.sqlite3  │
 │                         │                      │                        │                       │
 │                         │                      │  {response: success}  │                       │
 │                         │                      │◄────────────────────────│                       │
 │                         │  {response: "Task    │                        │                       │
 │                         │   created..."}      │                        │                       │
 │                         │◄────────────────────│                        │                       │
 │                         │                      │                        │                       │
 │  "Task created with ID: │                      │                        │                       │
 │   1"                    │                      │                        │                       │
 │◄────────────────────────│                       │                        │                       │
 │                         │                      │                        │                       │
```

---

## 8. Docker Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE SETUP                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  docker-compose.yml                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  services:                                                            │  │
│  │    web:                                                                │  │
│  │      build: .                                                          │  │
│  │      ports: "8000:8000"                                               │  │
│  │      volumes:                                                          │  │
│  │        - .:/app                    ← Project files                   │  │
│  │        - ./checkpoints.db:/app/checkpoints.db                        │  │
│  │        - ./db.sqlite3:/app/db.sqlite3                                │  │
│  │      env_file: .env                                                    │  │
│  │      healthcheck:                                                      │  │
│  │        test: curl -f http://localhost:8000/                           │  │
│  │        interval: 30s                                                   │  │
│  │        timeout: 10s    retries: 3    start_period: 10s               │  │
│  │      restart: unless-stopped                                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Dockerfile                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  FROM python:3.12-slim                                                │  │
│  │  WORKDIR /app                                                        │  │
│  │  RUN apt-get update && apt-get install -y gcc && rm -rf ...         │  │
│  │  COPY requirements.txt .                                              │  │
│  │  RUN pip install -r requirements.txt                                  │  │
│  │  COPY . .                                                             │  │
│  │  RUN python manage.py migrate --noinput                              │  │
│  │  EXPOSE 8000                                                          │  │
│  │  CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Tech Stack Table

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | Django | 6.0.3 | Web framework, ORM, routing |
| **AI Agent** | LangGraph | 1.1.3 | Agent orchestration with checkpoints |
| **LLM** | Qwen2.5-7B-Instruct | - | HuggingFace hosted model |
| **LLM Integration** | langchain-huggingface | 1.2.1 | ChatHuggingFace wrapper |
| **Vector/Checkpoints** | langgraph-checkpoint-sqlite | 3.0.3 | SQLite-based state persistence |
| **Web Search** | Tavily Search | - | langchain_tavily tool |
| **Database** | SQLite3 | - | Task storage + agent checkpoints |
| **Frontend** | Tailwind CSS | - | Styling via CDN |
| **Icons** | Font Awesome | 6.5.1 | UI icons via CDN |
| **Charts** | Chart.js | - | Task statistics visualization |
| **Container** | Docker + Compose | - | Application packaging |

---

## 10. Available Tools Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AVAILABLE TOOLS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TOOL                 │ INPUT                 │ DESCRIPTION              │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  web_search           │ query: str            │ Search web via Tavily     │
│                       │ (max_results=2)        │ Returns web search       │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  fetch_user_tasks     │ query: str = ""       │ Query InternalTask table │
│                       │                        │ Returns matching tasks   │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  get_task_by_id       │ task_id: int          │ Get single task by ID   │
│                       │                        │ Returns task details     │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  create_new_task      │ title: str            │ Create new InternalTask  │
│                       │                        │ Returns confirmation     │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  update_task_status   │ task_id: int,         │ Update task status       │
│                       │ new_status: str       │ Valid: Pending/In Progress│
│                       │                        │ /Completed/Cancelled     │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  delete_task          │ task_id: int          │ Delete task by ID        │
│                       │                        │ Returns confirmation      │
│ ──────────────────────┼────────────────────────┼───────────────────────── │
│  get_task_statistics  │ (none)                │ Get counts by status    │
│                       │                        │ Returns statistics dict  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. State Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AGENT STATE & CHECKPOINTING                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Thread/Conversation State (SqliteSaver → checkpoints.db)                  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Stores:                                                             │  │
│  │    - Conversation history (messages)                                 │  │
│  │    - Current agent state                                             │  │
│  │    - Pending tool calls (when interrupted)                           │  │
│  │    - Thread_id for session identification                           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  Application State (Django ORM → db.sqlite3)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Stores:                                                             │  │
│  │    - InternalTask records                                            │  │
│  │    - User-managed task data                                         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Security & Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| `DEBUG` | `True` (dev) | Set False in production |
| `ALLOWED_HOSTS` | localhost, 127.0.0.1, web, 0.0.0.0 | Docker-compatible |
| `CSRF_TRUSTED_ORIGINS` | http://localhost:8000, http://127.0.0.1:8000 | For Docker |
| `SECRET_KEY` | (insecure default) | Change in production |
| `HUGGINGFACEHUB_API_TOKEN` | Required | Set in .env file |

---

## 13. Quick Reference Commands

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Access container shell
docker-compose exec web bash

# Check running containers
docker-compose ps
```
