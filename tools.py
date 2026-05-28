from langchain_core.tools import tool
from agents.models import InternalTask

@tool
def query_internal_tasks(query: str):
    """Search for internal task status in the local database. Returns tasks matching the query."""
    tasks = InternalTask.objects.filter(title__icontains=query)
    if not tasks.exists():
        return "No tasks found matching your query."
    return [f"[ID:{t.id}] {t.title} - {t.status} (Created: {t.created_at.strftime('%Y-%m-%d %H:%M')})" for t in tasks]