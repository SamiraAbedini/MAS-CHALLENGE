import os
from typing import List, Dict, Optional

from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class LLMClient:
    """Thin wrapper around OpenAI chat completions with demo fallback."""

    def __init__(self, force_demo: bool = False) -> None:
        load_dotenv()
        self.api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None
        if not force_demo and self.api_key and OpenAI is not None:
            self._client = OpenAI(api_key=self.api_key)

    @property
    def is_demo(self) -> bool:
        return self._client is None

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 600) -> str:
        if self._client is None:
            # Demo mode shouldn't be called from here; agents provide handcrafted outputs
            raise RuntimeError("Demo mode does not support direct LLM calls")
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""