"""One area: writers, scorers, and references. Grade runs in the parent tree.

The check uses no network. A paid run appends one ledger line per call.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

from jevdt.client import CHAT_BASE_URL, api_key, decide

AREAS = ("inbox", "money", "guard")

# The liquid id returned HTTP 404 on the first pass. This rerun does not call it.
SKIPPED_WRITERS = ("liquid/lfm-2.5-2.6b",)
WRITERS = (
    "qwen/qwen3.8-27b",
    "google/gemma-4-31b-it",
)
WRITER_SLUG = {
    "liquid/lfm-2.5-2.6b": "lfm",
    "qwen/qwen3.8-27b": "qwen",
    "google/gemma-4-31b-it": "gemma",
}
SCORERS = (
    "typesafe/jev-1.13",
    "cloudflare/clef-omni",
    "nace-ai/drex-v1.5",
    "microsoft/microsoft-decision-1",
)
REFERENCES = (
    "~deepseek/deepseek-v4-flash-latest",
    "xiaomi/mimo-v2.6-flash",
)
FORBIDDEN = ("x-ai/grok-4.7", "moonshotai/kimi-k3")

WRITER_CAP = 8
SCORER_CAP = 24
REFERENCE_CAP = 12
AREA_COST_CAP = 0.55
PARENT_CAP = 2.00
GRADE_CALL_CAP = 18
GRADE_COST_CAP = 0.20
GRADE_SKIP_AT = 1.80
MISSING_COST = 0.01
WRITER_MAX_TOKENS = 700
REFERENCE_MAX_TOKENS = 512

BANNED_STRINGS = ("explore", "exploit", "reply", "ask", "escalate", "wait")
BANNED_NAMES = ("inbox", "money", "guard")
STRING_BAN = re.compile("|".join(BANNED_STRINGS), re.I)
NAME_BAN = re.compile(r"\b(?:inbox|money|guard)\b", re.I)
KEY_RE = re.compile(r"^[a-z]+$")

GRADE_QUESTIONS = {
    "Disagree": {
        "type": "noul",
        "instructions": "The four scorers do not all choose the same option key.",
    },
    "ClefGap": {
        "type": "noul",
        "instructions": "The Cloudflare option key differs from the Jev option key.",
    },
}

SETTINGS = {
    "inbox": "The employee reads a support thread. The company sells a product.",
    "money": "The employee reads a refund, a cancellation, or a billing change.",
    "guard": (
        "The employee watches a sales chat. A sales assistant talks with the customer. "
        "The employee does not write the assistant message. The employee chooses a preventive action. "
        "The company goal is a sale. The product signal names are ready, hotter, quiet, and distress. "
        "Distress means the customer wants to stop, is afraid, or is angry. "
        "Distress is not a medical label. Do not name a disorder, a diagnosis, or a treatment."
    ),
}

FROZEN_SEEDS = {
    "inbox": [
        {
            "id": "s1",
            "text": (
                "The customer cannot find an order. The thread has the order number "
                "and the delivery day. The employee can answer from the thread."
            ),
        },
        {
            "id": "s2",
            "text": (
                "The customer wants a person. The thread does not have the account email. "
                "One fact is missing."
            ),
        },
    ],
    "money": [
        {
            "id": "s1",
            "text": (
                "The customer wants a refund. The thread has the order number and the reason. "
                "The company rule allows that refund."
            ),
        },
        {
            "id": "s2",
            "text": (
                "The customer wants to cancel. The account has two products. "
                "The thread does not name the product."
            ),
        },
    ],
    "guard": [
        {
            "id": "s1",
            "text": "The assistant offers a discount. The customer accepts the price and asks how to pay.",
        },
        {
            "id": "s2",
            "text": (
                "The assistant repeats the offer. The customer says they are done and "
                "tells the assistant to stop. The customer is angry. Do not name a mental condition."
            ),
        },
    ],
}


def find_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise SystemExit("repo root not found")


ROOT = find_root()
RUN = ROOT / "experiments" / "run-003"
LEDGER = RUN / "ledger.jsonl"
SEEDS_PATH = RUN / "seeds.json"
# Call caps for this process start after the first-pass lines.
LEDGER_OFFSET = 0


def load_seeds() -> dict:
    return json.loads(SEEDS_PATH.read_text())


def arm_window() -> None:
    """Count new writer, scorer, and reference calls after the bytes already on disk."""
    global LEDGER_OFFSET
    LEDGER_OFFSET = LEDGER.stat().st_size if LEDGER.is_file() else 0


def read_ledger(*, window: bool = False) -> list[dict]:
    if not LEDGER.is_file():
        return []
    data = LEDGER.read_bytes()
    if window:
        data = data[LEDGER_OFFSET:]
    text = data.decode()
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                continue
            raise
    return rows


def ledger_sum() -> float:
    return sum(float(row["cost"]) for row in read_ledger())


def area_sum(area: str) -> float:
    return sum(float(row["cost"]) for row in read_ledger() if row.get("area") == area)


def call_count(area: str, kind: str) -> int:
    total = 0
    window = kind != "grade"
    for row in read_ledger(window=window):
        if row.get("area") != area:
            continue
        model = row.get("model")
        if kind == "writer" and model in WRITERS:
            total += 1
        elif kind == "scorer" and row.get("route") == "decisions" and model in SCORERS:
            total += 1
        elif kind == "reference" and model in REFERENCES:
            total += 1
        elif kind == "grade" and row.get("agent") == "grade":
            total += 1
    return total


def blocked(area: str, kind: str) -> str | None:
    parent = ledger_sum()
    if parent >= PARENT_CAP:
        return f"parent cap {PARENT_CAP:.2f}"
    if kind == "grade":
        if call_count(area, "grade") >= GRADE_CALL_CAP:
            return f"grade call cap {GRADE_CALL_CAP}"
        if area_sum(area) >= GRADE_COST_CAP:
            return f"grade cost cap {GRADE_COST_CAP:.2f}"
        return None
    if area_sum(area) >= AREA_COST_CAP:
        return f"area cost cap {AREA_COST_CAP:.2f}"
    if kind == "writer" and call_count(area, "writer") >= WRITER_CAP:
        return f"writer cap {WRITER_CAP}"
    if kind == "scorer" and call_count(area, "scorer") >= SCORER_CAP:
        return f"scorer cap {SCORER_CAP}"
    if kind == "reference" and call_count(area, "reference") >= REFERENCE_CAP:
        return f"reference cap {REFERENCE_CAP}"
    return None


def ledger_row(agent: str, area: str, item: str, route: str, model: str, cost: float) -> dict:
    return {
        "agent": agent,
        "area": area,
        "item": item,
        "route": route,
        "model": model,
        "cost": cost,
    }


def append_ledger(agent: str, area: str, item: str, route: str, model: str, cost: float) -> None:
    row = ledger_row(agent, area, item, route, model, cost)
    line = (json.dumps(row, separators=(",", ":")) + "\n").encode()
    fd = os.open(LEDGER, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def usage_numbers(body: dict) -> tuple[float, bool, int, int]:
    """Cost, missing-cost flag, input tokens, output tokens.

    A 200 body with no usage.cost counts as MISSING_COST. Callers that saw
    an HTTP error pass a synthesized body and should not use this helper.
    """
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return MISSING_COST, True, 0, 0
    raw_cost = usage.get("cost")
    gap = not isinstance(raw_cost, (int, float))
    cost = float(MISSING_COST if gap else raw_cost)
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    return (
        cost,
        gap,
        int(input_tokens) if isinstance(input_tokens, (int, float)) else 0,
        int(output_tokens) if isinstance(output_tokens, (int, float)) else 0,
    )


def status_code(exc: BaseException) -> int | None:
    match = re.search(r"decisions API (\d+)", str(exc))
    if not match:
        return None
    return int(match.group(1))


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def content_of(body: dict) -> str:
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(message, dict):
        return ""
    text = message_text(message.get("content"))
    if text.strip():
        return text
    for key in ("reasoning", "reasoning_content"):
        extra = message_text(message.get(key))
        if extra.strip():
            return extra
    return ""


def parse_json_object(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
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
    if isinstance(payload, dict):
        return payload
    return None


def transcript_ban(turns: list) -> str | None:
    chunks = []
    for turn in turns:
        if isinstance(turn, dict) and isinstance(turn.get("text"), str):
            chunks.append(turn["text"])
    text = "\n".join(chunks)
    string_hit = STRING_BAN.search(text)
    if string_hit:
        return string_hit.group(0).lower()
    name_hit = NAME_BAN.search(text)
    if name_hit:
        return name_hit.group(0).lower()
    return None


def transcript_chars(turns: list[dict]) -> int:
    return len("\n".join(f"{turn['role']}: {turn['text']}" for turn in turns))


def clean_question(question: dict) -> dict:
    cleaned = {
        "type": question["type"],
        "instructions": question["instructions"],
    }
    if "criteria" in question:
        cleaned["criteria"] = question["criteria"]
    return cleaned


def scorer_questions(questions: dict) -> dict:
    return {name: clean_question(question) for name, question in questions.items()}


def normalize_role(value) -> str | None:
    if not isinstance(value, str):
        return None
    role = value.strip().lower()
    if role == "user":
        role = "customer"
    if role in {"customer", "assistant"}:
        return role
    return role


def parse_transcript_string(text: str) -> list[dict]:
    turns = []
    for line in text.splitlines():
        match = re.match(r"^(customer|assistant|user)\s*:\s*(.*)$", line.strip(), re.I)
        if not match:
            continue
        role = normalize_role(match.group(1))
        turns.append({"role": role, "text": match.group(2).strip()})
    return turns


def normalize_turns(turns) -> list | None:
    if isinstance(turns, str):
        return parse_transcript_string(turns)
    if not isinstance(turns, list):
        return None
    fixed = []
    for turn in turns:
        if not isinstance(turn, dict):
            fixed.append(turn)
            continue
        role = normalize_role(turn.get("role", turn.get("speaker")))
        fixed.append({"role": role, "text": turn.get("text")})
    return fixed


def lower_key(key):
    if isinstance(key, str) and key.isalpha():
        return key.lower()
    return key


def normalize_roles(roles: dict, criteria: dict | None) -> dict:
    mapped = {}
    for key, value in roles.items():
        new_key = lower_key(key)
        if isinstance(value, str) and value.lower() in {"explore", "exploit"}:
            mapped[new_key] = value.lower()
        else:
            mapped[new_key] = value
    if isinstance(criteria, dict):
        # Keep the role map on the same keys as the criteria after lowercasing.
        mapped = {lower_key(key): value for key, value in mapped.items()}
    return mapped


def usable_extra(question: dict) -> bool:
    """Keep a real extra question. Drop a list of bare options."""
    if question.get("type") not in {"noul", "choice"}:
        return False
    instructions = question.get("instructions", question.get("text"))
    if not isinstance(instructions, str) or not instructions.strip():
        return False
    if question["type"] == "choice" and not isinstance(question.get("criteria"), dict):
        return False
    return True


def normalize_writer(payload: dict) -> dict:
    """Repair the object shapes the first pass actually returned.

    Turns may use speaker. The transcript may be one string. questions may be
    a list. roles may sit beside questions. A broken extra question is dropped.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    turns = normalize_turns(out.get("transcript"))
    if turns is not None:
        out["transcript"] = turns
    questions = out.get("questions")
    leaf = None
    extras: list[tuple[str, dict]] = []
    if isinstance(questions, dict) and isinstance(questions.get("Leaf"), dict):
        leaf = dict(questions["Leaf"])
        extras = [(name, value) for name, value in questions.items() if name != "Leaf" and isinstance(value, dict)]
    elif isinstance(questions, list):
        for index, entry in enumerate(questions):
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("Leaf"), dict) and leaf is None:
                leaf = dict(entry["Leaf"])
                continue
            if entry.get("type") == "choice" and isinstance(entry.get("criteria"), dict) and leaf is None:
                leaf = dict(entry)
                continue
            extras.append((str(entry.get("id") or f"Extra{index}"), entry))
    if not isinstance(leaf, dict):
        return out
    criteria = leaf.get("criteria")
    if isinstance(criteria, dict):
        leaf["criteria"] = {lower_key(key): value for key, value in criteria.items()}
        criteria = leaf["criteria"]
    roles = leaf.get("roles")
    if not isinstance(roles, dict) and isinstance(out.get("roles"), dict):
        roles = out["roles"]
    if isinstance(roles, dict):
        leaf["roles"] = normalize_roles(roles, criteria if isinstance(criteria, dict) else None)
    instructions = leaf.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        leaf["instructions"] = "Choose the employee action."
    built: dict = {"Leaf": leaf}
    for name, extra in extras:
        if not isinstance(extra, dict):
            continue
        extra = dict(extra)
        if not isinstance(extra.get("instructions"), str) and isinstance(extra.get("text"), str):
            extra["instructions"] = extra["text"]
        if usable_extra(extra):
            built[name] = extra
    out["questions"] = built
    return out


