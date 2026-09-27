"""The AI Stylist: a LangGraph ReAct agent (spec section 8).

    START -> reason --(tool calls)--> tools --> reason ... --(enough context)--> synthesize -> END

`reason` asks the LLM which tools to call next (Gemini function calling). `tools` runs them
against the catalog (pgvector), Open-Meteo, the user's history and the style-notes knowledge base.
`synthesize` writes the reply plus try-on-ready garment cards and preference updates.

Without an API key, a deterministic planner and template writer stand in for the LLM, so the
same graph, tools and database paths run offline.
"""

import asyncio
import json
import logging
import operator
import uuid
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.spend import record_paid_call
from app.services import gemini
from app.services.stylist import tools

log = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 3

SYSTEM = """You are LOOKBOOK's personal stylist. Be warm, specific and concise (under 120 words).
Always ground outfit suggestions in catalog items returned by search_catalog, and use
search_style_notes for dress codes and occasions. If the user mentions a place or being outside,
check the weather. Never comment on the user's body, face or skin. If a request isn't about
clothing or style, answer briefly and steer back to fashion."""


class StylistState(TypedDict, total=False):
    message: str
    history: list[dict]
    memory: dict
    steps: Annotated[list[dict], operator.add]
    pending: list[dict]
    rounds: int
    reply: str
    garment_ids: list[str]
    memory_updates: dict


class MemoryUpdates(BaseModel):
    liked_colors: list[str] = Field(default_factory=list)
    disliked_cuts: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)


class Synthesis(BaseModel):
    reply: str
    recommended_garment_ids: list[str] = Field(default_factory=list)
    memory_updates: MemoryUpdates = Field(default_factory=MemoryUpdates)


def _use_llm() -> bool:
    s = get_settings()
    return bool(s.gemini_api_key) and not s.use_mock


def _transcript(state: StylistState) -> str:
    lines = [f"{m['role']}: {m['content']}" for m in state.get("history", [])[-8:]]
    lines.append(f"user: {state['message']}")
    if state.get("steps"):
        lines.append("\nTool results so far:")
        for step in state["steps"]:
            lines.append(f"- {step['tool']}({json.dumps(step['args'])}) -> {json.dumps(step['result'])[:1500]}")
    lines.append(f"\nKnown preferences: {json.dumps(state.get('memory', {}))}")
    return "\n".join(lines)


# --- nodes ---------------------------------------------------------------------------------------


async def reason(state: StylistState) -> dict:
    rounds = state.get("rounds", 0)
    if rounds >= MAX_TOOL_ROUNDS:
        return {"pending": []}
    if not _use_llm():
        return {"pending": _offline_plan(state) if rounds == 0 else []}

    from google.genai import types

    record_paid_call("gemini")
    resp = await asyncio.to_thread(
        gemini.generate_content,
        model=get_settings().gemini_stylist_model,
        contents=_transcript(state),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM
            + "\nCall tools until you have enough context, then reply with the single word DONE.",
            tools=[types.Tool(function_declarations=tools.DECLARATIONS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,
        ),
    )
    calls = [{"tool": c.name, "args": dict(c.args or {})} for c in (resp.function_calls or [])]
    return {"pending": calls[:4]}


async def run_tools(state: StylistState, config: RunnableConfig) -> dict:
    db = config["configurable"]["db"]
    user_id = config["configurable"]["user_id"]
    steps = []
    for call in state.get("pending", []):
        name, args = call["tool"], call["args"]
        try:
            if name == "search_catalog":
                result = await tools.search_catalog(db, args.get("query", state["message"]), args.get("category"))
            elif name == "get_local_weather":
                result = await tools.get_local_weather(args.get("city", ""))
            elif name == "get_user_style_history":
                result = await tools.get_user_style_history(db, user_id, state.get("memory", {}))
            elif name == "search_style_notes":
                result = tools.search_style_notes(args.get("query", state["message"]))
            else:
                result = {"error": f"Unknown tool {name}"}
        except Exception as exc:  # noqa: BLE001 - a failing tool shouldn't sink the whole reply
            log.warning("Stylist tool %s failed: %s", name, type(exc).__name__)
            result = {"error": "Tool unavailable"}
        steps.append({"tool": name, "args": args, "result": result})
    return {"steps": steps, "pending": [], "rounds": state.get("rounds", 0) + 1}


async def synthesize(state: StylistState) -> dict:
    found = _catalog_hits(state)
    if not _use_llm():
        return _offline_reply(state, found)

    from google.genai import types

    record_paid_call("gemini")
    resp = await asyncio.to_thread(
        gemini.generate_content,
        model=get_settings().gemini_stylist_model,
        contents=_transcript(state)
        + "\n\nWrite the reply now. recommended_garment_ids must only contain ids from search_catalog results.",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_schema=Synthesis,
            temperature=0.6,
        ),
    )
    out = resp.parsed if isinstance(resp.parsed, Synthesis) else Synthesis(reply=resp.text or "")
    valid = {g["id"] for g in found}
    ids = [i for i in out.recommended_garment_ids if i in valid][:4] or [g["id"] for g in found[:4]]
    return {"reply": out.reply, "garment_ids": ids, "memory_updates": out.memory_updates.model_dump()}


