"""Run one frozen graph: flat, chain, or dag. No chat calls."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from jevdt import DECISION_MODEL, decide

CALL_CAP = 48
AGENT_COST_CAP = 0.30
PARENT_COST_CAP = 1.50
MISSING_COST = 0.01
CHOICES = ("reply", "ask", "escalate", "wait")

TONE = {
    "type": "noul",
    "instructions": "The latest user turn is heated.",
}
FACT = {
    "type": "noul",
    "instructions": "The agent needs one missing fact before it can act.",
}
NEXT = {
    "type": "choice",
    "instructions": "Choose the next agent action.",
    "criteria": {
        "reply": "the agent can answer from the transcript.",
        "ask": "the agent must request one missing fact.",
        "escalate": "a person must take the case.",
        "wait": "no action is due on this turn.",
    },
}


def find_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise SystemExit("repo root not found")


ROOT = find_root()
RUN = ROOT / "experiments" / "run-001"
LEDGER = RUN / "ledger.jsonl"


def self_check() -> None:
    transcript = [{"role": "user", "text": "hi"}]
    tone = {"type": "noul", "noul": 0.25}
    fact = {"type": "noul", "noul": 0.75}
    assert TONE["instructions"] == "The latest user turn is heated."
    assert FACT["instructions"] == "The agent needs one missing fact before it can act."
    assert NEXT["instructions"] == "Choose the next agent action."
    assert list(NEXT["criteria"]) == list(CHOICES)
    chain_fact = chain_state(transcript, tone, None)
    assert chain_fact["Tone"] == tone and "Fact" not in chain_fact
    dag_fact = transcript
    assert dag_fact == transcript and not isinstance(dag_fact, dict)
    both = chain_state(transcript, tone, fact)
    assert both["Tone"] == tone and both["Fact"] == fact
    assert both["transcript"] == transcript


def chain_state(transcript: list, tone: dict | None, fact: dict | None) -> dict:
    state: dict = {"transcript": transcript}
    if tone is not None:
        state["Tone"] = tone
    if fact is not None:
        state["Fact"] = fact
    return state


def read_ledger() -> list[dict]:
    if not LEDGER.is_file():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def tally(strategy: str) -> tuple[int, float, float]:
    calls = 0
    own = 0.0
    total = 0.0
    for row in read_ledger():
        cost = float(row["cost"])
        total += cost
        if row.get("agent") == strategy:
            calls += 1
            own += cost
    return calls, own, total


def stop_reason(strategy: str) -> str | None:
    calls, own, total = tally(strategy)
    if calls >= CALL_CAP:
        return f"call cap {CALL_CAP}"
    if own >= AGENT_COST_CAP:
        return f"agent cost cap {AGENT_COST_CAP}"
    if total >= PARENT_COST_CAP:
        return f"parent cap {PARENT_COST_CAP}"
    return None


def append_ledger(strategy: str, item_id: str, cost: float) -> None:
    row = {
        "agent": strategy,
        "item": item_id,
        "route": "decisions",
        "model": DECISION_MODEL,
        "cost": cost,
    }
    line = (json.dumps(row, separators=(",", ":")) + "\n").encode()
    fd = os.open(LEDGER, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def status_code(exc: BaseException) -> int | None:
    match = re.search(r"decisions API (\d+)", str(exc))
    if not match:
        return None
    return int(match.group(1))


def usage_of(body: dict) -> tuple[float, int, int, bool]:
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return MISSING_COST, 0, 0, True
    raw_cost = usage.get("cost")
    gap = not isinstance(raw_cost, (int, float))
    cost = float(MISSING_COST if gap else raw_cost)
    return (
        cost,
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        gap,
    )


def one_call(strategy: str, item_id: str, state, questions: dict) -> tuple[dict | None, str | None]:
    """One Decisions call, plus one retry only after HTTP 429 or 5xx."""
    reason = stop_reason(strategy)
    if reason:
        return None, reason
    try:
        body = decide(state, questions, model=DECISION_MODEL)
    except RuntimeError as exc:
        code = status_code(exc)
        append_ledger(strategy, item_id, 0.0)
        if code != 429 and not (code is not None and code >= 500):
            return None, str(exc)
        time.sleep(2)
        blocked = stop_reason(strategy)
        if blocked:
            return None, blocked
        try:
            body = decide(state, questions, model=DECISION_MODEL)
        except Exception as retry_exc:  # noqa: BLE001
            append_ledger(strategy, item_id, 0.0)
            return None, str(retry_exc)
    except Exception as exc:  # noqa: BLE001
        append_ledger(strategy, item_id, 0.0)
        return None, str(exc)
    cost, _input, _output, _gap = usage_of(body)
    append_ledger(strategy, item_id, cost)
    return body, None


def pack(body: dict, names: list[str]) -> dict:
    cost, input_tokens, output_tokens, gap = usage_of(body)
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict):
        answers = {}
    return {
        "questions": names,
        "answers": {name: answers.get(name) for name in names},
        "model": body.get("model") if isinstance(body, dict) else None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "cost_gap": gap,
    }


def leaf_from(calls: list[dict]) -> str | None:
    for call in reversed(calls):
        answer = call["answers"].get("Next")
        if isinstance(answer, dict) and isinstance(answer.get("choice"), str):
            return answer["choice"]
    return None


def run_item(strategy: str, item_id: str, transcript: list) -> dict:
    calls: list[dict] = []
    error = None
    tone = None
    fact = None

    def take(state, questions: dict) -> bool:
        nonlocal error
        names = list(questions)
        body, err = one_call(strategy, item_id, state, questions)
        if err or body is None:
            error = err or "no body"
            return False
        packed = pack(body, names)
        calls.append(packed)
        if packed["answers"].get("Tone") is None and "Tone" in names:
            error = "Tone answer missing"
            return False
        if packed["answers"].get("Fact") is None and "Fact" in names:
            error = "Fact answer missing"
            return False
        if "Next" in names and leaf_from([packed]) is None:
            error = "Next choice missing"
            return False
        return True

    if strategy == "flat":
        take(transcript, {"Tone": TONE, "Fact": FACT, "Next": NEXT})
    elif strategy == "chain":
        if take(transcript, {"Tone": TONE}):
            tone = calls[-1]["answers"]["Tone"]
            if take(chain_state(transcript, tone, None), {"Fact": FACT}):
                fact = calls[-1]["answers"]["Fact"]
                take(chain_state(transcript, tone, fact), {"Next": NEXT})
    elif strategy == "dag":
        if take(transcript, {"Tone": TONE}):
            tone = calls[-1]["answers"]["Tone"]
            if take(transcript, {"Fact": FACT}):
                fact = calls[-1]["answers"]["Fact"]
                take(chain_state(transcript, tone, fact), {"Next": NEXT})
    else:
        error = f"unknown strategy {strategy}"

    input_tokens = sum(call["input_tokens"] for call in calls)
    output_tokens = sum(call["output_tokens"] for call in calls)
    cost = sum(call["cost"] for call in calls)
    return {
        "id": item_id,
        "leaf": leaf_from(calls),
        "answers": [call["answers"] for call in calls],
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "cost_gap": any(call["cost_gap"] for call in calls),
        "error": error,
    }


def load_done(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text())
    return {item["id"]: item for item in payload.get("items", []) if item.get("error") != "not run"}


def write_results(path: Path, strategy: str, items: list[dict], stopped: str | None) -> None:
    calls, own, total = tally(strategy)
    payload = {
        "strategy": strategy,
        "model": DECISION_MODEL,
        "items": items,
        "calls": calls,
        "cost": own,
        "ledger_sum": total,
        "stopped": stopped,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        self_check()
        print("check ok")
        return
    if len(sys.argv) != 2 or sys.argv[1] not in {"flat", "chain", "dag"}:
        raise SystemExit("usage: run_graph.py flat|chain|dag")
    self_check()
    strategy = sys.argv[1]
    items = json.loads((RUN / "items.json").read_text())["items"]
    out_dir = RUN / strategy
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.json"
    done = load_done(out_path)
    records: list[dict] = []
    stopped = None
    for item in items:
        if item["id"] in done:
            records.append(done[item["id"]])
            print(f"{strategy} {item['id']} skip", flush=True)
            continue
        reason = stop_reason(strategy)
        if reason:
            stopped = reason
            records.append(
                {
                    "id": item["id"],
                    "leaf": None,
                    "answers": [],
                    "calls": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                    "cost_gap": False,
                    "error": f"not run: {reason}",
                }
            )
            continue
        record = run_item(strategy, item["id"], item["transcript"])
        records.append(record)
        if record["error"] in {
            f"call cap {CALL_CAP}",
            f"agent cost cap {AGENT_COST_CAP}",
            f"parent cap {PARENT_COST_CAP}",
        }:
            stopped = record["error"]
        print(
            f"{strategy} {item['id']} leaf={record['leaf']} cost={record['cost']:.8f} "
            f"error={record['error']}",
            flush=True,
        )
        write_results(out_path, strategy, records, stopped)
    if stopped is None:
        for record in records:
            if isinstance(record.get("error"), str) and record["error"].startswith("not run"):
                stopped = record["error"].removeprefix("not run: ")
                break
    write_results(out_path, strategy, records, stopped)
    calls, own, total = tally(strategy)
    print(
        f"{strategy} done calls={calls} cost={own:.8f} ledger={total:.8f} stopped={stopped}",
        flush=True,
    )


if __name__ == "__main__":
    main()
