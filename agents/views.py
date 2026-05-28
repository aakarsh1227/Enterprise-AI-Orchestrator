from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .logic.graph import run_agent_step
from .models import InternalTask
import json

def chat_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            action = data.get("action")
            
            thread_id = "aakarsh_session"
            
            result = run_agent_step(user_message, thread_id, action)
            
            return JsonResponse({
                "response": result["response"],
                "is_pending": result["is_pending"]
            })
        except Exception as e:
            return JsonResponse({"response": f"System Error: {str(e)}", "is_pending": False})
            
    return render(request, "index.html")

@require_http_methods(["GET"])
def task_history_view(request):
    tasks = InternalTask.objects.all().order_by('-created_at')
    data = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "created_at": t.created_at.isoformat()
        }
        for t in tasks
    ]
    return JsonResponse({"tasks": data})

@require_http_methods(["GET"])
def task_stats_view(request):
    total = InternalTask.objects.count()
    pending = InternalTask.objects.filter(status="Pending").count()
    in_progress = InternalTask.objects.filter(status="In Progress").count()
    completed = InternalTask.objects.filter(status="Completed").count()
    cancelled = InternalTask.objects.filter(status="Cancelled").count()
    
    return JsonResponse({
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "cancelled": cancelled
    })