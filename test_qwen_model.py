import os
import sys

sys.path.insert(0, "/home/aakarsh/Enterprise-AI-Orchestrator")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from dotenv import load_dotenv
load_dotenv()

import django
django.setup()

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from agents.logic.tools import tools

def test_model():
    hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not hf_token:
        print("ERROR: HUGGINGFACEHUB_API_TOKEN not found")
        return False
    
    repo_id = "Qwen/Qwen2.5-7B-Instruct"
    print(f"Testing model: {repo_id}")
    
    llm = HuggingFaceEndpoint(
        repo_id=repo_id,
        max_new_tokens=512,
        huggingfacehub_api_token=hf_token,
        timeout=120,
    )
    model = ChatHuggingFace(llm=llm)
    
    print("Testing direct model invocation...")
    try:
        response = model.invoke("Say 'Hello' in one word.")
        print(f"SUCCESS - Model response: {response.content}")
    except Exception as e:
        print(f"ERROR during model invocation: {type(e).__name__}: {e}")
        return False
    
    print("\nTesting with LangGraph agent...")
    try:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        memory = SqliteSaver(conn)
        graph = create_react_agent(
            model,
            tools=tools,
            checkpointer=memory,
            interrupt_before=["tools"]
        )
        
        config = {"configurable": {"thread_id": "test-001"}}
        result = graph.invoke(
            {"messages": [("user", "What is 2 + 2? Answer in one sentence.")]},
            config
        )
        final_message = result["messages"][-1].content
        print(f"SUCCESS - Agent response: {final_message}")
    except Exception as e:
        print(f"ERROR during agent invocation: {type(e).__name__}: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_model()
    sys.exit(0 if success else 1)