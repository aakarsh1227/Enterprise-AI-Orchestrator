from django.urls import path
from agents.consumers import AgentConsumer

websocket_urlpatterns = [
    path('ws/agent/', AgentConsumer.as_asgi()),
]