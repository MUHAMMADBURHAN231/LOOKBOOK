# Landing page 3D scene: cloth-simulated dressing

> **The page now uses the robot version in [`robot/`](robot/README.md):** the NEXBOT mannequin
> dressed by garments sewn from flat 2D patterns. This directory's top-level scripts are the
> earlier version, which dressed a scanned model of the woman from the landing video. They are
> kept for reference.

The home page's story is a real-time 3D scene (`frontend/src/components/three/DressingScene.tsx`):
a 3D model of the woman from the landing video, and three garments that dress her as you scroll.
Each garment is split into its sewing panels. The panels fly in from the right, fan out around
her, close onto her and drape. The blouse and blazer later open and fly off to the left. The
motion is a Blender cloth simulation, baked and scrubbed by scroll in the browser.

These scripts build it. They run offline; the page only loads the result from
`frontend/public/look/3d/`.

## Requirements

- Python 3.11 with `bpy==4.2.0` (Blender as a module), `trimesh`, `scipy`, `numpy`, `pillow`,
  `pymeshlab`, `shapely`, `networkx`, `rtree`.
  On Linux, pymeshlab also needs `libopengl0`.
- Node with `@gltf-transform/cli` and `sharp` (to compress the body model).

## Inputs

Generated on Higgsfield with Meshy 7 image-to-3D (ultra, PBR, A-pose), from the look images in
`assets/look-source/`. Put them in `gen/`:

| file                    | source image   | Higgsfield job                         |
| ----------------------- | -------------- | -------------------------------------- |
| `gen/body-meshy.glb`    | `0-base.jpg`   | `7545850e-08c0-45a8-9cf5-b26ffaccd2db` |
| `gen/look-blouse.glb`   | `1-blouse.jpg` | `5ded39e5-6a77-495a-b612-35737f9ea7c0` |
| `gen/look-blazer.glb`   | `2-blazer.jpg` | `46b6f447-bc21-402a-9ce4-ab1c2bd209b3` |
| `gen/look-coat.glb`     | `3-coat.jpg`   | `9279e8c4-bd79-4c4e-ac56-6bc7779b1c70` |

## Steps

```sh
python common.py                 # body landmarks (shoulders, arm axes, neck) -> work/landmarks.json
python extract.py blouse         # cut each garment out of its look, fit it to the body -> work/<g>-cloth.npz
python extract.py blazer
python extract.py coat
python collision.py              # simplified body for collisions -> work/body-collision.npz
python panels.py blouse          # sewing panels, pin weights, choreography -> work/<g>-panels.npz, <g>.pc2
python sim.py blouse             # Blender cloth simulation -> work/<g>-sim.npy
python export_web.py ../../frontend/public/look/3d   # pack garments + manifest for the page
python body_web.py               # body with smooth normals -> work/body-n.glb
npx gltf-transform optimize work/body-n.glb ../../frontend/public/look/3d/body.glb \
  --compress meshopt --texture-compress webp --texture-size 2048 --simplify true --simplify-error 0.00012
```

(`panels.py` and `sim.py` run once per garment.)

`preview.py` and `render_sim.py` render any stage with Cycles for checking.

## How the pieces fit

- **extract.py** welds the look's texture seams and aligns it to the body using its head and
  lower legs. It rotates each sleeve so the look's arm matches the body's arm, then selects the
  garment by colour. The colour mask is smoothed over the surface, and the result is remeshed
  into even 12–15 mm triangles. Holes are filled, but the garment's real openings are kept: cuffs
  (trimmed at any gap before the cuff band), neckline and hem. Finally it smooths the edges and
  surface, fixes the face orientation, and keeps the cloth 10 mm outside the body.
- **panels.py** splits the garment into panels: two fronts, the back, and front and back halves
  of each sleeve. It straightens their seam edges and weights pins so panel centres follow the
  choreography while edges trail. It writes each panel's rigid path per frame, and a PC2 cache of
  those paths for Blender. Timeline at 30 fps: 0–60 fly in, 60–95 close, 95–130 settle,
  130–190 open and fly off (not the coat).
- **sim.py**: pinned vertices follow the cache (a Mesh Cache modifier before the Cloth modifier).
  The body is a collision object. Pin stiffness is low in flight and high while settling.
- **export_web.py** removes single-vertex spikes and straightens seam edges while panels are apart.
  It zips seams by the timeline: closing 70–95, closed while worn, opening 130–145. It fades the
  simulation's own motion out while the garment is on her, so the dressed look is exactly the
  fitted shape; on the body the simulation would only add collision snags. It stores each panel's
  rigid transform every frame, plus the cloth's own motion every other frame as int8, scaled per
  panel (under 0.5 mm error). Each garment is gzipped (about 1.3–1.7 MB); the page decompresses it.

## Notes

- The generated meshes mix face windings. The page renders garments double-sided and smooths
  their normals with orientation alignment. Garments cast shadows but don't receive them: inward
  facing patches would otherwise print the body's shadow as blotches.
- The page's Content Security Policy allows `'wasm-unsafe-eval'` (the meshopt decoder is
  WebAssembly) and `blob:` in `connect-src` (textures unpacked from the GLB).
- Without WebGL the page falls back to the scroll video in `frontend/public/look/frames/`.
