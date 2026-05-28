import os
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from .tools import tools

conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(conn)

hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")

llm = HuggingFaceEndpoint(
    repo_id="Qwen/Qwen2.5-7B-Instruct",
    max_new_tokens=512,
    huggingfacehub_api_token=hf_token,
)
model = ChatHuggingFace(llm=llm)

graph = create_react_agent(
    model, 
    tools=tools, 
    checkpointer=memory, 
    interrupt_before=["tools"]
)

def run_agent_step(user_input, thread_id, action=None):
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        current_state = graph.get_state(config)
        is_interrupted = len(current_state.next) > 0
        
        if action == "approve" and is_interrupted:
            result = graph.invoke(None, config)
        elif action == "reject":
            result = graph.invoke({"messages": [("user", "User denied tool execution.")]}, config)
        elif is_interrupted:
            result = graph.invoke({"messages": [("user", user_input)]}, config)
        else:
            result = graph.invoke({"messages": [("user", user_input)]}, config)
        
        snapshot = graph.get_state(config)
        return {
            "response": result["messages"][-1].content,
            "is_pending": len(snapshot.next) > 0
        }
    except Exception as e:
        error_msg = str(e)
        if "tool_calls" in error_msg and "ToolMessage" in error_msg:
            os.remove("checkpoints.db")
            global conn, memory
            conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
            memory = SqliteSaver(conn)
            graph.checkpointer = memory
            graph.invoke({"messages": [("user", user_input)]}, config)
            return {"response": "Reset conversation due to invalid state. Please try again.", "is_pending": False}
        return {"response": f"Error: {error_msg[:200]}", "is_pending": False}
