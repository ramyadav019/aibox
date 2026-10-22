from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal


class CoEfficient(TypedDict):
    a: float
    b: float
    c: float
    equation: str
    discriminant: float
    result: str


def show_equation(state: CoEfficient) -> CoEfficient:
    state["equation"] = f"{state['a']}x^2 + {state['b']}x + {state['c']} = 0"
    return state


def calculate_discriminant(state: CoEfficient) -> CoEfficient:
    state["discriminant"] = state["b"] ** 2 - 4 * state["a"] * state["c"]
    return state


def different_roots(state: CoEfficient) -> dict:
    root1 = (-state["b"] + state["discriminant"] ** 0.5) / (2 * state["a"])
    root2 = (-state["b"] - state["discriminant"] ** 0.5) / (2 * state["a"])
    return {"result": f"Roots: {root1}, {root2}"}


def repeated_roots(state: CoEfficient) -> dict:
    root = -state["b"] / (2 * state["a"])
    return {"result": f"Repeated root: {root}"}


def no_real_roots(state: CoEfficient) -> dict:
    return {"result": "No real roots"}


def check_discriminant(
    state: CoEfficient,
) -> Literal["different_roots", "repeated_roots", "no_real_roots"]:
    if state["discriminant"] > 0:
        return "different_roots"
    elif state["discriminant"] == 0:
        return "repeated_roots"
    else:
        return "no_real_roots"


# 1. Initialize Graph
graph = StateGraph(CoEfficient)

# 2. Add Nodes
graph.add_node("show_equation", show_equation)
graph.add_node("calculate_discriminant", calculate_discriminant)
graph.add_node("repeated_roots", repeated_roots)
graph.add_node("different_roots", different_roots)
graph.add_node("no_real_roots", no_real_roots)

# 3. Add Fixed Edges
graph.add_edge(START, "show_equation")
graph.add_edge("show_equation", "calculate_discriminant")

# FIX 1: Use add_conditional_edges instead of add_edge for routing
graph.add_conditional_edges("calculate_discriminant", check_discriminant)

# FIX 2: Connect the actual nodes ("different_roots", not "real_roots") to END
graph.add_edge("different_roots", END)
graph.add_edge("repeated_roots", END)
graph.add_edge("no_real_roots", END)

# 4. Compile the graph (CRITICAL: graph must be compiled to draw it)
workflow = graph.compile()

# 5. Output the ASCII representation
workflow.get_graph().print_ascii()

initial_state = {"a": 1, "b": -3, "c": 2}

final_state = workflow.invoke(initial_state)
print(final_state["result"])