def validate_writer(payload: dict) -> tuple[bool, str | None, str | None]:
    """Return ok, error, banned string. A ban is set only from transcript text."""
    if not isinstance(payload, dict):
        return False, "writer JSON is not an object", None
    payload = normalize_writer(payload)
    turns = payload.get("transcript")
    if not isinstance(turns, list):
        return False, "transcript is missing", None
    ban = transcript_ban(turns)
    if not 3 <= len(turns) <= 5:
        return False, f"transcript has {len(turns)} turns", ban
    stored = []
    for turn in turns:
        if not isinstance(turn, dict):
            return False, "a turn is not an object", ban
        role = turn.get("role")
        text = turn.get("text")
        if role not in {"customer", "assistant"}:
            return False, "a turn role is not customer or assistant", ban
        if not isinstance(text, str) or not text.strip():
            return False, "a turn has no text", ban
        stored.append({"role": role, "text": text})
    if transcript_chars(stored) >= 1200:
        return False, "transcript has 1200 characters or more", ban
    if ban:
        return False, f"transcript contains {ban}", ban
    questions = payload.get("questions")
    if not isinstance(questions, dict):
        return False, "questions are missing", None
    if "Leaf" not in questions:
        return False, "Leaf is missing", None
    extra = [name for name in questions if name != "Leaf"]
    if len(extra) > 1:
        return False, "more than one extra question", None
    leaf = questions["Leaf"]
    if not isinstance(leaf, dict):
        return False, "Leaf is not an object", None
    if leaf.get("type") != "choice":
        return False, "Leaf type is not choice", None
    if not isinstance(leaf.get("instructions"), str) or not leaf["instructions"].strip():
        return False, "Leaf instructions are missing", None
    criteria = leaf.get("criteria")
    if not isinstance(criteria, dict) or len(criteria) != 2:
        return False, "Leaf does not have exactly two criteria", None
    for key, value in criteria.items():
        if not isinstance(key, str) or KEY_RE.fullmatch(key) is None:
            return False, f"criterion key {key!r} is not one lowercase word", None
        if key in BANNED_STRINGS:
            return False, f"criterion key {key} is banned", None
        if not isinstance(value, str) or not value.strip():
            return False, f"criterion {key} has no text", None
    roles = leaf.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(criteria):
        return False, "roles do not match the criterion keys", None
    role_values = list(roles.values())
    if sorted(role_values) != ["exploit", "explore"]:
        return False, "roles are not one explore and one exploit", None
    if extra:
        other = questions[extra[0]]
        if not isinstance(other, dict):
            return False, "the extra question is not an object", None
        if other.get("type") not in {"noul", "choice"}:
            return False, "the extra question type is not noul or choice", None
        if not isinstance(other.get("instructions"), str) or not other["instructions"].strip():
            return False, "the extra question has no instructions", None
        if other["type"] == "choice":
            other_criteria = other.get("criteria")
            if not isinstance(other_criteria, dict) or not 1 <= len(other_criteria) <= 4:
                return False, "the extra choice does not have 1 to 4 options", None
            for key, value in other_criteria.items():
                if not isinstance(key, str) or not key.strip():
                    return False, "an extra option key is empty", None
                if not isinstance(value, str) or not value.strip():
                    return False, "an extra option has no text", None
    return True, None, None


