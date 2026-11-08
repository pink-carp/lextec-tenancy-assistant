"""Thin client for the Public AI inference service (OpenAI-compatible API).

Every call is recorded (prompt, reply, tokens, time, cost) so the audit trail can show it.
"""
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
# Provider: Public AI (Apertus, default) or OpenAI (comparison version, set LLM_PROVIDER=openai and LLM_MODEL)
PROVIDER = os.environ.get("LLM_PROVIDER", "publicai")
if PROVIDER == "openai":
    API_BASE = "https://api.openai.com/v1"
    MODEL = os.environ.get("LLM_MODEL", "gpt-5.6-sol")
    FALLBACK_MODEL = MODEL
    REASONING = os.environ.get("LLM_REASONING", "low")
else:
    API_BASE = "https://api.publicai.co/v1"
    MODEL = "swiss-ai/apertus-v1.5-70b"
    FALLBACK_MODEL = "swiss-ai/apertus-70b-instruct"
USER_AGENT = "lextec-hackathon-prototype/0.1"

# USD per million tokens (input, output), from api.publicai.co/v1/models on 2026-11-07
PRICES = {
    "swiss-ai/apertus-v1.5-70b": (0.82, 2.92),
    "swiss-ai/apertus-70b-instruct": (0.82, 2.92),
    "swiss-ai/apertus-v1.5-8b": (0.10, 0.20),
    "cohere/command-a-plus-05-2026-w4a4": (3.0, 15.0),
    "aisingapore/Nemotron-SEA-LION-v4.8-120B-A12B": (0.5, 2.0),
    # OpenAI list prices as reported by third-party pages on 2026-11-08 (not confirmed on openai.com): estimates only
    "gpt-5.6-sol": (5.0, 30.0), "gpt-5.6-terra": (2.0, 12.0), "gpt-5.5": (5.0, 30.0),
}


def _api_key() -> str:
    name = "OPENAI_API_KEY" if PROVIDER == "openai" else "PUBLICAI_API_KEY"
    if os.environ.get(name):
        return os.environ[name]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"{name} missing (set it in .env)")


_client = httpx.Client(timeout=httpx.Timeout(300.0, connect=20.0))


class LLMError(RuntimeError):
    pass


def _strip_constraints(node):
    if isinstance(node, dict):
        return {k: _strip_constraints(v) for k, v in node.items()
                if k not in ("minimum", "maximum", "minItems", "maxItems")}
    if isinstance(node, list):
        return [_strip_constraints(v) for v in node]
    return node


def _degenerate(text: str) -> bool:
    """Observed failure: the model emits endless blank lines or repeats a short chunk inside JSON."""
    tail = text[-160:]
    if len(tail) == 160 and not tail.strip():
        return True
    chunk = text[-40:]
    return len(text) > 400 and len(chunk) == 40 and text[-200:].count(chunk[-20:]) >= 6


def _stream(body, headers):
    """Rate limits (HTTP 429) were observed under parallel load: wait and retry (5 s, 15 s, 30 s)."""
    for wait in (5, 15, 30, None):
        try:
            return _stream_once(body, headers)
        except RateLimited:
            if wait is None:
                raise LLMError(f"{body['model']} is rate-limited (HTTP 429) after 3 retries")
            time.sleep(wait)


class RateLimited(Exception):
    pass


def _stream_once(body, headers):
    """Stream the reply so a degenerate generation can be stopped early. Returns (text, finish, usage)."""
    body = {**body, "stream": True, "stream_options": {"include_usage": True}}
    parts, finish, usage = [], None, {}
    with _client.stream("POST", f"{API_BASE}/chat/completions", json=body, headers=headers) as resp:
        if resp.status_code == 429:
            resp.read()
            raise RateLimited()
        if resp.status_code != 200:
            resp.read()
            raise LLMError(f"{body['model']} returned HTTP {resp.status_code}: {resp.text[:300]}")
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            if chunk.get("usage"):
                usage = chunk["usage"]
            for ch in chunk.get("choices", []):
                parts.append(ch.get("delta", {}).get("content") or "")
                finish = ch.get("finish_reason") or finish
            if len(parts) % 20 == 0 and _degenerate("".join(parts)):
                finish = "stopped_degenerate"
                break
    return "".join(parts), finish, usage


