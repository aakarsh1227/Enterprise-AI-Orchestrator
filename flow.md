# Enterprise AI Orchestrator - System Architecture & Flow Documentation

## 1. System Overview

The Enterprise AI Orchestrator is a Django-based web application that combines a LangGraph-powered AI agent with task management capabilities. Users interact via a modern chat UI, and the AI agent can perform web searches and manage internal tasks with human-in-the-loop approval.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE AI ORCHESTRATOR                               │
│                                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Frontend  │◄──►│   Django    │◄──►│  LangGraph  │◄──►│   LLM API   │       │
│  │  (Chat UI)  │    │   Web App   │    │   Agent     │    │ Qwen 2.5-7B │       │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘    └─────────────┘       │
│                           │                   │                                   │
│                    ┌──────▼──────┐    ┌──────▼──────┐                           │
│                    │   SQLite    │    │   Tools     │                           │
│                    │  Database   │◄──►│  (7 tools)  │                           │
│                    └─────────────┘    └─────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Architecture

### 2.1 Core Modules

| Module | File(s) | Purpose |
|--------|---------|---------|
| **Web Server** | `core/settings.py`, `core/urls.py`, `core/wsgi.py` | Django configuration, routing, WSGI application |
| **Agent Logic** | `agents/logic/graph.py` | LangGraph agent initialization and execution with checkpointing |
| **Tools** | `agents/logic/tools.py` | Tool definitions (7 tools: web search, task CRUD, statistics) |
| **Models** | `agents/models.py` | Django ORM model for InternalTask |
| **Views/API** | `agents/views.py` | REST endpoints for chat and task management |
| **Frontend** | `templates/index.html` | Tailwind CSS chat interface with approval buttons |
| **Container** | `Dockerfile`, `docker-compose.yml` | Docker deployment configuration |

### 2.2 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | Django | 6.0.3 | Web framework, ORM, routing |
| **AI Agent** | LangGraph | 1.1.3 | Agent orchestration with checkpoints |
| **LLM** | Qwen2.5-7B-Instruct | - | HuggingFace hosted model |
| **LLM Integration** | langchain-huggingface | 1.2.1 | ChatHuggingFace wrapper |
| **Checkpoints** | langgraph-checkpoint-sqlite | 3.0.3 | SQLite-based state persistence |
| **Web Search** | Tavily Search | - | langchain_tavily tool |
| **Database** | SQLite3 | - | Task storage + agent checkpoints |
| **Frontend** | Tailwind CSS | - | Styling via CDN |
| **Container** | Docker + Compose | - | Application packaging |

---

## 3. Flow Charts

### 3.1 User Request Flow

```
┌──────────────┐
│ User Input   │
│ "Create a    │
│  task"       │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. Frontend (index.html)                                        │
│    - User types message in chat input                          │
│    - Presses Send button                                       │
│    - JS sends POST to '/' with JSON payload                    │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. Django Views (views.py) - chat_view()                       │
│    - Receive POST request with JSON body                        │
│    - Extract 'message' and 'action' parameters                 │
│    - Call run_agent_step() with thread_id                      │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. LangGraph Agent (graph.py) - run_agent_step()               │
│    - Create config with thread_id                               │
│    - Invoke graph with user input                               │
│    - Check if response is pending (tool approval needed)       │
│    - Return response + is_pending flag                          │
└──────────────────────────────┬─────────────────────────────────┘
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
         │ Return response  │  │ Set is_pending   │
         │ to user          │  │ = true           │
         │                  │  │ Show approval    │
         │                  │  │ buttons          │
         └──────────────────┘  └──────────────────┘
```

### 3.2 Human-in-the-Loop Tool Execution Flow

