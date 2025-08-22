from __future__ import annotations

import os
from typing import Optional
from dotenv import load_dotenv

# Load variables from .env if present
load_dotenv()


class LLMClient:
    """
    API-only client for OpenAI chat models.
    Requires OPENAI_API_KEY in environment or .env file.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Please add it to your .env file or export it."
            )

        # Try to import OpenAI SDK (new or legacy)
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=self.api_key)
            self._sdk = "new"
        except Exception:
            try:
                import openai  # type: ignore
                openai.api_key = self.api_key
                self._client = openai
                self._sdk = "legacy"
            except Exception as e:
                raise RuntimeError(
                    "Failed to import OpenAI SDK. Install with `pip install openai`."
                ) from e

    def chat(self, system: str, user: str) -> str:
        if self._sdk == "new":
            # OpenAI Python SDK v1+
            resp = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.6,
                max_tokens=500,
            )
            return (resp.choices[0].message.content or "").strip()

        # Legacy SDK
        resp = self._client.ChatCompletion.create(  # type: ignore[attr-defined]
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            max_tokens=500,
        )
        return (resp["choices"][0]["message"]["content"] or "").strip()
