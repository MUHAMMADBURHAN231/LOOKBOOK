"""Thin wrapper around the Google Gen AI SDK."""

from functools import lru_cache

from google import genai
from google.genai import errors, types

from ..config import get_settings


class GeminiError(RuntimeError):
    pass


@lru_cache
def client() -> genai.Client:
    key = get_settings().gemini_api_key
    if not key:
        raise GeminiError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key)


def generate_content(**kwargs) -> types.GenerateContentResponse:
    """`models.generate_content`, with API errors turned into readable GeminiErrors."""
    try:
        return client().models.generate_content(**kwargs)
    except errors.APIError as exc:
        if exc.code in (401, 403):
            raise GeminiError(
                "Gemini rejected GEMINI_API_KEY. Use an AI Studio API key "
                "(starts with 'AIza') from https://aistudio.google.com/apikey"
            ) from exc
        if exc.code == 429:
            raise GeminiError("Gemini rate limit or quota reached, try again shortly") from exc
        raise GeminiError(f"Gemini API error {exc.code}: {exc.message}") from exc


def generate_json(model: str, prompt: str, schema, system: str = ""):
    """Generate a response constrained to a Pydantic schema and return the parsed object."""
    resp = generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.4,
        ),
    )
    if resp.parsed is None:
        raise GeminiError("Gemini returned no structured output")
    return resp.parsed


def edit_image(model: str, image: bytes, prompt: str) -> bytes:
    """Send a photo plus instructions to an image model and return the first image it outputs."""
    resp = generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=image, mime_type="image/jpeg"), prompt],
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for candidate in resp.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    text = resp.text or "no image returned (the request may have been blocked)"
    raise GeminiError(f"Image model did not return an image: {text}")
