from __future__ import annotations

import mimetypes
import time
from typing import Any

import httpx


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    """Thin async client around ComfyUI's existing HTTP/WebSocket API."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._object_info: dict[str, Any] | None = None
        self._object_info_at = 0.0

    async def _get(self, path: str, **kwargs: Any) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url + path, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ComfyError(f"GET {path} failed: {exc}") from exc

    async def system_stats(self) -> dict[str, Any]:
        return await self._get("/system_stats")

    async def queue(self) -> dict[str, Any]:
        return await self._get("/queue")

    async def history(self, prompt_id: str) -> dict[str, Any]:
        return await self._get(f"/history/{prompt_id}")

    async def object_info(self, node: str | None = None) -> dict[str, Any]:
        if node:
            return await self._get(f"/object_info/{node}")
        if self._object_info is not None and time.time() - self._object_info_at < 30:
            return self._object_info
        data = await self._get("/object_info")
        self._object_info = data
        self._object_info_at = time.time()
        return data

    async def submit(self, prompt: dict[str, Any], client_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url + "/prompt",
                    json={"prompt": prompt, "client_id": client_id},
                )
                if response.status_code >= 400:
                    raise ComfyError(f"ComfyUI rejected the workflow ({response.status_code}): {response.text}")
                return response.json()
        except httpx.HTTPError as exc:
            raise ComfyError(f"POST /prompt failed: {exc}") from exc

    async def interrupt(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(self.base_url + "/interrupt")
        except httpx.HTTPError as exc:
            raise ComfyError(f"POST /interrupt failed: {exc}") from exc

    async def view(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url + "/view", params=params)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            raise ComfyError(f"GET /view failed: {exc}") from exc

    async def upload_image(self, content: bytes, filename: str, overwrite: bool = True) -> dict[str, Any]:
        """Upload an image into ComfyUI's input directory for LoadImage nodes."""
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        files = {"image": (filename, content, mime)}
        data = {"overwrite": "true" if overwrite else "false", "type": "input"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.base_url + "/upload/image", files=files, data=data)
                if response.status_code >= 400:
                    raise ComfyError(
                        f"ComfyUI rejected the image upload ({response.status_code}): {response.text}"
                    )
                return response.json()
        except httpx.HTTPError as exc:
            raise ComfyError(f"POST /upload/image failed: {exc}") from exc

    def ws_url(self, client_id: str) -> str:
        base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/ws?clientId={client_id}"