def store_transcript(turns: list) -> list[dict]:
    return [{"role": turn["role"], "text": turn["text"]} for turn in turns]


def writer_prompt(area: str, item_id: str, model: str, seed: str, ban: str | None) -> str:
    fix = ""
    if ban:
        fix = (
            f"The previous transcript contained the banned string {ban}. "
            "Write a new transcript. Do not use that string.\n"
        )
    return (
        "Return one JSON object only. Do not add markdown.\n"
        f"{fix}"
        f"Setting: {SETTINGS[area]}\n"
        "Each turn is an object with the keys role and text.\n"
        "role is customer or assistant. Do not use any other key for the role.\n"
        "The transcript has 3 to 5 turns and fewer than 1200 characters.\n"
        "Do not put these strings in the transcript: "
        "explore, exploit, reply, ask, escalate, wait.\n"
        "Do not use a word that contains one of those strings.\n"
        "Do not use the names inbox, money, or guard.\n"
        "Do not name a company.\n"
        "Do not name a disorder, a diagnosis, or a treatment.\n"
        "Do not copy a seed sentence into the transcript.\n"
        "questions.Leaf has type choice, one instructions sentence, and exactly two criteria.\n"
        "Each criterion key is one lowercase word of letters only.\n"
        "A key is not explore, exploit, reply, ask, escalate, or wait.\n"
        "roles maps each criterion key to explore or exploit. Use each role one time.\n"
        "In the roles map only, explore means slow down, collect one fact, hold, or stop the offer.\n"
        "In the roles map only, exploit means use the path the thread already supports, "
        "send the answer, finish the refund or the cancellation, or continue the sale.\n"
        "You may add one more question. Its type is noul or choice. "
        "A choice has at most four options.\n"
        "Use your own criterion keys and your own sentences.\n"
        "questions is one object. It is not a list. The required key is Leaf.\n"
        "Copy this shape. Replace the sentences and the criterion keys.\n"
        '{"id":"'
        + item_id
        + '","seed":"...","writer":"'
        + model
        + '","transcript":['
        '{"role":"customer","text":"I cannot find the order."},'
        '{"role":"assistant","text":"The number is 100. The day is Tuesday."},'
        '{"role":"customer","text":"Thanks, that helps."}'
        '],"questions":{"Leaf":{"type":"choice","instructions":"Choose the employee action.",'
        '"criteria":{"hold":"collect one missing fact","send":"use the path the thread already supports"},'
        '"roles":{"hold":"explore","send":"exploit"}}}}\n'
        "Seed:\n"
        f"{seed}\n"
    )


