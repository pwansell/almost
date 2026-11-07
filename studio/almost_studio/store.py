"""Where the Studio keeps things: a local folder for development, R2 in production.

Layout (same in both):
  artwork/<key>.png        generated Artwork, kept forever
  library/<keyword>.png    Art Library; library/default.png is the Default Artwork
  idle/idle.png            Idle Artwork (supplied by hand)
  plates/<YYYY-MM-DD>.png  the next days' Plates
  plates/charge-me.png     the Charge Me Plate
  plates/manifest.json     what the Frame should hold
  state/battery.json       last battery level reported by the Frame (written by the Worker)
  state/generations.json   Artwork generations per month, for the cap
"""

from __future__ import annotations

import os
from pathlib import Path


class LocalStore:
    def __init__(self, root: Path):
        self.root = root

    def get(self, key: str) -> bytes | None:
        p = self.root / key
        return p.read_bytes() if p.exists() else None

    def put(self, key: str, data: bytes, content_type: str = "") -> None:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def list(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file())

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class R2Store:
    """Cloudflare R2 through its S3-compatible API."""

    def __init__(self):
        import boto3

        self.bucket = os.environ["R2_BUCKET"]
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def get(self, key: str) -> bytes | None:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None

    def put(self, key: str, data: bytes, content_type: str = "") -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)

    def list(self, prefix: str) -> list[str]:
        keys, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kw["ContinuationToken"] = token
            r = self.s3.list_objects_v2(**kw)
            keys += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return sorted(keys)
            token = r["NextContinuationToken"]

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)
