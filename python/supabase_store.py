from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


class SupabaseStore:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}))
        response = requests.request(method, f"{self.url}{path}", headers=headers, timeout=90, **kwargs)
        response.raise_for_status()
        return response

    def list_puzzles(self) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/rest/v1/xiangqi_puzzles",
            params={"select": "*", "is_active": "eq.true", "order": "created_at.desc", "limit": 100},
        )
        return response.json()

    def create_job(self, job: dict[str, Any], puzzle_id: str | None = None) -> None:
        payload = {
            "id": job["id"],
            "puzzle_id": puzzle_id,
            "status": "processing",
            "title": job["title"],
            "language": job["language"],
            "input_payload": job,
        }
        self._request("POST", "/rest/v1/video_jobs", json=payload, headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def update_job(self, job_id: str, status: str, **fields: Any) -> None:
        payload = {"status": status, **fields}
        self._request("PATCH", "/rest/v1/video_jobs", params={"id": f"eq.{job_id}"}, json=payload, headers={"Prefer": "return=minimal"})

    def upload(self, bucket: str, object_path: str, file_path: str | Path, content_type: str) -> str:
        path = Path(file_path)
        data = path.read_bytes()
        response = self._request(
            "POST",
            f"/storage/v1/object/{bucket}/{object_path}",
            data=data,
            headers={
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )
        response.close()
        return f"{self.url}/storage/v1/object/public/{bucket}/{object_path}"


def optional_store() -> SupabaseStore | None:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return None
    return SupabaseStore()
