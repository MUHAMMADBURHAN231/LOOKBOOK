# LOOKBOOK film: assets and generation records

The landing page is one continuous fashion film: **scroll position is the film timeline**. These are its
source assets. Web-optimised versions live in `frontend/public/film/`.

## Brand lock

| Token | Value |
| --- | --- |
| Background | `#F3F0E9` (ivory) |
| Secondary background | `#E9E5DC` |
| Text | `#171714` |
| Secondary text | `#77736B` |
| Border | `rgba(23,23,20,0.14)` |
| Display / editorial | Cormorant Garamond |
| UI / product info | Manrope |

The garments carry the colour; the interface stays ivory, black and grey.

## Model lock

One woman, never regenerated from scratch: every later frame is an **edit of `stills/woman-a.png`**.

- Mid-20s, slim natural proportions, dark brown straight hair tucked behind the ears, minimal makeup,
  neutral expression, relaxed full-length standing pose facing camera, barefoot.
- Base layer: cream fitted long-sleeve bodysuit and cream leggings.
- Frame: 16:9, figure right of centre (about 58% across), left 40% empty for type.
- Light: large softbox camera-left, soft fill camera-right, faint floor shadow. 85 mm look, chest-height
  camera.

## Motion lock

Slow, controlled, quiet. Locked-off camera inside each shot. Rotations under 10°. No bounce, no spin,
no zoom punches. Text eases in after a garment has settled (`power3.out`, about 0.7 s).

## Shots

| Shot | Scroll beats | Source | Web frames |
| --- | --- | --- | --- |
| 01 The shirt | she stands alone, the shirt drifts in from the right, wraps on, settles | `video/shirt-1080p.mp4` | `frontend/public/film/shirt/` |

Rebuild a shot's web frames with `python scripts/build_film.py assets/film/video/shirt-1080p.mp4 --name shirt`
(180 frames re-timed for even motion, at 960 and 1600 px wide, plus proxies and posters: about 3.5 MB).

The page's scroll timing lives in `frontend/src/components/marketing/FashionFilm.tsx` (`FILM_START`,
`FILM_END`, and the intro and label ramps). Its copy is in the same file (`Intro`, `Label`).

## Generation records

Higgsfield, October 2026. Job IDs can be passed back to Higgsfield as references.

| File | Model | Settings | Job ID | Credits |
| --- | --- | --- | --- | --- |
| `stills/woman-a.png` (chosen) | GPT Image 2.5 | 16:9, high, 2k | `6b71f3f1-5e56-47e0-8c11-0479e7d6db2a` | 2.75 |
| woman-b (not kept) | GPT Image 2.5 | 16:9, high, 2k | `d4c579f6-0357-4fbf-95ff-cb9672439288` | 2.75 |
| woman-c (not kept) | GPT Image 2.5 | 16:9, high, 2k | `9c0b36da-a39d-4244-b9ad-462844fcf8b7` | 2.75 |
| shirt-a (not kept) | GPT Image 2.5, edit of woman-a | 16:9, high, 2k | `cba8206b-a259-4d8a-b6bd-1e478e28b6cf` | 2.75 |
| `stills/shirt-b.png` (chosen) | GPT Image 2.5, edit of woman-a | 16:9, high, 2k | `08e42d11-0955-4aa2-8c01-df53ac3f7d59` | 2.75 |
| shirt draft (not kept) | Seedance 2.5, omni reference, start woman-a, end shirt-b | 8 s, 480p draft, no audio | `613d45ab-c81a-43de-a2a7-0a2d06058994` | 24 |
| `video/shirt-1080p.mp4` (approved) | Seedance 2.5, finalized from the draft | 8 s, 1080p, 24 fps, no audio | `ca06f80d-4f5d-41bb-a38c-f9a33cd76635` | 96 |

Total for the shirt shot: about 134 credits.

### Prompts

**Woman (woman-a).** Luxury fashion e-commerce campaign photograph. One female fashion model, mid-20s,
slim natural proportions, dark brown straight hair tucked behind her ears, minimal makeup, neutral calm
expression, standing in a relaxed full-length pose facing the camera, arms resting naturally at her sides,
weight slightly on one leg. She wears only a plain cream fitted long-sleeve bodysuit and matching cream
fitted leggings, barefoot. Full body visible head to toe with headroom and floor visible. She stands
slightly right of center (about 58% across the frame); the left 40% of the frame is calm empty space.
Seamless warm ivory studio backdrop, color #F3F0E9, continuous with the floor, no horizon line. Lighting:
large soft box from camera left, gentle fill from camera right, very soft faint floor shadow. 85mm lens
look, camera at chest height, no distortion. Quiet, restrained, editorial (Jil Sander, COS, The Row).
Photorealistic, natural skin texture, accurate hands. No text, no logos, no props, no jewelry.

**Shirt end frame (shirt-a, shirt-b).** Edit the reference photograph. Keep everything identical: the
same woman, same face, same hair, same pose, same feet, same position in the frame, same camera, same
ivory backdrop, same lighting and floor shadow, same cream leggings. Only change: she is now wearing a
relaxed oversized button-up shirt in pale sky-blue washed cotton poplin, worn untucked over her cream
bodysuit, buttoned up to the second button, long sleeves falling just past the wrists, a soft point
collar, the hem reaching mid-thigh, natural soft folds and realistic fabric weight, accurate buttons and
seams. The shirt fits her body naturally. Photorealistic. No text, no logos.

**Shirt shot (video).** Locked-off static camera, no camera movement at all, same framing from first to
last frame. A woman stands still in a relaxed pose on a seamless warm ivory studio backdrop, breathing
calmly, looking at the camera. A pale sky-blue cotton poplin button-up shirt, empty and unworn, drifts
slowly into the frame from the right edge at chest height, floating gently through the air as if carried
by a soft breeze, its fabric rippling softly, rotating only slightly as it travels. It glides toward her,
slows down, turns to face the same way she faces, and in front of her torso it softly wraps onto her
body: the sleeves slide over her arms, the shirt settles onto her shoulders, the hem drops and the fabric
relaxes into natural folds. She barely moves. Then everything is completely still. Elegant, slow,
controlled, quiet luxury fashion film. Preserve her face, hair, body, pose, lighting and the backdrop
exactly throughout. No cuts, no camera shake, no zoom, no morphing of her face, no extra garments, no
text, no logos.

## Known limits

- One desktop shot, cropped for phones (the phone layout draws her lower with the text above). A
  dedicated 9:16 phone shot would frame the shirt's flight better on narrow screens.
- For a few frames at contact her cream sleeves show through the shirt's sleeves before it settles.
  It reads as the shirt sliding on at scroll speed.
