"""Minimal Replicate HTTP client (predictions API), used by the VTON pipeline."""

import asyncio
import base64

import httpx

from app.core.config import get_settings

API = "https://api.replicate.com/v1"
POLL_SECONDS = 1.5
TIMEOUT_SECONDS = 180


class ReplicateError(RuntimeError):
    pass


def data_uri(image: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


async def run(model: str, inputs: dict) -> object:
    """Run `owner/name` or `owner/name:version` and return the prediction output."""
    token = get_settings().replicate_api_token
    if not token:
        raise ReplicateError("REPLICATE_API_TOKEN is not set")
    headers = {"Authorization": f"Bearer {token}", "Prefer": "wait=60"}

    async with httpx.AsyncClient(timeout=90) as http:
        if ":" in model:
            version = model.split(":", 1)[1]
            resp = await http.post(
                f"{API}/predictions", headers=headers, json={"version": version, "input": inputs}
            )
        else:
            # Official models accept runs by name; community models need their latest version id.
            resp = await http.post(
                f"{API}/models/{model}/predictions", headers=headers, json={"input": inputs}
            )
            if resp.status_code == 404:
                meta = await http.get(f"{API}/models/{model}", headers=headers)
                _check(meta, model)
                version = (meta.json().get("latest_version") or {}).get("id")
                if not version:
                    raise ReplicateError(f"{model} has no published version")
                resp = await http.post(
                    f"{API}/predictions",
                    headers=headers,
                    json={"version": version, "input": inputs},
                )
        _check(resp, model)
        prediction = resp.json()

        waited = 0.0
        while prediction["status"] not in ("succeeded", "failed", "canceled"):
            if waited > TIMEOUT_SECONDS:
                raise ReplicateError(f"{model} timed out")
            await asyncio.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            poll = await http.get(prediction["urls"]["get"], headers=headers)
            _check(poll, model)
            prediction = poll.json()

        if prediction["status"] != "succeeded":
            raise ReplicateError(f"{model} failed: {prediction.get('error')}")
        return prediction["output"]


async def download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return resp.content


def first_url(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output and isinstance(output[0], str):
        return output[0]
    raise ReplicateError(f"Unexpected model output: {output!r}")


def _check(resp: httpx.Response, model: str) -> None:
    if resp.status_code >= 400:
        raise ReplicateError(f"{model}: HTTP {resp.status_code} {resp.text[:300]}")
