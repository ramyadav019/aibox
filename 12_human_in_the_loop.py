from typing import TypedDict

from dotenv import load_dotenv

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from langgraph.graph import (
    START,
    END,
    StateGraph,
)

from langgraph.checkpoint.memory import InMemorySaver

from langgraph.types import (
    interrupt,
    Command,
)

# ============================================================
# Load environment
# ============================================================

load_dotenv()

# ============================================================
# LLM
# ============================================================

llm = ChatNVIDIA(
    model="openai/gpt-oss-20b",
    temperature=0.7,
    max_completion_tokens=1024,
)


# ============================================================
# State
# ============================================================


class JokeState(TypedDict):
    topic: str
    joke: str
    explanation: str
    approved: bool


# ============================================================
# Generate Joke
# ============================================================


def generate_joke(state: JokeState):

    prompt = f"""
Generate a short joke about {state["topic"]}.

Return only the joke.
"""

    response = llm.invoke(prompt)

    return {"joke": response.content}


# ============================================================
# Human Approval
# ============================================================


def human_approval(state: JokeState):

    decision = interrupt(
        {
            "message": "Review the generated joke",
            "joke": state["joke"],
        }
    )

    return {"approved": decision == "yes"}


# ============================================================
# Generate Explanation
# ============================================================


def generate_explanation(state: JokeState):

    prompt = f"""
Explain why this joke is funny.

Joke:
{state["joke"]}

Give a short explanation.
"""

    response = llm.invoke(prompt)

    return {"explanation": response.content}


# ============================================================
# Routing
# ============================================================


def route_after_approval(state: JokeState):

    if state["approved"]:
        return "generate_explanation"

    return END


# ============================================================
# Build Graph
# ============================================================

graph = StateGraph(JokeState)


graph.add_node("generate_joke", generate_joke)

graph.add_node("human_approval", human_approval)

graph.add_node("generate_explanation", generate_explanation)


# ============================================================
# Edges
# ============================================================

graph.add_edge(START, "generate_joke")

graph.add_edge("generate_joke", "human_approval")

graph.add_conditional_edges("human_approval", route_after_approval)

graph.add_edge("generate_explanation", END)


# ============================================================
# Checkpointer
# ============================================================

checkpointer = InMemorySaver()


# ============================================================
# Compile
# ============================================================

workflow = graph.compile(checkpointer=checkpointer)


# ============================================================
# Thread
# ============================================================

config = {"configurable": {"thread_id": "human-review-1"}}


# ============================================================
# First execution
# ============================================================

print("\nRunning graph...")

result = workflow.invoke({"topic": "programming"}, config=config)


# ============================================================
# Graph paused here
# ============================================================

print("\n===================================")
print("GRAPH PAUSED")
print("===================================")

print(result)


state = workflow.get_state(config)

print("\nCurrent state:")
print(state.values)

print("\nNext:")
print(state.next)


# ============================================================
# Human input
# ============================================================

print("\n===================================")
print("HUMAN REVIEW")
print("===================================")

print("Generated joke:")
print(state.values["joke"])

decision = input("\nApprove this joke? (yes/no): ").strip().lower()


# ============================================================
# Resume graph
# ============================================================

result = workflow.invoke(Command(resume=decision), config=config)


# ============================================================
# Final result
# ============================================================

print("\n===================================")
print("FINAL RESULT")
print("===================================")

print(result)