def chat(messages, *, schema=None, schema_name="output", model=MODEL, max_tokens=1500,
         temperature=0.0, seed=7, trace=None, step=""):
    """Call the model. With `schema`, the reply is constrained to that JSON schema and parsed.

    Returns the parsed object (schema) or the text. Appends a record to `trace` (a list) if given.
    """
    if messages and messages[0]["role"] == "system" and PROVIDER != "openai":
        # Observed 2026-11-08: Public AI rejects requests with a system message about 1 in 3 times
        # (HTTP 400/500 "only accepts a system message as the first message"); without one, 0 of 8 failed.
        # So the instructions travel in the first user message instead.
        sys_txt, rest = messages[0]["content"], messages[1:]
        first = rest[0]["content"] if rest else ""
        messages = [{"role": "user", "content": f"INSTRUCTIONS:\n{sys_txt}\n\nINPUT:\n{first}"}] + rest[1:]
    body = {"model": model, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "seed": seed}
    if PROVIDER == "openai":  # reasoning models: default temperature only; reasoning tokens count against the limit
        body = {"model": model, "messages": messages, "seed": seed, "reasoning_effort": REASONING,
                "max_completion_tokens": max_tokens * 4 + 2000}
    if schema is not None:
        if model.startswith("cohere/"):
            schema = _strip_constraints(schema)  # Cohere rejects minimum/maximum/minItems/maxItems
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": schema_name, "schema": schema, "strict": True}}
    headers = {"Authorization": f"Bearer {_api_key()}", "User-Agent": USER_AGENT}
    t0 = time.time()
    # Structured replies: up to 3 attempts. Observed failure: the model stalls in whitespace inside the JSON;
    # the stream is cut early, so a failed attempt costs seconds, and each retry changes seed and temperature.
    attempts = 3 if schema is not None else 1
    last_err = None
    for attempt in range(attempts):
        if attempt:  # a retry with the same seed at temperature 0 would repeat the same failure
            body["seed"] = seed + attempt
            if PROVIDER != "openai":
                body["temperature"] = 0.3 * attempt
        try:
            text, finish, usage = _stream(body, headers)
        except LLMError as e:  # server errors were observed to be intermittent: one retry
            if attempt + 1 < attempts:
                last_err = str(e)
                continue
            raise
        if schema is None:
            result = text
            break
        try:
            result = json.loads(text)
            break
        except json.JSONDecodeError as e:
            last_err = f"{e} (finish_reason={finish}, {usage.get('completion_tokens')} tokens, ends with: {text[-120:]!r})"
    else:
        raise LLMError(f"{model} returned invalid JSON {attempts} times in step '{step}': {last_err}")
    elapsed = time.time() - t0
    pin, pout = PRICES.get(model, (0.0, 0.0))
    cost = (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6
    if trace is not None:
        trace.append({
            "step": step, "model": model, "seconds": round(elapsed, 1),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": round(cost, 5), "attempts": attempt + 1,
            "messages": messages, "reply": text,
        })
    return result


def extract_json(text: str):
    """The first complete JSON object in a free-text reply (models sometimes add prose or ``` fences)."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                esc = (ch == "\\" and not esc)
                if ch == '"' and not esc:
                    in_str = False
                elif ch != "\\":
                    esc = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def ask_json(prompt: str, *, trace=None, step="", max_tokens=800, model=MODEL):
    """Free-form JSON: the model writes JSON without a forced grammar; code parses and validates.

    Why: with the provider's forced JSON-schema mode the model was observed (2026-11-08) to stall in
    whitespace and to be pushed into wrong categories; free JSON was valid in 8/8 probes at 2-5 s per call.
    Up to 3 tries: same model with a new seed, then the older Apertus model."""
    tries = [(model, 0.0, 7), (model, 0.3, 8), (FALLBACK_MODEL, 0.0, 7)]
    for m, temp, seed in tries:
        try:
            text = chat([{"role": "user", "content": prompt}], model=m, max_tokens=max_tokens,
                        temperature=temp, seed=seed, trace=trace, step=step)
        except LLMError:
            continue
        obj = extract_json(text)
        if isinstance(obj, dict):
            return obj
    raise LLMError(f"no valid JSON after 3 tries in step '{step}'")
