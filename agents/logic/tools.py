import os
from dotenv import load_dotenv
load_dotenv()

from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from agents.models import InternalTask

@tool
def web_search(query: str):
    """Search the web for information. Returns results with titles and snippets."""
    search = TavilySearch(max_results=2, tavily_api_key=os.getenv("TAVILY_API_KEY"))
    results = search.invoke(query)
    return results

@tool
def fetch_user_tasks(query: str = ""):
    """Search for projects or tasks in the internal Django database. Returns all tasks or ones matching the query."""
    if query:
        tasks = InternalTask.objects.filter(title__icontains=query)
    else:
        tasks = InternalTask.objects.all()
    if not tasks.exists():
        return "The database is currently empty."
    return [f"[ID:{t.id}] {t.title} - {t.status} (Created: {t.created_at.strftime('%Y-%m-%d %H:%M')})" for t in tasks]

@tool
def get_task_by_id(task_id: int):
    """Get a specific task by its ID. Returns the task details or error if not found."""
    try:
        task = InternalTask.objects.get(id=task_id)
        return f"[ID:{task.id}] {task.title}\nStatus: {task.status}\nCreated: {task.created_at.strftime('%Y-%m-%d %H:%M')}"
    except InternalTask.DoesNotExist:
        return f"Task with ID {task_id} not found."

@tool
def create_new_task(title: str):
    """Use this to save a new task or reminder to the internal database."""
    task = InternalTask.objects.create(title=title, status="Pending")
    return f"Successfully created task: '{task.title}' with ID: {task.id}"

@tool
def update_task_status(task_id: int, new_status: str):
    """Update the status of an existing task. Status options: Pending, In Progress, Completed, Cancelled."""
    valid_statuses = ["Pending", "In Progress", "Completed", "Cancelled"]
    if new_status not in valid_statuses:
        return f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
    try:
        task = InternalTask.objects.get(id=task_id)
        old_status = task.status
        task.status = new_status
        task.save()
        return f"Task [ID:{task.id}] '{task.title}' status updated from '{old_status}' to '{new_status}'."
    except InternalTask.DoesNotExist:
        return f"Task with ID {task_id} not found."

@tool
def delete_task(task_id: int):
    """Delete a task from the database by its ID. Use with caution."""
    try:
        task = InternalTask.objects.get(id=task_id)
        task_title = task.title
        task.delete()
        return f"Task [ID:{task_id}] '{task_title}' has been deleted."
    except InternalTask.DoesNotExist:
        return f"Task with ID {task_id} not found."

@tool
def get_task_statistics():
    """Get statistics about all tasks in the database: total count, by status, etc."""
    total = InternalTask.objects.count()
    pending = InternalTask.objects.filter(status="Pending").count()
    in_progress = InternalTask.objects.filter(status="In Progress").count()
    completed = InternalTask.objects.filter(status="Completed").count()
    cancelled = InternalTask.objects.filter(status="Cancelled").count()
    
    return f"""Task Statistics:
- Total Tasks: {total}
- Pending: {pending}
- In Progress: {in_progress}
- Completed: {completed}
- Cancelled: {cancelled}"""

tools = [web_search, fetch_user_tasks, get_task_by_id, create_new_task, update_task_status, delete_task, get_task_statistics]
