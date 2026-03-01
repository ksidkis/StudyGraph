"""LangGraph flow that generates syllabus modules and full lesson content."""

from __future__ import annotations

import json
import math
import re
import os
import time
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv()

class ModuleOutline(BaseModel):
    sequence: int = Field(description="1-based sequence number")
    title: str = Field(description="Module title")

class Syllabus(BaseModel):
    modules: list[ModuleOutline]

class StudyGraphState(TypedDict, total=False):
    goal: str
    module_count: int
    outline: list[dict[str, Any]]
    modules: list[dict[str, Any]]

def _infer_module_count_from_goal(goal: str) -> int:
    match = re.search(r"(\d+)\s*day", goal, flags=re.IGNORECASE)
    if not match:
        return 10
    day_count = int(match.group(1))
    return max(5, min(day_count, 30))

def generate_syllabus(state: StudyGraphState) -> dict[str, Any]:
    goal = state["goal"]
    module_count = state.get("module_count") or _infer_module_count_from_goal(goal)

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        max_retries=6,
    )
    syllabus_llm = llm.with_structured_output(Syllabus)

    prompt = (
        "You are an expert instructional designer. "
        f"Create a learning syllabus of exactly {module_count} modules for this goal: {goal}. "
        "Each module must have a short, specific title and a correct sequence number starting from 1."
    )

    response: Syllabus = syllabus_llm.invoke(prompt)
    outline = [m.model_dump() for m in response.modules]

    if len(outline) != module_count:
        outline = outline[:module_count]
        while len(outline) < module_count:
            outline.append(
                {
                    "sequence": len(outline) + 1,
                    "title": f"Module {len(outline) + 1}",
                }
            )

    return {"module_count": module_count, "outline": outline}

def expand_syllabus_content(state: StudyGraphState) -> dict[str, Any]:
    goal = state["goal"]
    outline = state["outline"]

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
        max_retries=6,
    )
    modules: list[dict[str, Any]] = []

    for item in outline:
        sequence = int(item["sequence"])
        title = str(item["title"])

        prompt = (
            "You are writing a study lesson. "
            f"Goal: {goal}\n"
            f"Module {sequence} title: {title}\n"
            "Write approximately 500 words of dense but clear instructional content with: "
            "(1) concepts, (2) practical examples, (3) one short exercise, (4) recap."
        )

        success = False
        for attempt in range(5):
            try:
                content = llm.invoke(prompt).content
                modules.append(
                    {
                        "sequence_no": sequence,
                        "title": title,
                        "content": content.strip(),
                    }
                )
                success = True
                break
                
            except Exception as e:
                if "429" in str(e):
                    print(f"Speed limit hit on Day {sequence}. Cooling down for 10 seconds...")
                    time.sleep(10)
                else:
                    raise e
        
        if not success:
            raise Exception(f"Failed to generate Day {sequence} after multiple retries.")
        
        # A tiny 3-second delay to keep the free API happy
        time.sleep(3)

    return {"modules": modules}

def build_graph():
    builder = StateGraph(StudyGraphState)
    builder.add_node("generate_syllabus", generate_syllabus)
    builder.add_node("expand_syllabus_content", expand_syllabus_content)
    builder.set_entry_point("generate_syllabus")
    builder.add_edge("generate_syllabus", "expand_syllabus_content")
    builder.add_edge("expand_syllabus_content", END)
    return builder.compile()

def run_study_graph(goal: str) -> list[dict[str, Any]]:
    graph = build_graph()
    result = graph.invoke({"goal": goal})
    modules = result.get("modules", [])

    if not isinstance(modules, list):
        raise ValueError("Invalid graph output: modules is not a list")

    normalized = []
    for idx, module in enumerate(modules, start=1):
        normalized.append(
            {
                "sequence_no": int(module.get("sequence_no", idx)),
                "title": str(module.get("title", f"Module {idx}")),
                "content": str(module.get("content", "")).strip(),
            }
        )
    return normalized