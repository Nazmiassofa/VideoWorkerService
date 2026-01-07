# services/r2_service.py

import boto3
import uuid

from typing import Optional
from config.settings import config

class R2UploaderService:
    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: Optional[str] = config.R2_BUCKET,
        public_base_url: Optional[str] = config.R2_BASE_URL,
    ):
        self.bucket = bucket
        self.public_base = public_base_url.rstrip("/") if public_base_url else None

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
        
        
    def upload_video(
        self,
        file_path: str,
        folder: str = "jobs/videos"
    ) -> str:
        filename = f"{uuid.uuid4().hex}.mp4"
        key = f"{folder}/{filename}"

        with open(file_path, "rb") as f:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=f,
                ContentType="video/mp4",
                ACL="public-read",
            )

        return f"{self.public_base}/{key}"
