"""Hello-world smoke test for the configured AI provider (Groq by default).

Run from the backend/ directory:
    python -m scripts.test_ai_hello
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import AsyncOpenAI

from config import get_settings


async def main() -> int:
    settings = get_settings()
    ai_client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url=settings.AI_BASE_URL,
    )
    print(f"Provider base_url : {settings.AI_BASE_URL}")
    print(f"Model             : {settings.AI_MODEL}")
    print(f"Key prefix        : {settings.GROQ_API_KEY[:5]}... ({len(settings.GROQ_API_KEY)} chars)")
    print()
    print("Sending hello prompt...")

    completion = await ai_client.chat.completions.create(
        model=settings.AI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a terse assistant."},
            {"role": "user", "content": "Reply with exactly: Hello from <model_name>."},
        ],
    )
    reply = (completion.choices[0].message.content or "").strip()
    usage = completion.usage

    print(f"Reply             : {reply}")
    if usage is not None:
        print(f"Tokens (in/out)   : {usage.prompt_tokens}/{usage.completion_tokens}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
