from django.shortcuts import render
from django.http import JsonResponse
from .logic.graph import run_agent_step
import json

def chat_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            action = data.get("action")
            
            # Use a static thread_id for now
            thread_id = "aakarsh_session"
            
            result = run_agent_step(user_message, thread_id, action)
            
            return JsonResponse({
                "response": result["response"],
                "is_pending": result["is_pending"]
            })
        except Exception as e:
            return JsonResponse({"response": f"System Error: {str(e)}", "is_pending": False})
            
    return render(request, "index.html")