def reference_prompt(transcript: list[dict], leaf: dict) -> str:
    lines = ["Transcript:"]
    for turn in transcript:
        lines.append(f"{turn['role']}: {turn['text']}")
    lines.append("")
    lines.append("Leaf:")
    lines.append(f"Instruction: {leaf['instructions']}")
    for key, text in leaf["criteria"].items():
        lines.append(f"{key}: {text}")
    keys = ", ".join(leaf["criteria"])
    lines.append("")
    lines.append(
        "Return one JSON object only. The choice value must be one of these option keys: "
        f"{keys}."
    )
    return "\n".join(lines)


def parse_choice(raw: str, option_keys: set[str]) -> str | None:
    payload = parse_json_object(raw)
    if not isinstance(payload, dict):
        return None
    choice = payload.get("choice")
    if isinstance(choice, str) and choice in option_keys:
        return choice
    action = payload.get("action")
    if isinstance(action, str) and action in option_keys:
        return action
    found = [key for key in payload if isinstance(key, str) and key in option_keys]
    if len(found) == 1:
        return found[0]
    return None


def post_chat(
    client: httpx.Client,
    model: str,
    prompt: str,
    max_tokens: int,
    *,
    writer: bool,
) -> httpx.Response:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    # Writer models spent the token cap on a hidden trace and returned no JSON.
    # This is not reasoning_effort. References stay on the plain chat call.
    if writer:
        body["reasoning"] = {"enabled": False}
    return client.post(
        f"{CHAT_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json=body,
    )


def chat_call(
    client: httpx.Client,
    area: str,
    item_id: str,
    model: str,
    prompt: str,
    max_tokens: int,
    kind: str,
) -> dict:
    reason = blocked(area, kind)
    if reason:
        return {"skipped": True, "error": reason, "cost": 0.0, "cost_gap": False, "raw": ""}

    def finish_error(response: httpx.Response | None, message: str) -> dict:
        append_ledger(area, area, item_id, "chat", model, 0.0)
        raw = ""
        if response is not None:
            raw = response.text[:4000]
        return {
            "skipped": False,
            "error": message,
            "cost": 0.0,
            "cost_gap": False,
            "raw": raw,
            "input_tokens": 0,
            "output_tokens": 0,
            "body": None,
        }

    response = None
    try:
        response = post_chat(client, model, prompt, max_tokens, writer=kind == "writer")
    except httpx.HTTPError as exc:
        return finish_error(None, f"transport: {exc}")
    if response.status_code == 429 or response.status_code >= 500:
        append_ledger(area, area, item_id, "chat", model, 0.0)
        reason = blocked(area, kind)
        if reason:
            return {
                "skipped": False,
                "error": f"HTTP {response.status_code}; {reason}",
                "cost": 0.0,
                "cost_gap": False,
                "raw": response.text[:4000],
                "input_tokens": 0,
                "output_tokens": 0,
                "body": None,
            }
        time.sleep(2)
        try:
            response = post_chat(client, model, prompt, max_tokens, writer=kind == "writer")
        except httpx.HTTPError as exc:
            return finish_error(None, f"retry transport: {exc}")
    if response.status_code >= 400:
        return finish_error(response, f"HTTP {response.status_code}")
    try:
        body = response.json()
    except json.JSONDecodeError:
        return finish_error(response, "response is not JSON")
    cost, gap, input_tokens, output_tokens = usage_numbers(body)
    append_ledger(area, area, item_id, "chat", model, cost)
    return {
        "skipped": False,
        "error": None,
        "cost": cost,
        "cost_gap": gap,
        "raw": content_of(body),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "body": body,
    }


