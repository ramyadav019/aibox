import asyncio
import json
import os
import re
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from fastapi import BackgroundTasks, FastAPI, HTTPException
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


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "dummy-api-key"
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("GEMINI_BASE_URL")
    model_name = os.getenv("GEMINI_MODEL") or os.getenv("OPENAI_MODEL") or "gemini-3.1-pro"

    llm_kwargs = {
        "model": model_name,
        "temperature": 0.7,
        "api_key": api_key,
    }
    if base_url:
        llm_kwargs["base_url"] = base_url

    return ChatOpenAI(**llm_kwargs)


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
            pool = None
            checkpointer = None
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
    try:
        await ensure_initialized()
    except Exception as e:
        print(f"Startup initialization error: {e}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "has_openai_key": bool(os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "has_db_url": bool(os.getenv("NEON_DATABASE_URL")),
    }


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "1"


async def get_history(thread_id: str) -> list:
    await ensure_initialized()
    if not chatbot:
        return []
    config = {"configurable": {"thread_id": str(thread_id)}}
    try:
        state = await chatbot.aget_state(config)
        return state.values.get("messages", []) if state.values else []
    except Exception as e:
        print(f"Error in get_history for thread {thread_id}: {e}")
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
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        async def err_stream():
            yield f"data: {json.dumps({'token': '⚠️ Error: Neither OPENAI_API_KEY nor GOOGLE_API_KEY is configured in Vercel environment variables.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    llm = get_llm()
    config = {
        "configurable": {"thread_id": str(req.thread_id)},
        "run_name": f"chat-thread-{req.thread_id}",
        "metadata": {
            "thread_id": str(req.thread_id),
            "user_message": req.message[:100],
        },
    }
    history = await get_history(req.thread_id)

    async def save_messages(user_msg: str, ai_msg: str):
        try:
            clean = XML_TAGS.sub("", ai_msg).strip()
            async for _ in chatbot.astream(
                {"messages": [HumanMessage(content=user_msg), AIMessage(content=clean)]},
                config=config,
            ):
                pass
        except Exception as e:
            print(f"Error saving to checkpoint: {e}")

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

        background_tasks.add_task(save_messages, req.message, full)
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/conversation")
async def list_conversations():
    try:
        await ensure_initialized()
        if not pool:
            return {"conversations": []}
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
                rows = await cur.fetchall()
                thread_ids = [row[0] for row in rows]
    except Exception as e:
        print(f"Error listing threads from db: {e}")
        return {"conversations": []}

    result = []
    for tid in thread_ids:
        try:
            tid_str = str(tid)
            msgs = await get_history(tid_str)
            if not msgs:
                continue
            first_user = next(
                (
                    m.content if isinstance(m.content, str) else str(m.content)
                    for m in msgs
                    if isinstance(m, HumanMessage)
                ),
                tid_str,
            )
            last_content = msgs[-1].content if msgs else ""
            last_msg = last_content if isinstance(last_content, str) else str(last_content)
            result.append(
                {
                    "thread_id": tid_str,
                    "title": str(first_user)[:50],
                    "message_count": len(msgs),
                    "preview": str(last_msg)[:80],
                }
            )
        except Exception as e:
            print(f"Error processing thread {tid}: {e}")
            continue

    return {"conversations": result}


@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    await ensure_initialized()
    msgs = await get_history(str(thread_id))
    if not msgs:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {
        "thread_id": str(thread_id),
        "messages": [
            {
                "role": "user" if isinstance(m, HumanMessage) else "assistant",
                "content": m.content if isinstance(m.content, str) else str(m.content),
            }
            for m in msgs
        ],
    }


@app.delete("/conversation/{thread_id}")
async def delete_conversation(thread_id: str):
    await ensure_initialized()
    if not pool:
        return {"status": "ok", "deleted": str(thread_id)}
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (str(thread_id),))
                for table in ("checkpoint_blobs", "checkpoint_writes"):
                    try:
                        await cur.execute(f"DELETE FROM {table} WHERE thread_id = %s", (str(thread_id),))
                    except Exception:
                        pass
        return {"status": "ok", "deleted": str(thread_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
