"""AI Stylist: chat grounded in the fashion knowledge base (RAG), returning try-on-able looks."""

from google.genai import types
from pydantic import BaseModel, Field

from ..config import get_settings
from ..schemas import ChatMessage, ChatResponse, OutfitSuggestion
from . import gemini, knowledge

MAX_SUGGESTIONS = 4

SYSTEM = """You are LOOKBOOK's personal AI stylist. Be warm, concise and specific.
Ground your advice in the STYLE NOTES provided; you may add general fashion knowledge
but never contradict them. When the user asks what to wear, give up to 4 outfit
suggestions. Each suggestion's `description` must be a single plain-English outfit
description that an image model can render on the user's photo, e.g.
"a charcoal slim-fit suit with a white shirt, burgundy tie and brown oxford shoes".
Do not describe or judge the user's body, face or skin. If the question is not about
clothing or style, answer briefly and steer back to fashion. Keep `reply` under 120 words."""


class _StylistOutput(BaseModel):
    reply: str
    suggestions: list[OutfitSuggestion] = Field(default_factory=list)


def chat(messages: list[ChatMessage]) -> ChatResponse:
    settings = get_settings()
    recent_user = " ".join(m.content for m in messages[-3:] if m.role == "user")
    docs = knowledge.search(recent_user, k=3)
    sources = [d.title for d in docs]

    if settings.use_mock:
        return _mock_reply(docs, sources)

    notes = "\n\n".join(f"[{d.title}]\n{d.text}" for d in docs) or "(no matching notes)"
    contents = [
        types.Content(
            role="user" if m.role == "user" else "model",
            parts=[types.Part.from_text(text=m.content)],
        )
        for m in messages
    ]
    resp = gemini.generate_content(
        model=settings.gemini_stylist_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=f"{SYSTEM}\n\nSTYLE NOTES:\n{notes}",
            response_mime_type="application/json",
            response_schema=_StylistOutput,
            temperature=0.7,
        ),
    )
    out = resp.parsed
    if not isinstance(out, _StylistOutput):
        raise gemini.GeminiError("Stylist returned no structured output")
    return ChatResponse(
        reply=out.reply,
        suggestions=out.suggestions[:MAX_SUGGESTIONS],
        sources=sources,
        mock=False,
    )


_MOCK_LOOKS = {
    "wedding-guest-western": [
        ("Classic navy", "a tailored navy suit with a white shirt, silk burgundy tie and brown oxford shoes"),
        ("Evening velvet", "a midnight-blue velvet dinner jacket with black trousers and a black bow tie"),
        ("Garden party", "a light grey linen suit with a pale blue shirt and tan loafers"),
        ("Midi elegance", "an emerald green satin midi dress with gold earrings and nude heels"),
    ],
    "wedding-guest-desi": [
        ("Barat royal", "a cream sherwani with gold embroidery, a maroon shawl and gold khussa"),
        ("Mehndi bright", "a mustard yellow embroidered kurta with white churidar and peshawari chappal"),
        ("Walima classic", "a black prince coat over a white kurta with slim white trousers"),
        ("Pastel festive", "a mint green embroidered lehenga with silver jewellery"),
    ],
    "streetwear": [
        ("Classic street", "an oversized black hoodie, olive cargo pants and Jordan 4 sneakers"),
        ("Layered", "a washed grey boxy tee under an unbuttoned flannel overshirt with baggy jeans and chunky sneakers"),
        ("Puffer season", "a black puffer jacket over a white hoodie with black joggers and white sneakers"),
    ],
    "job-interview": [
        ("Corporate", "a slim-fit charcoal suit with a light-blue shirt, navy tie and black oxford shoes"),
        ("Tech smart", "a navy blazer over a white crewneck knit with dark chinos and brown loafers"),
    ],
}
_DEFAULT_LOOKS = [
    ("Smart casual", "a black turtleneck with a tailored navy blazer, dark chinos and loafers"),
    ("Clean casual", "a white oxford shirt with straight-leg jeans and white leather sneakers"),
    ("Street edge", "an oversized hoodie, cargo pants and Jordan 4 sneakers"),
]


def _mock_reply(docs: list[knowledge.Doc], sources: list[str]) -> ChatResponse:
    if docs:
        top = docs[0]
        reply = f"Here's what I'd suggest ({top.title.lower()}): {top.text}"
        looks = _MOCK_LOOKS.get(top.id, _DEFAULT_LOOKS)
    else:
        reply = (
            "Tell me the occasion, the weather and the vibe you're going for, "
            "and I'll put together a few looks for you to try on."
        )
        looks = _DEFAULT_LOOKS
    return ChatResponse(
        reply=reply + "\n\n(Mock mode: add a GEMINI_API_KEY for real stylist answers.)",
        suggestions=[OutfitSuggestion(title=t, description=d) for t, d in looks[:MAX_SUGGESTIONS]],
        sources=sources,
        mock=True,
    )
