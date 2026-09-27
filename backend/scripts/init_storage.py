"""Create the bucket (if needed) and apply retention lifecycle rules, public-access block and CORS.

    python -m scripts.init_storage
"""

from app.core.config import get_settings
from app.services.storage import S3Storage

if __name__ == "__main__":
    if get_settings().storage_backend != "s3":
        print("STORAGE_BACKEND is not s3; nothing to do.")
    else:
        S3Storage().ensure_bucket_and_lifecycle()
        print("Bucket ready with lifecycle rules.")
