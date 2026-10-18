from typing import Any

import httpx

from app.core.settings import Settings
from app.modules.ai.errors import PermanentAIError, TransientAIError


class QdrantVectorStore:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.collection_name = f"{settings.qdrant_collection_prefix}_content_v1"

    @property
    def headers(self) -> dict[str, str]:
        if self.settings.qdrant_api_key is None:
            return {}
        value = self.settings.qdrant_api_key.get_secret_value()
        return {"api-key": value} if value else {}

    async def ensure_collection(self, dimensions: int) -> None:
        response = await self._request("GET", f"/collections/{self.collection_name}")
        if response.status_code == 404:
            created = await self._request(
                "PUT",
                f"/collections/{self.collection_name}",
                json={"vectors": {"size": dimensions, "distance": "Cosine"}},
            )
            if created.status_code == 409:
                response = await self._request("GET", f"/collections/{self.collection_name}")
                if response.status_code == 404:
                    raise TransientAIError(
                        "Qdrant collection creation conflict is not yet visible"
                    )
                self._validate_dimensions(response, dimensions)
                return
            self._raise_for_status(created)
            return
        self._validate_dimensions(response, dimensions)

    @classmethod
    def _validate_dimensions(cls, response: httpx.Response, dimensions: int) -> None:
        cls._raise_for_status(response)
        try:
            configured = response.json()["result"]["config"]["params"]["vectors"]["size"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PermanentAIError("Qdrant returned an invalid collection configuration") from exc
        if configured != dimensions:
            raise PermanentAIError(
                f"Qdrant collection expects {configured} dimensions, received {dimensions}"
            )

    async def upsert(
        self,
        *,
        point_id: int,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        await self.ensure_collection(len(vector))
        response = await self._request(
            "PUT",
            f"/collections/{self.collection_name}/points",
            params={"wait": "true"},
            json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
        )
        self._raise_for_status(response)

    async def search(
        self, vector: list[float], *, limit: int
    ) -> list[tuple[int, float]] | None:
        response = await self._request(
            "POST",
            f"/collections/{self.collection_name}/points/query",
            json={"query": vector, "limit": limit, "with_payload": False},
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        try:
            points = response.json()["result"]["points"]
            return [(int(point["id"]), float(point["score"])) for point in points]
        except (KeyError, TypeError, ValueError) as exc:
            raise PermanentAIError("Qdrant returned an invalid search response") from exc

    async def delete(self, point_id: int) -> None:
        await self.delete_many([point_id])

    async def delete_many(self, point_ids: list[int]) -> None:
        if not point_ids:
            return
        response = await self._request(
            "POST",
            f"/collections/{self.collection_name}/points/delete",
            params={"wait": "true"},
            json={"points": point_ids},
        )
        if response.status_code != 404:
            self._raise_for_status(response)

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self.client.request(
                method,
                f"{self.settings.qdrant_url.rstrip('/')}{path}",
                headers=self.headers,
                timeout=self.settings.ai_http_timeout_seconds,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise TransientAIError("Qdrant request failed") from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientAIError(f"Qdrant returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise PermanentAIError(f"Qdrant returned HTTP {response.status_code}")
