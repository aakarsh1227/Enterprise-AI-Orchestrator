import os
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from .tools import tools

# 1. Memory Setup
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
memory = SqliteSaver(conn)

# 2. Correct Token Injection (The "Fix")
# We pass the string variable 'hf_token' directly to the parameter
hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")

llm = HuggingFaceEndpoint(
    repo_id="Qwen/Qwen2.5-72B-Instruct", 
    task="text-generation",
    max_new_tokens=512,
    huggingfacehub_api_token=hf_token 
)
model = ChatHuggingFace(llm=llm)

# 3. Build the Graph (Remains the same)
graph = create_react_agent(
    model, 
    tools=tools, 
    checkpointer=memory, 
    interrupt_before=["tools"]
)

# ... (rest of your run_agent_step function)

def run_agent_step(user_input, thread_id, action=None):
    config = {"configurable": {"thread_id": thread_id}}
    
    if action == "approve":
        result = graph.invoke(None, config)
    elif action == "reject":
        result = graph.invoke({"messages": [("user", "User denied tool.")]}, config)
    else:
        result = graph.invoke({"messages": [("user", user_input)]}, config)
    
    snapshot = graph.get_state(config)
    return {
        "response": result["messages"][-1].content,
        "is_pending": len(snapshot.next) > 0
    }