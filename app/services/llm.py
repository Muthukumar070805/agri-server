import httpx

from app.core.config import get_settings
from app.core.logger import setup_logger

logger = setup_logger("llm")

HF_API_URL = "https://api-inference.huggingface.co/models/{model}"


class LLMService:
    def __init__(self, model: str = "mistralai/Mistral-7B-Instruct-v0.3"):
        self.model = model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {settings.HUGGINGFACE_ACCESS_TOKEN}"
                },
                timeout=60.0,
            )
        return self._client

    async def generate(self, prompt: str, max_new_tokens: int = 256) -> str:
        client = await self._get_client()
        try:
            resp = await client.post(
                HF_API_URL.format(model=self.model),
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": max_new_tokens,
                        "return_full_text": False,
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "").strip()
            return str(result).strip()
        except Exception as e:
            logger.error("llm_error", extra={"error": str(e)})
            return "I'm sorry, I couldn't process that. Could you please repeat?"

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
