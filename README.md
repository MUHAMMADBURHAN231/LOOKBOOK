# LOOKBOOK — AI Fashion Designer & Virtual Try-On

> Upload your photo. Describe **any** outfit in plain English. See a photorealistic image of **you** wearing it.

```
"Wearing a sleek black turtleneck with a tailored navy blazer, aviator sunglasses,
 standing in front of a Ferrari"            →  a photo of you in exactly that
```

## Features (MVP)

| Feature | Status |
|---|---|
| **Natural-language outfit design**: describe an outfit, get it on your photo | ✅ |
| **Outfit Interpreter**: turns plain text into a structured garment spec (items, colours, fit, accessories, scene) | ✅ |
| **Two generation engines**: Gemini image editing (fast, supports scenes) or IDM-VTON try-on pipeline | ✅ |
| **AI Stylist chat** grounded in a fashion knowledge base (RAG); visualise up to 4 suggestions on your photo | ✅ |
| **Wardrobe**: save looks, organise into collections, remix, share | ✅ |
| **Privacy**: explicit consent, EXIF/GPS stripping, 30-day auto-deletion, "delete all my data" | ✅ |
| **Mock mode**: the full app runs with no API keys, for offline development and demos | ✅ |
| Trend-aware recommendations (seasonal notes in the KB) | 🟡 basic |
| Body analysis (pose estimation + segmentation) | 🔜 roadmap |
| Encryption at rest (AES-256), user accounts | 🔜 roadmap |

## Architecture

```
            ┌──────────────────────────────┐
            │  Next.js frontend (:3000)    │  Studio · AI Stylist · Wardrobe
            └──────────────┬───────────────┘
                           │ REST (multipart / JSON)
            ┌──────────────▼───────────────┐
            │  FastAPI backend (:8000)     │
            │                              │
 photo ───► │  imaging    normalize, strip EXIF, letterbox 768×1024
 text  ───► │  interpreter  Gemini 2.5 Flash → OutfitSpec (JSON schema)
            │                              │
            │  generator ─┬─ edit:  Gemini 2.5 Flash Image (photo + prompt)
            │             └─ vton:  FLUX garment image → IDM-VTON per garment
            │                       → CodeFormer face restore   (Replicate)
            │                              │
            │  stylist    BM25 retrieval over fashion_kb.json → Gemini 2.5 Pro
            │  storage    SQLite + local media, retention purge on startup
            └──────────────────────────────┘
```

**Why two pipelines?** Classic virtual try-on models (IDM-VTON, CatVTON) need a *garment image*
and keep the original background, so they can't put you "on the moon". The `edit` pipeline uses an
instruction-following image model that handles garments **and** scenes in one call. The `vton`
pipeline shows the research-style stack: text → garment image → masked try-on → face restoration.

## Project layout

```
backend/
  app/main.py                  API routes
  app/schemas.py               Pydantic models (OutfitSpec, Look, ...)
  app/storage.py               SQLite + media files, retention, wipe
  app/services/interpreter.py  NL → OutfitSpec (Gemini, offline fallback parser)
  app/services/generator.py    edit / vton pipelines
  app/services/stylist.py      RAG stylist chat
  app/services/knowledge.py    BM25 search over app/data/fashion_kb.json
  app/services/imaging.py      preprocessing + mock renderer
  tests/                       pytest suite (runs in mock mode)
frontend/
  src/app/page.tsx             Studio (upload → describe → generate → save)
  src/app/stylist/page.tsx     AI Stylist chat
  src/app/wardrobe/page.tsx    Saved looks & collections
  src/lib/api.ts               Typed API client
```

## Getting started

Requirements: Python 3.11+, Node 20+.

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add keys (optional, see below)
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000.

### API keys

| Key | Needed for | Get it |
|---|---|---|
| `GEMINI_API_KEY` | Interpreter, `edit` pipeline, stylist | https://aistudio.google.com/apikey |
| `REPLICATE_API_TOKEN` | `vton` pipeline (optional) | https://replicate.com/account/api-tokens |

With no `GEMINI_API_KEY` the app runs in **mock mode**: a keyword parser interprets outfits, the
"generated" image is your photo with a caption, and the stylist uses canned answers from the
knowledge base. Every screen still works, which is handy for development and as a backup for the demo.

Model names are configurable in `backend/.env` (see `.env.example`).

## Tests

```bash
cd backend && python -m pytest -q
cd frontend && npm run lint && npm run build
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Mode, default pipeline, retention |
| POST | `/api/interpret` | `{description}` → `OutfitSpec` |
| POST | `/api/generate` | multipart: `description`, `consent=true`, `photo` **or** `source_file`, optional `pipeline` |
| POST | `/api/stylist/chat` | `{messages: [{role, content}]}` → reply + up to 4 outfit suggestions |
| GET / POST | `/api/looks` | List (optional `?collection=`) / save a generation to the wardrobe |
| DELETE | `/api/looks/{id}` | Remove a saved look |
| DELETE | `/api/data` | Delete all photos, generations and looks |

## Demo script

1. Upload your photo, tick consent.
2. Click the Ferrari example chip → **Generate**. Toggle *Show original* for the before/after.
3. Ask classmates for prompts: *"traditional Pakistani sherwani with gold embroidery"*,
   *"full astronaut suit on the moon"*, *"streetwear: oversized hoodie, cargo pants, Jordan 4s"*.
4. AI Stylist → *"What should I wear to a wedding?"* → **Visualize all 4 on me**.
5. Save favourites to a collection in the Wardrobe.

## Roadmap

- Body analysis with MediaPipe Pose + human parsing to validate photos and auto-pick garment masks
- Embedding-based retrieval (Gemini embeddings + FAISS) and a scraped seasonal-trends corpus
- AES-256 encryption at rest, user accounts, shareable public look pages
- Queue-based GPU inference (Celery/Redis) and CDN image delivery for scale
