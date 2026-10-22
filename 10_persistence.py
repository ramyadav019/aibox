from typing import TypedDict

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv()


# --------------------------------------------------
# NVIDIA LLM
# --------------------------------------------------

llm = ChatNVIDIA(
    model="openai/gpt-oss-20b",
    temperature=0.7,
    max_completion_tokens=2048,
)


# --------------------------------------------------
# State
# --------------------------------------------------


class JokeState(TypedDict):
    topic: str
    joke: str
    explanation: str


# --------------------------------------------------
# Node 1: Generate joke
# --------------------------------------------------


def generate_joke(state: JokeState):

    prompt = f"""
Generate a short joke about {state["topic"]}.

Return only the joke.
"""

    response = llm.invoke(prompt)

    return {"joke": response.content}


# --------------------------------------------------
# Node 2: Explain joke
# --------------------------------------------------


def generate_explanation(state: JokeState):

    prompt = f"""
Explain why this joke is funny.

Joke:
{state["joke"]}

Give a short explanation.
"""

    response = llm.invoke(prompt)

    return {"explanation": response.content}


# --------------------------------------------------
# Create graph
# --------------------------------------------------

graph = StateGraph(JokeState)


# Add nodes
graph.add_node("generate_joke", generate_joke)

graph.add_node("generate_explanation", generate_explanation)


# --------------------------------------------------
# Graph edges
# --------------------------------------------------

graph.add_edge(START, "generate_joke")

graph.add_edge("generate_joke", "generate_explanation")

graph.add_edge("generate_explanation", END)


# --------------------------------------------------
# Checkpointer
# --------------------------------------------------

checkpointer = InMemorySaver()


# --------------------------------------------------
# Compile
# --------------------------------------------------

workflow = graph.compile(checkpointer=checkpointer)


# --------------------------------------------------
# Thread 1
# --------------------------------------------------

config1 = {"configurable": {"thread_id": "1"}}


# --------------------------------------------------
# Run graph
# --------------------------------------------------

final_result1 = workflow.invoke({"topic": "programming"}, config=config1)


# --------------------------------------------------
# Print final result
# --------------------------------------------------

print("\n===================================")
print("FINAL RESULT 1")
print("===================================")

print(final_result1)


# --------------------------------------------------
# Read persisted state
# --------------------------------------------------

current_state = workflow.get_state(config1)

print("\n===================================")
print("CURRENT PERSISTED STATE")
print("===================================")

print(current_state.values)


# --------------------------------------------------
# Checkpoint history
# --------------------------------------------------

print("\n===================================")
print("CHECKPOINT HISTORY")
print("===================================")

for state in workflow.get_state_history(config1):
    print(state.values)
