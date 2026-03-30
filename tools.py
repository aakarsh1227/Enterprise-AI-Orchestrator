@tool
def query_internal_tasks(query: str):
    """Search for internal task status in the local database."""
    # This uses your existing 'Task Manage Engine' logic 
    from agents.models import Task 
    tasks = Task.objects.filter(title__icontains=query)
    return [t.title for t in tasks]