```
┌───────────────┐
│ User Request  │
│ "Create a     │
│  new task"    │
└───────┬───────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ Agent analyzes request → decides to call create_new_task()     │
│                                                                 │
│ Tool called: create_new_task(title="...")                      │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ LangGraph interrupt_before=["tools"]                          │
│ → Execution PAUSES before tool executes                        │
│ → Returns is_pending=true to frontend                          │
│ → User sees Approve/Reject buttons                            │
└──────────────────────────┬────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌──────────────────┐               ┌──────────────────┐
│ User clicks      │               │ User clicks      │
│ APPROVE         │               │ REJECT           │
└───────┬─────────┘               └───────┬─────────┘
        │                                 │
        ▼                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ If approved: graph.invoke(None, config) continues              │
│    → Tool executes (create_new_task writes to SQLite)          │
│    → Result returned to user                                    │
│                                                                 │
│ If rejected: graph.invoke with "User denied tool execution."    │
│    → Tool does NOT execute                                      │
│    → User receives denial message                               │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Error Recovery Flow (tool_calls Error)

```
┌─────────────────────────────────────────────────────────────────┐
│ Exception Occurs: "Found AIMessages with tool_calls that do   │
│                    not have a corresponding ToolMessage"       │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Error Handler in run_agent_step()                               │
│    - Checks if "tool_calls" and "ToolMessage" in error         │
│    - Deletes corrupted checkpoints.db                           │
│    - Creates fresh SqliteSaver connection                      │
│    - Updates graph.checkpointer to new memory                  │
│    - Resumes conversation with fresh state                     │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ User receives: "Reset conversation due to invalid state.      │
│                Please try again."                               │
└─────────────────────────────────────────────────────────────────┘
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
│  Column      │  Type          │  Description               │
│──────────────┼────────────────┼─────────────────────────────│
│  id          │  INTEGER (PK) │  Auto-increment primary key │
│  title       │  VARCHAR(200) │  Task title/description    │
│  status      │  VARCHAR(50)  │  Status value              │
│  created_at  │  DATETIME      │  Auto-set on creation       │
└──────────────┴────────────────┴─────────────────────────────┘

Status Values:
┌────────────────────────────────────────────────┐
│  Status       │  Description                   │
│───────────────┼─────────────────────────────────│
│  Pending      │  Task created, not started     │
│  In Progress  │  Task is being worked on       │
│  Completed   │  Task finished successfully     │
│  Cancelled   │  Task cancelled/abandoned        │
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
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            LANGGRAPH AGENT CONFIG                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Model: ChatHuggingFace                                                           │
│  ├── LLM: HuggingFaceEndpoint                                                    │
│  │   ├── repo_id: "Qwen/Qwen2.5-7B-Instruct"                                     │
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

