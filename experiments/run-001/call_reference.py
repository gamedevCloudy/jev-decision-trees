"""One DeepSeek call per item. Record the ledger line before the next call."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from jevdt.client import CHAT_BASE_URL, api_key

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "experiments" / "run-001"
ITEMS_PATH = RUN / "items.json"
LEDGER_PATH = RUN / "ledger.jsonl"
REFERENCE_PATH = RUN / "reference.json"

MODEL = "~deepseek/deepseek-v4-flash-latest"
ROUTE = "chat"
AGENT = "reference"
CALL_CAP = 12
COST_CAP = 0.40
PARENT_CAP = 1.50
CHOICES = ("reply", "ask", "escalate", "wait")
MISSING_COST = 0.01

NEXT = (
    "Instruction: Choose the next agent action.\n"
    "reply: the agent can answer from the transcript.\n"
    "ask: the agent must request one missing fact.\n"
    "escalate: a person must take the case.\n"
    "wait: no action is due on this turn.\n"
    "Return one JSON object only."
)


def render(transcript: list[dict]) -> str:
    return "\n".join(f"{turn['role']}: {turn['text']}" for turn in transcript)


def ledger_sum() -> float:
    if not LEDGER_PATH.is_file():
        return 0.0
    total = 0.0
    for line in LEDGER_PATH.read_text().splitlines():
        if not line.strip():
            continue
        total += float(json.loads(line)["cost"])
    return total


def append_ledger(item_id: str, cost: float) -> None:
    row = {
        "agent": AGENT,
        "item": item_id,
        "route": ROUTE,
        "model": MODEL,
        "cost": cost,
    }
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        handle.flush()


def parse_choice(raw: str) -> str | None:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    choice = payload.get("choice")
    if isinstance(choice, str) and choice in CHOICES:
        return choice
    return None


def post_once(client: httpx.Client, prompt: str) -> httpx.Response:
    return client.post(
        f"{CHAT_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "usage": {"include": True},
        },
    )


def call_item(client: httpx.Client, prompt: str) -> tuple[httpx.Response | None, str | None]:
    """One request, plus one retry only after HTTP 429 or 5xx."""
    try:
        response = post_once(client, prompt)
    except httpx.HTTPError as exc:
        return None, f"transport: {exc}"
    if response.status_code == 429 or response.status_code >= 500:
        time.sleep(2)
        try:
            response = post_once(client, prompt)
        except httpx.HTTPError as exc:
            return None, f"retry transport: {exc}"
    return response, None


def cost_of(body: dict) -> tuple[float, bool]:
    usage = body.get("usage") if isinstance(body, dict) else None
    if isinstance(usage, dict) and isinstance(usage.get("cost"), (int, float)):
        return float(usage["cost"]), False
    return MISSING_COST, True


def tokens_of(body: dict) -> tuple[int | None, int | None]:
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    return (
        int(prompt) if isinstance(prompt, int) else None,
        int(completion) if isinstance(completion, int) else None,
    )


def content_of(body: dict) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError):
        return ""
    return content or ""


def check_items(items: list[dict]) -> None:
    ids = [item["id"] for item in items]
    expected = [f"c{n:02d}" for n in range(1, 13)]
    if ids != expected:
        raise SystemExit(f"item ids are {ids}, expected {expected}")
    for item in items:
        turns = item["transcript"]
        if not 3 <= len(turns) <= 5:
            raise SystemExit(f"{item['id']} has {len(turns)} turns")
        rendered = render(turns)
        if len(rendered) >= 1200:
            raise SystemExit(f"{item['id']} transcript is {len(rendered)} characters")


def main() -> None:
    items = json.loads(ITEMS_PATH.read_text())["items"]
    check_items(items)
    records: list[dict] = []
    stopped = None
    calls = 0
    with httpx.Client(timeout=60.0) as client:
        for item in items:
            spent = ledger_sum()
            if spent >= PARENT_CAP:
                stopped = f"parent cap ${PARENT_CAP:.2f} at ledger ${spent:.6f}"
                break
            if spent >= COST_CAP:
                stopped = f"reference cap ${COST_CAP:.2f} at ledger ${spent:.6f}"
                break
            if calls >= CALL_CAP:
                stopped = f"reference call cap {CALL_CAP}"
                break
            prompt = f"Transcript:\n{render(item['transcript'])}\n\n{NEXT}"
            response, transport_error = call_item(client, prompt)
            calls += 1
            if transport_error or response is None:
                append_ledger(item["id"], 0.0)
                records.append(
                    {
                        "id": item["id"],
                        "choice": None,
                        "raw": "",
                        "input_tokens": None,
                        "output_tokens": None,
                        "cost": 0.0,
                        "cost_gap": False,
                        "error": transport_error,
                    }
                )
                continue
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {}
            if response.status_code >= 400:
                append_ledger(item["id"], 0.0)
                records.append(
                    {
                        "id": item["id"],
                        "choice": None,
                        "raw": response.text[:2000],
                        "input_tokens": None,
                        "output_tokens": None,
                        "cost": 0.0,
                        "cost_gap": False,
                        "error": f"HTTP {response.status_code}",
                    }
                )
                continue
            cost, gap = cost_of(body)
            input_tokens, output_tokens = tokens_of(body)
            raw = content_of(body)
            choice = parse_choice(raw)
            append_ledger(item["id"], cost)
            error = None if choice else "choice not parsed"
            records.append(
                {
                    "id": item["id"],
                    "choice": choice,
                    "raw": raw,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                    "cost_gap": gap,
                    "error": error,
                }
            )
            print(
                f"{item['id']} choice={choice} cost={cost:.8f} "
                f"in={input_tokens} out={output_tokens} gap={gap}",
                flush=True,
            )
            if ledger_sum() >= COST_CAP:
                stopped = f"reference cap ${COST_CAP:.2f} reached"
                break
    payload = {
        "model": MODEL,
        "items": records,
        "calls": calls,
        "stopped": stopped,
        "ledger_sum": ledger_sum(),
    }
    REFERENCE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {REFERENCE_PATH} stopped={stopped} ledger={payload['ledger_sum']:.8f}")


if __name__ == "__main__":
    main()
