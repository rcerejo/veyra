from __future__ import annotations

import json

import httpx

from app.schemas.query import QueryPlan


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return any(item.get("name", "").startswith(self.model) for item in response.json().get("models", []))
        except (httpx.HTTPError, ValueError):
            return False

    async def generate_sql(self, question: str, plan: QueryPlan, schema: str) -> str:
        prompt = f"""You are VEYRA's SQLite query compiler. Return JSON only as {{\"sql\": \"SELECT ...\"}}.
Use exactly one read-only SELECT statement. Never use PRAGMA, ATTACH, or write operations.
Schema:\n{schema}\nPlan:\n{plan.model_dump_json()}\nQuestion:\n{question}"""
        payload = {"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0}}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
        body = json.loads(response.json()["response"])
        sql = body.get("sql")
        if not isinstance(sql, str):
            raise ValueError("Ollama returned no SQL")
        return sql