## 7. Available Tools Reference

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
│                         │                        │ Returns matching/all tasks    │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  get_task_by_id         │ task_id: int           │ Get single task by ID        │
│                         │                        │ Returns task details         │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  create_new_task        │ title: str             │ Create new InternalTask      │
│                         │                        │ Returns confirmation          │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  update_task_status     │ task_id: int,          │ Update task status           │
│                         │ new_status: str        │ Valid: Pending/In Progress/  │
│                         │                        │        Completed/Cancelled     │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  delete_task            │ task_id: int           │ Delete task by ID            │
│                         │                        │ Returns confirmation          │
│  ───────────────────────┼────────────────────────┼────────────────────────────  │
│  get_task_statistics    │ (none)                 │ Get counts by status         │
│                         │                        │ Returns statistics string     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Docker Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE SETUP                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  docker-compose.yml                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  services:                                                                 │  │
│  │    web:                                                                     │  │
│  │      build: .                                                               │  │
│  │      ports: "8000:8000"                                                    │  │
│  │      volumes:                                                               │  │
│  │        - .:/app                      ← Project files (live reload)        │  │
│  │      env_file: .env                      ← Environment variables          │  │
│  │      restart: unless-stopped                                            │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Dockerfile                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  FROM python:3.12-slim                                                     │  │
│  │  WORKDIR /app                                                             │  │
│  │  RUN apt-get update && apt-get install -y gcc                             │  │
│  │  COPY requirements.txt .                                                  │  │
│  │  RUN pip install --no-cache-dir -r requirements.txt                       │  │
│  │  RUN touch checkpoints.db         ← Pre-create empty checkpoints DB       │  │
│  │  COPY . .                                                                  │  │
│  │  RUN python manage.py migrate --noinput    ← Run migrations at build       │  │
│  │  EXPOSE 8000                                                               │  │
│  │  CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]                 │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  .env (not committed to repo)                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  TAVILY_API_KEY=tvly-dev-...                                              │  │
│  │  HUGGINGFACEHUB_API_TOKEN=hf_...                                          │  │
│  │  OPENAI_API_KEY=sk-proj-...            ← Not used but checked              │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.1 Build & Run Commands

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Execute shell in container
docker-compose exec web bash
```

---

## 9. Complete Request Lifecycle

```
USER                    FRONTEND               DJANGO                  LANGGRAPH               TOOLS/DATABASE
 │                         │                      │                        │                      │
 │  "Create a task"        │                      │                        │                      │
 │────────────────────────►│                      │                        │                      │
 │                         │  POST / {message}    │                        │                      │
 │                         │──────────────────────│                        │                      │
 │                         │                      │  run_agent_step()       │                      │
 │                         │                      │────────────────────────►│                      │
 │                         │                      │                        │                      │
 │                         │                      │                        │  Agent analyzes       │
 │                         │                      │                        │  ────────────────    │
 │                         │                      │                        │  Needs to call        │
 │                         │                      │                        │  create_new_task()    │
 │                         │                      │                        │                       │
 │                         │                      │                        │  INTERRUPT triggered  │
 │                         │                      │                        │  is_pending=true      │
 │                         │                      │◄────────────────────────│                       │
 │                         │  {response,         │                        │                       │
 │                         │   is_pending: true}  │                        │                       │
 │                         │◄────────────────────│                        │                       │
 │                         │                      │                        │                       │
 │  Shows approval UI      │                      │                        │                       │
 │◄────────────────────────│                       │                        │                       │
 │                         │                      │                        │                       │
 │  [APPROVE] clicked      │                      │                        │                       │
 │────────────────────────►│                      │                        │                      │
 │                         │  POST / {action:    │                        │                      │
 │                         │       "approve"}    │                        │                       │
 │                         │──────────────────────│                        │                      │
 │                         │                      │  invoke(action=approve)│                      │
 │                         │                      │────────────────────────►│                      │
 │                         │                      │                        │                       │
 │                         │                      │                        │  Execute tool          │
 │                         │                      │                        │  ────────────────     │
 │                         │                      │                        │  create_new_task()    │
 │                         │                      │                        │  →写入 SQLite         │
 │                         │                      │                        │                       │
 │                         │                      │  {response: success} │                      │
 │                         │                      │◄────────────────────────│                      │
 │                         │  {response: "Task   │                        │                       │
 │                         │   created..."}      │                        │                       │
 │                         │◄────────────────────│                        │                       │
 │                         │                      │                        │                       │
 │  "Task created with    │                      │                        │                       │
 │   ID: 1"               │                      │                        │                       │
 │◄────────────────────────│                       │                        │                       │
```

---

## 10. Error Handling

### 10.1 tool_calls Error Recovery

When LangGraph detects corrupted checkpoint state (missing ToolMessage), the system automatically:
1. Catches the exception
2. Removes the corrupted `checkpoints.db`
3. Creates a fresh checkpoint connection
4. Returns a user-friendly error message
5. User can retry their request

### 10.2 Exception Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    run_agent_step()                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Try:                                                   ││
│  │   - Check current state (is_interrupted?)              ││
│  │   - Handle approve/reject/new message                  ││
│  │   - Return response                                    ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                │
│                    ┌──────┴──────┐                         │
│                    │    ERROR    │                         │
│                    └──────┬──────┘                         │
│           ┌────────────────┼────────────────┐              │
│           │                │                │              │
│           ▼                ▼                ▼              │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ │
│  │ ToolCalls Error│ │ Other Error    │ │ Tavily/DB Error │ │
│  │               │→│               │→│                 │ │
│  │ Reset DB      │ │ Return error   │ │ Return error    │ │
│  │ Retry once    │ │ message        │ │ message         │ │
│  └────────────────┘ └────────────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. State Management

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AGENT STATE & CHECKPOINTING                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Thread/Conversation State (SqliteSaver → checkpoints.db)                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  Stores:                                                                    │  │
│  │    - Conversation history (all AIMessages)                               │  │
│  │    - Current agent state                                                   │  │
│  │    - Pending tool calls (when interrupted)                                │  │
│  │    - Thread_id for session identification                                  │  │
│  │    - Created fresh in Dockerfile ( touch checkpoints.db )                 │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Application State (Django ORM → db.sqlite3)                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  Stores:                                                                    │  │
│  │    - InternalTask records                                                  │  │
│  │    - CRUD operations via tools                                             │  │
│  │    - Persisted via docker-compose volume mount                             │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Session/User State                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  thread_id: "aakarsh_session" (hardcoded in views.py)                      │  │
│  │  - Used for LangGraph checkpointer                                         │  │
│  │  - All conversations in same thread                                       │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
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
│   ├── views.py                  ← REST endpoints (chat, stats, history)
│   ├── logic/
│   │   ├── graph.py              ← LangGraph agent + error handling
│   │   └── tools.py              ← 7 tool definitions
│   └── migrations/
│       └── 0001_initial.py
├── core/
│   ├── __init__.py
│   ├── settings.py               ← Django settings
│   ├── urls.py                   ← URL routing
│   ├── wsgi.py
│   └── asgi.py
├── templates/
│   └── index.html                ← Chat UI with approval buttons
├── db.sqlite3                    ← SQLite database
├── checkpoints.db               ← LangGraph checkpoints
├── Dockerfile                   ← Container build
├── docker-compose.yml          ← Container orchestration
├── requirements.txt            ← Python dependencies
├── flow.md                      ← This documentation
└── .env                        ← API keys (not committed)
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
