"""Object storage behind one interface.

- `S3Storage`: AWS S3, Cloudflare R2 or MinIO. Browsers upload directly with a presigned POST whose
  policy pins the content type, a size range and server-side AES-256 encryption.
- `LocalStorage`: files on disk, encrypted with AES-256-GCM, served through HMAC-signed expiring
  URLs on the API. Lets the whole app run without Docker/S3 in development.

Key layout (retention rules key off these prefixes):
  raw/{user_id}/...      user portraits              (RAW_UPLOAD_RETENTION_DAYS)
  results/{user_id}/...  generated try-on images     (RESULT_RETENTION_DAYS)
  garments/...           catalog images              (kept)
"""

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.security import constant_time_equal, sign

log = logging.getLogger(__name__)


@dataclass
class UploadTicket:
    url: str
    method: str  # "POST" (multipart form with `fields`) or "PUT" (raw body with `headers`)
    fields: dict[str, str]
    headers: dict[str, str]
    expires_in: int


class StorageError(RuntimeError):
    pass


class Storage:
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def size(self, key: str) -> int | None: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def presign_upload(self, key: str, content_type: str, max_bytes: int, expires: int = 600) -> UploadTicket: ...
    def presign_download(self, key: str, expires: int = 900) -> str: ...
    def ping(self) -> None: ...
    def purge_older_than(self, prefix: str, days: int) -> int: ...


class S3Storage(Storage):
    def __init__(self):
        s = get_settings()
        common = dict(
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id or None,
            aws_secret_access_key=s.s3_secret_access_key or None,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )
        self.bucket = s.s3_bucket
        self.sse = s.s3_server_side_encryption
        self.client = boto3.client("s3", endpoint_url=s.s3_endpoint_url, **common)
        # Presigned URLs must point at an endpoint the browser can reach.
        self.presigner = boto3.client(
            "s3", endpoint_url=s.s3_public_endpoint_url or s.s3_endpoint_url, **common
        )

    def _sse(self) -> dict:
        return {"ServerSideEncryption": self.sse} if self.sse else {}

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, **self._sse())

    def get(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            raise StorageError(f"Object not found: {key}") from exc

    def size(self, key):
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        except ClientError:
            return None

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix):
        removed = 0
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys, "Quiet": True})
                removed += len(keys)
        return removed

    def presign_upload(self, key, content_type, max_bytes, expires=600):
        fields = {"Content-Type": content_type}
        conditions: list = [["content-length-range", 1, max_bytes], {"Content-Type": content_type}]
        if self.sse:
            fields["x-amz-server-side-encryption"] = self.sse
            conditions.append({"x-amz-server-side-encryption": self.sse})
        post = self.presigner.generate_presigned_post(
            self.bucket, key, Fields=fields, Conditions=conditions, ExpiresIn=expires
        )
        return UploadTicket(url=post["url"], method="POST", fields=post["fields"], headers={}, expires_in=expires)

    def presign_download(self, key, expires=900):
        return self.presigner.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )

    def ping(self):
        self.client.head_bucket(Bucket=self.bucket)

    def purge_older_than(self, prefix, days):
        # In S3/R2/MinIO the bucket lifecycle rules (scripts/init_storage.py) do this server-side.
        return 0

    def ensure_bucket_and_lifecycle(self) -> None:
        s = get_settings()
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            kwargs = {}
            if s.s3_region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": s.s3_region}
            self.client.create_bucket(Bucket=self.bucket, **kwargs)
        if not s.s3_endpoint_url:  # AWS only; MinIO/R2 don't implement this call
            self.client.put_public_access_block(
                Bucket=self.bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
        rules = [
            ("expire-raw-uploads", "raw/", s.raw_upload_retention_days),
            ("expire-results", "results/", s.result_retention_days),
            ("expire-temp-masks", "tmp/", 1),
        ]
        self.client.put_bucket_lifecycle_configuration(
            Bucket=self.bucket,
            LifecycleConfiguration={
                "Rules": [
                    {"ID": rid, "Filter": {"Prefix": prefix}, "Status": "Enabled", "Expiration": {"Days": days}}
                    for rid, prefix, days in rules
                ]
            },
        )
        self.client.put_bucket_cors(
            Bucket=self.bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": get_settings().allowed_origins,
                        "AllowedMethods": ["POST", "GET"],
                        "AllowedHeaders": ["*"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )


class LocalStorage(Storage):
    """Development storage: AES-256-GCM encrypted files + signed URLs served by the API."""

    def __init__(self):
        s = get_settings()
        self.root = Path(s.local_storage_dir) / "objects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret = s.secret_key
        self.aes = AESGCM(hashlib.sha256(("storage-encryption:" + s.secret_key).encode()).digest())
        self.api_url = s.api_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve()) + os.sep):
            raise StorageError("Invalid storage key")
        return path

    def put(self, key, data, content_type):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        nonce = os.urandom(12)
        meta = json.dumps({"ct": content_type}).encode()
        blob = nonce + self.aes.encrypt(nonce, data, meta)
        path.write_bytes(len(meta).to_bytes(2, "big") + meta + blob)

    def _read(self, key) -> tuple[bytes, str]:
        path = self._path(key)
        if not path.is_file():
            raise StorageError(f"Object not found: {key}")
        raw = path.read_bytes()
        mlen = int.from_bytes(raw[:2], "big")
        meta, blob = raw[2 : 2 + mlen], raw[2 + mlen :]
        data = self.aes.decrypt(blob[:12], blob[12:], meta)
        return data, json.loads(meta)["ct"]

    def get(self, key):
        return self._read(key)[0]

    def get_with_type(self, key) -> tuple[bytes, str]:
        return self._read(key)

    def size(self, key):
        try:
            return len(self.get(key))
        except StorageError:
            return None

    def delete(self, key):
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def delete_prefix(self, prefix):
        base = self.root / prefix.strip("/")
        removed = 0
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file():
                    p.unlink()
                    removed += 1
        return removed

    def _token(self, payload: dict) -> str:
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        return f"{body}.{sign(body, self.secret)}"

    def verify_token(self, token: str, op: str) -> dict:
        try:
            body, mac = token.rsplit(".", 1)
            if not constant_time_equal(mac, sign(body, self.secret)):
                raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise StorageError("Invalid link") from exc
        if payload.get("op") != op or payload.get("exp", 0) < time.time():
            raise StorageError("Link expired")
        return payload

    def presign_upload(self, key, content_type, max_bytes, expires=600):
        token = self._token({"op": "put", "k": key, "ct": content_type, "max": max_bytes, "exp": int(time.time()) + expires})
        return UploadTicket(
            url=f"{self.api_url}/api/v1/media/local/{token}",
            method="PUT",
            fields={},
            headers={"Content-Type": content_type},
            expires_in=expires,
        )

    def presign_download(self, key, expires=900):
        token = self._token({"op": "get", "k": key, "exp": int(time.time()) + expires})
        return f"{self.api_url}/api/v1/media/local/{token}"

    def ping(self):
        if not self.root.is_dir():
            raise StorageError("Storage directory missing")

    def purge_older_than(self, prefix, days):
        cutoff = time.time() - days * 86400
        base = self.root / prefix
        removed = 0
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
        return removed


@lru_cache
def get_storage() -> Storage:
    return S3Storage() if get_settings().storage_backend == "s3" else LocalStorage()