def decision_call(area: str, item_id: str, model: str, state, questions: dict, kind: str) -> dict:
    agent = "grade" if kind == "grade" else area
    ledger_area = "grade" if kind == "grade" else area
    reason = blocked(ledger_area, kind)
    if reason:
        return {"skipped": True, "error": reason, "cost": 0.0, "cost_gap": False, "body": None}

    def fail(message: str) -> dict:
        append_ledger(agent, ledger_area, item_id, "decisions", model, 0.0)
        return {
            "skipped": False,
            "error": message,
            "cost": 0.0,
            "cost_gap": False,
            "body": None,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    body = None
    try:
        body = decide(state, questions, model=model, timeout=120.0)
    except RuntimeError as exc:
        code = status_code(exc)
        append_ledger(agent, ledger_area, item_id, "decisions", model, 0.0)
        if code != 429 and not (code is not None and code >= 500):
            return {
                "skipped": False,
                "error": str(exc)[:2000],
                "cost": 0.0,
                "cost_gap": False,
                "body": None,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        reason = blocked(ledger_area, kind)
        if reason:
            return {
                "skipped": False,
                "error": f"{exc}; {reason}"[:2000],
                "cost": 0.0,
                "cost_gap": False,
                "body": None,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        time.sleep(2)
        try:
            body = decide(state, questions, model=model, timeout=120.0)
        except Exception as retry_exc:  # noqa: BLE001
            return fail(str(retry_exc)[:2000])
    except Exception as exc:  # noqa: BLE001
        return fail(str(exc)[:2000])
    if not isinstance(body, dict):
        return fail("decision body is not an object")
    cost, gap, input_tokens, output_tokens = usage_numbers(body)
    append_ledger(agent, ledger_area, item_id, "decisions", model, cost)
    return {
        "skipped": False,
        "error": None,
        "cost": cost,
        "cost_gap": gap,
        "body": body,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def blank_item(area: str, seed: dict, model: str, error: str) -> dict:
    return {
        "id": f"{area}-{seed['id']}-{WRITER_SLUG[model]}",
        "area": area,
        "seed_id": seed["id"],
        "seed": seed["text"],
        "writer": model,
        "transcript": None,
        "questions": None,
        "valid": False,
        "replaced": False,
        "ban": None,
        "error": error,
        "cost": 0.0,
        "cost_gap": False,
    }


def item_from_call(area: str, seed: dict, model: str, item_id: str, result: dict, replaced: bool, ban: str | None) -> dict:
    base = {
        "id": item_id,
        "area": area,
        "seed_id": seed["id"],
        "seed": seed["text"],
        "writer": model,
        "transcript": None,
        "questions": None,
        "valid": False,
        "replaced": replaced,
        "ban": ban,
        "error": result.get("error"),
        "cost": result.get("cost", 0.0),
        "cost_gap": result.get("cost_gap", False),
    }
    if result.get("skipped") or result.get("error"):
        if result.get("raw"):
            base["raw"] = result["raw"][:4000]
        return base
    payload = parse_json_object(result.get("raw") or "")
    if payload is None:
        base["error"] = "writer JSON did not parse"
        base["raw"] = (result.get("raw") or "")[:4000]
        return base
    payload = normalize_writer(payload)
    ok, error, found_ban = validate_writer(payload)
    base["ban"] = ban or found_ban
    if not ok:
        base["error"] = error
        base["raw"] = (result.get("raw") or "")[:4000]
        if isinstance(payload.get("transcript"), list):
            try:
                base["transcript"] = store_transcript(payload["transcript"])
            except (KeyError, TypeError):
                base["transcript"] = None
        return base
    base["transcript"] = store_transcript(payload["transcript"])
    base["questions"] = payload["questions"]
    base["valid"] = True
    base["error"] = None
    return base


def write_one(client: httpx.Client, area: str, seed: dict, model: str) -> dict:
    item_id = f"{area}-{seed['id']}-{WRITER_SLUG[model]}"
    prompt = writer_prompt(area, item_id, model, seed["text"], None)
    first = chat_call(client, area, item_id, model, prompt, WRITER_MAX_TOKENS, "writer")
    if first.get("skipped"):
        row = blank_item(area, seed, model, f"not run: {first['error']}")
        return row
    payload = parse_json_object(first.get("raw") or "") if not first.get("error") else None
    ban = None
    if isinstance(payload, dict):
        payload = normalize_writer(payload)
    if isinstance(payload, dict) and isinstance(payload.get("transcript"), list):
        ban = transcript_ban(payload["transcript"])
    if ban is None:
        return item_from_call(area, seed, model, item_id, first, False, None)
    reason = blocked(area, "writer")
    if reason:
        row = item_from_call(area, seed, model, item_id, first, False, ban)
        row["error"] = f"{row['error']}; replacement not run: {reason}"
        return row
    second_prompt = writer_prompt(area, item_id, model, seed["text"], ban)
    second = chat_call(client, area, item_id, model, second_prompt, WRITER_MAX_TOKENS, "writer")
    if second.get("skipped"):
        row = item_from_call(area, seed, model, item_id, first, False, ban)
        row["error"] = f"{row['error']}; replacement not run: {second['error']}"
        row["cost"] = first["cost"]
        return row
    row = item_from_call(area, seed, model, item_id, second, True, ban)
    row["cost"] = float(first["cost"]) + float(second["cost"])
    row["cost_gap"] = bool(first["cost_gap"] or second["cost_gap"])
    return row


def leaf_option(body: dict | None, criteria: dict) -> tuple[str | None, float | None, str | None]:
    if not isinstance(body, dict):
        return None, None, "missing leaf"
    answers = body.get("answers")
    if not isinstance(answers, dict):
        return None, None, "missing leaf"
    leaf = answers.get("Leaf")
    if not isinstance(leaf, dict) or not isinstance(leaf.get("choice"), str):
        return None, None, "missing leaf"
    choice = leaf["choice"]
    if choice not in criteria:
        return None, None, "missing leaf"
    probabilities = leaf.get("probabilities")
    probability = None
    if isinstance(probabilities, dict) and isinstance(probabilities.get(choice), (int, float)):
        probability = float(probabilities[choice])
    return choice, probability, None


def score_one(area: str, item: dict, model: str) -> dict:
    questions = scorer_questions(item["questions"])
    roles = item["questions"]["Leaf"]["roles"]
    result = decision_call(area, item["id"], model, item["transcript"], questions, "scorer")
    row = {
        "id": item["id"],
        "area": area,
        "model": model,
        "option": None,
        "probability": None,
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost": result.get("cost", 0.0),
        "cost_gap": result.get("cost_gap", False),
        "roles": roles,
        "request_questions": questions,
        "error": result.get("error"),
    }
    if result.get("skipped"):
        row["error"] = f"not run: {result['error']}"
        return row
    if result.get("error"):
        return row
    body = result["body"]
    option, probability, error = leaf_option(body, questions["Leaf"]["criteria"])
    row["option"] = option
    row["probability"] = probability
    row["error"] = error
    if isinstance(body, dict) and body.get("model"):
        row["resolved_model"] = body.get("model")
    return row


def reference_one(client: httpx.Client, area: str, item: dict, model: str) -> dict:
    leaf = clean_question(item["questions"]["Leaf"])
    roles = item["questions"]["Leaf"]["roles"]
    prompt = reference_prompt(item["transcript"], leaf)
    result = chat_call(client, area, item["id"], model, prompt, REFERENCE_MAX_TOKENS, "reference")
    row = {
        "id": item["id"],
        "area": area,
        "model": model,
        "choice": None,
        "raw": result.get("raw") or "",
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost": result.get("cost", 0.0),
        "cost_gap": result.get("cost_gap", False),
        "roles": roles,
        "leaf": leaf,
        "error": result.get("error"),
    }
    if result.get("skipped"):
        row["error"] = f"not run: {result['error']}"
        return row
    if result.get("error"):
        return row
    choice = parse_choice(result.get("raw") or "", set(leaf["criteria"]))
    row["choice"] = choice
    if choice is None:
        row["error"] = "choice not parsed" if result.get("raw") else "no choice in content"
    return row


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def run_area(area: str) -> None:
    if area not in AREAS:
        raise SystemExit(f"unknown area {area}")
    arm_window()
    seeds = load_seeds()[area]
    out = RUN / area
    items_path = out / "items.json"
    if items_path.exists():
        raise SystemExit(f"{items_path} already exists")
    out.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    scores: list[dict] = []
    references: list[dict] = []
    stopped = None
    pairs = [(model, seed) for model in WRITERS for seed in seeds]
    with httpx.Client(timeout=120.0) as client:
        for index, (model, seed) in enumerate(pairs):
            reason = blocked(area, "writer")
            if reason:
                stopped = reason
                for later_model, later_seed in pairs[index:]:
                    items.append(blank_item(area, later_seed, later_model, f"not run: {reason}"))
                break
            row = write_one(client, area, seed, model)
            items.append(row)
            print(
                f"{area} writer {row['id']} valid={row['valid']} "
                f"cost={row['cost']:.8f} error={row['error']}",
                flush=True,
            )
            write_json(
                items_path,
                {"area": area, "items": items, "stopped": stopped},
            )
        valid = [item for item in items if item["valid"]]
        for item in valid:
            for model in SCORERS:
                reason = blocked(area, "scorer")
                if reason:
                    stopped = stopped or reason
                    scores.append(
                        {
                            "id": item["id"],
                            "area": area,
                            "model": model,
                            "option": None,
                            "probability": None,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cost": 0.0,
                            "cost_gap": False,
                            "roles": item["questions"]["Leaf"]["roles"],
                            "request_questions": scorer_questions(item["questions"]),
                            "error": f"not run: {reason}",
                        }
                    )
                    continue
                row = score_one(area, item, model)
                scores.append(row)
                print(
                    f"{area} score {row['id']} {model} option={row['option']} "
                    f"p={row['probability']} cost={row['cost']:.8f} error={row['error']}",
                    flush=True,
                )
                write_json(
                    out / "scores.json",
                    {"area": area, "scores": scores, "stopped": stopped},
                )
        for item in valid:
            for model in REFERENCES:
                reason = blocked(area, "reference")
                if reason:
                    stopped = stopped or reason
                    references.append(
                        {
                            "id": item["id"],
                            "area": area,
                            "model": model,
                            "choice": None,
                            "raw": "",
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cost": 0.0,
                            "cost_gap": False,
                            "roles": item["questions"]["Leaf"]["roles"],
                            "leaf": clean_question(item["questions"]["Leaf"]),
                            "error": f"not run: {reason}",
                        }
                    )
                    continue
                row = reference_one(client, area, item, model)
                references.append(row)
                print(
                    f"{area} reference {row['id']} {model} choice={row['choice']} "
                    f"cost={row['cost']:.8f} error={row['error']}",
                    flush=True,
                )
                write_json(
                    out / "reference.json",
                    {"area": area, "references": references, "stopped": stopped},
                )
    write_json(items_path, {"area": area, "items": items, "stopped": stopped})
    write_json(out / "scores.json", {"area": area, "scores": scores, "stopped": stopped})
    write_json(out / "reference.json", {"area": area, "references": references, "stopped": stopped})
    print(
        f"{area} done items={len(items)} valid={sum(1 for item in items if item['valid'])} "
        f"scores={len(scores)} references={len(references)} "
        f"area_cost={area_sum(area):.8f} ledger={ledger_sum():.8f} stopped={stopped}",
        flush=True,
    )


def load_area_files() -> list[dict]:
    """Join valid writer items with scorer options and reference choices."""
    joined = []
    for area in AREAS:
        items_path = RUN / area / "items.json"
        if not items_path.is_file():
            continue
        items = json.loads(items_path.read_text()).get("items", [])
        scores = []
        references = []
        scores_path = RUN / area / "scores.json"
        reference_path = RUN / area / "reference.json"
        if scores_path.is_file():
            scores = json.loads(scores_path.read_text()).get("scores", [])
        if reference_path.is_file():
            references = json.loads(reference_path.read_text()).get("references", [])
        for item in items:
            if not item.get("valid"):
                continue
            scorer_options = {}
            for model in SCORERS:
                match = next(
                    (row for row in scores if row.get("id") == item["id"] and row.get("model") == model),
                    None,
                )
                scorer_options[model] = None if match is None else match.get("option")
            reference_choices = {}
            for model in REFERENCES:
                match = next(
                    (
                        row
                        for row in references
                        if row.get("id") == item["id"] and row.get("model") == model
                    ),
                    None,
                )
                reference_choices[model] = None if match is None else match.get("choice")
            joined.append(
                {
                    "id": item["id"],
                    "area": area,
                    "scorers": scorer_options,
                    "references": reference_choices,
                }
            )
    return joined


def run_grade() -> None:
    parent = ledger_sum()
    out = RUN / "grade.json"
    if parent >= GRADE_SKIP_AT:
        write_json(
            out,
            {
                "model": SCORERS[0],
                "skipped": True,
                "reason": f"ledger sum {parent:.8f} is at or above {GRADE_SKIP_AT:.2f}",
                "items": [],
                "calls": 0,
                "cost": 0.0,
            },
        )
        print(f"grade skipped ledger={parent:.8f}", flush=True)
        return
    joined = load_area_files()
    rows = []
    stopped = None
    for index, item in enumerate(joined):
        reason = blocked("grade", "grade")
        if reason:
            stopped = reason
            for later in joined[index:]:
                rows.append(
                    {
                        "id": later["id"],
                        "area": later["area"],
                        "state": None,
                        "answers": None,
                        "cost": 0.0,
                        "cost_gap": False,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "error": f"not run: {reason}",
                    }
                )
            break
        state = {
            "id": item["id"],
            "references": item["references"],
            "scorers": item["scorers"],
        }
        result = decision_call("grade", item["id"], SCORERS[0], state, GRADE_QUESTIONS, "grade")
        answers = None
        if isinstance(result.get("body"), dict):
            answers = result["body"].get("answers")
        row = {
            "id": item["id"],
            "area": item["area"],
            "state": state,
            "answers": answers,
            "cost": result.get("cost", 0.0),
            "cost_gap": result.get("cost_gap", False),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "error": f"not run: {result['error']}" if result.get("skipped") else result.get("error"),
        }
        rows.append(row)
        print(
            f"grade {item['id']} cost={row['cost']:.8f} error={row['error']}",
            flush=True,
        )
    payload = {
        "model": SCORERS[0],
        "skipped": False,
        "reason": stopped,
        "items": rows,
        "calls": call_count("grade", "grade"),
        "cost": area_sum("grade"),
        "ledger_sum": ledger_sum(),
    }
    write_json(out, payload)
    print(
        f"grade done calls={payload['calls']} cost={payload['cost']:.8f} "
        f"ledger={payload['ledger_sum']:.8f} stopped={stopped}",
        flush=True,
    )


def sample_payload() -> dict:
    return {
        "id": "inbox-s1-lfm",
        "seed": "seed",
        "writer": WRITERS[0],
        "transcript": [
            {"role": "customer", "text": "I cannot find the order."},
            {"role": "assistant", "text": "The order number is 100 and the day is Tuesday."},
            {"role": "customer", "text": "Thanks, that helps."},
        ],
        "questions": {
            "Leaf": {
                "type": "choice",
                "instructions": "Choose the employee action.",
                "criteria": {
                    "hold": "collect one missing fact",
                    "send": "use the path the thread already supports",
                },
                "roles": {"hold": "explore", "send": "exploit"},
            }
        },
    }


def self_check() -> None:
    seeds = load_seeds()
    if list(seeds) != list(AREAS):
        raise SystemExit(f"seed areas are {list(seeds)}")
    for area in AREAS:
        got = seeds[area]
        want = FROZEN_SEEDS[area]
        if got != want:
            raise SystemExit(f"{area} seeds differ from the frozen text")
    if len(FROZEN_SEEDS["guard"]) != 2:
        raise SystemExit("guard seed count drifted")
    if "asks" not in FROZEN_SEEDS["guard"][0]["text"]:
        raise SystemExit("guard s1 seed text drifted")
    for model in (*WRITERS, *SCORERS, *REFERENCES):
        if ":free" in model:
            raise SystemExit(f"{model} is a free route")
        if model in FORBIDDEN:
            raise SystemExit(f"{model} is forbidden")
    if WRITERS != (
        "qwen/qwen3.8-27b",
        "google/gemma-4-31b-it",
    ):
        raise SystemExit("writer ids drifted")
    if SKIPPED_WRITERS != ("liquid/lfm-2.5-2.6b",):
        raise SystemExit("skipped writer drifted")
    if set(SKIPPED_WRITERS) & set(WRITERS):
        raise SystemExit("a skipped writer is still called")
    if SCORERS != (
        "typesafe/jev-1.13",
        "cloudflare/clef-omni",
        "nace-ai/drex-v1.5",
        "microsoft/microsoft-decision-1",
    ):
        raise SystemExit("scorer ids drifted")
    if REFERENCES != (
        "~deepseek/deepseek-v4-flash-latest",
        "xiaomi/mimo-v2.6-flash",
    ):
        raise SystemExit("reference ids drifted")
    if FORBIDDEN != ("x-ai/grok-4.7", "moonshotai/kimi-k3"):
        raise SystemExit("forbidden ids drifted")
    if (WRITER_CAP, SCORER_CAP, REFERENCE_CAP) != (8, 24, 12):
        raise SystemExit("call caps drifted")
    if (AREA_COST_CAP, PARENT_CAP, GRADE_COST_CAP, GRADE_SKIP_AT) != (0.55, 2.00, 0.20, 1.80):
        raise SystemExit("money caps drifted")
    if GRADE_CALL_CAP != 18 or MISSING_COST != 0.01:
        raise SystemExit("grade cap or missing cost drifted")
    if WRITER_MAX_TOKENS != 700 or REFERENCE_MAX_TOKENS != 512:
        raise SystemExit("max tokens drifted")
    if GRADE_QUESTIONS["Disagree"]["instructions"] != (
        "The four scorers do not all choose the same option key."
    ):
        raise SystemExit("Disagree instruction drifted")
    if GRADE_QUESTIONS["ClefGap"]["instructions"] != (
        "The Cloudflare option key differs from the Jev option key."
    ):
        raise SystemExit("ClefGap instruction drifted")
    if "guard" in SETTINGS["guard"]:
        raise SystemExit("guard setting contains the area name")
    payload = sample_payload()
    ok, error, ban = validate_writer(payload)
    if not ok or error or ban:
        raise SystemExit(f"sample leaf failed: {error} {ban}")
    questions = scorer_questions(payload["questions"])
    if "roles" in json.dumps(questions):
        raise SystemExit("scorer questions still contain roles")
    leaf = clean_question(payload["questions"]["Leaf"])
    prompt = reference_prompt(payload["transcript"], leaf)
    if "explore" in prompt or "exploit" in prompt or "roles" in prompt:
        raise SystemExit("reference prompt contains the role map")
    if "Extra" in prompt:
        raise SystemExit("reference prompt contains an extra question")
    copied = sample_payload()
    copied["transcript"] = [
        {"role": "customer", "text": "Please ask the desk."},
        {"role": "assistant", "text": "I can help."},
        {"role": "customer", "text": "Thanks."},
    ]
    ok, error, ban = validate_writer(copied)
    if ok or ban != "ask":
        raise SystemExit(f"ask ban failed: {ok} {error} {ban}")
    named = sample_payload()
    named["transcript"][0]["text"] = "Look in the inbox please."
    ok, _error, ban = validate_writer(named)
    if ok or ban != "inbox":
        raise SystemExit("area name ban failed")
    long_turn = sample_payload()
    long_turn["transcript"][0]["text"] = "x" * 1200
    ok, error, _ban = validate_writer(long_turn)
    if ok or "1200" not in (error or ""):
        raise SystemExit("length rule failed")
    short = sample_payload()
    short["transcript"] = short["transcript"][:2]
    ok, error, _ban = validate_writer(short)
    if ok or "2 turns" not in (error or ""):
        raise SystemExit("turn count rule failed")
    bad_key = sample_payload()
    bad_key["questions"]["Leaf"]["criteria"] = {
        "reply": "send it",
        "hold": "slow down",
    }
    bad_key["questions"]["Leaf"]["roles"] = {"reply": "exploit", "hold": "explore"}
    ok, error, _ban = validate_writer(bad_key)
    if ok or "banned" not in (error or ""):
        raise SystemExit("banned key rule failed")
    both = sample_payload()
    both["questions"]["Leaf"]["roles"] = {"hold": "explore", "send": "explore"}
    ok, error, _ban = validate_writer(both)
    if ok or "one explore" not in (error or ""):
        raise SystemExit("role rule failed")
    extra = sample_payload()
    extra["questions"]["Heat"] = {"type": "noul", "instructions": "The customer is angry."}
    extra["questions"]["More"] = {"type": "noul", "instructions": "Another one."}
    ok, error, _ban = validate_writer(extra)
    if ok or "extra" not in (error or ""):
        raise SystemExit("extra question rule failed")
    wide = sample_payload()
    wide["questions"]["Heat"] = {
        "type": "choice",
        "instructions": "Pick one.",
        "criteria": {f"o{n}": f"option {n}" for n in range(5)},
    }
    ok, error, _ban = validate_writer(wide)
    if ok or "4" not in (error or ""):
        raise SystemExit("extra choice size rule failed")
    choice = parse_choice('{"choice": "send"}', {"hold", "send"})
    action = parse_choice('{"action": "hold"}', {"hold", "send"})
    one_key = parse_choice('{"send": true}', {"hold", "send"})
    other = parse_choice('{"choice": "reply"}', {"hold", "send"})
    if (choice, action, one_key, other) != ("send", "hold", "send", None):
        raise SystemExit("choice parser drifted")
    row = ledger_row("inbox", "inbox", "inbox-s1-lfm", "chat", WRITERS[0], 0.0)
    if list(row) != ["agent", "area", "item", "route", "model", "cost"]:
        raise SystemExit("ledger row drifted")
    cost, gap, _in_tokens, _out_tokens = usage_numbers({})
    if cost != MISSING_COST or not gap:
        raise SystemExit("missing cost rule drifted")
    messy = sample_payload()
    messy["transcript"] = [
        {"speaker": "customer", "text": "I cannot find the order."},
        {"speaker": "assistant", "text": "The number is 100. The day is Tuesday."},
        {"speaker": "Customer", "text": "Thanks, that helps."},
    ]
    messy["questions"] = [
        {
            "type": "choice",
            "instructions": "Choose the employee action.",
            "criteria": {
                "hold": "collect one missing fact",
                "send": "use the path the thread already supports",
            },
            "roles": {"hold": "Explore", "send": "Exploit"},
        },
        {"id": "q2", "type": "choice", "options": ["one", "two"]},
    ]
    ok, error, ban = validate_writer(messy)
    if not ok or error or ban:
        raise SystemExit(f"speaker shape failed: {error} {ban}")
    stringy = sample_payload()
    stringy["transcript"] = (
        "Customer: I cannot find the order.\n"
        "Assistant: The number is 100. The day is Tuesday.\n"
        "Customer: Thanks, that helps."
    )
    ok, error, ban = validate_writer(stringy)
    if not ok or error or ban:
        raise SystemExit(f"string transcript failed: {error} {ban}")
    hidden = content_of(
        {"choices": [{"message": {"content": "", "reasoning": '{"id":"x"}'}}]}
    )
    if hidden != '{"id":"x"}':
        raise SystemExit("empty content did not use the reasoning text")
    print("check ok")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        self_check()
        return
    if len(sys.argv) == 2 and sys.argv[1] == "--grade":
        run_grade()
        return
    if len(sys.argv) == 2 and sys.argv[1] in AREAS:
        run_area(sys.argv[1])
        return
    raise SystemExit("usage: run_area.py --check | --grade | inbox|money|guard")


if __name__ == "__main__":
    main()
