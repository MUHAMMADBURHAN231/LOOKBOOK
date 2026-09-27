"""S3 backend against moto's in-memory S3 (same API as AWS S3 / R2 / MinIO)."""

import os

import boto3
import pytest
from moto import mock_aws

from app.core.config import get_settings


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        for k, v in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"}.items():
            monkeypatch.setenv(k, v)
        settings = get_settings()
        monkeypatch.setattr(settings, "s3_bucket", "lookbook-test")
        monkeypatch.setattr(settings, "s3_endpoint_url", None)
        from app.services.storage import S3Storage

        storage = S3Storage()
        storage.ensure_bucket_and_lifecycle()
        yield storage


def test_bucket_is_private_encrypted_and_has_retention_rules(s3):
    client = boto3.client("s3", region_name="us-east-1")
    rules = {r["ID"]: r for r in client.get_bucket_lifecycle_configuration(Bucket="lookbook-test")["Rules"]}
    assert rules["expire-raw-uploads"]["Expiration"]["Days"] == get_settings().raw_upload_retention_days
    assert rules["expire-temp-masks"]["Expiration"]["Days"] == 1
    block = client.get_public_access_block(Bucket="lookbook-test")["PublicAccessBlockConfiguration"]
    assert all(block.values())

    s3.put("raw/u1/a.jpg", b"\xff\xd8\xffdata", "image/jpeg")
    head = client.head_object(Bucket="lookbook-test", Key="raw/u1/a.jpg")
    assert head["ServerSideEncryption"] == "AES256"
    assert s3.get("raw/u1/a.jpg") == b"\xff\xd8\xffdata"
    assert s3.delete_prefix("raw/u1/") == 1 and s3.size("raw/u1/a.jpg") is None


def test_presigned_post_pins_type_size_and_encryption(s3):
    ticket = s3.presign_upload("raw/u1/b.jpg", "image/jpeg", 1024)
    assert ticket.method == "POST"
    assert ticket.fields["Content-Type"] == "image/jpeg"
    assert ticket.fields["x-amz-server-side-encryption"] == "AES256"
    assert "policy" in {k.lower() for k in ticket.fields}
    assert "X-Amz-Signature" in s3.presign_download("raw/u1/b.jpg") or "Signature" in s3.presign_download("raw/u1/b.jpg")
    assert os.environ["AWS_ACCESS_KEY_ID"] == "test"
