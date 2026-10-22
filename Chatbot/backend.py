from typing import Annotated, TypedDict

from dotenv import load_dotenv
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

load_dotenv()

# llm = ChatNVIDIA(
#     model="openai/gpt-oss-20b",
#     temperature=0.7,
#     max_completion_tokens=4096,
# )
llm = ChatGroq(
    model="openai/gpt-oss-20b",  # Blazing fast inference via speculative decoding
    temperature=0.7,
    max_retries=3,
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def chat_node(state: ChatState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def get_history(thread_id: str) -> list:
    config = {"configurable": {"thread_id": thread_id}}
    state = chatbot.get_state(config)
    return state.values.get("messages", []) if state.values else []


checkpointer = MemorySaver()
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)
chatbot = graph.compile(checkpointer=checkpointer)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


dist_dir = os.path.join(os.path.dirname(__file__), "dist")


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "1"


@app.post("/chat")
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    history = get_history(req.thread_id)

    async def stream():
        full = ""
        async for chunk in llm.astream(history + [HumanMessage(content=req.message)]):
            token = chunk.content
            if token:
                full += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        # Save final message to checkpointer
        chatbot.invoke(
            {"messages": [HumanMessage(content=req.message)]},
            config=config,
        )
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/")
def index():
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


if os.path.isdir(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
