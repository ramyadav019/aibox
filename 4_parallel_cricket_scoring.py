from langgraph.graph import StateGraph, START, END
from typing import TypedDict


# 1. Fixed TypedDict syntax (removed default values)
class BatsmanState(TypedDict):
    runs: int
    balls_faced: int
    fours: int
    sixes: int
    bpb: float
    strike_rate: float
    boundary_percentage: float
    summary_text: str  # Added a state key to store the summary text


graph = StateGraph(BatsmanState)


# 2. Fixed nodes to always return a dictionary updating the state
def cal_strike_rate(state: BatsmanState) -> dict:
    if state.get("balls_faced", 0) == 0:
        return {"strike_rate": 0.0}

    sr = (state["runs"] / state["balls_faced"]) * 100
    return {"strike_rate": sr}


def cal_boundary_percentage(state: BatsmanState) -> dict:
    if state.get("balls_faced", 0) == 0:
        return {"boundary_percentage": 0.0}

    total_boundaries = state.get("fours", 0) + state.get("sixes", 0)
    bp = (total_boundaries / state["balls_faced"]) * 100
    return {"boundary_percentage": bp}


def cal_balls_per_boundary(state: BatsmanState) -> dict:
    total_boundaries = state.get("fours", 0) + state.get("sixes", 0)
    if total_boundaries == 0:
        return {"bpb": 0.0}

    bpb_val = state["balls_faced"] / total_boundaries
    return {"bpb": bpb_val}


def summary(state: BatsmanState) -> dict:
    # Safely fetch calculated metrics with defaults to prevent formatting errors
    sr = state.get("strike_rate", 0.0)
    bp = state.get("boundary_percentage", 0.0)

    text = (
        f"Runs: {state['runs']}, Balls Faced: {state['balls_faced']}, "
        f"Strike Rate: {sr:.2f}, Boundary Percentage: {bp:.2f}%"
    )
    return {"summary_text": text}


# 3. Registering the nodes
graph.add_node("strike_rate", cal_strike_rate)
graph.add_node("boundary_percentage", cal_boundary_percentage)
graph.add_node("balls_per_boundary", cal_balls_per_boundary)
graph.add_node("summary", summary)

# 4. Clean linear routing (Parallel fan-out to a single join without an aggregator node
# will throw a structural error in LangGraph compilation; chaining them is safer here).
graph.add_edge(START, "strike_rate")
graph.add_edge("strike_rate", "boundary_percentage")
graph.add_edge("boundary_percentage", "balls_per_boundary")
graph.add_edge("balls_per_boundary", "summary")
graph.add_edge("summary", END)

# Initial data
initial_state = {"runs": 50, "balls_faced": 30, "fours": 5, "sixes": 2}

workflow = graph.compile()
output = workflow.invoke(initial_state)

print(output["summary_text"])
