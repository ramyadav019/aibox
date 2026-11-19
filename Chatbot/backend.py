import json
import os
import re
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

load_dotenv()


api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
base_url = os.getenv("OPENAI_API_BASE") or os.getenv("GEMINI_BASE_URL")
model_name = os.getenv("GEMINI_MODEL") or os.getenv("OPENAI_MODEL") or "gemini-3.1-pro"

llm_kwargs = {
    "model": model_name,
    "temperature": 0.7,
}
if api_key:
    llm_kwargs["api_key"] = api_key
if base_url:
    llm_kwargs["base_url"] = base_url

llm = ChatOpenAI(**llm_kwargs)

XML_TAGS = re.compile(
    r"<ElicitationsGroup\b[^>]*>[\s\S]*?</ElicitationsGroup>|"
    r"<Steps\b[^>]*>[\s\S]*?</Steps>|"
    r"</?(?:ElicitationsGroup|Elicitation|Steps|Step|thought)\b[^>]*?/?>",
    re.IGNORECASE | re.DOTALL,
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def chat_node(state: ChatState):
    return {}


graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

checkpointer: AsyncPostgresSaver = None
chatbot = None
pool: AsyncConnectionPool = None


async def ensure_initialized():
    global checkpointer, chatbot, pool
    if chatbot is not None:
        return
    db_url = os.getenv("NEON_DATABASE_URL")
    if db_url:
        try:
            pool = AsyncConnectionPool(conninfo=db_url, max_size=5, open=False)
            await pool.open()
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            chatbot = graph.compile(checkpointer=checkpointer)
            return
        except Exception as e:
            print(f"Warning: Failed to connect to Postgres checkpointer: {e}")
    chatbot = graph.compile()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await ensure_initialized()


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "1"


async def get_history(thread_id: str) -> list:
    await ensure_initialized()
    if not chatbot:
        return []
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await chatbot.aget_state(config)
        return state.values.get("messages", []) if state.values else []
    except Exception:
        return []


dist_path = os.path.join(os.path.dirname(__file__), "dist")
dist_assets = os.path.join(dist_path, "assets")
if os.path.isdir(dist_assets):
    app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")


@app.get("/")
def index():
    dist_index = os.path.join(dist_path, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))



@app.post("/chat")
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    history = await get_history(req.thread_id)

    async def stream():
        full = ""
        try:
            async for chunk in llm.astream(history + [HumanMessage(content=req.message)]):
                token = chunk.content
                if token:
                    full += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            print(f"Error streaming LLM tokens: {e}")
            yield f"data: {json.dumps({'token': f'\n\n⚠️ Error: {str(e)}'})}\n\n"

        # Notify the client that generation is complete immediately
        yield f"data: {json.dumps({'done': True})}\n\n"

        # Save to checkpoint
        try:
            clean = XML_TAGS.sub("", full).strip()
            async for _ in chatbot.astream(
                {"messages": [HumanMessage(content=req.message), AIMessage(content=clean)]},
                config=config,
            ):
                pass
        except Exception as e:
            print(f"Error saving to checkpoint: {e}")

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/conversation")
async def list_conversations():
    await ensure_initialized()
    if not pool:
        return {"conversations": []}
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
                thread_ids = [row[0] for row in await cur.fetchall()]
    except Exception:
        return {"conversations": []}

    result = []
    for tid in thread_ids:
        msgs = await get_history(tid)
        if not msgs:
            continue
        first_user = next((m.content for m in msgs if isinstance(m, HumanMessage)), tid)
        last_msg = msgs[-1].content[:80] if msgs else ""
        result.append(
            {
                "thread_id": tid,
                "title": first_user[:50],
                "message_count": len(msgs),
                "preview": last_msg,
            }
        )

    return {"conversations": result}


@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    await ensure_initialized()
    msgs = await get_history(thread_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {
        "thread_id": thread_id,
        "messages": [
            {
                "role": "user" if isinstance(m, HumanMessage) else "assistant",
                "content": m.content,
            }
            for m in msgs
        ],
    }


@app.delete("/conversation/{thread_id}")
async def delete_conversation(thread_id: str):
    await ensure_initialized()
    if not pool:
        return {"status": "ok", "deleted": thread_id}
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
                for table in ("checkpoint_blobs", "checkpoint_writes"):
                    try:
                        await cur.execute(f"DELETE FROM {table} WHERE thread_id = %s", (thread_id,))
                    except Exception:
                        pass
        return {"status": "ok", "deleted": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

