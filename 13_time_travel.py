from dotenv import load_dotenv

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import InMemorySaver

# Load environment variables
load_dotenv()

# Initialize NVIDIA model
llm = ChatNVIDIA(
    model="openai/gpt-oss-20b", temperature=0.7, max_completion_tokens=1024
)


# Define graph node
def chatbot(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# Build graph
builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

# Enable checkpointing
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Use a persistent thread ID
config = {"configurable": {"thread_id": "demo-thread"}}

# Step 1: First conversation turn
graph.invoke(
    {"messages": [HumanMessage(content="My name is Ram.")]},
    config=config,
)

# Step 2: Second conversation turn
graph.invoke(
    {"messages": [HumanMessage(content="What is my name?")]},
    config=config,
)

print("\n--- Current conversation ---")
state = graph.get_state(config)

for message in state.values["messages"]:
    print(f"{message.type}: {message.content}")

# Step 3: Inspect checkpoint history
print("\n--- Checkpoint history ---")
history = list(graph.get_state_history(config))

for index, snapshot in enumerate(history):
    print(
        f"Checkpoint {index}:",
        snapshot.config["configurable"]["checkpoint_id"],
        "| Messages:",
        len(snapshot.values.get("messages", [])),
    )

# Step 4: Travel back to the first user message
# Find a checkpoint containing only the first user/assistant exchange.
target = next(
    snapshot for snapshot in history if len(snapshot.values.get("messages", [])) == 2
)

print("\n--- Historical state ---")
for message in target.values["messages"]:
    print(f"{message.type}: {message.content}")

# Step 5: Fork a new conversation from that checkpoint
fork_config = {
    "configurable": {
        "thread_id": "demo-thread",
        "checkpoint_id": target.config["configurable"]["checkpoint_id"],
    }
}

graph.invoke(
    {"messages": [HumanMessage(content="Actually, call me Alex. What is my name?")]},
    config=fork_config,
)

print("\n--- Forked conversation ---")
forked_state = graph.get_state(config)

for message in forked_state.values["messages"]:
    print(f"{message.type}: {message.content}")
