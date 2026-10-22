import operator
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

load_dotenv()


# ============================================================
# 1. STRUCTURED OUTPUT SCHEMA
# ============================================================


class EvaluationSchema(BaseModel):
    feedback: str = Field(
        description="Concise and constructive feedback. Maximum 100 words."
    )
    score: int = Field(ge=0, le=10, description="Score from 0 to 10.")


# ============================================================
# 2. MODEL
# ============================================================

model = ChatNVIDIA(
    model="openai/gpt-oss-20b",
    temperature=0,
)

# Convert the model into a structured-output model.
structured_model = model.with_structured_output(EvaluationSchema)


# ============================================================
# 3. ESSAY
# ============================================================

essay = """
Technology has become an important part of our daily lives.
It has changed the way we communicate, work, study, and access information.
With smartphones and the internet, people can connect with others
and learn new things from almost anywhere.

Technology has also improved healthcare, education, and business.
Online learning helps students access knowledge easily, while digital
services make many tasks faster and more convenient. Artificial intelligence
is further creating new opportunities in different fields.

However, technology also brings challenges. Excessive use of digital devices
can affect social relationships and privacy. Automation may also change
employment opportunities for some workers. Therefore, technology should
be used responsibly and thoughtfully.

In conclusion, technology is a powerful tool that can improve human life
when used wisely. The goal should not simply be technological progress,
but progress that benefits society as a whole.
"""


# ============================================================
# 4. LANGGRAPH STATE
# ============================================================


class UPSCState(TypedDict):
    essay: str

    language_feedback: str
    clarity_feedback: str
    analysis_feedback: str
    overall_feedback: str

    individual_scores: Annotated[list[int], operator.add]

    avg_score: float


# ============================================================
# 5. LANGUAGE EVALUATION
# ============================================================


def evaluate_language(state: UPSCState):

    prompt = f"""
You are an expert essay evaluator.

Evaluate ONLY the following aspects:

- Grammar
- Sentence construction
- Vocabulary
- Language fluency

Give concise and constructive feedback.

Do not discuss clarity, organization, or critical analysis.

Essay:

{state["essay"]}
"""

    result = structured_model.invoke(prompt)

    return {
        "language_feedback": result.feedback,
        "individual_scores": [result.score],
    }


# ============================================================
# 6. CLARITY EVALUATION
# ============================================================


def evaluate_clarity(state: UPSCState):

    prompt = f"""
You are an expert essay evaluator.

Evaluate ONLY the following aspects:

- Clarity
- Coherence
- Logical flow
- Organization of ideas

Give concise and constructive feedback.

Do not focus on grammar or critical analysis.

Essay:

{state["essay"]}
"""

    result = structured_model.invoke(prompt)

    return {
        "clarity_feedback": result.feedback,
        "individual_scores": [result.score],
    }


# ============================================================
# 7. ANALYSIS EVALUATION
# ============================================================


def evaluate_analysis(state: UPSCState):

    prompt = f"""
You are an expert essay evaluator.

Evaluate ONLY the following aspects:

- Depth of analysis
- Critical thinking
- Development of ideas
- Supporting arguments
- Originality of thought

Give concise and constructive feedback.

Do not focus primarily on grammar or sentence construction.

Essay:

{state["essay"]}
"""

    result = structured_model.invoke(prompt)

    return {
        "analysis_feedback": result.feedback,
        "individual_scores": [result.score],
    }


# ============================================================
# 8. OVERALL EVALUATION
# ============================================================


def evaluate_overall(state: UPSCState):

    prompt = f"""
You are an expert essay evaluator.

Create a concise overall assessment of the essay using
the evaluations below.

LANGUAGE:
{state["language_feedback"]}

CLARITY:
{state["clarity_feedback"]}

ANALYSIS:
{state["analysis_feedback"]}

Provide constructive overall feedback.

Do not generate a new score.
The final score will be calculated mathematically by Python.
"""

    # We only need feedback here.
    class OverallFeedback(BaseModel):
        feedback: str = Field(description="Concise overall constructive feedback.")

    overall_model = model.with_structured_output(OverallFeedback)

    result = overall_model.invoke(prompt)

    scores = state["individual_scores"]

    avg_score = sum(scores) / len(scores)

    return {
        "overall_feedback": result.feedback,
        "avg_score": avg_score,
    }


# ============================================================
# 9. BUILD GRAPH
# ============================================================

graph = StateGraph(UPSCState)


graph.add_node("evaluate_language", evaluate_language)

graph.add_node("evaluate_clarity", evaluate_clarity)

graph.add_node("evaluate_analysis", evaluate_analysis)

graph.add_node("evaluate_overall", evaluate_overall)


# ============================================================
# 10. PARALLEL EXECUTION
# ============================================================

graph.add_edge(START, "evaluate_language")

graph.add_edge(START, "evaluate_clarity")

graph.add_edge(START, "evaluate_analysis")


# ============================================================
# 11. WAIT FOR ALL EVALUATORS
# ============================================================

graph.add_edge("evaluate_language", "evaluate_overall")

graph.add_edge("evaluate_clarity", "evaluate_overall")

graph.add_edge("evaluate_analysis", "evaluate_overall")


graph.add_edge("evaluate_overall", END)


# ============================================================
# 12. COMPILE
# ============================================================

workflow = graph.compile()


# ============================================================
# 13. INITIAL STATE
# ============================================================

initial_state = {
    "essay": essay,
    "individual_scores": [],
}


# ============================================================
# 14. RUN
# ============================================================

result = workflow.invoke(initial_state)


# ============================================================
# 15. DISPLAY RESULT
# ============================================================

print("\n================================")
print("FINAL ESSAY EVALUATION")
print("================================")

# print("\nLanguage Feedback:")
# print(result["language_feedback"])

# print("\nClarity Feedback:")
# print(result["clarity_feedback"])

# print("\nAnalysis Feedback:")
# print(result["analysis_feedback"])

# print("\nIndividual Scores:")
# print(result["individual_scores"])

print("\nAverage Score:")
print(result["avg_score"])

print("\nOverall Feedback:")
print(result["overall_feedback"])