def route_after_reason(state: StylistState) -> str:
    return "tools" if state.get("pending") else "synthesize"


# --- offline stand-ins -----------------------------------------------------------------------------


def _offline_plan(state: StylistState) -> list[dict]:
    msg = state["message"]
    plan = [
        {"tool": "search_style_notes", "args": {"query": msg}},
        {"tool": "search_catalog", "args": {"query": msg}},
        {"tool": "get_user_style_history", "args": {}},
    ]
    if city := tools.detect_city(msg):
        plan.insert(0, {"tool": "get_local_weather", "args": {"city": city}})
    return plan


def _offline_reply(state: StylistState, found: list[dict]) -> dict:
    parts = []
    for step in state.get("steps", []):
        if step["tool"] == "get_local_weather" and "temperature_c" in step["result"]:
            w = step["result"]
            parts.append(
                f"It's {w['temperature_c']:.0f}°C with {w['conditions']} in {w['place']}, so plan layers accordingly."
            )
        if step["tool"] == "search_style_notes" and step["result"]["notes"]:
            note = step["result"]["notes"][0]
            parts.append(f"{note['title']}: {note['text']}")
    if found:
        names = ", ".join(g["title"] for g in found[:3])
        parts.append(f"From the catalog, start with {names}. Tap any piece to try it on.")
    else:
        parts.append("Tell me the occasion and the vibe, and I'll pull pieces for you to try on.")
    return {"reply": " ".join(parts), "garment_ids": [g["id"] for g in found[:4]], "memory_updates": {}}


def _catalog_hits(state: StylistState) -> list[dict]:
    seen, hits = set(), []
    for step in state.get("steps", []):
        if step["tool"] == "search_catalog":
            for g in step["result"].get("garments", []):
                if g["id"] not in seen:
                    seen.add(g["id"])
                    hits.append(g)
    return hits


def build_graph():
    graph = StateGraph(StylistState)
    graph.add_node("reason", reason)
    graph.add_node("tools", run_tools)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "reason")
    graph.add_conditional_edges("reason", route_after_reason, {"tools": "tools", "synthesize": "synthesize"})
    graph.add_edge("tools", "reason")
    graph.add_edge("synthesize", END)
    return graph.compile()


_GRAPH = build_graph()


async def run_stylist(db, user_id: uuid.UUID, message: str, history: list[dict], memory: dict) -> StylistState:
    return await _GRAPH.ainvoke(
        {"message": message, "history": history, "memory": memory, "steps": [], "rounds": 0},
        config={"configurable": {"db": db, "user_id": user_id}, "recursion_limit": 12},
    )
