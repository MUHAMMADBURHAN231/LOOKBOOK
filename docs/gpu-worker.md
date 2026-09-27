# Self-hosted GPU worker contract

Set `GPU_WORKER_URL` (and `GPU_WORKER_TOKEN`) to route try-ons to your own model server, for example
CatVTON or IDM-VTON with DWPose and SCHP on Kaggle, RunPod or a local GPU. The Celery worker calls it
through `RemoteGpuAdapter` (`backend/app/services/pipeline/adapters.py`).

## Request

`POST {GPU_WORKER_URL}/v1/tryon` with `Authorization: Bearer {GPU_WORKER_TOKEN}` and a JSON body:

```json
{
  "person_image": "<base64 JPEG, EXIF-stripped, max 1536px>",
  "garment_image": "<base64 PNG/JPEG or null when only a description is given>",
  "garment_description": "a tailored navy wool blazer with gold buttons",
  "category": "upper_body | lower_body | dresses",
  "enhance_face": true,
  "steps": 30
}
```

## Response

`200 OK`:

```json
{
  "image": "<base64 PNG/JPEG/WebP result>",
  "pose_keypoints": { "format": "coco18", "points": [[x, y, confidence], "..."] },
  "timings": { "pose_ms": 120, "mask_ms": 340, "diffusion_ms": 2800, "face_ms": 410 }
}
```

`pose_keypoints` and `timings` are optional. When present, keypoints are stored on the photo.

## Errors

- `4xx`: permanent (bad input). The job fails with a user-facing message.
- `429` or `5xx`, or a timeout: transient. The job retries up to twice with backoff.

The request times out after 240 seconds. Keep the worker behind HTTPS and require the bearer token.
