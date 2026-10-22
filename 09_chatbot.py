from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()


llm = ChatNVIDIA(
    model="openai/gpt-oss-20b",
    temperature=0.7,
    max_completion_tokens=256,
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def chat_node(state: ChatState):
    response = llm.invoke(state["messages"])

    return {"messages": [response]}


checkpointer = MemorySaver()

graph = StateGraph(ChatState)

graph.add_node("chat_node", chat_node)

graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)


thread_id = "1"

while True:

    user_input = input("You: ").strip()

    # Check BEFORE calling the model
    if user_input.lower() in {"exit", "quit", "bye"}:
        print("Bot: Goodbye!")
        break

    config = {"configurable": {"thread_id": thread_id}}

    result = chatbot.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )

    print("Bot:", result["messages"][-1].content)
