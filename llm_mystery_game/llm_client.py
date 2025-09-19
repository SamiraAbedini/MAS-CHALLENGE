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
    Deterministic by default (temperature=0, top_p=1).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        *,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 500,
        seed: Optional[int] = None,
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.seed = seed

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

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> str:
        t = self.temperature if temperature is None else temperature
        p = self.top_p if top_p is None else top_p
        m = self.max_tokens if max_tokens is None else max_tokens
        s = self.seed if seed is None else seed

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        if self._sdk == "new":
            # OpenAI Python SDK v1+
            resp = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=t,
                top_p=p,
                max_tokens=m,
                seed=s,  # determinism (supported by gpt-4o, gpt-4o-mini)
                n=1,
            )
            return (resp.choices[0].message.content or "").strip()

        # Legacy SDK
        kwargs = {}
        if s is not None:
            kwargs["seed"] = s  # will be ignored if not supported
        resp = self._client.ChatCompletion.create(  # type: ignore[attr-defined]
            model=self.model_name,
            messages=messages,
            temperature=t,
            top_p=p,
            max_tokens=m,
            n=1,
            **kwargs,
        )
        return (resp["choices"][0]["message"]["content"] or "").strip()
