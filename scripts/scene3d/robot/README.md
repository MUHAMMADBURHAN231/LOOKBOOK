# Robot dressing scene: sewn garments on NEXBOT

The landing page's 3D story (`frontend/src/components/three/DressingScene.tsx`) dresses the NEXBOT
robot mannequin. Each garment is cut as flat 2D sewing patterns that fly in from the right, sew
themselves together on the robot and drape, like a Marvelous Designer / CLO simulation. The
blouse and blazer then un-sew and fly off to the left, and the coat stays on. The motion is a
Blender cloth simulation, baked and scrubbed by scroll in the browser.

These scripts run offline. The page only loads their output from `frontend/public/look/3d/`.

## Requirements

- Python 3.11 with the packages in `../requirements.txt` (`bpy==4.2.0` is Blender as a module).
  On Linux, pymeshlab also needs `libopengl0`.
- Node with `@gltf-transform/cli` (to compress the robot model).

## Input

`assets/robot/nexbot.gltf`, the robot model exported from Spline.

## Steps

Run from this directory:

```sh
python robot_prep.py ../../../assets/robot/nexbot.gltf  # parts + landmarks -> work/
python envelope.py                   # smooth closed skin (collision body) -> work/envelope.npz, body-collision.npz
python patterns.py blouse            # 2D patterns, arranged around the robot -> work/blouse-pattern.npz
python sew_sim.py blouse             # sew + drape (Blender cloth) -> work/blouse-sew.npy
# ...and the same two lines for blazer and coat
python export_sew.py ../../../frontend/public/look/3d   # choreography, pack for the page
python body_web.py                   # robot as two meshes (shell, joint) -> work/robot-web.glb
npx gltf-transform optimize work/robot-web.glb ../../../frontend/public/look/3d/body.glb \
  --compress meshopt --simplify false --join false
```

`final.py <garment>` saves the last simulated frame. `view_parts.py` renders it with the robot
in Cycles, for checking: `python view_parts.py r/check --extra work/blouse-final.npz`.

## How it works

- **robot_prep.py** drops the logo, lights and cameras, and swings the arms out 14° at the
  shoulder into an A-pose. It scales the robot to 1.68 m and sorts parts into white shell and
  dark joints. It measures landmarks from the parts: shoulders, elbows, wrists, neck, hips.
- **envelope.py** voxelises the robot and closes the gaps between parts. It grows the skin by a
  voxel and blurs it before extracting the surface, so the cloth drapes over a smooth skin instead
  of a voxel staircase. The skin stays at least 1.5 mm outside every shell.
- **patterns.py** drafts each garment from the robot's measurements:
  - **Pieces.** Bodice front (or two fronts for the jackets) and back, each with a waist-shaped
    side seam, plus two sleeves.
  - **Sleeves.** Sized from the arm girth, which is 0.53 m below the shoulder and 0.46 m at the
    forearm. The cap is low because the upper arm is raised about 49°. The armhole depth is
    solved so each armhole matches the cap's edge less 1.5% ease.
  - **Meshing.** The pieces are meshed flat with a constrained Delaunay triangulation (package
    `triangle`), about 12 mm triangles, one clean disk per piece.
  - **Arrangement.** Bodices wrap on an ellipse around the torso. Sleeves wrap on a tube that
    follows the bent arm, flared at the top to clear the shoulder, and start 5 cm down the arm.
  - **Clearing the robot.** A push, smoothed in pattern space, moves anything within 1.5 cm of
    the robot back out.
  - **Sewing lines.** Each vertex on either edge is paired with the nearest point on the other
    edge: side seams, shoulders, sleeve underarms, sleeve caps to armholes. The jacket fronts are
    tacked together at the button heights.
  - **Output.** The flat pattern is saved too, as the cloth's rest shape.
- **sew_sim.py** runs Blender cloth with sewing springs. The rest shape is the flat pattern, so
  the arrangement's distortion doesn't become the garment's shape. The sewing force is capped in
  proportion to the fabric's weight, so pieces close over a second or so instead of snapping,
  which would crumple them. Once the seams have met, the cap rises six-fold so they hold like
  stitches under the garment's weight.
  Gravity eases in once the seams are closing. Friction against the robot is low, so fabric
  slides over the shoulder brackets into place. Self-collision is off: it can trap a seam edge on
  the wrong side of the piece it's sewn to, which leaves the back of the armhole open.
- **export_sew.py** choreographs the page timeline at 30 fps:
  - **0–60:** pieces fly in on curved paths, spinning and fluttering.
  - **60–130:** the simulation, time-warped so the sewing gets half of it.
  - **130–155:** un-sew, the simulation reversed (blouse and blazer only).
  - **155–190:** fly off to the left (blouse and blazer only).

  Seams zip closed as they meet. For each piece the exporter stores a best-fit rigid motion
  every frame, plus the cloth's own deformation every other frame as int8 (under 1 mm error).
  Each file is gzipped.
