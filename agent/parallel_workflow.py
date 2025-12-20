from typing import TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine


# Shared State
class State(TypedDict):
    raw_cv_text: str
    anonymized_cv_text: str
    preprocessed_cv_text: str
    job_description: str
    identified_hard_skills: list[str]
    identified_soft_skills: list[str]
    hard_skill_analyser_output: str
    soft_skill_analyser_output: str
    summary_generator_output: str


# without llm to test things out
# class LLM:
#     def invoke(self, str: str) -> str:
#         return str


# llm = LLM()

llm = ChatOllama(
    base_url="",
    model="smollm:135m",
)


# nodes (agents)
def anonymizer_agent(state: State) -> State:
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    )

    nlp_engine = provider.create_engine()

    pii_analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

    analyzer_results = pii_analyzer.analyze(
        text=state["raw_cv_text"],
        language="en",
    )
    anonymize_engine = AnonymizerEngine()
    anonymized_cv_text = anonymize_engine.anonymize(
        text=state["raw_cv_text"], analyzer_results=analyzer_results
    )
    state["anonymized_cv_text"] = anonymized_cv_text.text
    return state


def preprocess_agent(state: State) -> State:
    print("preprocess_agent")
    # https://docs.langchain.com/oss/python/integrations/llms/google_generative_ai
    state["preprocessed_cv_text"] = llm.invoke(
        f"""
    Extract and rewrite the important sections from the following CV text.
    Keep only useful information such as: skills, work experience, projects, achievements, education.
    Remove irrelevant parts like addresses, phone numbers, decorative formatting, etc.

    CV Text:
    {state["anonymized_cv_text"]}
    """
    ).text
    print("-" * 70, "preprocessed_cv_text")
    print(state["preprocessed_cv_text"])

    return state


def hard_skill_identifier_agent(state: State) -> State:
    print("hard_skill_identifier_agent")
    state["identified_hard_skills"] = llm.invoke(
        f"""
    Identify all hard skills required for this job from the given job description.
    Return only a simple Python list of skill names.

    Job Description:
    {state["job_description"]}
    """
    ).text
    print("-" * 70, "identified_hard_skills")
    print(state["identified_hard_skills"])
    return state


def soft_skill_identifier_agent(state: State) -> State:
    print("soft_skill_identifier_agent")
    state["identified_soft_skills"] = llm.invoke(
        f"""
    Identify all soft skills required for this job from the given job description.
    Return only a simple Python list of soft skill names.

    Job Description:
    {state["job_description"]}
    """
    ).text
    print("-" * 70, "identified_soft_skills")
    print(state["identified_soft_skills"])
    return state


def hard_skill_analyzer_agent(state: State) -> State:
    print("hard_skill_analyzer_agent")
    state["hard_skill_analyser_output"] = llm.invoke(
        f"""
    Analyze how well the following CV demonstrates the required hard skills.

    Required Hard Skills:
    {state["identified_hard_skills"]}

    Preprocessed CV:
    {state["preprocessed_cv_text"]}

    Explain:
    - which required hard skills are present
    - which required hard skills are missing
    - short justification for each
    - overall match quality in simple words
    """
    ).text
    print("-" * 70, "hard_skill_analyser_output")
    print(state["hard_skill_analyser_output"])
    return state


def soft_skill_analyzer_agent(state: State) -> State:
    print("soft_skill_analyzer_agent")
    state["soft_skill_analyser_output"] = llm.invoke(
        f"""
    Analyze how well the CV demonstrates the required soft skills.

    Required Soft Skills:
    {state["identified_soft_skills"]}

    Preprocessed CV:
    {state["preprocessed_cv_text"]}

    Explain:
    - which required soft skills are visible in the CV
    - which soft skills are not shown
    - short justification for each
    - overall match quality in simple words
    """
    ).text
    print("-" * 70, "soft_skill_analyser_output")
    print(state["soft_skill_analyser_output"])
    return state


def summary_generator_agent(state: State) -> State:
    print("summary_generator_agent")
    state["summary_generator_output"] = llm.invoke(
        f"""
    Generate a clean summary for the user based on all previous outputs.

    Hard Skill Analysis:
    {state["hard_skill_analyser_output"]}

    Soft Skill Analysis:
    {state["soft_skill_analyser_output"]}

    Summarize:
    - strengths based on both analyses
    - weaknesses or missing items
    - overall suitability for the job in simple language
    - recommended improvements to the CV
    """
    ).text
    print("-" * 70, "summary_generator_output")
    print(state["summary_generator_output"])
    return state


graph = StateGraph(State)

# adding agents (nodes)
graph.add_node("preprocess_agent", preprocess_agent)
graph.add_node("hard_skill_identifier_agent", hard_skill_identifier_agent)
graph.add_node("soft_skill_identifier_agent", soft_skill_identifier_agent)
graph.add_node("hard_skill_analyzer_agent", hard_skill_analyzer_agent)
graph.add_node("soft_skill_analyzer_agent", soft_skill_analyzer_agent)
# aggregator
graph.add_node("summary_generator_agent", summary_generator_agent)

# adding edges
graph.add_edge(START, "preprocess_agent")
graph.add_edge(START, "hard_skill_identifier_agent")
graph.add_edge(START, "soft_skill_identifier_agent")

graph.add_edge("preprocess_agent", "hard_skill_analyzer_agent")
graph.add_edge("preprocess_agent", "soft_skill_analyzer_agent")

graph.add_edge("hard_skill_identifier_agent", "summary_generator_agent")
graph.add_edge("soft_skill_identifier_agent", "summary_generator_agent")
graph.add_edge("hard_skill_analyzer_agent", "summary_generator_agent")
graph.add_edge("soft_skill_analyzer_agent", "summary_generator_agent")

graph.add_edge("summary_generator_agent", END)


parallel_workflow = graph.compile()

raw_cv_text = """
"""

job_description = """
"""

result = parallel_workflow.invoke(
    {"raw_cv_text": raw_cv_text, "job_description": job_description}
)

import json

with open("agent_result.txt", "w", encoding="utf-8") as f:
    f.write(str(result))  # Convert to string if it's not already
with open("agent_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)
