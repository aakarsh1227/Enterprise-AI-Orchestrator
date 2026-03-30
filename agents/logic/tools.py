from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from agents.models import InternalTask

# Initialize the 2026 Search Tool
web_search = TavilySearch(max_results=2)

@tool
def fetch_user_tasks(query: str):
    """Search for projects or tasks in the internal Django database."""
    tasks = InternalTask.objects.all()
    if not tasks.exists():
        return "The database is currently empty."
    return [f"{t.title}: {t.status}" for t in tasks]

tools = [web_search, fetch_user_tasks]

@tool
def create_new_task(title: str):
    """Use this to save a new task or reminder to the internal database."""
    from agents.models import InternalTask
    task = InternalTask.objects.create(title=title, status="Pending")
    return f"Successfully created task: '{task.title}' with ID: {task.id}"

# Add it to your tool list
tools = [web_search, fetch_user_tasks, create_new_task]