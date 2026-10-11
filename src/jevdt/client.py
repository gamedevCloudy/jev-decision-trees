"""OpenRouter access for the two kinds of call this project makes.

Chat models write plans, code, and the text of a decision node. Decision
models score a fixed question against a state and return probabilities.
Those are different routes. The same OPENROUTER_API_KEY covers both.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
CHAT_BASE_URL = "https://openrouter.ai/api/v1"
DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"

# notes/02-setup.md: grok-4.7 at high reasoning for planning and experiments.
PLANNER_MODEL = "x-ai/grok-4.7"
PLANNER_REASONING_EFFORT = "high"

# notes/02-setup.md: kimi-k3 for coding.
CODER_MODEL = "moonshotai/kimi-k3"

# A small open model will write the text of each decision node.
# Left unset until the first prompt-generation experiment picks one.
NODE_PROMPT_MODEL: str | None = None

# OpenRouter's documented Decisions model. Swap this per experiment.
DECISION_MODEL = "typesafe/jev-1.13"


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from the repo .env. Existing variables win."""
    env_path = path or ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_key() -> str:
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing from the environment and .env")
    return key


def chat_client() -> OpenAI:
    return OpenAI(base_url=CHAT_BASE_URL, api_key=api_key())


def complete(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str | None = None,
) -> str:
    """One user turn on the chat completions route. Returns the message text."""
    kwargs: dict = {}
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    response = chat_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(f"{model} returned no message content")
    return content


def decide(
    state: str | dict | list,
    questions: dict,
    *,
    model: str = DECISION_MODEL,
    timeout: float = 60.0,
) -> dict:
    """POST one Decisions request. Questions in a single call are independent."""
    response = httpx.post(
        DECISIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json={"model": model, "state": state, "questions": questions},
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"decisions API {response.status_code}: {response.text}")
    return response.json()
