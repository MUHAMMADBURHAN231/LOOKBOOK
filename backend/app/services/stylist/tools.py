"""Tools the stylist agent can call."""

import logging
import re
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Look
from app.services import catalog, knowledge

log = logging.getLogger(__name__)

_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "violent rain showers", 95: "thunderstorm", 96: "thunderstorm with hail",
}

# JSON-schema declarations handed to the LLM for function calling.
DECLARATIONS = [
    {
        "name": "search_catalog",
        "description": "Semantic search over the garment catalog. Use for any request for clothing ideas.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, e.g. 'warm wool overcoat for a gallery opening'"},
                "category": {"type": "string", "enum": ["upper_body", "lower_body", "dresses", "outerwear"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_local_weather",
        "description": "Current weather for a city. Use when the user mentions a place, the weather, or being outdoors.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_user_style_history",
        "description": "The user's saved looks and remembered preferences (liked colors, disliked cuts).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_style_notes",
        "description": "Curated styling guidance (dress codes, occasions, seasonal trends, fit rules).",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


async def search_catalog(db: AsyncSession, query: str, category: str | None = None) -> dict:
    cards = await catalog.search(db, query, category=category, limit=4)
    return {"garments": [c.model_dump(mode="json", exclude={"image_url"}) for c in cards]}


async def get_local_weather(city: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=6) as http:
            geo = await http.get(
                "https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}
            )
            places = geo.json().get("results") or []
            if not places:
                return {"error": f"Couldn't find a place called {city}."}
            p = places[0]
            wx = await http.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                },
            )
            cur = wx.json()["current"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.info("Weather lookup failed: %s", type(exc).__name__)
        return {"error": "Weather is unavailable right now."}
    return {
        "place": f"{p['name']}, {p.get('country', '')}".strip(", "),
        "temperature_c": cur["temperature_2m"],
        "feels_like_c": cur["apparent_temperature"],
        "conditions": _WMO.get(cur["weather_code"], "mixed conditions"),
        "precipitation_mm": cur["precipitation"],
        "wind_kmh": cur["wind_speed_10m"],
    }


async def get_user_style_history(db: AsyncSession, user_id: uuid.UUID, memory: dict) -> dict:
    looks = await db.scalars(
        select(Look).where(Look.user_id == user_id).order_by(Look.created_at.desc()).limit(8)
    )
    return {
        "saved_looks": [{"title": lk.title, "collection": lk.collection} for lk in looks],
        "preferences": memory,
    }


def search_style_notes(query: str) -> dict:
    return {"notes": [{"title": d.title, "text": d.text} for d in knowledge.search(query, k=3)]}


_CITY = re.compile(r"\b(?:in|at|to|around|visiting)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)")


def detect_city(message: str) -> str | None:
    """Heuristic used by the offline planner (the LLM planner decides for itself)."""
    m = _CITY.search(message)
    if m and m.group(1).lower() not in {"the", "a", "my", "summer", "winter", "autumn", "spring"}:
        return m.group(1)
    return None

