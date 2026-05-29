import os
import json
import uuid
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .logic.graph import run_agent_step
from .models import InternalTask
from .services.redis_manager import prompt_state_manager

def chat_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            action = data.get("action")
            prompt_id = data.get("prompt_id", str(uuid.uuid4()))
            
            thread_id = "aakarsh_session"
            
            channel_layer = get_channel_layer()
            
            if action in ["approve", "reject"]:
                result = run_agent_step(user_message, thread_id, action)
                prompt_state_manager.set_response(
                    prompt_id,
                    result["response"],
                    result.get("is_pending", False)
                )
                
                if hasattr(async_to_sync(channel_layer.group_send), '__call__'):
                    async_to_sync(channel_layer.group_send)(
                        f"prompt_{prompt_id}",
                        {
                            'type': 'prompt_update',
                            'data': {
                                'type': 'response',
                                'response': result["response"],
                                'is_pending': result.get("is_pending", False)
                            }
                        }
                    )
                
                return JsonResponse({
                    "response": result["response"],
                    "is_pending": result.get("is_pending", False)
                })
            
            prompt_state_manager.create_prompt_state(prompt_id, user_message, thread_id)
            prompt_state_manager.set_status(prompt_id, "PROCESSING")
            
            async_to_sync(channel_layer.group_add)(
                f"prompt_{prompt_id}",
                "websocket"
            )
            
            result = run_agent_step(user_message, thread_id, None)
            
            prompt_state_manager.set_response(
                prompt_id,
                result["response"],
                result.get("is_pending", False)
            )
            
            async_to_sync(channel_layer.group_send)(
                f"prompt_{prompt_id}",
                {
                    'type': 'prompt_update',
                    'data': {
                        'type': 'response',
                        'response': result["response"],
                        'is_pending': result.get("is_pending", False)
                    }
                }
            )
            
            return JsonResponse({
                "prompt_id": prompt_id,
                "response": result["response"],
                "is_pending": result.get("is_pending", False)
            })
            
        except Exception as e:
            error_msg = str(e)
            if prompt_id:
                prompt_state_manager.set_error(prompt_id, error_msg)
            return JsonResponse({"response": f"System Error: {error_msg}", "is_pending": False})
            
    return render(request, "index.html")

def process_action(prompt_id, user_input, action):
    thread_id = "aakarsh_session"
    result = run_agent_step(user_input, thread_id, action)
    
    prompt_state_manager.set_response(
        prompt_id,
        result["response"],
        result.get("is_pending", False)
    )
    
    return result

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

@require_http_methods(["GET"])
def get_prompt_state_view(request, prompt_id):
    state = prompt_state_manager.get_prompt_state(prompt_id)
    if not state:
        return JsonResponse({"error": "Prompt not found"}, status=404)
    return JsonResponse(state)

@require_http_methods(["GET"])
def get_prompt_stream_view(request, prompt_id):
    stream = prompt_state_manager.get_stream(prompt_id)
    return JsonResponse({"stream": stream})