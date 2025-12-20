import re
from typing import TypedDict

import environ
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

import time


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


from langchain_google_genai import ChatGoogleGenerativeAI

env = environ.Env()
env.read_env(".env")
GEN_AI_API_KEY = env("GEN_AI_API_KEY")
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL")


# without llm to test things out
# class LLM:
#     def invoke(self, str: str) -> str:
#         return str
# llm = LLM()

# Select model name, makesure a entry in PROMPTS is available
# model="smollm:135m",
# model="hhao/qwen2.5-coder-tools:0.5b",
# MODEL_NAME = "hhao/qwen2.5-coder-tools:0.5b"
MODEL_NAME = "gemini-2.5-flash-lite"

# OLLAMA for local testing without ratelimits and other hinderances
# llm = ChatOllama(base_url=OLLAMA_BASE_URL, model=MODEL_NAME)

# https://github.com/langchain-ai/langchain-google/issues/1042
# https://github.com/IrakliGLD/langchain_railway/commit/d149adc21bf03c39ba432260f6ecadb58a007687
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    api_key=GEN_AI_API_KEY,
    max_retries=1,
)

from agent.parseJson import parse_markdown_json
from agent.prompts import get_prompt, model_prompts, print_agent_prompt_and_response


PROMPTS = get_prompt(model_prompts=model_prompts, model=MODEL_NAME)


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
    print_agent_prompt_and_response(
        agent="anonymizer_agent",
        prompt="None",
        response=state["anonymized_cv_text"],
    )
    return state


def preprocess_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["preprocess"]}

    CV Text:
    {state["anonymized_cv_text"]}
    """
    # https://docs.langchain.com/oss/python/integrations/llms/google_generative_ai
    state["preprocessed_cv_text"] = llm.invoke(prompt).text
    print_agent_prompt_and_response(
        agent="preprocess_agent",
        prompt=prompt,
        response=state["preprocessed_cv_text"],
    )
    time.sleep(15)
    return state


def hard_skill_identifier_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["hard_skill_identifier"]}

    Job Description:
    {state["job_description"]}
    """
    state["identified_hard_skills"] = parse_markdown_json(llm.invoke(prompt).text)
    print_agent_prompt_and_response(
        agent="hard_skill_identifier_agent",
        prompt=prompt,
        response=state["identified_hard_skills"],
    )
    time.sleep(15)
    return state


def soft_skill_identifier_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["soft_skill_identifier"]}

    Job Description:
    {state["job_description"]}
    """
    state["identified_soft_skills"] = parse_markdown_json(llm.invoke(prompt).text)
    print_agent_prompt_and_response(
        agent="soft_skill_identifier_agent",
        prompt=prompt,
        response=state["identified_soft_skills"],
    )
    time.sleep(15)
    return state


def hard_skill_analyzer_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["hard_skill_analyzer"]}

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
    state["hard_skill_analyser_output"] = parse_markdown_json(llm.invoke(prompt).text)
    print_agent_prompt_and_response(
        agent="hard_skill_analyzer_agent",
        prompt=prompt,
        response=state["hard_skill_analyser_output"],
    )
    time.sleep(15)
    return state


def soft_skill_analyzer_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["soft_skill_analyzer"]}

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
    state["soft_skill_analyser_output"] = parse_markdown_json(llm.invoke(prompt).text)
    print_agent_prompt_and_response(
        agent="soft_skill_analyzer_agent",
        prompt=prompt,
        response=state["soft_skill_analyser_output"],
    )
    time.sleep(15)
    return state


def summary_generator_agent(state: State) -> State:
    prompt = f"""
    {PROMPTS["summary_generator"]}

    Hard Skill Analysis:
    {state["hard_skill_analyser_output"]}

    Soft Skill Analysis:
    {state["soft_skill_analyser_output"]}
    """
    state["summary_generator_output"] = parse_markdown_json(llm.invoke(prompt).text)
    print_agent_prompt_and_response(
        agent="summary_generator_agent",
        prompt=prompt,
        response=state["summary_generator_output"],
    )
    return state


graph = StateGraph(State)

# adding agents
graph.add_node("anonymizer_agent", anonymizer_agent)
graph.add_node("preprocess_agent", preprocess_agent)
graph.add_node("hard_skill_identifier_agent", hard_skill_identifier_agent)
graph.add_node("soft_skill_identifier_agent", soft_skill_identifier_agent)
graph.add_node("hard_skill_analyzer_agent", hard_skill_analyzer_agent)
graph.add_node("soft_skill_analyzer_agent", soft_skill_analyzer_agent)
graph.add_node("summary_generator_agent", summary_generator_agent)

# adding edges
graph.set_entry_point("anonymizer_agent")
graph.add_edge("anonymizer_agent", "preprocess_agent")
graph.add_edge("preprocess_agent", "hard_skill_identifier_agent")
graph.add_edge("hard_skill_identifier_agent", "soft_skill_identifier_agent")
graph.add_edge("soft_skill_identifier_agent", "hard_skill_analyzer_agent")
graph.add_edge("hard_skill_analyzer_agent", "soft_skill_analyzer_agent")
graph.add_edge("soft_skill_analyzer_agent", "summary_generator_agent")
graph.set_finish_point("summary_generator_agent")

# Currently we are only chaining LLM responses so it is called workflow not agent.
# once we attach tools and let LLM to decied what to do it will become agent(s)
# Hope we could do it too.
steam_line_workflow = graph.compile()

# raw_cv_text = """
# Python developer with Django experience.
# """

# job_description = """
# FullStack developer using Python, Django, Docker, React.
# """

# result = steam_line_workflow.invoke(
#     {"raw_cv_text": raw_cv_text, "job_description": job_description}
# )


# print("-" * 30)
# print("| Final result |")
# print("-" * 30)
# print(result)

# import json

# with open("agent_result.txt", "w", encoding="utf-8") as f:
#     f.write(str(result))  # Convert to string if it's not already
# with open("agent_result.json", "w", encoding="utf-8") as f:
#     json.dump(result, f, indent=2)
