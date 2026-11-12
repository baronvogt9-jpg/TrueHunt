"""'First five seconds' review: what a newcomer does not get from the project's own pitch.

Gemini reads only the public record (name, tracks, description, links). The answer is cached in
memory per project and per record version, so a page view never costs more than one call.
"""
from __future__ import annotations

import json
import os

import httpx

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You are a blunt but fair hackathon reviewer who has five seconds per project.
Read this NEAR Hackathon submission record and answer in JSON with keys:
  "one_liner": what the project does, in at most 15 plain words, or "unclear" if you can't tell,
  "clarity": integer 1-5, how fast a newcomer understands what it does and for whom,
  "proof": integer 1-5, how much the pitch shows real working evidence (mainnet tx, live demo, repo),
  "missing": up to 3 short items a newcomer needs and does not get,
  "best_line": the single most convincing phrase from the pitch, quoted exactly, or "".
Judge only what is written. Do not praise. Do not invent facts.

RECORD:
{record}
"""

_cache: dict[tuple[str, int | None], dict] = {}


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def review(pid: str, record: dict) -> dict:
    key = (pid, record.get("block_height"))
    if key in _cache:
        return _cache[key]
    if not available():
        return {"error": "AI reviews are off: GEMINI_API_KEY is not set."}
    public = {k: record.get(k) for k in ("name", "tracks", "description", "demo_url", "repository_url")}
    public["links"] = [l.get("url") for l in record.get("links") or [] if isinstance(l, dict)]
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(record=json.dumps(public, ensure_ascii=False))}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    try:
        r = httpx.post(ENDPOINT.format(model=MODEL), json=body, timeout=40,
                       headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        out = json.loads(text)
        out = {
            "one_liner": str(out.get("one_liner", ""))[:200],
            "clarity": max(1, min(5, int(out.get("clarity", 1)))),
            "proof": max(1, min(5, int(out.get("proof", 1)))),
            "missing": [str(m)[:160] for m in (out.get("missing") or [])][:3],
            "best_line": str(out.get("best_line", ""))[:240],
            "model": MODEL,
        }
    except Exception as e:  # never break the page over a review
        return {"error": f"Review failed: {type(e).__name__}"}
    _cache[key] = out
    return out
