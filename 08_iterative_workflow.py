from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal, Annotated
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

load_dotenv()

# Generator: current NVIDIA endpoint for text generation
generator_llm = ChatNVIDIA(
    model="google/gemma-4-31b-it",
    timeout=180,
    max_completion_tokens=128,
)

evaluation_llm = ChatNVIDIA(
    model="openai/gpt-oss-120b",  # Frontier 120B reasoning model
    timeout=180,
    max_completion_tokens=256,
)

optimizer_llm = ChatNVIDIA(
    model="nvidia/nemotron-3-super-120b-a12b",  # Flagship planning & agent model
    timeout=180,
    max_completion_tokens=128,
).with_thinking_mode(enabled=True)


class TweetState(TypedDict):
    topic: str
    feedback: str
    tweet: str
    evaluation: Literal["approved", "needs optimization"]
    no_of_iterations: int
    max_iterations: int


class EvaluationSchema(BaseModel):
    evaluation: Annotated[
        Literal["approved", "needs optimization"],
        Field(description="The evaluation result of the tweet."),
    ]
    feedback: Annotated[
        str, Field(description="Detailed feedback on the tweet's quality.")
    ]


graph = StateGraph(TweetState)


def generate_tweet(state: TweetState) -> dict:
    prompt = [
        SystemMessage(
            content="You are a creative social media content generator. "
            "Your task is to create a compelling tweet based on the given topic."
        ),
        HumanMessage(
            content=f"""Write a short, original, and hilarious tweet on the topic: "{state['topic']}" .
Rules:
- Do NOT use question-answer format .
- Max 280 characters.
- Use observational humor, irony, sarcasm, or cultural references.
- Think in meme logic, punchlines, or relatable takes.
- Use simple, day to day english"""
        ),
    ]
    response = generator_llm.invoke(prompt)
    # Return updates to state cleanly
    return {"tweet": response.content}


def evaluate_tweet(state: TweetState) -> dict:
    prompt = [
        SystemMessage(
            content="You are a meticulous social media content evaluator. "
            "Your task is to assess the quality of the provided tweet."
        ),
        HumanMessage(
            content=f"""Evaluate the following tweet for humor, originality, and engagement potential:

{state['tweet']}"""
        ),
    ]
    structured_evaluation_llm = evaluation_llm.with_structured_output(EvaluationSchema)
    response = structured_evaluation_llm.invoke(prompt)
    # Return updates to state cleanly
    return {"evaluation": response.evaluation, "feedback": response.feedback}


def optimize_tweet(state: TweetState) -> dict:
    # FIX: Read state fields safely with fallbacks to avoid KeyErrors
    current_tweet = state.get("tweet", "")
    feedback = state.get("feedback", "Needs general improvement.")

    prompt = [
        SystemMessage(
            content="You are a skilled content optimizer. "
            "Your task is to improve the tweet based on the evaluation feedback."
        ),
        HumanMessage(
            content=f"Current tweet: {current_tweet}\n\nEvaluation Feedback: {feedback}\n\nPlease optimize the tweet based on the instructions."
        ),
    ]
    # FIX: Correctly increment counter state
    iteration = state.get("no_of_iterations", 0) + 1
    response = optimizer_llm.invoke(prompt)
    return {"tweet": response.content, "no_of_iterations": iteration}


def route_tweet(state: TweetState) -> Literal["optimize_tweet", "end"]:
    # FIX: Read with safe defaults (.get) to prevent crashes on edge paths
    evaluation = state.get("evaluation", "needs optimization")
    no_of_iterations = state.get("no_of_iterations", 0)
    max_iterations = state.get("max_iterations", 3)

    if evaluation == "approved" or no_of_iterations >= max_iterations:
        return "end"
    else:
        return "optimize_tweet"


graph.add_node("generate_tweet", generate_tweet)
graph.add_node("evaluate_tweet", evaluate_tweet)
graph.add_node("optimize_tweet", optimize_tweet)

graph.add_edge(START, "generate_tweet")
graph.add_edge("generate_tweet", "evaluate_tweet")
graph.add_conditional_edges(
    "evaluate_tweet",
    route_tweet,
    {
        "end": END,
        "optimize_tweet": "optimize_tweet",
    },
)
graph.add_edge("optimize_tweet", "evaluate_tweet")

workflow = graph.compile()

initial_state = {
    "topic": "The absurdity of modern dating apps",
    "no_of_iterations": 0,
    "max_iterations": 3,
}

final_state = workflow.invoke(initial_state)
print("\n--- Final Output ---")
print("Final Tweet:", final_state["tweet"])
